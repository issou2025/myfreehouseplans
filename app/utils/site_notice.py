from __future__ import annotations

import json
import os
from datetime import datetime

from flask import current_app

DEFAULT_NOTICE = {
    "enabled": True,
    "message": (
        "Pack 2 and Pack 3 links are currently in experimental release. "
        "The full files will be available soon. In the meantime, only the free files are available."
    ),
}


def _notice_path() -> str:
    instance_path = current_app.instance_path
    return os.path.join(instance_path, "site_notice.json")


def load_site_notice() -> dict:
    try:
        path = _notice_path()
        if not os.path.exists(path):
            return DEFAULT_NOTICE.copy()
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            return DEFAULT_NOTICE.copy()
        return {
            "enabled": bool(data.get("enabled", DEFAULT_NOTICE["enabled"])),
            "message": (data.get("message") or DEFAULT_NOTICE["message"]).strip(),
        }
    except Exception:
        return DEFAULT_NOTICE.copy()


def save_site_notice(enabled: bool, message: str) -> None:
    path = _notice_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "enabled": bool(enabled),
        "message": (message or "").strip(),
        "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
