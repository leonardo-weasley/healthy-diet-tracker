"""E1-E4: end-to-end workflow over the HTTP API."""

from __future__ import annotations

import copy
import io

from pytest import approx

from app.database.models import Meal
from app.extensions import db
from app.services import meal_service
from app.utils.errors import AIProviderError


def _upload_meal(client, image_bytes, filename="meal.png"):
    return client.post(
        "/analyze",
        data={"image": (io.BytesIO(image_bytes), filename)},
        content_type="multipart/form-data",
    )


def _meal_payload(draft):
    return {
        "meal_type": "lunch",
        "meal_datetime_utc": "2026-11-01T04:30:00Z",
        "meal_date": "2026-11-01",
        "image_path": None,
        "items": draft["items"],
    }


def test_e1_analyze_then_save_then_dashboard(
    client, seeded_db, monkeypatch, mock_ai_result, sample_meal_image
):
    monkeypatch.setattr(
        meal_service, "analyze_food", lambda *_args, **_kwargs: mock_ai_result
    )

    analyzed = _upload_meal(client, sample_meal_image)
    assert analyzed.status_code == 200
    draft = analyzed.get_json()
    assert len(draft["items"]) == 2

    created = client.post("/meals", json=_meal_payload(draft))
    assert created.status_code == 201
    assert created.get_json()["meal_id"] > 0

    summary = client.get(
        "/dashboard/daily", query_string={"date": "2026-11-01"}
    ).get_json()
    expected = round(sum(item["calories_kcal"] for item in draft["items"]), 1)
    assert summary["meal_count"] == 1
    assert summary["totals"]["calories_kcal"] == approx(expected)
    assert summary["totals"]["calories_kcal"] == approx(481.5)


def test_e2_delete_returns_dashboard_to_zero(client, seeded_db, sample_meal_payload):
    created = client.post("/meals", json=sample_meal_payload)
    assert created.status_code == 201
    meal_id = created.get_json()["meal_id"]

    deleted = client.delete(f"/meals/{meal_id}")
    assert deleted.status_code == 204

    summary = client.get(
        "/dashboard/daily", query_string={"date": "2026-11-01"}
    ).get_json()
    assert summary["meal_count"] == 0
    assert summary["totals"]["calories_kcal"] == approx(0.0)


def test_e3_two_meals_are_summed_on_the_dashboard(
    client, seeded_db, sample_meal_payload
):
    first = client.post("/meals", json=sample_meal_payload)
    assert first.status_code == 201

    dinner = copy.deepcopy(sample_meal_payload)
    dinner["meal_type"] = "dinner"
    dinner["meal_datetime_utc"] = "2026-11-01T11:30:00Z"
    dinner["items"][0] = {
        "food_name": "grilled_chicken_breast",
        "display_name": "Grilled chicken breast",
        "weight_g": 150.0,
        "calories_kcal": 247.5,
        "protein_g": 46.5,
        "carbs_g": 0.0,
        "fat_g": 5.4,
        "food_data_source": "USDA",
    }
    second = client.post("/meals", json=dinner)
    assert second.status_code == 201

    summary = client.get(
        "/dashboard/daily", query_string={"date": "2026-11-01"}
    ).get_json()
    assert summary["meal_count"] == 2
    assert summary["totals"]["calories_kcal"] == approx(481.5)


def test_e4_ai_provider_error_returns_502_and_writes_nothing(
    client, seeded_db, monkeypatch, sample_meal_image
):
    def _boom(*_args, **_kwargs):
        raise AIProviderError("provider is down")

    monkeypatch.setattr(meal_service, "analyze_food", _boom)

    response = _upload_meal(client, sample_meal_image)
    assert response.status_code == 502
    assert response.get_json()["error"]["code"] == "AI_PROVIDER_ERROR"
    assert db.session.query(Meal).count() == 0
