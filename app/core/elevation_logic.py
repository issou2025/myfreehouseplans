from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ElevationComplexity:
    levels_label: str
    levels_bucket: str
    multiplier: float


_LEVEL_OPTIONS = {
    '1': ('1 level (ground floor)', '1_level', 1.00),
    '2': ('2 levels', '2_levels', 1.15),
    '3': ('3 levels', '3_levels', 1.30),
    '4+': ('4 levels or more', '4_or_more', 1.50),
}


def validate_levels_choice(levels_choice: str) -> str:
    value = str(levels_choice or '').strip()
    if value not in _LEVEL_OPTIONS:
        raise ValueError('levels must be one of: 1, 2, 3, 4+')
    return value


def elevation_complexity(levels_choice: str) -> ElevationComplexity:
    key = validate_levels_choice(levels_choice)
    label, bucket, multiplier = _LEVEL_OPTIONS[key]
    return ElevationComplexity(levels_label=label, levels_bucket=bucket, multiplier=float(multiplier))
