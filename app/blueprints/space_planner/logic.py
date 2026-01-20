from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


Verdict = str  # 'comfortable' | 'tight' | 'not_suitable'


VERDICT_RANK: Dict[Verdict, int] = {
    'not_suitable': 0,
    'tight': 1,
    'comfortable': 2,
}


@dataclass(frozen=True)
class ClearanceProfile:
    """Defines how to inflate furniture dimensions to include functional clearances.

    All inputs/outputs are in centimeters.

    Modes:
      - 'all_around': clearance on all sides (e.g., dining table).
      - 'front_only': clearance in front (e.g., sofa/wardrobe/WC/shower).
      - 'bed_access': clearance for access around a bed (typical headboard-on-wall).
    """

    mode: str
    all_around_cm: float = 0.0
    front_cm: float = 0.0
    bed_side_cm: float = 0.0
    bed_foot_cm: float = 0.0
    bed_head_cm: float = 0.0

    def expand(self, length_cm: float, width_cm: float, rotated: bool) -> Tuple[float, float, str]:
        """Return (required_length_cm, required_width_cm, human_note)."""

        if rotated:
            length_cm, width_cm = width_cm, length_cm

        if self.mode == 'all_around':
            req_len = length_cm + 2 * self.all_around_cm
            req_wid = width_cm + 2 * self.all_around_cm
            note = f"Includes ~{int(self.all_around_cm)}cm clearance on all sides."
            return req_len, req_wid, note

        if self.mode == 'front_only':
            # Convention:
            # - length_cm is along the wall (frontage)
            # - width_cm is the depth/projection into the room
            req_len = length_cm
            req_wid = width_cm + self.front_cm
            note = f"Includes ~{int(self.front_cm)}cm functional clearance in front."
            return req_len, req_wid, note

        if self.mode == 'bed_access':
            # Typical bedroom placement:
            # - bed headboard placed to a wall (0 head clearance)
            # - access on both sides + at the foot
            req_len = length_cm + self.bed_head_cm + self.bed_foot_cm
            req_wid = width_cm + 2 * self.bed_side_cm
            note = (
                f"Includes ~{int(self.bed_side_cm)}cm side access and "
                f"~{int(self.bed_foot_cm)}cm at the foot (headboard to wall)."
            )
            return req_len, req_wid, note

        raise ValueError(f"Unsupported clearance profile mode: {self.mode}")


@dataclass(frozen=True)
class FurnitureType:
    key: str
    label: str
    clearance: ClearanceProfile


@dataclass(frozen=True)
class OrientationResult:
    rotated: bool
    required_length_cm: float
    required_width_cm: float
    remaining_length_cm: float
    remaining_width_cm: float
    verdict: Verdict
    tight_axis: Optional[str]
    clearance_note: str


@dataclass(frozen=True)
class FitAnalysis:
    room_length_cm: float
    room_width_cm: float
    furniture_key: str
    furniture_label: str
    furniture_length_cm: float
    furniture_width_cm: float
    results: List[OrientationResult]
    best: OrientationResult


def _classify_fit(remaining_length_cm: float, remaining_width_cm: float) -> Tuple[Verdict, Optional[str]]:
    """Return (verdict, tight_axis)."""

    min_remaining = min(remaining_length_cm, remaining_width_cm)
    if min_remaining < 0:
        return 'not_suitable', None

    # "Comfort" buffer:
    # If you can still move around without squeezing against walls/doors.
    # 30cm is a practical global threshold for 'feels okay' in unknown layouts.
    if min_remaining >= 30:
        return 'comfortable', None

    # Fits, but circulation is limited on at least one axis.
    tight_axis = 'length' if remaining_length_cm < remaining_width_cm else 'width'
    return 'tight', tight_axis


def evaluate_fit(
    *,
    room_length_cm: float,
    room_width_cm: float,
    furniture: FurnitureType,
    furniture_length_cm: float,
    furniture_width_cm: float,
) -> FitAnalysis:
    """Evaluate fit in normal and 90° rotation.

    Returns a FitAnalysis with per-orientation results and the best recommendation.
    """

    if room_length_cm <= 0 or room_width_cm <= 0:
        raise ValueError('Room dimensions must be positive.')
    if furniture_length_cm <= 0 or furniture_width_cm <= 0:
        raise ValueError('Furniture dimensions must be positive.')

    # Normalize room orientation (length is the longer side for stable messaging)
    if room_width_cm > room_length_cm:
        room_length_cm, room_width_cm = room_width_cm, room_length_cm

    results: List[OrientationResult] = []

    for rotated in (False, True):
        req_len, req_wid, note = furniture.clearance.expand(
            furniture_length_cm,
            furniture_width_cm,
            rotated=rotated,
        )

        remaining_len = room_length_cm - req_len
        remaining_wid = room_width_cm - req_wid

        verdict, tight_axis = _classify_fit(remaining_len, remaining_wid)

        results.append(
            OrientationResult(
                rotated=rotated,
                required_length_cm=req_len,
                required_width_cm=req_wid,
                remaining_length_cm=remaining_len,
                remaining_width_cm=remaining_wid,
                verdict=verdict,
                tight_axis=tight_axis,
                clearance_note=note,
            )
        )

    def _score(r: OrientationResult) -> Tuple[int, float, float]:
        # Higher verdict is better; then maximize min remaining; then maximize area remaining.
        rank = VERDICT_RANK.get(r.verdict, 0)
        min_remaining = min(r.remaining_length_cm, r.remaining_width_cm)
        area_remaining = max(0.0, r.remaining_length_cm) * max(0.0, r.remaining_width_cm)
        return rank, min_remaining, area_remaining

    best = sorted(results, key=_score, reverse=True)[0]

    return FitAnalysis(
        room_length_cm=room_length_cm,
        room_width_cm=room_width_cm,
        furniture_key=furniture.key,
        furniture_label=furniture.label,
        furniture_length_cm=furniture_length_cm,
        furniture_width_cm=furniture_width_cm,
        results=results,
        best=best,
    )


def get_furniture_catalog() -> Dict[str, FurnitureType]:
    """Central catalog for furniture + architectural clearance assumptions."""

    return {
        'bed': FurnitureType(
            key='bed',
            label='Bed',
            clearance=ClearanceProfile(
                mode='bed_access',
                bed_side_cm=70,
                bed_foot_cm=70,
                bed_head_cm=0,
            ),
        ),
        'sofa': FurnitureType(
            key='sofa',
            label='Sofa',
            clearance=ClearanceProfile(
                mode='front_only',
                front_cm=60,
            ),
        ),
        'table': FurnitureType(
            key='table',
            label='Table',
            clearance=ClearanceProfile(
                mode='all_around',
                all_around_cm=60,
            ),
        ),
        'wardrobe': FurnitureType(
            key='wardrobe',
            label='Wardrobe / Closet',
            clearance=ClearanceProfile(
                mode='front_only',
                front_cm=90,
            ),
        ),
        'shower': FurnitureType(
            key='shower',
            label='Shower',
            clearance=ClearanceProfile(
                mode='front_only',
                front_cm=70,
            ),
        ),
        'wc': FurnitureType(
            key='wc',
            label='WC',
            clearance=ClearanceProfile(
                mode='front_only',
                front_cm=60,
            ),
        ),
    }
