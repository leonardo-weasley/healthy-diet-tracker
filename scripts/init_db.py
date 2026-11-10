"""Create all three tables.  Safe to run repeatedly (``create_all``)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402


def main() -> int:
    app = create_app()
    with app.app_context():
        db.create_all()
        tables = sorted(inspect(db.engine).get_table_names())
    print(f"tables created: {', '.join(tables)}")
    print(f"database: {app.config['SQLALCHEMY_DATABASE_URI']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
