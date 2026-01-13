from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image

# pillow-avif-plugin registers the AVIF encoder/decoder at import time.
try:
    import pillow_avif  # noqa: F401
    AVIF_AVAILABLE = True
except Exception:
    AVIF_AVAILABLE = False


@dataclass(frozen=True)
class VariantSpec:
    name: str
    aspect: float | None  # width / height


SPECS = (
    VariantSpec("base", None),
    VariantSpec("portrait", 4 / 5),
    VariantSpec("landscape", 16 / 9),
)

DEFAULT_WIDTHS = (320, 480, 640, 960, 1280, 1600, 1920)


def _center_crop_to_aspect(img: Image.Image, aspect: float) -> Image.Image:
    w, h = img.size
    current = w / h
    if abs(current - aspect) < 1e-3:
        return img

    if current > aspect:
        # too wide
        new_w = int(h * aspect)
        left = (w - new_w) // 2
        box = (left, 0, left + new_w, h)
    else:
        # too tall
        new_h = int(w / aspect)
        top = (h - new_h) // 2
        box = (0, top, w, top + new_h)

    return img.crop(box)


def _save_variant(img: Image.Image, out_path: Path, fmt: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    save_kwargs = {}
    if fmt == "webp":
        save_kwargs.update({"quality": 82, "method": 6})
    elif fmt == "avif":
        # pillow-avif-plugin supports these; if not installed, save will raise.
        save_kwargs.update({"quality": 45})

    img.save(out_path, format=fmt.upper(), **save_kwargs)


def _iter_images(root: Path) -> Iterable[Path]:
    for ext in (".jpg", ".jpeg", ".png"):
        yield from root.rglob(f"*{ext}")


def generate(
    *,
    uploads_root: Path,
    variants_root: Path,
    widths: tuple[int, ...],
    generate_avif: bool,
    generate_webp: bool,
) -> None:
    if not uploads_root.exists():
        raise SystemExit(f"No uploads directory found at: {uploads_root}")

    if generate_avif and not AVIF_AVAILABLE:
        print("[warn] AVIF requested but pillow-avif-plugin is unavailable; skipping AVIF outputs.")
        generate_avif = False

    for src in _iter_images(uploads_root):
        # Never generate variants-of-variants.
        try:
            rel_from_uploads = src.relative_to(uploads_root)
        except Exception:
            continue
        if rel_from_uploads.parts and rel_from_uploads.parts[0] == "variants":
            continue

        rel = src.relative_to(uploads_root)
        stem = src.stem
        parent = rel.parent

        try:
            with Image.open(src) as im:
                im = im.convert("RGB")
                for spec in SPECS:
                    base_img = im
                    if spec.aspect:
                        base_img = _center_crop_to_aspect(base_img, spec.aspect)

                    for w in widths:
                        if base_img.width <= w:
                            resized = base_img
                        else:
                            ratio = w / base_img.width
                            resized = base_img.resize((w, int(base_img.height * ratio)), Image.Resampling.LANCZOS)

                        if generate_webp:
                            out_rel = Path("variants") / parent / f"{stem}__{spec.name}__w{w}.webp"
                            _save_variant(resized, variants_root / out_rel.relative_to("variants"), "webp")

                        if generate_avif:
                            out_rel = Path("variants") / parent / f"{stem}__{spec.name}__w{w}.avif"
                            _save_variant(resized, variants_root / out_rel.relative_to("variants"), "avif")
        except Exception as exc:
            print(f"[warn] failed {src}: {exc}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate responsive image variants (WebP/AVIF + crops).")
    parser.add_argument(
        "--uploads-root",
        default=str(Path(__file__).resolve().parents[1] / "app" / "static" / "uploads"),
        help="Path to app/static/uploads",
    )
    parser.add_argument(
        "--widths",
        default=",".join(str(w) for w in DEFAULT_WIDTHS),
        help="Comma-separated widths to generate",
    )
    parser.add_argument("--no-webp", action="store_true", help="Disable WebP generation")
    parser.add_argument("--no-avif", action="store_true", help="Disable AVIF generation")

    args = parser.parse_args()

    uploads_root = Path(args.uploads_root).resolve()
    variants_root = uploads_root / "variants"

    widths = tuple(int(x) for x in str(args.widths).split(",") if x.strip())

    generate(
        uploads_root=uploads_root,
        variants_root=variants_root,
        widths=widths,
        generate_avif=not args.no_avif,
        generate_webp=not args.no_webp,
    )


if __name__ == "__main__":
    # Pillow can be noisy about decompression bomb warnings in dev; keep defaults.
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    main()
