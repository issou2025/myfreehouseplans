from __future__ import annotations

import sys
import traceback
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from wsgi import app


def main() -> None:
    app.testing = True
    app.config["PROPAGATE_EXCEPTIONS"] = True

    client = app.test_client()

    try:
        resp = client.get("/")
        print("STATUS", resp.status_code)
        print(resp.data[:500])
    except Exception:
        traceback.print_exc()


if __name__ == "__main__":
    main()
