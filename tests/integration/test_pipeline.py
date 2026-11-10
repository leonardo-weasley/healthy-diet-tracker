"""I1-I3: the AI -> nutrition -> database pipeline, with the AI stubbed."""

from __future__ import annotations

from pytest import approx

from app.database import repository
from app.database.models import Food, Meal, MealItem
from app.extensions import db
from app.services import meal_service
from app.utils.errors import InvalidAIResponse


def _stub_ai(monkeypatch, result):
    monkeypatch.setattr(meal_service, "analyze_food", lambda *_args, **_kwargs: result)


def test_i1_mock_ai_produces_nutrition_and_database_rows(
    monkeypatch, seeded_db, mock_ai_result, sample_meal_payload
):
    _stub_ai(monkeypatch, mock_ai_result)

    draft = meal_service.analyze_image(b"fake-image", "image/png")
    assert len(draft["items"]) == 2
    assert draft["warnings"] == []

    payload = meal_service.build_meal_payload(
        draft,
        meal_type="lunch",
        meal_datetime_utc="2026-11-01T04:30:00Z",
        meal_date="2026-11-01",
    )
    meal_id = repository.save_meal(payload)

    assert db.session.query(Meal).count() == 1
    assert db.session.query(MealItem).count() == 2
    meal = repository.get_meal(meal_id)
    assert len(meal["items"]) == 2
    assert meal["totals"]["calories_kcal"] == approx(481.5)

    # 180 g rice -> the values from contract §5.2.
    rice = next(item for item in meal["items"] if item["food_name"] == "cooked_white_rice")
    assert rice["calories_kcal"] == approx(234.0)
    assert rice["protein_g"] == approx(4.86)


def test_i2_unknown_food_is_dropped_with_a_warning(
    monkeypatch, seeded_db, mock_ai_result_unknown
):
    _stub_ai(monkeypatch, mock_ai_result_unknown)

    draft = meal_service.analyze_image(b"fake-image", "image/jpeg")

    assert len(draft["items"]) == 1
    assert len(draft["warnings"]) == 1
    warning = draft["warnings"][0]
    assert warning["code"] == "FOOD_NOT_FOUND"
    assert warning["food_name"] == "mystery_sauce"


def test_i3_snapshot_does_not_change_when_food_values_change(
    seeded_db, sample_meal_payload
):
    meal_id = repository.save_meal(sample_meal_payload)
    before = repository.get_meal(meal_id)

    food = db.session.query(Food).filter_by(food_name="cooked_white_rice").one()
    food.calories_per_100g = 900.0
    food.protein_per_100g = 99.0
    db.session.commit()

    after = repository.get_meal(meal_id)
    assert after["items"][0]["calories_kcal"] == approx(
        before["items"][0]["calories_kcal"]
    )
    assert after["items"][0]["calories_kcal"] == approx(234.0)
    assert after["items"][0]["protein_g"] == approx(4.86)


def test_i4_malformed_ai_response_raises(monkeypatch, seeded_db):
    _stub_ai(monkeypatch, {"detected": []})

    try:
        meal_service.analyze_image(b"fake-image", "image/png")
    except InvalidAIResponse as exc:
        assert exc.code == "INVALID_AI_RESPONSE"
    else:  # pragma: no cover - explicit failure message
        raise AssertionError("InvalidAIResponse was not raised")
