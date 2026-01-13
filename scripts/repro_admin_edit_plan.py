"""Repro / smoke test for the admin plan edit flow.

- Ensures admin exists (seed)
- Logs in via /admin/login
- Creates a plan + category
- Loads /admin/plans/edit/<id>
- Submits a POST update

Usage (PowerShell):
  $env:DATABASE_URL='sqlite:///myfreehouseplan.db'
  python scripts/repro_admin_edit_plan.py

Note: Disables CSRF for test client only.
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
    app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)

    with app.app_context():
        category = Category.query.filter_by(slug="test-category").first()
        if not category:
            category = Category(name="Test Category", slug="test-category")
            db.session.add(category)
            db.session.commit()

        plan = HousePlan(
            title="Edit Flow Test Plan",
            description="Initial description.",
            short_description="Initial short.",
            price=10,
            price_pack_1=0,
            is_published=True,
        )
        plan.categories = [category]
        db.session.add(plan)
        db.session.commit()
        plan_id = plan.id

    client = app.test_client()

    # Login (default seeded admin)
    login_resp = client.post(
        "/admin/login",
        data={"username": "admin", "password": "ton_mot_de_passe_secret"},
        follow_redirects=False,
    )
    print("POST /admin/login ->", login_resp.status_code, "Location:", login_resp.headers.get("Location"))

    get_resp = client.get(f"/admin/plans/edit/{plan_id}")
    print(f"GET /admin/plans/edit/{plan_id} ->", get_resp.status_code)

    # Minimal POST update (must include required fields)
    post_data = {
        "title": "Edit Flow Test Plan UPDATED",
        "description": "Updated description.",
        "short_description": "Updated short.",
        "plan_type": "family",
        "bedrooms": 3,
        "bathrooms": 2,
        "stories": 1,
        "garage": 1,
        "price": 10,
        "sale_price": "",
        "price_pack_1": 0,
        "price_pack_2": "",
        "price_pack_3": "",
        "gumroad_pack_2_url": "",
        "gumroad_pack_3_url": "",
        "seo_title": "",
        "seo_description": "",
        "seo_keywords": "",
        "is_featured": "y",
        "is_published": "y",
        "category_ids": [category.id],
    }

    post_resp = client.post(f"/admin/plans/edit/{plan_id}", data=post_data, follow_redirects=False)
    print(f"POST /admin/plans/edit/{plan_id} ->", post_resp.status_code, "Location:", post_resp.headers.get("Location"))


if __name__ == "__main__":
    main()
