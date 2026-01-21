from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .units import normalize_area_to_m2


PHASES = [
    'Preparation',
    'Foundation',
    'Structure',
    'Envelope (walls + roof)',
    'Closure (doors + windows)',
    'Services (basic habitability)',
    'Finishing',
]


@dataclass(frozen=True)
class Inputs:
    building_type: str
    floors: str
    material: str
    area_value: float
    area_unit: str
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
    rhythm: str  # stable|fragile|stoppage
    margin_flag: bool
    statuses: list[PhaseStatus]
    explanation: str
    advice: list[str]
    scenarios: list[dict[str, Any]]


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    s = str(value).strip()
    if s == '':
        return None
    try:
        v = float(s)
    except Exception:
        return None
    if v < 0:
        return 0.0
    return float(v)


def _load_country_factor(country_name: str) -> dict[str, float]:
    name = (country_name or '').strip() or 'Global'
    path = os.path.join(os.path.dirname(__file__), 'country_factors.json')
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {}

    entry = data.get(name) or data.get('Global') or {'pressure': 0.5, 'volatility': 0.5, 'logistics': 0.5}

    def n(v: Any) -> float:
        try:
            return _clamp01(float(v))
        except Exception:
            return 0.5

    return {
        'pressure': n(entry.get('pressure')),
        'volatility': n(entry.get('volatility')),
        'logistics': n(entry.get('logistics')),
    }


def _building_type_multiplier(building_type: str) -> float:
    key = (building_type or '').strip()
    return {
        'Single-family house': 1.00,
        'Multi-family building': 1.22,
        'School': 1.12,
        'Health center': 1.20,
        'Commercial building': 1.15,
        'Light industrial / workshop': 1.10,
    }.get(key, 1.10)


def _floors_multiplier(floors: str) -> float:
    key = (floors or '').strip()
    return {
        'Ground floor only': 1.00,
        'Ground + 1 floor': 1.18,
        'Ground + 2 floors': 1.38,
        'Ground + 3 floors or more': 1.60,
    }.get(key, 1.25)


def _material_profile(material: str) -> dict[str, Any]:
    key = (material or '').strip()
    if key == 'Steel':
        return {
            'mult': 1.06,
            'weights_adjust': {'Preparation': +0.03, 'Structure': +0.02, 'Services (basic habitability)': -0.02, 'Finishing': -0.03},
            'continuity_sensitivity': 1.05,
            'note': 'Steel projects are sensitive early: precision and coordination matter from the start.',
        }
    if key == 'Wood':
        return {
            'mult': 0.98,
            'weights_adjust': {'Finishing': +0.02, 'Envelope (walls + roof)': -0.01, 'Preparation': -0.01},
            'continuity_sensitivity': 1.15,
            'note': 'Wood can progress fast early, but interruptions can create fragility later.',
        }
    # Concrete default
    return {
        'mult': 1.00,
        'weights_adjust': {'Finishing': +0.03, 'Services (basic habitability)': +0.02, 'Preparation': -0.02, 'Structure': -0.03},
        'continuity_sensitivity': 1.00,
        'note': 'Concrete projects often feel easy early but become demanding near the end.',
    }


def _base_phase_weights() -> dict[str, float]:
    # Intentionally non-linear: later phases consume disproportionate resources.
    return {
        'Preparation': 0.08,
        'Foundation': 0.12,
        'Structure': 0.22,
        'Envelope (walls + roof)': 0.16,
        'Closure (doors + windows)': 0.10,
        'Services (basic habitability)': 0.12,
        'Finishing': 0.20,
    }


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, float(v)) for v in weights.values())
    if total <= 0:
        return _base_phase_weights()
    return {k: max(0.0, float(v)) / total for k, v in weights.items()}


def _apply_adjustments(weights: dict[str, float], adjustments: dict[str, float]) -> dict[str, float]:
    out = dict(weights)
    for k, delta in (adjustments or {}).items():
        if k in out:
            out[k] = float(out[k]) + float(delta)
    return _normalize_weights(out)


def _required_resource_index(area_m2: float, building_type: str, floors: str, material: str, country_name: str) -> float:
    # Dimensionless index used only to map user's own amounts to a stopping point.
    # We keep it simple and globally applicable.
    t_mult = _building_type_multiplier(building_type)
    f_mult = _floors_multiplier(floors)
    m_prof = _material_profile(material)

    factors = _load_country_factor(country_name)
    pressure = (0.45 * factors['pressure']) + (0.35 * factors['volatility']) + (0.20 * factors['logistics'])

    # Surface grows sub-linearly to avoid over-penalizing large community projects.
    surface_term = (max(10.0, area_m2) / 100.0) ** 0.88

    # Baseline index: calibrated so typical inputs produce readable phase splits.
    base = 110.0
    return base * surface_term * t_mult * f_mult * float(m_prof['mult']) * (0.90 + 0.35 * pressure)


def _compute_rhythm(required_index: float, monthly: float | None, *, target_months: int, material: str) -> tuple[str, float]:
    if not monthly or monthly <= 0:
        return ('stoppage', 0.0)

    # Convert required index into a monthly "continuity" target (dimensionless).
    needed_per_month = required_index / float(target_months)
    if needed_per_month <= 0:
        return ('stable', 1.0)

    ratio = monthly / needed_per_month
    ratio = float(ratio)

    sensitivity = float(_material_profile(material).get('continuity_sensitivity', 1.0))
    ratio = ratio / sensitivity

    if ratio >= 1.0:
        return ('stable', ratio)
    if ratio >= 0.60:
        return ('fragile', ratio)
    return ('stoppage', ratio)


def simulate(inputs: Inputs) -> Result:
    lang = (inputs.lang or 'en').strip().lower()

    # Normalize + validate area
    area_m2 = normalize_area_to_m2(inputs.area_value, inputs.area_unit)
    if area_m2 < 10:
        raise ValueError('Surface area is too small. Please enter at least 10 m² (or equivalent).')
    if area_m2 > 200000:
        raise ValueError('Surface area is too large for this tool. Please reduce it or split the project.')

    total_budget = inputs.total_budget or 0.0
    monthly = inputs.monthly_contribution or 0.0

    required = _required_resource_index(area_m2, inputs.building_type, inputs.floors, inputs.material, inputs.country_name)

    # Budget-based reach ratio (0..1+)
    # We keep it bounded for stability.
    reach_ratio = 0.0
    if required > 0:
        reach_ratio = max(0.0, float(total_budget) / float(required))

    # Add a limited time-horizon contribution to represent continuity.
    # This avoids pretending we know infinite future.
    horizon_months = 24
    if monthly > 0 and required > 0:
        reach_ratio = max(0.0, float(total_budget + (monthly * horizon_months)) / float(required))

    reach_ratio = min(1.25, reach_ratio)

    weights = _base_phase_weights()
    weights = _apply_adjustments(weights, _material_profile(inputs.material).get('weights_adjust', {}))

    cumulative = 0.0
    statuses: list[PhaseStatus] = []
    stopping_phase = PHASES[0]

    for phase in PHASES:
        w = float(weights.get(phase, 0.0))
        prev = cumulative
        cumulative += w

        if reach_ratio >= cumulative:
            statuses.append(PhaseStatus(phase=phase, status='green', note='Reached with realistic continuity.'))
            stopping_phase = phase
        elif reach_ratio > prev:
            statuses.append(PhaseStatus(phase=phase, status='orange', note='Partially reachable, but fragile.'))
            stopping_phase = phase
        else:
            statuses.append(PhaseStatus(phase=phase, status='red', note='Not realistically reachable with current pattern.'))

    rhythm, rhythm_ratio = _compute_rhythm(required, monthly if monthly > 0 else None, target_months=horizon_months, material=inputs.material)

    margin_flag = bool(inputs.max_monthly_effort and monthly > 0 and rhythm in {'fragile', 'stoppage'})

    material_note = _material_profile(inputs.material).get('note', '')

    explanation = (
        f"Stopping point tends to appear around: {stopping_phase}. "
        "This is a simulation of progression stress, not a quote. "
        + (material_note or '')
    )

    advice: list[str] = []
    if stopping_phase in {'Finishing', 'Services (basic habitability)'}:
        advice.append('Protect the final stretch. Late changes are the #1 reason stable projects become fragile.')
    else:
        advice.append('The safest improvement is to reduce surface or floors before starting.')

    if rhythm == 'stable':
        advice.append('Your monthly rhythm looks stable. Keep it consistent — continuity matters more than speed.')
    elif rhythm == 'fragile':
        advice.append('Your monthly rhythm looks fragile. Small interruptions can move the stopping point earlier.')
    else:
        advice.append('Without a steady rhythm, projects often stall for long periods. Protect continuity if possible.')

    if margin_flag:
        advice.append('You marked your monthly effort as “maximum”. That means low margin — risk increases under pressure.')

    advice.append('Split the project into finishable milestones. Completion-first is safer than starting many parts.')

    scenarios = _scenario_suggestions(inputs, base_required=required)

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
    )


def _scenario_suggestions(inputs: Inputs, *, base_required: float) -> list[dict[str, Any]]:
    # Show improvement directions without exposing any "prices".
    scenarios: list[dict[str, Any]] = []

    def sim(area_factor: float = 1.0, floors_override: str | None = None, monthly_factor: float = 1.0) -> str:
        area_m2 = normalize_area_to_m2(inputs.area_value, inputs.area_unit) * area_factor
        floors = floors_override or inputs.floors
        required = _required_resource_index(area_m2, inputs.building_type, floors, inputs.material, inputs.country_name)

        total_budget = inputs.total_budget or 0.0
        monthly = (inputs.monthly_contribution or 0.0) * monthly_factor

        horizon_months = 24
        reach_ratio = 0.0
        if required > 0:
            reach_ratio = (total_budget + monthly * horizon_months) / required
        reach_ratio = min(1.25, max(0.0, float(reach_ratio)))

        weights = _apply_adjustments(_base_phase_weights(), _material_profile(inputs.material).get('weights_adjust', {}))

        cumulative = 0.0
        last = PHASES[0]
        for phase in PHASES:
            cumulative += float(weights.get(phase, 0.0))
            if reach_ratio >= cumulative:
                last = phase
            elif reach_ratio > (cumulative - float(weights.get(phase, 0.0))):
                last = phase
        return last

    scenarios.append({
        'title': 'Reduce surface by 10%',
        'effect': f"Stopping point tends to move toward: {sim(area_factor=0.90)}",
    })
    scenarios.append({
        'title': 'Reduce surface by 20%',
        'effect': f"Stopping point tends to move toward: {sim(area_factor=0.80)}",
    })

    floors_order = ['Ground floor only', 'Ground + 1 floor', 'Ground + 2 floors', 'Ground + 3 floors or more']
    if inputs.floors in floors_order:
        idx = floors_order.index(inputs.floors)
        if idx > 0:
            scenarios.append({
                'title': 'Simplify floors (one step down)',
                'effect': f"Stopping point tends to move toward: {sim(floors_override=floors_order[idx - 1])}",
            })

    if (inputs.monthly_contribution or 0.0) > 0:
        scenarios.append({
            'title': 'Improve monthly rhythm by +20%',
            'effect': f"Stopping point tends to move toward: {sim(monthly_factor=1.20)}",
        })

    return scenarios
