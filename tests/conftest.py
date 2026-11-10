"""Shared pytest fixtures.

Every test gets a brand new in-memory SQLite database (``sqlite:///:memory:``),
so tests never share state and never touch ``instance/diet_tracker.db``.
The suite does not use the network, an API key, or a ``.env`` file.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
FOOD_DATA_PATH = ROOT / "app" / "nutrition" / "food_database.json"

from app import create_app  # noqa: E402
from app.database.models import Food  # noqa: E402
from app.extensions import db  # noqa: E402


@pytest.fixture
def app():
    """Flask app with an isolated in-memory database."""
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_ENGINE_OPTIONS": {
                "poolclass": StaticPool,
                "connect_args": {"check_same_thread": False},
            },
            "APP_TIMEZONE": "Asia/Shanghai",
        }
    )
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seeded_db(app):
    """Load the placeholder nutrition rows into the test database."""
    payload = json.loads(FOOD_DATA_PATH.read_text(encoding="utf-8"))
    for row in payload["foods"]:
        aliases = row.get("aliases") or []
        db.session.add(
            Food(
                food_name=row["food_name"],
                display_name=row["display_name"],
                calories_per_100g=row["calories_per_100g"],
                protein_per_100g=row["protein_per_100g"],
                carbs_per_100g=row["carbs_per_100g"],
                fat_per_100g=row["fat_per_100g"],
                source=row.get("source", "local"),
                aliases=",".join(aliases),
                is_verified=int(row.get("is_verified", 0)),
            )
        )
    db.session.commit()
    yield app


@pytest.fixture
def sample_meal_payload():
    """One 180 g rice meal, matching the example in contract §5.2."""
    return {
        "meal_type": "lunch",
        "meal_datetime_utc": "2026-11-01T04:30:00Z",
        "meal_date": "2026-11-01",
        "image_path": None,
        "items": [
            {
                "food_name": "cooked_white_rice",
                "display_name": "White rice",
                "weight_g": 180.0,
                "calories_kcal": 234.0,
                "protein_g": 4.86,
                "carbs_g": 50.76,
                "fat_g": 0.54,
                "food_data_source": "USDA",
            }
        ],
    }


@pytest.fixture
def make_meal_payload(sample_meal_payload):
    """Deep-copied meal payload factory so tests can tweak one field."""

    def _make(**overrides):
        payload = copy.deepcopy(sample_meal_payload)
        payload.update({key: copy.deepcopy(value) for key, value in overrides.items()})
        return payload

    return _make


@pytest.fixture
def mock_ai_result():
    return json.loads((FIXTURES_DIR / "mock_ai_result.json").read_text(encoding="utf-8"))


@pytest.fixture
def mock_ai_result_unknown():
    return json.loads(
        (FIXTURES_DIR / "mock_ai_result_unknown.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def sample_meal_image():
    return (FIXTURES_DIR / "sample_meal.png").read_bytes()
