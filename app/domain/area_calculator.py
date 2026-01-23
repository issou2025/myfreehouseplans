from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from typing import Iterable, Optional


@dataclass(frozen=True)
class CalculatorInput:
    occupants: int
    household_type: str
    comfort_level: str
    future_growth: str
    extra_rooms: tuple[str, ...]
    land_size: Optional[float]
    layout: str


@dataclass(frozen=True)
class TableRow:
    label: str
    quantity: int
    area_each: Optional[float]
    total_area: float


@dataclass(frozen=True)
class CirculationRow:
    label: str
    method: str
    area: float


@dataclass(frozen=True)
class TotalRow:
    label: str
    area: float


@dataclass(frozen=True)
class LandRow:
    label: str
    value: str


@dataclass(frozen=True)
class SummaryCard:
    label: str
    value: str
    helper: str


@dataclass(frozen=True)
class Recommendation:
    title: str
    detail: str
    tone: str


@dataclass(frozen=True)
class Insight:
    title: str
    body: str
    tone: str


@dataclass(frozen=True)
class AlternativeOption:
    label: str
    description: str
    gross_area: float
    net_area: float
    bedrooms: int
    bathrooms: int
    circulation_ratio: float


@dataclass(frozen=True)
class FaqItem:
    question: str
    answer: str


@dataclass(frozen=True)
class CalculationResult:
    bedrooms: list[TableRow]
    living_day: list[TableRow]
    additional: list[TableRow]
    sanitary: list[TableRow]
    circulation: list[CirculationRow]
    totals: list[TotalRow]
    land: list[LandRow]
    recommendations: list[Recommendation]
    summary_cards: list[SummaryCard]
    insights: list[Insight]
    warnings: list[Insight]
    tradeoffs: list[Insight]
    alternatives: list[AlternativeOption]
    next_steps: list[str]
    faq: list[FaqItem]
    summary: dict[str, float | int | str | None]


# ---- Rule constants (named for clarity, not magic numbers) ----
BEDROOM_CAP_MASTER = 16.0
BEDROOM_CAP_CHILD = 12.0
BATHROOM_CAP = 6.0
WC_AREA_CAP = 2.4
GROSS_MULTIPLIER_MIN = 1.08
GROSS_MULTIPLIER_MAX = 1.12
CIRCULATION_MIN = 0.12
CIRCULATION_MAX = 0.18

COMFORT_MULTIPLIERS = {
    'essential': 0.92,
    'standard': 1.0,
    'high': 1.1,
}

EXTRA_ROOM_RULES = {
    'home_office': {
        'label': 'Home office',
        'base': 7.0,
        'per_person': 0.4,
        'cap': 11.0,
    },
    'guest_room': {
        'label': 'Guest room',
        'base': 10.0,
        'per_person': 0.3,
        'cap': 13.0,
    },
    'storage': {
        'label': 'Storage',
        'base': 4.0,
        'per_person': 0.3,
        'cap': 7.0,
    },
}


def calculate_house_area(data: CalculatorInput) -> CalculationResult:
    occupants = max(1, min(data.occupants, 10))
    comfort_multiplier = COMFORT_MULTIPLIERS.get(data.comfort_level, 1.0)

    bedrooms_count = _bedroom_count(occupants)
    if data.household_type == 'extended_family' and occupants >= 4:
        bedrooms_count += 1

    master_area = min(12 + occupants * 0.5, BEDROOM_CAP_MASTER) * comfort_multiplier
    child_area = min(9 + occupants * 0.3, BEDROOM_CAP_CHILD) * comfort_multiplier

    master_qty = 1
    child_qty = max(0, bedrooms_count - 1)

    bedrooms_rows = [
        TableRow('Master bedroom', master_qty, _r(master_area), _r(master_area * master_qty)),
    ]
    if child_qty:
        bedrooms_rows.append(TableRow('Additional bedroom', child_qty, _r(child_area), _r(child_area * child_qty)))

    living_area = (18 + occupants * 2.5) * comfort_multiplier
    kitchen_area = (8 + occupants * 0.8) * comfort_multiplier
    dining_area = (8 + occupants * 0.6) * comfort_multiplier

    living_day_rows = [
        TableRow('Living room', 1, _r(living_area), _r(living_area)),
        TableRow('Kitchen', 1, _r(kitchen_area), _r(kitchen_area)),
        TableRow('Dining area', 1, _r(dining_area), _r(dining_area)),
    ]

    bathrooms_count = _bathroom_count(occupants)
    bathroom_area = min(4 + occupants * 0.3, BATHROOM_CAP) * comfort_multiplier
    wc_count = max(1, ceil(occupants / 4))
    wc_area = min(1.8 + occupants * 0.1, WC_AREA_CAP)

    sanitary_rows = [
        TableRow('Bathroom', bathrooms_count, _r(bathroom_area), _r(bathroom_area * bathrooms_count)),
        TableRow('WC', wc_count, _r(wc_area), _r(wc_area * wc_count)),
    ]

    additional_rows: list[TableRow] = []
    for room_key in data.extra_rooms:
        rule = EXTRA_ROOM_RULES.get(room_key)
        if not rule:
            continue
        area = min(rule['base'] + occupants * rule['per_person'], rule['cap']) * comfort_multiplier
        additional_rows.append(TableRow(rule['label'], 1, _r(area), _r(area)))

    growth_area = _growth_buffer(occupants, data.future_growth) * comfort_multiplier
    if growth_area > 0:
        additional_rows.append(TableRow('Future growth / flex space', 1, _r(growth_area), _r(growth_area)))

    net_area = sum(r.total_area for r in bedrooms_rows + living_day_rows + sanitary_rows + additional_rows)

    room_count = bedrooms_count + len(living_day_rows) + len(additional_rows) + bathrooms_count + wc_count
    circulation_ratio = _circulation_ratio(occupants, room_count)
    circulation_area = _r(net_area * circulation_ratio)

    circulation_rows = [
        CirculationRow(
            label='Circulation and internal movement',
            method=f"{int(circulation_ratio * 100)}% of net area (scaled by rooms + occupants)",
            area=circulation_area,
        )
    ]

    net_with_circulation = net_area + circulation_area
    gross_multiplier = _gross_multiplier(data.comfort_level, data.layout)
    gross_area = _r(net_with_circulation * gross_multiplier)

    totals_rows = [
        TotalRow('Net living area (rooms only)', _r(net_area)),
        TotalRow('Net area + circulation', _r(net_with_circulation)),
        TotalRow(f"Gross built area (x {gross_multiplier:.2f})", gross_area),
    ]

    land_rows = _land_rows(data.land_size, gross_area, data.layout)
    land_metrics = _land_metrics(data.land_size, gross_area, data.layout)

    summary = {
        'bedrooms': bedrooms_count,
        'bathrooms': bathrooms_count,
        'wc': wc_count,
        'net_area': _r(net_area),
        'gross_area': gross_area,
        'circulation_ratio': circulation_ratio,
        'gross_multiplier': gross_multiplier,
        'occupants': occupants,
        'layout': data.layout,
        'land_size': data.land_size or 0,
        'land_coverage': land_metrics.get('coverage'),
        'footprint': land_metrics.get('footprint'),
        'comfort_level': data.comfort_level,
    }

    summary_cards = _summary_cards(summary)
    recommendations = _recommendations(summary)
    insights, warnings, tradeoffs = _interpretation(summary)
    alternatives = _alternatives(summary)
    next_steps = _next_steps(summary)
    faq = _faq(summary)

    return CalculationResult(
        bedrooms=bedrooms_rows,
        living_day=living_day_rows,
        additional=additional_rows,
        sanitary=sanitary_rows,
        circulation=circulation_rows,
        totals=totals_rows,
        land=land_rows,
        recommendations=recommendations,
        summary_cards=summary_cards,
        insights=insights,
        warnings=warnings,
        tradeoffs=tradeoffs,
        alternatives=alternatives,
        next_steps=next_steps,
        faq=faq,
        summary=summary,
    )


def _bedroom_count(occupants: int) -> int:
    if occupants <= 2:
        return 1
    if occupants == 3:
        return 2
    if occupants == 4:
        return 3
    if occupants <= 6:
        return 4
    if occupants <= 8:
        return 5
    return 6


def _bathroom_count(occupants: int) -> int:
    if occupants <= 4:
        return 1
    if occupants <= 6:
        return 2
    return 3


def _circulation_ratio(occupants: int, room_count: int) -> float:
    base = 0.12
    room_factor = max(0, room_count - 6) * 0.005
    occupant_factor = max(0, occupants - 2) * 0.004
    return _clamp(base + room_factor + occupant_factor, CIRCULATION_MIN, CIRCULATION_MAX)


def _gross_multiplier(comfort_level: str, layout: str) -> float:
    base = GROSS_MULTIPLIER_MIN
    comfort_bonus = 0.0
    if comfort_level == 'standard':
        comfort_bonus = 0.01
    elif comfort_level == 'high':
        comfort_bonus = 0.02

    layout_bonus = 0.01 if layout == 'single_storey' else 0.0
    return _clamp(base + comfort_bonus + layout_bonus, GROSS_MULTIPLIER_MIN, GROSS_MULTIPLIER_MAX)


def _growth_buffer(occupants: int, future_growth: str) -> float:
    if future_growth == 'yes':
        return max(6.0, occupants * 1.8)
    if future_growth == 'maybe':
        return max(4.5, occupants * 1.2)
    return 0.0


def _land_metrics(land_size: Optional[float], gross_area: float, layout: str) -> dict[str, float | None]:
    if not land_size:
        return {'coverage': None, 'footprint': None}

    footprint_single = gross_area
    footprint_two = gross_area / 2
    if layout == 'two_storey':
        footprint = footprint_two
    elif layout == 'single_storey':
        footprint = footprint_single
    else:
        footprint = min(footprint_single, footprint_two)

    coverage = footprint / land_size
    return {'coverage': coverage, 'footprint': footprint}


def _land_rows(land_size: Optional[float], gross_area: float, layout: str) -> list[LandRow]:
    if not land_size:
        return [
            LandRow('Land size provided', 'Not provided'),
            LandRow('Footprint estimate', 'Add land size to evaluate compatibility'),
        ]

    footprint_single = gross_area
    footprint_two = gross_area / 2

    if layout == 'single_storey':
        coverage = footprint_single / land_size
        return [
            LandRow('Land size', f"{land_size:.0f} m²"),
            LandRow('Estimated footprint', f"{footprint_single:.1f} m²"),
            LandRow('Site coverage', f"{coverage * 100:.0f}%"),
        ]
    if layout == 'two_storey':
        coverage = footprint_two / land_size
        return [
            LandRow('Land size', f"{land_size:.0f} m²"),
            LandRow('Estimated footprint', f"{footprint_two:.1f} m²"),
            LandRow('Site coverage', f"{coverage * 100:.0f}%"),
        ]

    coverage_single = footprint_single / land_size
    coverage_two = footprint_two / land_size
    return [
        LandRow('Land size', f"{land_size:.0f} m²"),
        LandRow('Footprint (single-storey)', f"{footprint_single:.1f} m² · {coverage_single * 100:.0f}%"),
        LandRow('Footprint (two-storey)', f"{footprint_two:.1f} m² · {coverage_two * 100:.0f}%"),
    ]


def _summary_cards(summary: dict[str, float | int | str]) -> list[SummaryCard]:
    bedrooms = int(summary.get('bedrooms', 0) or 0)
    bathrooms = int(summary.get('bathrooms', 0) or 0)
    net_area = float(summary.get('net_area', 0.0) or 0.0)
    gross_area = float(summary.get('gross_area', 0.0) or 0.0)
    circulation_ratio = float(summary.get('circulation_ratio', 0.0) or 0.0)

    cards = [
        SummaryCard('Bedrooms', f"{bedrooms}", 'Sleeping rooms sized for your household.'),
        SummaryCard('Bathrooms', f"{bathrooms}", 'Full bathrooms; WCs are listed separately.'),
        SummaryCard('Net living area', f"{_r(net_area)} m²", 'Room-only area before circulation.'),
        SummaryCard('Gross built area', f"{_r(gross_area)} m²", 'Includes circulation and construction allowance.'),
        SummaryCard('Circulation share', f"{int(circulation_ratio * 100)}%", 'Hallways and movement space.'),
    ]

    coverage = summary.get('land_coverage')
    if isinstance(coverage, (int, float)):
        cards.append(SummaryCard('Land coverage', f"{coverage * 100:.0f}%", 'Estimated footprint share of the site.'))

    return cards


def _recommendations(summary: dict[str, float | int | str]) -> list[Recommendation]:
    tips: list[Recommendation] = []

    occupants = int(summary.get('occupants', 0) or 0)
    bedrooms = int(summary.get('bedrooms', 0) or 0)
    bathrooms = int(summary.get('bathrooms', 0) or 0)
    coverage = summary.get('land_coverage')
    layout = str(summary.get('layout', 'no_preference'))

    if occupants >= 5 and bathrooms < 2:
        tips.append(
            Recommendation(
                'Add a second full bathroom',
                'Larger households benefit from parallel morning routines and quieter shared use.',
                'caution',
            )
        )

    if bedrooms < max(2, ceil(occupants / 2)):
        tips.append(
            Recommendation(
                'Consider one more bedroom',
                'A buffer room preserves privacy as household routines overlap.',
                'neutral',
            )
        )

    if isinstance(coverage, (int, float)):
        if coverage >= 0.45 and layout != 'two_storey':
            tips.append(
                Recommendation(
                    'Explore a two-storey option',
                    'Reducing the footprint keeps outdoor space breathable and improves daylight access.',
                    'caution',
                )
            )
        elif coverage < 0.35:
            tips.append(
                Recommendation(
                    'You have flexibility on the site',
                    'Low coverage allows courtyards, terraces, or future expansion without crowding.',
                    'positive',
                )
            )
    else:
        tips.append(
            Recommendation(
                'Confirm land size to validate the footprint',
                'Site coverage is the key check that prevents a house from feeling too dense.',
                'neutral',
            )
        )

    return tips


def _interpretation(summary: dict[str, float | int | str]) -> tuple[list[Insight], list[Insight], list[Insight]]:
    insights: list[Insight] = []
    warnings: list[Insight] = []
    tradeoffs: list[Insight] = []

    occupants = int(summary.get('occupants', 0) or 0)
    gross_area = float(summary.get('gross_area', 0.0) or 0.0)
    net_area = float(summary.get('net_area', 0.0) or 0.0)
    coverage = summary.get('land_coverage')
    circulation_ratio = float(summary.get('circulation_ratio', 0.0) or 0.0)
    comfort = str(summary.get('comfort_level', 'standard'))

    if occupants:
        area_per_person = gross_area / max(1, occupants)
        if area_per_person < 22:
            warnings.append(
                Insight(
                    'This is a compact program',
                    'Your total area per person is on the compact side. Expect efficient spaces and less storage.',
                    'caution',
                )
            )
        elif area_per_person > 35:
            insights.append(
                Insight(
                    'You have comfortable breathing room',
                    'The area per person allows flexible furniture layouts and long-term adaptability.',
                    'positive',
                )
            )

    if isinstance(coverage, (int, float)):
        if coverage >= 0.5:
            warnings.append(
                Insight(
                    'Outdoor space will feel tight',
                    'A high site coverage limits gardens, daylight, and airflow. Consider a multi-storey option.',
                    'caution',
                )
            )
        elif coverage <= 0.3:
            insights.append(
                Insight(
                    'The site has generous breathing space',
                    'You can preserve outdoor comfort or plan for future extensions without crowding.',
                    'positive',
                )
            )
    else:
        insights.append(
            Insight(
                'Land size will refine this result',
                'Adding land size turns the program into a real-world footprint check.',
                'neutral',
            )
        )

    if circulation_ratio >= 0.17:
        tradeoffs.append(
            Insight(
                'Circulation is relatively high',
                'Complex layouts feel spacious but use more area for hallways and transitions.',
                'neutral',
            )
        )

    if comfort == 'high':
        insights.append(
            Insight(
                'High comfort means future flexibility',
                'Rooms scale up to handle changing routines without renovations.',
                'positive',
            )
        )

    if net_area <= 0.0:
        warnings.append(
            Insight(
                'We need more information',
                'Complete the form to calculate a reliable program and guidance.',
                'caution',
            )
        )

    return insights, warnings, tradeoffs


def _alternatives(summary: dict[str, float | int | str]) -> list[AlternativeOption]:
    gross_area = float(summary.get('gross_area', 0.0) or 0.0)
    net_area = float(summary.get('net_area', 0.0) or 0.0)
    bedrooms = int(summary.get('bedrooms', 0) or 0)
    bathrooms = int(summary.get('bathrooms', 0) or 0)
    circulation_ratio = float(summary.get('circulation_ratio', 0.0) or 0.0)

    if gross_area <= 0 or net_area <= 0:
        return []

    return [
        AlternativeOption(
            'Compact',
            'Reduce room sizes slightly to protect budget and footprint.',
            _r(gross_area * 0.92),
            _r(net_area * 0.92),
            bedrooms,
            bathrooms,
            circulation_ratio,
        ),
        AlternativeOption(
            'Standard',
            'Balanced program that fits the inputs you provided.',
            _r(gross_area),
            _r(net_area),
            bedrooms,
            bathrooms,
            circulation_ratio,
        ),
        AlternativeOption(
            'Spacious',
            'Adds flexibility for storage, guests, and long-term comfort.',
            _r(gross_area * 1.08),
            _r(net_area * 1.08),
            bedrooms,
            bathrooms,
            circulation_ratio,
        ),
    ]


def _next_steps(summary: dict[str, float | int | str]) -> list[str]:
    bedrooms = int(summary.get('bedrooms', 0) or 0)
    gross_area = float(summary.get('gross_area', 0.0) or 0.0)
    steps = [
        f"Compare plans around {bedrooms} bedrooms and ~{_r(gross_area)} m² gross area.",
        'Validate key rooms with the Space Planner tools before final design work.',
        'Use your program as input for a cost or material estimate to align budget expectations.',
    ]
    return steps


def _faq(summary: dict[str, float | int | str]) -> list[FaqItem]:
    bedrooms = int(summary.get('bedrooms', 0) or 0)
    bathrooms = int(summary.get('bathrooms', 0) or 0)
    circulation_ratio = float(summary.get('circulation_ratio', 0.0) or 0.0)
    gross_multiplier = float(summary.get('gross_multiplier', 0.0) or 0.0)
    land_size = float(summary.get('land_size', 0) or 0)

    faqs = [
        FaqItem(
            'Why does circulation take space?',
            f"Circulation covers hallways and internal movement. In this program it is about {int(circulation_ratio * 100)}% of net area.",
        ),
        FaqItem(
            'What is the difference between net and gross area?',
            f"Net area totals rooms only. Gross area adds walls and construction allowance using a multiplier of {gross_multiplier:.2f}.",
        ),
        FaqItem(
            'How many bedrooms does this program assume?',
            f"The program targets {bedrooms} bedrooms and {bathrooms} full bathrooms based on household size.",
        ),
    ]

    if land_size > 0:
        faqs.append(
            FaqItem(
                'Is the footprint compatible with the land?',
                'Yes, the land compatibility table checks your estimated footprint against the site size to protect outdoor comfort.',
            )
        )

    return faqs


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def _r(value: float) -> float:
    return round(value, 1)
