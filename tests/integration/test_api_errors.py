"""API error-code coverage (one test per code in the shared contract).

Codes: INVALID_REQUEST, INVALID_IMAGE, IMAGE_TOO_LARGE, UNSUPPORTED_MEDIA_TYPE,
INVALID_WEIGHT, FOOD_NOT_FOUND, MEAL_NOT_FOUND, AI_PROVIDER_ERROR,
INVALID_AI_RESPONSE, DATABASE_ERROR, INTERNAL_ERROR.
"""

from __future__ import annotations

import io

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.services import meal_service
from app.utils.errors import AIProviderError, InvalidImage


def _assert_error(response, code: str, status: int) -> None:
    assert response.status_code == status, response.get_data(as_text=True)
    body = response.get_json()
    assert body["error"]["code"] == code


def _post_image(client, image_bytes, filename="meal.png"):
    return client.post(
        "/analyze",
        data={"image": (io.BytesIO(image_bytes), filename)},
        content_type="multipart/form-data",
    )


def test_invalid_request_for_empty_items(client):
    response = client.post(
        "/meals",
        json={
            "meal_type": "lunch",
            "meal_datetime_utc": "2026-11-01T04:30:00Z",
            "meal_date": "2026-11-01",
            "items": [],
        },
    )
    _assert_error(response, "INVALID_REQUEST", 400)


def test_invalid_image_from_provider(client, monkeypatch, sample_meal_image):
    def _bad_image(*_args, **_kwargs):
        raise InvalidImage("cannot decode image")

    monkeypatch.setattr(meal_service, "analyze_food", _bad_image)
    _assert_error(_post_image(client, sample_meal_image), "INVALID_IMAGE", 400)


def test_image_too_large(client, app):
    app.config["MAX_CONTENT_LENGTH"] = 512
    response = _post_image(client, b"x" * 2048)
    _assert_error(response, "IMAGE_TOO_LARGE", 413)


def test_unsupported_media_type(client):
    response = _post_image(client, b"GIF89a", filename="meal.gif")
    _assert_error(response, "UNSUPPORTED_MEDIA_TYPE", 415)


def test_invalid_weight(client, sample_meal_payload):
    payload = sample_meal_payload
    payload["items"][0]["weight_g"] = 0
    _assert_error(client.post("/meals", json=payload), "INVALID_WEIGHT", 400)


def test_food_not_found_when_no_detection_matches(client, seeded_db, monkeypatch, sample_meal_image):
    monkeypatch.setattr(
        meal_service,
        "analyze_food",
        lambda *_args, **_kwargs: {
            "detected": [{"food_name": "ghost_food", "weight_g": 10.0}]
        },
    )
    _assert_error(_post_image(client, sample_meal_image), "FOOD_NOT_FOUND", 422)


def test_meal_not_found_on_get(client):
    _assert_error(client.get("/meals/999999"), "MEAL_NOT_FOUND", 404)


def test_meal_not_found_on_delete(client):
    _assert_error(client.delete("/meals/999999"), "MEAL_NOT_FOUND", 404)


def test_ai_provider_error(client, monkeypatch, sample_meal_image):
    def _boom(*_args, **_kwargs):
        raise AIProviderError("provider is down")

    monkeypatch.setattr(meal_service, "analyze_food", _boom)
    _assert_error(_post_image(client, sample_meal_image), "AI_PROVIDER_ERROR", 502)


def test_invalid_ai_response(client, monkeypatch, sample_meal_image):
    monkeypatch.setattr(
        meal_service,
        "analyze_food",
        lambda *_args, **_kwargs: {"detected": [{"food_name": "rice"}]},
    )
    _assert_error(_post_image(client, sample_meal_image), "INVALID_AI_RESPONSE", 502)


def test_database_error(client, monkeypatch, sample_meal_payload):
    def _broken_commit(self):
        raise SQLAlchemyError("simulated commit failure")

    monkeypatch.setattr(Session, "commit", _broken_commit)
    response = client.post("/meals", json=sample_meal_payload)
    _assert_error(response, "DATABASE_ERROR", 500)


def test_internal_error(client, monkeypatch, sample_meal_image):
    def _unexpected(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(meal_service, "analyze_image", _unexpected)
    _assert_error(_post_image(client, sample_meal_image), "INTERNAL_ERROR", 500)
