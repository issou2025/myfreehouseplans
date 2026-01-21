from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SurfaceRisk:
    surface_m2: int
    band: str
    risk: float  # 0..1


def validate_surface_m2(surface_m2: int) -> int:
    try:
        value = int(surface_m2)
    except Exception as exc:
        raise ValueError('surface_m2 must be a whole number') from exc

    if value < 10:
        raise ValueError('surface_m2 must be at least 10')
    if value > 2000:
        raise ValueError('surface_m2 must be at most 2000')
    return value


def _lerp(a: float, b: float, t: float) -> float:
    if t <= 0:
        return a
    if t >= 1:
        return b
    return a + (b - a) * t


def surface_risk(surface_m2: int) -> SurfaceRisk:
    """Return a qualitative + quantitative surface risk.

    This is NOT a cost model.
    The risk reflects human and project fragility that scales with size:
    duration, fatigue, coordination, and exposure to end-of-project pressure.
    """

    s = validate_surface_m2(surface_m2)

    # Piecewise, smooth-ish curve.
    # Intuition: risk grows faster once the project becomes "big".
    if s <= 60:
        band = 'small_surface'
        risk = _lerp(0.18, 0.28, (s - 10) / (60 - 10))
    elif s <= 120:
        band = 'medium_surface'
        risk = _lerp(0.32, 0.52, (s - 61) / (120 - 61))
    elif s <= 200:
        band = 'large_surface'
        risk = _lerp(0.55, 0.72, (s - 121) / (200 - 121))
    else:
        band = 'very_large_surface'
        # Above ~200m², the curve saturates near critical.
        capped = min(s, 600)
        risk = _lerp(0.76, 0.92, (capped - 201) / (600 - 201))

    risk = max(0.0, min(1.0, float(risk)))
    return SurfaceRisk(surface_m2=s, band=band, risk=risk)
