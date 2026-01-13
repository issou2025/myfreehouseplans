from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wsgi import app
from app.extensions import db
from app.models import HousePlan


def main() -> None:
    app.testing = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["PROPAGATE_EXCEPTIONS"] = True

    with app.app_context():
        plan = HousePlan(
            title="No Category Smoke Test",
            description="This plan intentionally has no category relationship.",
            price=0,
            is_published=True,
        )
        db.session.add(plan)
        db.session.commit()

        slug = plan.slug

    client = app.test_client()
    resp = client.get(f"/plan/{slug}")
    print(f"GET /plan/{slug} -> {resp.status_code}")


if __name__ == "__main__":
    main()
