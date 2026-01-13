from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from flask import current_app, url_for
from markupsafe import Markup, escape

from app.utils.media import is_absolute_url, upload_url


@dataclass(frozen=True)
class ResponsivePreset:
    widths: tuple[int, ...]
    sizes: str


CARD_PRESET = ResponsivePreset(
    widths=(320, 480, 640, 960),
    sizes="(max-width: 640px) 92vw, (max-width: 1024px) 46vw, 320px",
)

HERO_PRESET = ResponsivePreset(
    widths=(640, 960, 1280, 1600, 1920),
    sizes="(max-width: 1024px) 100vw, 52vw",
)


def _variant_relpath(original_rel: str, variant: str, width: int, fmt: str) -> str:
    p = Path(original_rel)
    parent = p.parent
    stem = p.stem
    filename = f"{stem}__{variant}__w{width}.{fmt}"
    return str(Path("uploads") / "variants" / parent.name / filename).replace('\\', '/')


def _srcset(original_rel: str, variant: str, widths: Iterable[int], fmt: str) -> str:
    parts: list[str] = []
    for w in widths:
        rel = _variant_relpath(original_rel, variant=variant, width=w, fmt=fmt)
        parts.append(f"{url_for('static', filename=rel)} {w}w")
    return ", ".join(parts)


def picture_tag(
    value: str | None,
    *,
    alt: str = "",
    preset: ResponsivePreset = CARD_PRESET,
    variant: str = "base",
    orientation_swap: bool = False,
    loading: str = "lazy",
    css_class: str | None = None,
    itemprop: str | None = None,
    decoding: str = "async",
) -> Markup:
    """Return a <picture> tag with AVIF/WebP sources and an <img> fallback.

    - If value is an absolute URL, returns a plain <img>.
    - For local uploads, references generated variants under static/uploads/variants/...

    `orientation_swap=True` emits separate portrait/landscape sources using
    (orientation: ...) media queries and expects corresponding crops.
    """

    if not value:
        return Markup("")

    if is_absolute_url(value):
        attrs = []
        if css_class:
            attrs.append(f"class=\"{escape(css_class)}\"")
        if itemprop:
            attrs.append(f"itemprop=\"{escape(itemprop)}\"")
        attrs.append(f"src=\"{escape(value)}\"")
        attrs.append(f"alt=\"{escape(alt)}\"")
        attrs.append(f"loading=\"{escape(loading)}\"")
        attrs.append(f"decoding=\"{escape(decoding)}\"")
        return Markup(f"<img {' '.join(attrs)}>")

    original_rel = value
    fallback_src = upload_url(original_rel) or ""

    # If responsive variants have not been generated yet, do not emit <source>
    # tags or srcset pointing at missing files. Some browsers will select a
    # missing srcset candidate and render a broken image even though the
    # original upload exists. For admin uploads this is common (new files).
    variants_available = False
    try:
        static_folder = current_app.static_folder
        if static_folder:
            static_root = Path(static_folder).resolve()
            probe = _variant_relpath(original_rel, variant=variant, width=preset.widths[0], fmt="webp")
            variants_available = (static_root / probe).exists()
    except Exception:
        variants_available = False

    if not variants_available:
        attrs = []
        if css_class:
            attrs.append(f"class=\"{escape(css_class)}\"")
        if itemprop:
            attrs.append(f"itemprop=\"{escape(itemprop)}\"")
        attrs.append(f"src=\"{escape(fallback_src)}\"")
        attrs.append(f"alt=\"{escape(alt)}\"")
        attrs.append(f"loading=\"{escape(loading)}\"")
        attrs.append(f"decoding=\"{escape(decoding)}\"")
        return Markup(f"<img {' '.join(attrs)}>")

    img_attrs = []
    if css_class:
        img_attrs.append(f"class=\"{escape(css_class)}\"")
    if itemprop:
        img_attrs.append(f"itemprop=\"{escape(itemprop)}\"")
    img_attrs.extend(
        [
            f"src=\"{escape(fallback_src)}\"",
            f"alt=\"{escape(alt)}\"",
            f"loading=\"{escape(loading)}\"",
            f"decoding=\"{escape(decoding)}\"",
            f"sizes=\"{escape(preset.sizes)}\"",
        ]
    )

    if not orientation_swap:
        avif_srcset = _srcset(original_rel, variant=variant, widths=preset.widths, fmt="avif")
        webp_srcset = _srcset(original_rel, variant=variant, widths=preset.widths, fmt="webp")
        # Provide a fallback srcset for the <img> using WebP (even if missing, harmless).
        img_srcset = webp_srcset

        html = (
            "<picture>"
            f"<source type=\"image/avif\" srcset=\"{escape(avif_srcset)}\" sizes=\"{escape(preset.sizes)}\">"
            f"<source type=\"image/webp\" srcset=\"{escape(webp_srcset)}\" sizes=\"{escape(preset.sizes)}\">"
            f"<img {' '.join(img_attrs)} srcset=\"{escape(img_srcset)}\">"
            "</picture>"
        )
        return Markup(html)

    # Orientation-aware swap
    avif_land = _srcset(original_rel, variant="landscape", widths=preset.widths, fmt="avif")
    webp_land = _srcset(original_rel, variant="landscape", widths=preset.widths, fmt="webp")
    avif_port = _srcset(original_rel, variant="portrait", widths=preset.widths, fmt="avif")
    webp_port = _srcset(original_rel, variant="portrait", widths=preset.widths, fmt="webp")

    html = (
        "<picture>"
        f"<source media=\"(orientation: landscape)\" type=\"image/avif\" srcset=\"{escape(avif_land)}\" sizes=\"{escape(preset.sizes)}\">"
        f"<source media=\"(orientation: landscape)\" type=\"image/webp\" srcset=\"{escape(webp_land)}\" sizes=\"{escape(preset.sizes)}\">"
        f"<source media=\"(orientation: portrait)\" type=\"image/avif\" srcset=\"{escape(avif_port)}\" sizes=\"{escape(preset.sizes)}\">"
        f"<source media=\"(orientation: portrait)\" type=\"image/webp\" srcset=\"{escape(webp_port)}\" sizes=\"{escape(preset.sizes)}\">"
        f"<img {' '.join(img_attrs)} srcset=\"{escape(webp_port)}\">"
        "</picture>"
    )
    return Markup(html)
