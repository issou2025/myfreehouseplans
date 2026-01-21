from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .elevation_logic import ElevationComplexity
from .surface_logic import SurfaceRisk


@dataclass(frozen=True)
class CountryPressure:
    country_name: str
    financial_pressure: float  # 0..1
    volatility: float  # 0..1
    logistics_difficulty: float  # 0..1

    @property
    def pressure_score(self) -> float:
        # Weighted, intentionally simple.
        return (0.45 * self.financial_pressure) + (0.35 * self.volatility) + (0.20 * self.logistics_difficulty)


@dataclass(frozen=True)
class RiskResult:
    zone: str  # danger | tension | safety
    risk_score: float  # 0..1
    stability_score: float  # 0..100
    surface: SurfaceRisk
    elevation: ElevationComplexity
    country: CountryPressure
    created_utc: str


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def load_country_pressure(country_name: str) -> CountryPressure:
    name = (country_name or '').strip() or 'Global'

    data_path = os.path.join(os.path.dirname(__file__), 'countries.json')
    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            countries: dict[str, Any] = json.load(f)
    except Exception:
        countries = {}

    entry = countries.get(name) or countries.get('Global') or {
        'financial_pressure': 0.50,
        'volatility': 0.50,
        'logistics_difficulty': 0.50,
    }

    def norm(v: Any, default: float) -> float:
        try:
            return _clamp01(float(v))
        except Exception:
            return float(default)

    return CountryPressure(
        country_name=name,
        financial_pressure=norm(entry.get('financial_pressure'), 0.50),
        volatility=norm(entry.get('volatility'), 0.50),
        logistics_difficulty=norm(entry.get('logistics_difficulty'), 0.50),
    )


def evaluate_risk(
    *,
    surface: SurfaceRisk,
    elevation: ElevationComplexity,
    country: CountryPressure,
) -> RiskResult:
    """Return a single decision-oriented risk zone.

    This model is intentionally NOT a quotation engine.
    It combines three realities:
      - size stress (surface)
      - elevation complexity (levels)
      - context pressure (country)

    Output is deterministic.
    """

    # Core signals.
    surface_signal = surface.risk  # already 0..1
    elevation_signal = _clamp01((elevation.multiplier - 1.0) / 0.50)  # map 1.0..1.5 -> 0..1
    country_signal = _clamp01(country.pressure_score)

    # Combine (weighted). End-of-project fragility is dominated by size + elevation.
    risk = (0.62 * surface_signal) + (0.26 * elevation_signal) + (0.12 * country_signal)

    # Small nonlinear bump at high risk to reflect end-stage acceleration.
    if risk > 0.60:
        risk = _clamp01(risk + ((risk - 0.60) ** 2) * 0.55)

    # Translate to zone.
    if risk >= 0.68:
        zone = 'danger'
    elif risk >= 0.45:
        zone = 'tension'
    else:
        zone = 'safety'

    stability_score = round((1.0 - risk) * 100.0)

    return RiskResult(
        zone=zone,
        risk_score=float(risk),
        stability_score=float(stability_score),
        surface=surface,
        elevation=elevation,
        country=country,
        created_utc=datetime.utcnow().replace(microsecond=0).isoformat() + 'Z',
    )
