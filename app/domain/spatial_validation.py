from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SpatialValidationResult:
    ok: bool
    verdict: str  # Comfortable | Acceptable but tight | Not recommended
    status: str  # ok | warning | not_ok
    reason: str


def _fmt_num(value: float) -> str:
    # Keep outputs human: trim trailing zeros.
    return f"{value:.2f}".rstrip('0').rstrip('.')


def _to_user_length(value_m: float, units_key: str) -> float:
    if units_key == 'imperial':
        return float(value_m) / 0.3048
    return float(value_m)


def _units_label(units_key: str) -> str:
    return 'ft' if units_key == 'imperial' else 'm'


def min_side_m_for_room(room_slug: str) -> float:
    """Strict minimum side (width/depth) by room type.

    Rule intent: reject unusable shapes before any planning.
    Values are in meters.
    """

    slug = (room_slug or '').strip().lower()

    # Explicit room-specific rules (from the spec)
    if slug in {'bedroom', 'master-bedroom', 'children-room'}:
        return 2.4
    if slug in {'living-room', 'dining-room'}:
        return 2.8
    if slug in {'kitchen'}:
        return 1.8
    if slug in {'bathroom'}:
        return 1.5
    if slug in {'wc'}:
        return 0.9
    if slug in {'office'}:
        return 1.8
    if slug in {'garage'}:
        return 2.5
    if slug in {'corridor'}:
        return 1.0

    # Closest-fit for related slugs
    if slug in {'entrance'}:
        return 1.0

    # Global fallback
    return 1.8


def validate_room_dimensions(
    *,
    room_slug: str,
    room_label: str,
    length_m: Optional[float],
    width_m: Optional[float],
    units_key: str,
) -> SpatialValidationResult:
    """Validate a room as a *real* usable space.

    Non-negotiable rules:
    - Must have both dimensions (surface alone is not enough)
    - Minimum width + minimum depth (min side)
    - Max length-to-width ratio of 3:1

    Returns a result suitable for immediate UX display.
    """

    if length_m is None or width_m is None:
        return SpatialValidationResult(
            ok=False,
            verdict='Not recommended',
            status='not_ok',
            reason=(
                "To check if this space works in real life, please enter at least one side (length or width). "
                "Surface alone can’t confirm if the room is too narrow."
            ),
        )

    try:
        length_m = float(length_m)
        width_m = float(width_m)
    except (TypeError, ValueError):
        return SpatialValidationResult(
            ok=False,
            verdict='Not recommended',
            status='not_ok',
            reason="Please enter valid room dimensions.",
        )

    if length_m <= 0 or width_m <= 0:
        return SpatialValidationResult(
            ok=False,
            verdict='Not recommended',
            status='not_ok',
            reason="Please enter room dimensions greater than 0.",
        )

    a = max(length_m, width_m)
    b = min(length_m, width_m)

    min_side_m = min_side_m_for_room(room_slug)

    # 1) Minimum side check (width/depth)
    if b < min_side_m:
        target = _fmt_num(_to_user_length(min_side_m, units_key))
        u = _units_label(units_key)
        label = (room_label or 'room').lower()
        return SpatialValidationResult(
            ok=False,
            verdict='Not recommended',
            status='not_ok',
            reason=(
                f"This {label} is too narrow to work well in real life. "
                f"Try at least {target} {u} for a more comfortable layout."
            ),
        )

    # 2) Proportion check
    ratio = a / b if b else 999
    if ratio > 3.0:
        label = (room_label or 'room').lower()
        return SpatialValidationResult(
            ok=False,
            verdict='Not recommended',
            status='not_ok',
            reason=(
                f"This {label} is too long and narrow to feel practical day to day. "
                "A more balanced shape works much better."
            ),
        )

    return SpatialValidationResult(
        ok=True,
        verdict='Comfortable',
        status='ok',
        reason='',
    )
