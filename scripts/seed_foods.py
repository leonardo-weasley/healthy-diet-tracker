"""Idempotent import of the nutrition JSON into the ``food`` table.

Running it twice must not duplicate rows: an existing ``food_name`` is
skipped.  The JSON is owned by member 3; only the field names are contract.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from app.database.models import Food  # noqa: E402
from app.extensions import db  # noqa: E402

DATA_PATH = ROOT / "app" / "nutrition" / "food_database.json"


def load_payload(path: Path | None = None) -> dict:
    source = Path(path) if path is not None else DATA_PATH
    return json.loads(source.read_text(encoding="utf-8"))


def _alias_text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, Iterable):
        return ",".join(str(item).strip() for item in value if str(item).strip())
    return str(value)


def seed_foods(payload: dict | None = None) -> int:
    """Insert foods that do not exist yet; return the number inserted.

    Must be called inside an application context.
    """
    data = payload if payload is not None else load_payload()
    rows = data.get("foods") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError("food_database.json must contain a 'foods' list")

    inserted = 0
    for row in rows:
        if not isinstance(row, dict) or not row.get("food_name"):
            raise ValueError(f"invalid food row: {row!r}")
        if Food.query.filter_by(food_name=row["food_name"]).first():
            continue
        db.session.add(
            Food(
                food_name=row["food_name"],
                display_name=row["display_name"],
                calories_per_100g=float(row["calories_per_100g"]),
                protein_per_100g=float(row["protein_per_100g"]),
                carbs_per_100g=float(row["carbs_per_100g"]),
                fat_per_100g=float(row["fat_per_100g"]),
                source=row.get("source", "local"),
                aliases=_alias_text(row.get("aliases")),
                is_verified=int(row.get("is_verified", 0)),
            )
        )
        inserted += 1
    db.session.commit()
    return inserted


def main() -> int:
    app = create_app()
    with app.app_context():
        inserted = seed_foods()
        total = Food.query.count()
    print(f"inserted {inserted} foods (total {total})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
