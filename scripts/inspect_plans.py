"""Inspect recent HousePlan rows for missing/invalid fields.

Usage (PowerShell):
  $env:FLASK_APP='wsgi:app'
  $env:DATABASE_URL='sqlite:///myfreehouseplan.db'
  python scripts/inspect_plans.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure repository root is on sys.path when running as `python scripts/...`.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import create_app
from app.models import HousePlan


def main() -> None:
    app = create_app()
    limit = int(os.environ.get("LIMIT", "30"))

    with app.app_context():
        plans = HousePlan.query.order_by(HousePlan.id.desc()).limit(limit).all()
        print(f"Found {len(plans)} plans (limit={limit})")

        for plan in plans:
            issues: list[str] = []
            if not plan.slug:
                issues.append("slug")
            if not plan.reference_code:
                issues.append("reference_code")
            if not plan.title:
                issues.append("title")
            if not plan.description:
                issues.append("description")
            if plan.price is None:
                issues.append("price")
            if plan.price_pack_1 is None:
                issues.append("price_pack_1")

            # Fields that commonly trigger template/python errors if invalid
            if plan.bathrooms is not None:
                try:
                    float(plan.bathrooms)
                except Exception:
                    issues.append("bathrooms(non-numeric)")
            if plan.total_area_sqft is not None:
                try:
                    float(plan.total_area_sqft)
                except Exception:
                    issues.append("total_area_sqft(non-numeric)")
            if plan.total_area_m2 is not None:
                try:
                    float(plan.total_area_m2)
                except Exception:
                    issues.append("total_area_m2(non-numeric)")

            print(
                "id={id} published={pub} slug={slug!r} ref={ref!r} cover={cover} main={main} issues={issues}".format(
                    id=plan.id,
                    pub=plan.is_published,
                    slug=plan.slug,
                    ref=plan.reference_code,
                    cover=bool(plan.cover_image),
                    main=bool(plan.main_image),
                    issues=issues,
                )
            )


if __name__ == "__main__":
    main()
