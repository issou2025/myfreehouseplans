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
    land_size: Optional[int]
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
class CalculationResult:
    bedrooms: list[TableRow]
    living_day: list[TableRow]
    additional: list[TableRow]
    sanitary: list[TableRow]
    circulation: list[CirculationRow]
    totals: list[TotalRow]
    land: list[LandRow]
    recommendations: list[str]
    summary: dict[str, float | int | str]


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
    recommendations = _recommendations(
        occupants=occupants,
        bedrooms=bedrooms_count,
        land_size=data.land_size,
        layout=data.layout,
        gross_area=gross_area,
    )

    summary = {
        'bedrooms': bedrooms_count,
        'bathrooms': bathrooms_count,
        'wc': wc_count,
        'net_area': _r(net_area),
        'gross_area': gross_area,
        'circulation_ratio': circulation_ratio,
        'gross_multiplier': gross_multiplier,
    }

    return CalculationResult(
        bedrooms=bedrooms_rows,
        living_day=living_day_rows,
        additional=additional_rows,
        sanitary=sanitary_rows,
        circulation=circulation_rows,
        totals=totals_rows,
        land=land_rows,
        recommendations=recommendations,
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


def _land_rows(land_size: Optional[int], gross_area: float, layout: str) -> list[LandRow]:
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


def _recommendations(*, occupants: int, bedrooms: int, land_size: Optional[int], layout: str, gross_area: float) -> list[str]:
    tips: list[str] = []

    if occupants >= 5 and bedrooms < 3:
        tips.append('Consider at least three bedrooms so daily life can stay quiet for larger households.')

    if land_size:
        footprint = gross_area if layout != 'two_storey' else gross_area / 2
        coverage = footprint / land_size
        if coverage >= 0.6:
            tips.append('Your estimated footprint is dense for the land size. A two-storey layout can protect outdoor comfort.')
        elif coverage >= 0.5:
            tips.append('Your footprint is approaching the comfort limit. Keep outdoor breathing space for light and airflow.')
        else:
            tips.append('Your land size supports the footprint with room for outdoor living and daylight access.')
    else:
        tips.append('Add land size to verify the footprint and outdoor comfort ratio.')

    tips.append('Match plans with similar bedroom counts and total area to reduce redesign effort.')
    tips.append('Try the Space Planner tools to validate key rooms before finalizing the plan.')
    tips.append('Use a cost or material estimator after you confirm the program size.')

    return tips


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def _r(value: float) -> float:
    return round(value, 1)
