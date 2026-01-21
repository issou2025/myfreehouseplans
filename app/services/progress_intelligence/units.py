from __future__ import annotations

FT2_PER_M2 = 10.7639


def normalize_area_to_m2(value: float, unit: str) -> float:
    u = (unit or 'm2').strip().lower()
    v = float(value)
    if u in {'m2', 'm²', 'sqm'}:
        return v
    if u in {'ft2', 'ft²', 'sqft'}:
        return v / FT2_PER_M2
    raise ValueError('Unsupported unit')


def format_area(value: float, unit: str) -> str:
    u = (unit or 'm2').strip().lower()
    if u in {'m2', 'm²', 'sqm'}:
        return f"{value:.0f} m²"
    if u in {'ft2', 'ft²', 'sqft'}:
        return f"{value:.0f} ft²"
    return f"{value:.0f}"


def convert_m2_to_unit(m2: float, unit: str) -> float:
    u = (unit or 'm2').strip().lower()
    if u in {'m2', 'm²', 'sqm'}:
        return float(m2)
    if u in {'ft2', 'ft²', 'sqft'}:
        return float(m2) * FT2_PER_M2
    raise ValueError('Unsupported unit')
