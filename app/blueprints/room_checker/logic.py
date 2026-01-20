from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .data import RoomType


StatusFlag = str  # ok | warning | not_ok


@dataclass(frozen=True)
class UnitSystem:
    key: str  # metric | imperial
    length_label: str
    area_label: str
    placeholder_length: str
    placeholder_area: str


UNITS: Dict[str, UnitSystem] = {
    'metric': UnitSystem('metric', 'm', 'm²', 'e.g., 4.2', 'e.g., 12'),
    'imperial': UnitSystem('imperial', 'ft', 'ft²', 'e.g., 14', 'e.g., 130'),
}


def to_m(value: float, units_key: str) -> float:
    if units_key == 'imperial':
        return float(value) * 0.3048
    return float(value)


def to_m2(value: float, units_key: str) -> float:
    if units_key == 'imperial':
        return float(value) * 0.09290304
    return float(value)


def from_m(value_m: float, units_key: str) -> float:
    if units_key == 'imperial':
        return float(value_m) / 0.3048
    return float(value_m)


def from_m2(value_m2: float, units_key: str) -> float:
    if units_key == 'imperial':
        return float(value_m2) / 0.09290304
    return float(value_m2)


@dataclass(frozen=True)
class RoomSizeInputs:
    method: str  # dims | area
    length: Optional[float] = None
    width: Optional[float] = None
    area: Optional[float] = None


@dataclass(frozen=True)
class RoomQualityResult:
    status: StatusFlag
    verdict: str  # Comfortable | Acceptable but tight | Not recommended
    area_m2: float
    length_m: Optional[float]
    width_m: Optional[float]
    shape_note: Optional[str]


def _shape_notes(room: RoomType, length_m: Optional[float], width_m: Optional[float]) -> Optional[str]:
    if length_m is None or width_m is None:
        return None

    a = max(length_m, width_m)
    b = min(length_m, width_m)
    if b <= 0:
        return None

    if room.benchmarks.min_side_m and b < room.benchmarks.min_side_m:
        return 'One side is quite narrow, so daily movement may feel less comfortable.'

    if room.slug not in {'corridor'}:
        ratio = a / b
        if room.benchmarks.max_aspect_ratio and ratio > room.benchmarks.max_aspect_ratio:
            return 'The room is long and narrow, so it may feel less comfortable in everyday use.'

    return None


def evaluate_room_quality(*, room: RoomType, inputs: RoomSizeInputs, units_key: str) -> RoomQualityResult:
    # Normalize to meters / m²
    length_m: Optional[float] = None
    width_m: Optional[float] = None
    area_m2: Optional[float] = None

    if inputs.method == 'dims':
        if inputs.length is None or inputs.width is None:
            raise ValueError('length and width are required for dims')
        length_m = to_m(inputs.length, units_key)
        width_m = to_m(inputs.width, units_key)
        if length_m <= 0 or width_m <= 0:
            raise ValueError('length and width must be positive')
        area_m2 = length_m * width_m

    elif inputs.method == 'area':
        if inputs.area is None:
            raise ValueError('area is required for area')
        area_m2 = to_m2(inputs.area, units_key)
        if area_m2 <= 0:
            raise ValueError('area must be positive')

        # Optional: if user also gave one side, we can infer shape internally (without showing formulas).
        if inputs.length is not None and inputs.width is None and inputs.length > 0:
            length_m = to_m(inputs.length, units_key)
            width_m = area_m2 / length_m if length_m else None
        elif inputs.width is not None and inputs.length is None and inputs.width > 0:
            width_m = to_m(inputs.width, units_key)
            length_m = area_m2 / width_m if width_m else None
        elif inputs.length is not None and inputs.width is not None and inputs.length > 0 and inputs.width > 0:
            length_m = to_m(inputs.length, units_key)
            width_m = to_m(inputs.width, units_key)

    else:
        raise ValueError('unknown method')

    assert area_m2 is not None

    b = room.benchmarks
    shape_note = _shape_notes(room, length_m, width_m)

    # Base verdict from area alone
    if area_m2 >= b.comfortable_area_m2:
        status: StatusFlag = 'ok'
        verdict = 'Comfortable'
    elif area_m2 >= b.min_area_m2:
        status = 'warning'
        verdict = 'Acceptable but tight'
    else:
        status = 'not_ok'
        verdict = 'Not recommended'

    # Gentle downgrade if shape is likely to feel narrow (never upgrades)
    if shape_note and status == 'ok':
        status = 'warning'
        verdict = 'Acceptable but tight'

    return RoomQualityResult(
        status=status,
        verdict=verdict,
        area_m2=area_m2,
        length_m=length_m,
        width_m=width_m,
        shape_note=shape_note,
    )
