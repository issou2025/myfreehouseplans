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


def _safe_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    v = str(value).strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return default


def _clean_url(value: Any, *, max_len: int = 2000) -> Optional[str]:
    url = _clean_str(value, max_len=max_len)
    if not url:
        return None
    # Do not over-validate. Just ensure it is not a javascript: style URL.
    if url.lower().startswith("javascript:"):
        return None
    return url


def _normalize_recommendations(value: Any) -> List[Dict[str, Any]]:
    """Normalize a recommendations payload into a safe list.

    Each item is a dict with:
      - type: product|tool|service|resource
      - title: neutral display title
      - url: affiliate/external url
      - justification: short relevance text
      - position: end|dedicated
      - active: bool
    """

    if not value:
        return []

    items: List[Dict[str, Any]] = []
    if isinstance(value, list):
        raw_list = value
    else:
        return []

    for raw in raw_list[:10]:
        if not isinstance(raw, dict):
            continue

        rec_type = _clean_choice(raw.get("type"), ("product", "tool", "service", "resource"), "resource")
        title = _clean_str(raw.get("title"), max_len=140)
        url = _clean_url(raw.get("url"), max_len=2000)
        justification = _clean_str(raw.get("justification"), max_len=280)
        position = _clean_choice(raw.get("position"), ("end", "dedicated"), "end")
        active = _safe_bool(raw.get("active"), True)

        # URL is the minimum to render.
        if not url:
            continue

        item: Dict[str, Any] = {
            "type": rec_type,
            "url": url,
            "position": position,
            "active": bool(active),
        }
        if title:
            item["title"] = title
        if justification:
            item["justification"] = justification
        items.append(item)

    return items


def _normalize_media(value: Any) -> Dict[str, Any]:
    """Normalize media payload into a safe dict.

    Expected shape:
      {
        featured: { url, alt, caption }
        gallery: [ { url, alt, caption }, ... ]
      }
    """

    if not isinstance(value, dict):
        return {}

    out: Dict[str, Any] = {}

    featured_raw = value.get("featured")
    if isinstance(featured_raw, dict):
        url = _clean_url(featured_raw.get("url"))
        if url:
            featured: Dict[str, Any] = {"url": url}
            alt = _clean_str(featured_raw.get("alt"), max_len=220)
            caption = _clean_str(featured_raw.get("caption"), max_len=240)
            if alt:
                featured["alt"] = alt
            if caption:
                featured["caption"] = caption
            out["featured"] = featured

    gallery_out: List[Dict[str, Any]] = []
    gallery_raw = value.get("gallery")
    if isinstance(gallery_raw, list):
        for item in gallery_raw[:20]:
            if not isinstance(item, dict):
                continue
            url = _clean_url(item.get("url"))
            if not url:
                continue
            g: Dict[str, Any] = {"url": url}
            alt = _clean_str(item.get("alt"), max_len=220)
            caption = _clean_str(item.get("caption"), max_len=240)
            if alt:
                g["alt"] = alt
            if caption:
                g["caption"] = caption
            gallery_out.append(g)
    if gallery_out:
        out["gallery"] = gallery_out

    return out


def _normalize_tool_links(value: Any) -> List[Dict[str, Any]]:
    if not value:
        return []
    if not isinstance(value, list):
        return []

    items: List[Dict[str, Any]] = []
    for raw in value[:10]:
        if not isinstance(raw, dict):
            continue
        tool_key = _clean_str(raw.get("tool_key"), max_len=120)
        title = _clean_str(raw.get("title"), max_len=160)
        body = _clean_str(raw.get("body"), max_len=800)
        cta = _clean_str(raw.get("cta_label"), max_len=60)
        if not tool_key:
            continue
        payload = {"tool_key": tool_key}
        if title:
            payload["title"] = title
        if body:
            payload["body"] = body
        if cta:
            payload["cta_label"] = cta
        items.append(payload)
    return items


def normalize_article_extras(extras: Any) -> Dict[str, Any]:
    """Return a defensive, backward-compatible extras dict.

    - Preserves existing keys.
    - Adds normalized keys: intent, notes, recommendations, media.
    - Converts legacy affiliate/images into recommendations/media.
    """

    if not isinstance(extras, dict):
        return {}

    normalized: Dict[str, Any] = dict(extras)

    # intent + notes
    try:
        intent = _clean_choice(extras.get("intent"), ("guide", "howto", "inspiration", "review", "news", "other"), "other")
        if extras.get("intent") is not None:
            normalized["intent"] = intent
    except Exception:
        pass

    # optional experience link (article -> Space Planner)
    try:
        experience_key = _clean_str(extras.get("experience_key"), max_len=120)
        if experience_key:
            normalized["experience_key"] = experience_key
    except Exception:
        pass

    try:
        notes = _clean_str(extras.get("notes"), max_len=5000)
        if notes:
            normalized["notes"] = notes
    except Exception:
        pass

    # recommendations
    try:
        recs = _normalize_recommendations(extras.get("recommendations"))
    except Exception:
        recs = []

    # Legacy single affiliate -> one recommendation
    if not recs:
        try:
            aff = extras.get("affiliate")
            if isinstance(aff, dict):
                url = _clean_url(aff.get("affiliate_url"))
                if url:
                    rec = {
                        "type": "product",
                        "url": url,
                        "active": True,
                        "position": _clean_choice(aff.get("display_position"), ("before", "after"), "after"),
                    }
                    title = _clean_str(aff.get("product_title"), max_len=140)
                    justification = _clean_str(aff.get("short_description"), max_len=280)
                    if title:
                        rec["title"] = title
                    if justification:
                        rec["justification"] = justification
                    # Map legacy before/after to end/dedicated-ish behavior.
                    if rec["position"] == "before":
                        rec["position"] = "dedicated"
                    else:
                        rec["position"] = "end"
                    recs = [rec]
        except Exception:
            pass

    if recs:
        normalized["recommendations"] = recs

    # media
    try:
        media = _normalize_media(extras.get("media"))
    except Exception:
        media = {}

    # Legacy images -> media
    if not media:
        try:
            images = extras.get("images")
            if isinstance(images, dict):
                featured_url = _clean_url(images.get("featured"))
                gallery = images.get("gallery") if isinstance(images.get("gallery"), list) else []
                media_out: Dict[str, Any] = {}
                if featured_url:
                    media_out["featured"] = {"url": featured_url}
                gallery_items = []
                for src in gallery[:20]:
                    url = _clean_url(src)
                    if url:
                        gallery_items.append({"url": url})
                if gallery_items:
                    media_out["gallery"] = gallery_items
                media = media_out
        except Exception:
            pass

    if media:
        normalized["media"] = media

    # tool links
    try:
        tool_links = _normalize_tool_links(extras.get("tool_links"))
        if tool_links:
            normalized["tool_links"] = tool_links
    except Exception:
        pass

    return normalized


def extract_article_extras_from_form(form: Any) -> Dict[str, Any]:
    """Extract extras from request.form safely.

    Feature isolation rule: parsing failures in one feature must not break others.
    """

    extras: Dict[str, Any] = {}

    full_mode = False
    try:
        full_mode = str(form.get("extras__present") or "").strip() == "1"
    except Exception:
        full_mode = False

    if full_mode:
        extras["version"] = 2

    # Editorial intent + internal notes (non-public)
    try:
        intent = _clean_choice(
            form.get("extras__intent"),
            allowed=("guide", "howto", "inspiration", "review", "news", "other"),
            default="other",
        )
        if full_mode or form.get("extras__intent"):
            extras["intent"] = intent
    except Exception:
        try:
            current_app.logger.exception("Failed to parse intent extras")
        except Exception:
            pass

    # Optional experience link (article -> Space Planner)
    try:
        experience_key = _clean_str(form.get("extras__experience_key"), max_len=120)
        if full_mode:
            extras["experience_key"] = experience_key or ""
        elif experience_key:
            extras["experience_key"] = experience_key
    except Exception:
        try:
            current_app.logger.exception("Failed to parse experience link extras")
        except Exception:
            pass

    try:
        notes = _clean_str(form.get("extras__notes"), max_len=5000)
        if full_mode:
            extras["notes"] = notes or ""
        elif notes:
            extras["notes"] = notes
    except Exception:
        try:
            current_app.logger.exception("Failed to parse notes extras")
        except Exception:
            pass

    # Recommendations (preferred) OR legacy single affiliate
    try:
        recs_json = _clean_str(form.get("extras__recs_json"), max_len=40000)
        recs = []
        if recs_json:
            parsed = json.loads(recs_json)
            recs = _normalize_recommendations(parsed)
        else:
            recs = []

        if full_mode:
            extras["recommendations"] = recs
        elif recs:
            extras["recommendations"] = recs

        # Backward-compat: keep accepting legacy affiliate fields if present.
        affiliate = {
            "product_title": _clean_str(form.get("extras__affiliate_product_title"), max_len=200),
            "affiliate_url": _clean_url(form.get("extras__affiliate_url"), max_len=2000),
            "short_description": _clean_str(form.get("extras__affiliate_short_description"), max_len=800),
            "button_text": _clean_str(form.get("extras__affiliate_button_text"), max_len=60),
            "display_position": _clean_choice(
                form.get("extras__affiliate_position"),
                allowed=("before", "after"),
                default="after",
            ),
        }
        affiliate = {k: v for k, v in affiliate.items() if v is not None}
        if affiliate and "recommendations" not in extras:
            extras["affiliate"] = affiliate
    except Exception:
        try:
            current_app.logger.exception("Failed to parse recommendations/affiliate extras")
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

        if full_mode:
            extras["faq"] = faq_items
        elif faq_items:
            extras["faq"] = faq_items
    except Exception:
        try:
            current_app.logger.exception("Failed to parse FAQ extras")
        except Exception:
            pass

    # Media (preferred) OR legacy images
    try:
        media_json = _clean_str(form.get("extras__media_json"), max_len=60000)
        media: Dict[str, Any] = {}
        if media_json:
            parsed = json.loads(media_json)
            media = _normalize_media(parsed)

        if full_mode:
            extras["media"] = media
        elif media:
            extras["media"] = media

        # Backward-compat: accept legacy image fields if present.
        featured = _clean_url(form.get("extras__featured_image"), max_len=2000)
        gallery_lines = _split_lines(form.get("extras__gallery_images"), limit=30)
        images: Dict[str, Any] = {}
        if featured:
            images["featured"] = featured
        if gallery_lines:
            images["gallery"] = gallery_lines
        if images and "media" not in extras:
            extras["images"] = images
    except Exception:
        try:
            current_app.logger.exception("Failed to parse media extras")
        except Exception:
            pass

    # Tool links (up to 3)
    try:
        tool_links: List[Dict[str, Any]] = []
        for idx in range(1, 4):
            tool_key = _clean_str(form.get(f"extras__tool_key_{idx}"), max_len=120)
            title = _clean_str(form.get(f"extras__tool_title_{idx}"), max_len=160)
            body = _clean_str(form.get(f"extras__tool_body_{idx}"), max_len=800)
            cta = _clean_str(form.get(f"extras__tool_cta_{idx}"), max_len=60)
            if not tool_key:
                continue
            payload = {"tool_key": tool_key}
            if title:
                payload["title"] = title
            if body:
                payload["body"] = body
            if cta:
                payload["cta_label"] = cta
            tool_links.append(payload)

        if full_mode:
            extras["tool_links"] = tool_links
        elif tool_links:
            extras["tool_links"] = tool_links
    except Exception:
        try:
            current_app.logger.exception("Failed to parse tool link extras")
        except Exception:
            pass

    # SEO (non-DB overrides)
    try:
        seo = {
            "meta_title": _clean_str(form.get("extras__seo_meta_title"), max_len=200),
            "meta_description": _clean_str(form.get("extras__seo_meta_description"), max_len=400),
            "canonical_url": _clean_url(form.get("extras__seo_canonical_url"), max_len=2000),
            "robots": _clean_str(form.get("extras__seo_robots"), max_len=80),
            "og_image": _clean_url(form.get("extras__seo_og_image"), max_len=2000),
        }
        seo = {k: v for k, v in seo.items() if v is not None}
        if full_mode:
            extras["seo"] = seo
        elif seo:
            extras["seo"] = seo
    except Exception:
        try:
            current_app.logger.exception("Failed to parse SEO extras")
        except Exception:
            pass

    return extras
