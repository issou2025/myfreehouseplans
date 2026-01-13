"""Repro / smoke test for plan detail rendering.

Creates a minimal published plan (no images) and requests /plan/<slug>.

Usage (PowerShell):
  $env:FLASK_APP='wsgi:app'
  $env:DATABASE_URL='sqlite:///myfreehouseplan.db'
  python scripts/repro_plan_detail.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import create_app
from app.extensions import db
from app.models import Category, HousePlan


def main() -> None:
    app = create_app()

    with app.app_context():
        category = Category.query.filter_by(slug="test-category").first()
        if not category:
            category = Category(name="Test Category", slug="test-category")
            db.session.add(category)
            db.session.commit()

        plan = HousePlan(
            title="Admin Created Plan Smoke Test",
            description="Smoke test description.",
            short_description="Smoke test short description.",
            price=0,
            price_pack_1=0,
            is_published=True,
        )
        plan.categories = [category]

        db.session.add(plan)
        db.session.commit()

        path = f"/plan/{plan.slug}"
        client = app.test_client()
        resp = client.get(path)
        print(f"GET {path} -> {resp.status_code}")
        if resp.status_code >= 400:
            print(resp.data[:4000].decode('utf-8', errors='replace'))


if __name__ == "__main__":
    main()
