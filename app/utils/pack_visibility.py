from __future__ import annotations

import json
import os
from typing import Iterable

from flask import current_app

DEFAULT_VISIBILITY = {
    1: True,
    2: True,
    3: True,
}


def _normalize_visibility(data: dict | None) -> dict[int, bool]:
    if not isinstance(data, dict):
        return DEFAULT_VISIBILITY.copy()
    normalized: dict[int, bool] = {}
    for key in (1, 2, 3):
        raw = data.get(key) if key in data else data.get(str(key))
        normalized[key] = bool(raw) if raw is not None else DEFAULT_VISIBILITY[key]
    return normalized


def _visibility_path() -> str:
    instance_path = current_app.instance_path
    return os.path.join(instance_path, "pack_visibility.json")


def load_pack_visibility() -> dict[int, bool]:
    try:
        path = _visibility_path()
        if not os.path.exists(path):
            return DEFAULT_VISIBILITY.copy()
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return _normalize_visibility(data)
    except Exception:
        return DEFAULT_VISIBILITY.copy()


def save_pack_visibility(visibility: dict[int, bool]) -> None:
    path = _visibility_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {"1": bool(visibility.get(1, True)), "2": bool(visibility.get(2, True)), "3": bool(visibility.get(3, True))}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def is_pack_active(visibility: dict[int, bool], pack_id: int) -> bool:
    return bool(visibility.get(pack_id, True))


def filter_pack_tiers(tiers: Iterable[dict], visibility: dict[int, bool]) -> list[dict]:
    return [tier for tier in tiers if is_pack_active(visibility, int(tier.get("pack")))]


def visible_starting_price(tiers: Iterable[dict], visibility: dict[int, bool]) -> float | None:
    lowest = None
    for tier in filter_pack_tiers(tiers, visibility):
        price = tier.get("price")
        try:
            normalized = float(price) if price is not None else None
        except (TypeError, ValueError):
            normalized = None
        if normalized is None or normalized <= 0:
            continue
        if lowest is None or normalized < lowest:
            lowest = normalized
    return lowest
