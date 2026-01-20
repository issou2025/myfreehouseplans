from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .data import ItemSpec, RoomSpec


Verdict = str  # 'comfortable' | 'tight' | 'not_suitable'


@dataclass(frozen=True)
class UnitSystem:
    key: str  # 'metric' | 'imperial'
    length_label: str
    placeholder_room: str
    placeholder_item: str


UNITS: Dict[str, UnitSystem] = {
    'metric': UnitSystem('metric', 'cm', 'e.g., 420', 'e.g., 200'),
    'imperial': UnitSystem('imperial', 'ft', 'e.g., 14', 'e.g., 6.5'),
}


def to_cm(value: float, units_key: str) -> float:
    if units_key == 'imperial':
        return float(value) * 30.48  # feet -> cm
    return float(value)  # centimeters


def from_cm(cm: float, units_key: str) -> float:
    if units_key == 'imperial':
        return float(cm) / 30.48
    return float(cm)


@dataclass(frozen=True)
class OrientationResult:
    rotated: bool
    required_length_cm: float
    required_width_cm: float
    remaining_length_cm: float
    remaining_width_cm: float
    occupancy_ratio: float
    verdict: Verdict
    reason: str


@dataclass(frozen=True)
class FitAnalysis:
    room: RoomSpec
    item: ItemSpec
    room_length_cm: float
    room_width_cm: float
    item_length_cm: float
    item_width_cm: float
    best: OrientationResult
    other: OrientationResult


def _movement_expand(item: ItemSpec, length_cm: float, width_cm: float, rotated: bool) -> Tuple[float, float]:
    """Return a realistic 'needs space' footprint in cm.

    This is internal only. We avoid surfacing technical terms in UI.
    """

    if rotated:
        length_cm, width_cm = width_cm, length_cm

    p = item.movement_profile

    # Around-table movement (people sit/stand)
    if p == 'around_large':
        return length_cm + 120, width_cm + 120
    if p == 'around_small':
        return length_cm + 90, width_cm + 90

    # In-front usage (open doors, pull chairs, stand)
    if p == 'front_use_large':
        return length_cm, width_cm + 90
    if p == 'front_use_medium':
        return length_cm, width_cm + 60
    if p == 'front_use_small':
        return length_cm, width_cm + 45

    # Bed access: headboard assumed on a wall, access on sides + foot
    if p == 'bed_access':
        return length_cm + 70, width_cm + 140

    # Desk usage (chair + legroom)
    if p == 'seated_work':
        return length_cm, width_cm + 90

    # Small items: tiny buffer
    if p == 'small_item':
        return length_cm + 20, width_cm + 20

    # Wall-hug items (console tables, slim shelves): keep walking space realistic
    if p == 'wall_hug':
        return length_cm + 10, width_cm + 10

    # Garage vehicles: include door opening + walking around
    if p == 'garage_vehicle':
        # Keep it realistic: many garages are tight, but still usable.
        return length_cm + 80, width_cm + 60
    if p == 'garage_vehicle_small':
        return length_cm + 60, width_cm + 40

    # Fallback
    return length_cm + 60, width_cm + 60


def _classify(
    *,
    room: RoomSpec,
    remaining_len: float,
    remaining_wid: float,
    occupancy_ratio: float,
) -> Tuple[Verdict, str]:
    min_remaining = min(remaining_len, remaining_wid)

    if min_remaining < 0:
        return 'not_suitable', 'It simply doesn’t fit in this room size.'

    # Hallway/corridor rule: preserve a walkable strip.
    if room.preferred_walkway_cm:
        # Width is typically the pinch point for walking past items.
        walkway_left = remaining_wid

        # Corridors/entrances need the walkway to stay genuinely usable.
        if room.slug in {'corridor', 'entrance'}:
            # Treat the target as "comfortable"; allow tighter passages before rejecting.
            if walkway_left < (room.preferred_walkway_cm - 40):
                return 'not_suitable', 'It would make the space feel blocked when walking through.'
            if walkway_left < (room.preferred_walkway_cm - 15):
                return 'tight', 'It fits, but passing through will feel tight.'
        else:
            # In other rooms (garage, dressing, terrace), a tighter walkway can still be workable.
            if walkway_left < (room.preferred_walkway_cm - 50):
                return 'not_suitable', 'It would make the space feel blocked when walking through.'
            if walkway_left < (room.preferred_walkway_cm - 20):
                return 'tight', 'It fits, but you’ll need to squeeze past in one spot.'

    # Overcrowding heuristic (single-item version, ready for multi-item later)
    overcrowd_limit = 0.65
    if room.slug in {'garage', 'corridor', 'entrance', 'balcony'}:
        overcrowd_limit = 0.90
    if occupancy_ratio >= overcrowd_limit:
        return 'not_suitable', 'The room would feel overcrowded with this item.'

    if min_remaining >= 30 and occupancy_ratio <= 0.45:
        return 'comfortable', 'This layout feels comfortable for everyday use.'

    return 'tight', 'It fits, but movement will feel tight in at least one area.'


def evaluate_fit(
    *,
    room: RoomSpec,
    item: ItemSpec,
    room_length_cm: float,
    room_width_cm: float,
    item_length_cm: float,
    item_width_cm: float,
) -> FitAnalysis:
    if room_length_cm <= 0 or room_width_cm <= 0:
        raise ValueError('Room dimensions must be positive')
    if item_length_cm <= 0 or item_width_cm <= 0:
        raise ValueError('Item dimensions must be positive')

    # Normalize room so length is the longer side (keeps messaging stable)
    if room_width_cm > room_length_cm:
        room_length_cm, room_width_cm = room_width_cm, room_length_cm

    room_area = room_length_cm * room_width_cm

    def _result(rotated: bool) -> OrientationResult:
        req_len, req_wid = _movement_expand(item, item_length_cm, item_width_cm, rotated)
        remaining_len = room_length_cm - req_len
        remaining_wid = room_width_cm - req_wid
        occ = (max(0.0, req_len) * max(0.0, req_wid)) / room_area if room_area else 1.0
        verdict, reason = _classify(room=room, remaining_len=remaining_len, remaining_wid=remaining_wid, occupancy_ratio=occ)
        return OrientationResult(
            rotated=rotated,
            required_length_cm=req_len,
            required_width_cm=req_wid,
            remaining_length_cm=remaining_len,
            remaining_width_cm=remaining_wid,
            occupancy_ratio=occ,
            verdict=verdict,
            reason=reason,
        )

    normal = _result(False)
    rotated = _result(True)

    def _score(r: OrientationResult) -> Tuple[int, float, float]:
        rank = {'not_suitable': 0, 'tight': 1, 'comfortable': 2}.get(r.verdict, 0)
        min_remaining = min(r.remaining_length_cm, r.remaining_width_cm)
        return rank, min_remaining, -r.occupancy_ratio

    best = max([normal, rotated], key=_score)
    other = rotated if best is normal else normal

    return FitAnalysis(
        room=room,
        item=item,
        room_length_cm=room_length_cm,
        room_width_cm=room_width_cm,
        item_length_cm=item_length_cm,
        item_width_cm=item_width_cm,
        best=best,
        other=other,
    )
