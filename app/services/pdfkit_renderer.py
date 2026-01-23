from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

from flask import current_app


class PdfEngineUnavailable(RuntimeError):
    """Raised when wkhtmltopdf/pdfkit is not installed or misconfigured."""


@dataclass(frozen=True)
class PdfkitRenderOptions:
    page_size: str = "A4"
    encoding: str = "UTF-8"
    enable_local_file_access: bool = True


def _resolve_wkhtmltopdf_path() -> Optional[str]:
    """Resolve wkhtmltopdf binary path.

    Priority:
    1) Flask config WKHTMLTOPDF_PATH
    2) Env var WKHTMLTOPDF_PATH
    3) PATH lookup via shutil.which
    """

    cfg_path = (current_app.config.get("WKHTMLTOPDF_PATH") or "").strip()
    env_path = (os.environ.get("WKHTMLTOPDF_PATH") or "").strip()

    for candidate in (cfg_path, env_path):
        if not candidate:
            continue
        try:
            p = Path(candidate)
            if p.exists() and p.is_file():
                return str(p)
        except Exception:
            continue

    return shutil.which("wkhtmltopdf")


def render_pdf_from_html(
    *,
    html: str,
    css_paths: Iterable[Path] = (),
    filename: str = "report.pdf",
    options: PdfkitRenderOptions | None = None,
) -> bytes:
    """Render HTML string to PDF bytes using wkhtmltopdf + pdfkit.

    Raises:
        PdfEngineUnavailable: if pdfkit or wkhtmltopdf is not available.
        RuntimeError: for other conversion failures.
    """

    try:
        import pdfkit  # type: ignore
    except Exception as exc:
        raise PdfEngineUnavailable(
            "pdfkit is not installed. Add `pdfkit` to requirements and deploy."
        ) from exc

    wkhtmltopdf_path = _resolve_wkhtmltopdf_path()
    if not wkhtmltopdf_path:
        raise PdfEngineUnavailable(
            "wkhtmltopdf is not installed or not on PATH. "
            "Install wkhtmltopdf and/or set WKHTMLTOPDF_PATH."
        )

    render_opts = options or PdfkitRenderOptions()

    pdfkit_options: dict[str, str] = {
        "page-size": render_opts.page_size,
        "encoding": render_opts.encoding,
        "print-media-type": "",
        "quiet": "",
        # Reasonable defaults for reports.
        "margin-top": "10mm",
        "margin-right": "10mm",
        "margin-bottom": "10mm",
        "margin-left": "10mm",
    }

    if render_opts.enable_local_file_access:
        pdfkit_options["enable-local-file-access"] = ""

    css_files = [str(Path(p).resolve()) for p in (css_paths or []) if p]

    try:
        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
        # output_path=False => return bytes
        pdf_bytes = pdfkit.from_string(
            html,
            False,
            options=pdfkit_options,
            css=css_files or None,
            configuration=config,
        )
    except OSError as exc:
        # Typical when wkhtmltopdf cannot start.
        raise PdfEngineUnavailable(
            f"wkhtmltopdf failed to start. Resolved path: {wkhtmltopdf_path}"
        ) from exc
    except Exception as exc:
        raise RuntimeError(f"HTML-to-PDF rendering failed for {filename}.") from exc

    if not pdf_bytes:
        raise RuntimeError("wkhtmltopdf returned empty PDF output.")

    return pdf_bytes
