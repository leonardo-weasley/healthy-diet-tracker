"""D1-D9: database unit tests for the repository and seeding.

Each test runs against a fresh in-memory database (see ``conftest.py``).
"""

from __future__ import annotations

import copy

import pytest
from pytest import approx
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError

from app.database import repository
from app.database.models import Food, Meal, MealItem
from app.extensions import db
from app.utils.errors import DatabaseError, InvalidRequest

CHICKEN_ITEM = {
    "food_name": "grilled_chicken_breast",
    "display_name": "Grilled chicken breast",
    "weight_g": 150.0,
    "calories_kcal": 247.5,
    "protein_g": 46.5,
    "carbs_g": 0.0,
    "fat_g": 5.4,
    "food_data_source": "USDA",
}


def _count(model) -> int:
    return db.session.query(model).count()


def test_d1_save_meal_then_get_meal_round_trips(seeded_db, sample_meal_payload):
    meal_id = repository.save_meal(sample_meal_payload)

    assert isinstance(meal_id, int)
    meal = repository.get_meal(meal_id)
    assert meal is not None
    assert meal["meal_id"] == meal_id
    assert meal["meal_type"] == "lunch"
    assert meal["meal_datetime"] == "2026-11-01T12:30:00+08:00"
    assert meal["meal_date"] == "2026-11-01"
    assert len(meal["items"]) == 1

    item = meal["items"][0]
    assert item["food_name"] == "cooked_white_rice"
    assert item["display_name"] == "White rice"
    assert item["weight_g"] == approx(180.0)
    assert item["calories_kcal"] == approx(234.0)
    assert item["protein_g"] == approx(4.86)
    assert item["carbs_g"] == approx(50.76)
    assert item["fat_g"] == approx(0.54)
    assert meal["totals"]["calories_kcal"] == approx(234.0)
    assert meal["warnings"] == []


def test_d2_deleting_meal_cascades_at_database_level(seeded_db, sample_meal_payload):
    meal_id = repository.save_meal(sample_meal_payload)
    assert _count(MealItem) == 1

    # Prove the PRAGMA is really on: bypass the ORM cascade with a Core
    # DELETE, so only the database-level ON DELETE CASCADE can remove items.
    assert db.session.execute(text("PRAGMA foreign_keys")).scalar() == 1
    db.session.execute(delete(Meal).where(Meal.id == meal_id))
    db.session.commit()

    assert _count(Meal) == 0
    assert _count(MealItem) == 0


def test_d3_deleting_food_keeps_history_and_nulls_food_id(
    seeded_db, sample_meal_payload
):
    repository.save_meal(sample_meal_payload)
    item = db.session.query(MealItem).one()
    item_id, food_id = item.id, item.food_id
    assert food_id is not None

    db.session.execute(delete(Food).where(Food.id == food_id))
    db.session.commit()
    db.session.expire_all()

    kept = db.session.get(MealItem, item_id)
    assert kept is not None
    assert kept.food_id is None
    assert kept.calories_kcal == approx(234.0)
    assert kept.display_name == "White rice"


def test_d4_zero_weight_fails_check_constraint(seeded_db, make_meal_payload):
    payload = make_meal_payload()
    payload["items"][0]["weight_g"] = 0

    with pytest.raises(DatabaseError):
        repository.save_meal(payload)

    assert _count(Meal) == 0
    assert _count(MealItem) == 0


def test_d5_duplicate_food_name_fails_unique_constraint(seeded_db):
    duplicate = Food(
        food_name="cooked_white_rice",
        display_name="Duplicate rice",
        calories_per_100g=130.0,
        protein_per_100g=2.7,
        carbs_per_100g=28.2,
        fat_per_100g=0.3,
    )
    db.session.add(duplicate)

    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()

    assert db.session.query(Food).filter_by(food_name="cooked_white_rice").count() == 1


def test_d6_empty_day_summary_is_all_zeros(seeded_db):
    summary = repository.get_daily_summary("2026-11-01")

    assert summary["date"] == "2026-11-01"
    assert summary["meal_count"] == 0
    assert summary["totals"] == {
        "calories_kcal": 0.0,
        "protein_g": 0.0,
        "carbs_g": 0.0,
        "fat_g": 0.0,
    }


def test_d7_two_meals_same_day_are_summed(seeded_db, make_meal_payload):
    repository.save_meal(make_meal_payload())

    dinner = make_meal_payload(
        meal_type="dinner",
        meal_datetime_utc="2026-11-01T11:30:00Z",
        items=[copy.deepcopy(CHICKEN_ITEM)],
    )
    repository.save_meal(dinner)

    summary = repository.get_daily_summary("2026-11-01")
    assert summary["meal_count"] == 2
    assert summary["totals"]["calories_kcal"] == approx(481.5)
    assert summary["totals"]["protein_g"] == approx(51.36)
    assert summary["totals"]["carbs_g"] == approx(50.76)
    assert summary["totals"]["fat_g"] == approx(5.94)


def test_d8_delete_meal_reports_existence_and_removes_items(
    seeded_db, sample_meal_payload
):
    meal_id = repository.save_meal(sample_meal_payload)

    assert repository.delete_meal(meal_id) is True
    assert _count(Meal) == 0
    assert _count(MealItem) == 0

    assert repository.delete_meal(999_999) is False


def test_get_meals_filters_dates_and_orders_newest_first(
    seeded_db, make_meal_payload
):
    repository.save_meal(
        make_meal_payload(
            meal_date="2026-10-31", meal_datetime_utc="2026-10-31T04:00:00Z"
        )
    )
    repository.save_meal(
        make_meal_payload(
            meal_date="2026-11-01", meal_datetime_utc="2026-11-01T04:00:00Z"
        )
    )
    repository.save_meal(
        make_meal_payload(
            meal_date="2026-11-02", meal_datetime_utc="2026-11-02T04:00:00Z"
        )
    )

    result = repository.get_meals("2026-11-01", "2026-11-02")
    assert [row["meal_date"] for row in result] == ["2026-11-02", "2026-11-01"]
    assert all(row["item_count"] == 1 for row in result)

    page = repository.get_meal_page(limit=2, offset=0)
    assert len(page) == 2
    assert page[0]["meal_date"] == "2026-11-02"


def test_d9_seed_foods_is_idempotent(app):
    from scripts.seed_foods import load_payload, seed_foods

    expected = len(load_payload()["foods"])
    first = seed_foods()
    second = seed_foods()

    assert first == expected
    assert second == 0
    assert db.session.query(Food).count() == expected


def test_items_count_must_be_between_one_and_twenty(seeded_db, sample_meal_payload):
    empty = dict(sample_meal_payload, items=[])
    with pytest.raises(InvalidRequest):
        repository.save_meal(empty)

    too_many = dict(
        sample_meal_payload,
        items=[copy.deepcopy(sample_meal_payload["items"][0]) for _ in range(21)],
    )
    with pytest.raises(InvalidRequest):
        repository.save_meal(too_many)
