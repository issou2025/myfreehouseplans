"""Reproduce Floor Plan Analyzer /results rendering via Flask test_client.

Usage:
  venv/Scripts/python.exe scripts/repro_fp_results.py

This script is intentionally short and exits non-zero on failure.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    # Ensure project root is importable when running from ./scripts
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    # Force a non-production config to avoid strict env checks.
    os.environ.setdefault("FLASK_CONFIG", "development")
    os.environ.setdefault("FLASK_ENV", "development")

    from wsgi import app  # noqa: WPS433

    app.testing = True

    with app.test_client() as client:
        # Step 0
        r = client.post(
            "/tools/floor-plan-analyzer/start",
            data={"unit_system": "metric"},
            follow_redirects=True,
        )
        assert r.status_code == 200, r.status_code

        # Step 1 (budget optional)
        r = client.post(
            "/tools/floor-plan-analyzer/budget",
            data={
                "budget": "",
                "mortgage_duration": "",
                "country": "International",
            },
            follow_redirects=True,
        )
        assert r.status_code == 200, r.status_code

        # Step 2: add 3 rooms
        for room_type, length, width in [
            ("Bedroom", "4", "3"),
            ("Living Room", "6", "4"),
            ("Bathroom", "2.5", "2"),
        ]:
            r = client.post(
                "/tools/floor-plan-analyzer/rooms",
                data={
                    "action": "add_room",
                    "room_type": room_type,
                    "length": length,
                    "width": width,
                },
                follow_redirects=True,
            )
            assert r.status_code == 200, r.status_code

        # Analyze
        r = client.post(
            "/tools/floor-plan-analyzer/rooms",
            data={"action": "analyze"},
            follow_redirects=False,
        )
        assert r.status_code in (301, 302), r.status_code
        location = r.headers.get("Location")
        if not location:
            raise RuntimeError("Expected redirect to results; no Location header")

        # Results
        r = client.get(location)
        print("GET", location, "->", r.status_code)
        if r.status_code != 200:
            print(r.data[:2000])
            return 2

    print("OK: /results rendered successfully")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        # Ensure full traceback in CI/terminal
        raise
