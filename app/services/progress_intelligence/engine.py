from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .units import normalize_area_to_m2


# Fixed conservative internal rate (NEVER shown to user)
EUR_TO_USD = 1.1


PHASES = [
    'Preparation',
    'Foundation',
    'Structure',
    'Envelope',
    'Closure',
    'Basic habitability',
    'Finishing',
]


INTERNAL_BASE_COST_EUR_PER_M2 = {
    'Single-family house': 400,
    'Multi-family building': 500,
    'School': 450,
    'Health center': 550,
    'Commercial building': 600,
    'Light industrial / workshop': 500,
}


FLOOR_FACTORS = {
    'Ground floor only': 1.00,
    'Ground + 1': 1.15,
    'Ground + 2': 1.30,
    'Ground + 3 or more': 1.50,
}


MATERIAL_FACTORS = {
    'Wood': 0.95,
    'Concrete': 1.00,
    'Steel': 1.10,
}


PHASE_DISTRIBUTION = {
    'Preparation': 0.05,
    'Foundation': 0.15,
    'Structure': 0.25,
    'Envelope': 0.20,
    'Closure': 0.10,
    'Basic habitability': 0.15,
    'Finishing': 0.10,
}


@dataclass(frozen=True)
class Inputs:
    building_type: str
    floors: str
    material: str
    area_value: float
    area_unit: str
    currency: str
    total_budget: float | None
    monthly_contribution: float | None
    max_monthly_effort: bool
    country_name: str
    lang: str


@dataclass(frozen=True)
class PhaseStatus:
    phase: str
    status: str  # green|orange|red
    note: str


@dataclass(frozen=True)
class Result:
    created_utc: str
    inputs: Inputs
    stopping_phase: str
    rhythm: str  # stable|fragile|blocked
    margin_flag: bool
    statuses: list[PhaseStatus]
    explanation: str
    advice: list[str]
    scenarios: list[dict[str, Any]]
    # PDF-only charts
    progress_months: list[int]
    progress_ratios: list[float]
    reachable_ratio: float


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def _normalize_currency(value: float | None, currency: str) -> float:
    if not value:
        return 0.0
    v = max(0.0, float(value))
    c = (currency or 'EUR').strip().upper()
    if c == 'USD':
        return v / EUR_TO_USD
    return v


def _factor_for_building_type(building_type: str) -> float:
    # The €/m² value itself is never shown; we only use it to prevent impossible outputs.
    bt = (building_type or '').strip()
    return float(INTERNAL_BASE_COST_EUR_PER_M2.get(bt, 500))


def _floor_factor(floors: str) -> float:
    key = (floors or '').strip()
    return float(FLOOR_FACTORS.get(key, 1.30))


def _material_factor(material: str) -> float:
    key = (material or '').strip()
    return float(MATERIAL_FACTORS.get(key, 1.00))


def _minimum_realistic_budget_eur(inputs: Inputs, *, area_m2: float) -> float:
    base = _factor_for_building_type(inputs.building_type)
    return float(area_m2) * base * _floor_factor(inputs.floors) * _material_factor(inputs.material)


def _phase_statuses(ratio: float) -> tuple[list[PhaseStatus], str]:
    r = max(0.0, float(ratio))
    statuses: list[PhaseStatus] = []

    cumulative = 0.0
    last_phase = PHASES[0]

    for phase in PHASES:
        share = float(PHASE_DISTRIBUTION.get(phase, 0.0))
        prev = cumulative
        cumulative += share

        if r >= cumulative:
            statuses.append(PhaseStatus(phase=phase, status='green', note='Usually reachable under global constraints.'))
            last_phase = phase
        elif r > prev:
            statuses.append(PhaseStatus(phase=phase, status='orange', note='Partially reachable; fragile under interruptions.'))
            last_phase = phase
        else:
            statuses.append(PhaseStatus(phase=phase, status='red', note='Usually not reachable with this coverage.'))

    # Spec stopping rules (phrase-level)
    if r < 0.10:
        stopping = 'Preparation'
    elif r < 0.20:
        stopping = 'Foundation (partial)'
    elif r < 0.35:
        stopping = 'Structure (partial)'
    elif r < 0.55:
        stopping = 'Envelope (partial)'
    elif r < 0.70:
        stopping = 'Closure (partial)'
    elif r < 0.85:
        stopping = 'Basic habitability'
    else:
        stopping = 'Finishing possible'

    return statuses, stopping


def _simulate_monthly_progress(
    *,
    minimum_budget_eur: float,
    total_eur: float,
    monthly_eur: float,
    months: int = 24,
) -> tuple[list[int], list[float]]:
    if minimum_budget_eur <= 0:
        return [0], [1.0]

    m = max(0, int(months))
    monthly = max(0.0, float(monthly_eur))
    base = max(0.0, float(total_eur))

    xs: list[int] = []
    ys: list[float] = []
    for i in range(0, m + 1):
        covered = base + (monthly * i)
        xs.append(i)
        ys.append(_clamp(covered / minimum_budget_eur, 0.0, 1.25))
    return xs, ys


def _rhythm_indicator(*, minimum_budget_eur: float, monthly_eur: float) -> str:
    if monthly_eur <= 0:
        return 'blocked'
    if minimum_budget_eur <= 0:
        return 'stable'

    # Conservative: assume you need meaningful continuity across 24 months.
    needed_per_month = minimum_budget_eur / 24.0
    ratio = monthly_eur / needed_per_month if needed_per_month > 0 else 1.0

    if ratio >= 1.0:
        return 'stable'
    if ratio >= 0.60:
        return 'fragile'
    return 'blocked'


def simulate(inputs: Inputs, *, include_scenarios: bool = True) -> Result:
    # Normalize + validate area
    area_m2 = normalize_area_to_m2(inputs.area_value, inputs.area_unit)
    if area_m2 < 10:
        raise ValueError('Surface area is too small. Please enter at least 10 m² (or equivalent).')
    if area_m2 > 200000:
        raise ValueError('Surface area is too large for this tool. Please reduce it or split the project.')

    currency = (inputs.currency or 'EUR').strip().upper()
    if currency not in {'EUR', 'USD'}:
        currency = 'EUR'

    total_eur = _normalize_currency(inputs.total_budget, currency)
    monthly_eur = _normalize_currency(inputs.monthly_contribution, currency)

    minimum_budget_eur = _minimum_realistic_budget_eur(inputs, area_m2=area_m2)

    if minimum_budget_eur <= 0:
        raise ValueError('We could not compute a realistic minimum for this project. Please change inputs and try again.')

    # Economic coverage ratio: what portion of the minimum realistic budget is covered.
    ratio_now = _clamp(total_eur / minimum_budget_eur, 0.0, 1.25)

    # Use a conservative horizon to avoid “infinite future” assumptions.
    horizon_months = 24
    ratio_horizon = ratio_now
    if monthly_eur > 0:
        ratio_horizon = _clamp((total_eur + monthly_eur * horizon_months) / minimum_budget_eur, 0.0, 1.25)

    statuses, stopping_phase = _phase_statuses(ratio_horizon)
    rhythm = _rhythm_indicator(minimum_budget_eur=minimum_budget_eur, monthly_eur=monthly_eur)
    margin_flag = bool(inputs.max_monthly_effort and monthly_eur > 0 and rhythm in {'fragile', 'blocked'})

    progress_months, progress_ratios = _simulate_monthly_progress(
        minimum_budget_eur=minimum_budget_eur,
        total_eur=total_eur,
        monthly_eur=monthly_eur,
        months=horizon_months,
    )

    reachable_ratio = _clamp(ratio_horizon, 0.0, 1.0)

    explanation = (
        f"Stopping point tends to appear around: {stopping_phase}. "
        "This is a global realism check, not a quotation. "
        "We use internal reference standards to block impossible results, but we never display unit prices."
    )

    advice: list[str] = []
    if stopping_phase in {'Finishing possible', 'Basic habitability'}:
        advice.append('Protect the last stretch. Late changes often turn stable projects into fragile ones.')
    else:
        advice.append('The safest improvement is to reduce surface or floors before starting.')

    if rhythm == 'stable':
        advice.append('Your monthly rhythm looks stable. Continuity matters more than speed.')
    elif rhythm == 'fragile':
        advice.append('Your monthly rhythm looks fragile. Interruptions can move the stopping point earlier.')
    else:
        advice.append('Without steady monthly continuity, projects often stall for long periods.')

    if margin_flag:
        advice.append('You marked monthly effort as “maximum”. That means no margin — fragility increases under pressure.')

    advice.append('Split the project into finishable milestones. Completion-first is safer than starting many parts.')

    scenarios = _scenario_suggestions(inputs) if include_scenarios else []

    created_utc = datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
    return Result(
        created_utc=created_utc,
        inputs=inputs,
        stopping_phase=stopping_phase,
        rhythm=rhythm,
        margin_flag=margin_flag,
        statuses=statuses,
        explanation=explanation,
        advice=advice,
        scenarios=scenarios,
        progress_months=progress_months,
        progress_ratios=progress_ratios,
        reachable_ratio=reachable_ratio,
    )


def _scenario_suggestions(inputs: Inputs) -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []

    def sim(area_factor: float = 1.0, floors_override: str | None = None, monthly_factor: float = 1.0) -> str:
        area_m2 = normalize_area_to_m2(inputs.area_value, inputs.area_unit) * float(area_factor)

        floors = floors_override or inputs.floors
        tmp = Inputs(
            building_type=inputs.building_type,
            floors=floors,
            material=inputs.material,
            area_value=area_m2,
            area_unit='m2',
            currency=inputs.currency,
            total_budget=inputs.total_budget,
            monthly_contribution=(inputs.monthly_contribution or 0.0) * float(monthly_factor),
            max_monthly_effort=inputs.max_monthly_effort,
            country_name=inputs.country_name,
            lang=inputs.lang,
        )

        res = simulate(tmp, include_scenarios=False)
        return res.stopping_phase

    scenarios.append({'title': 'Reduce surface by 10%', 'effect': f"Stopping point tends to move toward: {sim(area_factor=0.90)}"})
    scenarios.append({'title': 'Reduce surface by 20%', 'effect': f"Stopping point tends to move toward: {sim(area_factor=0.80)}"})

    floors_order = ['Ground floor only', 'Ground + 1', 'Ground + 2', 'Ground + 3 or more']
    if inputs.floors in floors_order:
        idx = floors_order.index(inputs.floors)
        if idx > 0:
            scenarios.append({'title': 'Simplify floors (one step down)', 'effect': f"Stopping point tends to move toward: {sim(floors_override=floors_order[idx - 1])}"})

    if (inputs.monthly_contribution or 0.0) > 0:
        scenarios.append({'title': 'Improve monthly rhythm by +20%', 'effect': f"Stopping point tends to move toward: {sim(monthly_factor=1.20)}"})

    return scenarios
