"""Filesystem-backed per-article extras.

Design goals:
- Zero database changes
- Progressive enhancement (missing extras => no UI/render changes)
- Defensive: malformed/missing JSON never breaks admin or frontend
- Feature isolation: each feature parses independently

Storage location:
- <instance_path>/article_extras/<key>.json

Where <key> is based on article slug when available, otherwise a stable
fallback based on the post id.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from flask import current_app


_SAFE_KEY_RE = re.compile(r"[^a-z0-9\-]+")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _extras_root() -> Path:
    root = Path(current_app.instance_path).resolve() / "article_extras"
    try:
        root.mkdir(parents=True, exist_ok=True)
    except Exception:
        # If we cannot create the directory, we still must not crash.
        pass
    return root


def _safe_key(slug: Optional[str], post_id: Optional[int]) -> str:
    slug_value = (slug or "").strip().lower()
    slug_value = slug_value.replace("_", "-")
    slug_value = _SAFE_KEY_RE.sub("-", slug_value).strip("-")
    if slug_value:
        return slug_value
    if post_id is not None:
        return f"post-{int(post_id)}"
    return "post-unknown"


def _path_for(slug: Optional[str] = None, post_id: Optional[int] = None) -> Path:
    key = _safe_key(slug, post_id)
    return _extras_root() / f"{key}.json"


def load_article_extras(*, slug: Optional[str] = None, post_id: Optional[int] = None) -> Dict[str, Any]:
    """Load extras for an article. Returns an empty dict on any failure."""

    path = _path_for(slug, post_id)
    try:
        if not path.exists():
            return {}
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
    except Exception:
        try:
            current_app.logger.exception("Failed to load article extras: %s", str(path))
        except Exception:
            pass
    return {}


def save_article_extras(
    extras: Dict[str, Any],
    *,
    slug: Optional[str] = None,
    post_id: Optional[int] = None,
) -> None:
    """Persist extras atomically. Never raises."""

    try:
        if not isinstance(extras, dict):
            return

        payload = dict(extras)
        payload.setdefault("updated_at", _utc_iso())

        path = _path_for(slug, post_id)
        tmp_path = path.with_suffix(path.suffix + ".tmp")

        # Ensure directory exists (best effort)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        tmp_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(str(tmp_path), str(path))
    except Exception:
        try:
            current_app.logger.exception("Failed to save article extras")
        except Exception:
            pass


def _clean_str(value: Any, *, max_len: int = 5000) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if len(text) > max_len:
        text = text[:max_len]
    return text


def _clean_choice(value: Any, allowed: Iterable[str], default: str) -> str:
    v = (str(value).strip() if value is not None else "")
    return v if v in set(allowed) else default


def _split_lines(value: Any, *, limit: int = 50) -> List[str]:
    if value is None:
        return []
    raw = str(value)
    items: List[str] = []
    for line in raw.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        items.append(candidate)
        if len(items) >= limit:
            break
    return items


def extract_article_extras_from_form(form: Any) -> Dict[str, Any]:
    """Extract extras from request.form safely.

    Feature isolation rule: parsing failures in one feature must not break others.
    """

    extras: Dict[str, Any] = {}

    # Affiliate
    try:
        affiliate = {
            "product_title": _clean_str(form.get("extras__affiliate_product_title"), max_len=200),
            "affiliate_url": _clean_str(form.get("extras__affiliate_url"), max_len=2000),
            "short_description": _clean_str(form.get("extras__affiliate_short_description"), max_len=800),
            "button_text": _clean_str(form.get("extras__affiliate_button_text"), max_len=60),
            "display_position": _clean_choice(
                form.get("extras__affiliate_position"),
                allowed=("before", "after"),
                default="after",
            ),
        }
        affiliate = {k: v for k, v in affiliate.items() if v is not None}
        if affiliate:
            extras["affiliate"] = affiliate
    except Exception:
        try:
            current_app.logger.exception("Failed to parse affiliate extras")
        except Exception:
            pass

    # FAQ (from JSON hidden field if available; else from repeated inputs)
    try:
        faq_items: List[Dict[str, str]] = []
        faq_json = _clean_str(form.get("extras__faq_json"), max_len=20000)
        if faq_json:
            parsed = json.loads(faq_json)
            if isinstance(parsed, list):
                for item in parsed[:50]:
                    if not isinstance(item, dict):
                        continue
                    q = _clean_str(item.get("question"), max_len=300)
                    a = _clean_str(item.get("answer"), max_len=1500)
                    if q and a:
                        faq_items.append({"question": q, "answer": a})
        else:
            # Inputs: extras__faq_q_1, extras__faq_a_1, etc.
            for idx in range(1, 51):
                q = _clean_str(form.get(f"extras__faq_q_{idx}"), max_len=300)
                a = _clean_str(form.get(f"extras__faq_a_{idx}"), max_len=1500)
                if q and a:
                    faq_items.append({"question": q, "answer": a})

        if faq_items:
            extras["faq"] = faq_items
    except Exception:
        try:
            current_app.logger.exception("Failed to parse FAQ extras")
        except Exception:
            pass

    # Images
    try:
        featured = _clean_str(form.get("extras__featured_image"), max_len=2000)
        gallery_lines = _split_lines(form.get("extras__gallery_images"), limit=30)

        images: Dict[str, Any] = {}
        if featured:
            images["featured"] = featured
        if gallery_lines:
            images["gallery"] = gallery_lines
        if images:
            extras["images"] = images
    except Exception:
        try:
            current_app.logger.exception("Failed to parse image extras")
        except Exception:
            pass

    # SEO (non-DB overrides)
    try:
        seo = {
            "meta_title": _clean_str(form.get("extras__seo_meta_title"), max_len=200),
            "meta_description": _clean_str(form.get("extras__seo_meta_description"), max_len=400),
            "canonical_url": _clean_str(form.get("extras__seo_canonical_url"), max_len=2000),
            "robots": _clean_str(form.get("extras__seo_robots"), max_len=80),
            "og_image": _clean_str(form.get("extras__seo_og_image"), max_len=2000),
        }
        seo = {k: v for k, v in seo.items() if v is not None}
        if seo:
            extras["seo"] = seo
    except Exception:
        try:
            current_app.logger.exception("Failed to parse SEO extras")
        except Exception:
            pass

    return extras
