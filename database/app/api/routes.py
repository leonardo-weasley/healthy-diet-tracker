"""Reference HTTP API used by the integration and end-to-end tests.

Member 1 owns the production routes.  These endpoints are deliberately thin:
validate input, delegate to a service or repository function, serialise the
result.  Keeping the seam here lets the test suite exercise real HTTP
responses without depending on member 1's code being finished.

Endpoints:
    POST   /analyze                 image -> draft meal (not saved)
    POST   /meals                   save a confirmed meal (contract §5.2)
    GET    /meals                   history list; date_from/date_to or limit/offset
    GET    /meals/<meal_id>         contract D
    DELETE /meals/<meal_id>         cascade delete
    GET    /dashboard/daily         contract E (date defaults to local today)
"""

from __future__ import annotations

import re
from datetime import date as date_cls, datetime

from flask import Blueprint, current_app, jsonify, request

from ..database import repository
from ..services import meal_service
from ..utils.errors import (
    ImageTooLarge,
    InvalidImage,
    InvalidRequest,
    InvalidWeight,
    MealNotFound,
    UnsupportedMediaType,
)
from ..utils.timeutil import local_today

api_bp = Blueprint("api", __name__)

_MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}
_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_TOTAL_KEYS = ("calories_kcal", "protein_g", "carbs_g", "fat_g")


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------
def _validate_date(value: object, field: str) -> str:
    if not isinstance(value, str) or not _DATE_RE.match(value):
        raise InvalidRequest(
            f"'{field}' must be a YYYY-MM-DD date.", details={"field": field}
        )
    try:
        date_cls.fromisoformat(value)
    except ValueError as exc:
        raise InvalidRequest(
            f"'{field}' is not a valid calendar date.", details={"field": field}
        ) from exc
    return value


def _validate_utc(value: object) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise InvalidRequest(
            "'meal_datetime_utc' must be an ISO-8601 UTC string ending in 'Z'.",
            details={"field": "meal_datetime_utc"},
        )
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise InvalidRequest(
            "'meal_datetime_utc' is not a valid timestamp.",
            details={"field": "meal_datetime_utc"},
        ) from exc
    return value


def _validate_meal_payload(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise InvalidRequest("Request body must be a JSON object.")

    meal_type = payload.get("meal_type")
    if meal_type not in _MEAL_TYPES:
        raise InvalidRequest(
            "'meal_type' must be one of breakfast, lunch, dinner, snack.",
            details={"field": "meal_type"},
        )
    _validate_utc(payload.get("meal_datetime_utc"))
    _validate_date(payload.get("meal_date"), "meal_date")

    items = payload.get("items")
    if not isinstance(items, list) or not (1 <= len(items) <= 20):
        raise InvalidRequest(
            "A meal must contain 1-20 items.",
            details={"count": len(items) if isinstance(items, list) else None},
        )

    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise InvalidRequest(
                "Every meal item must be a JSON object.", details={"index": index}
            )
        display_name = item.get("display_name")
        if not isinstance(display_name, str) or not display_name.strip():
            raise InvalidRequest(
                "Meal item is missing 'display_name'.", details={"index": index}
            )
        try:
            weight = float(item.get("weight_g"))
        except (TypeError, ValueError) as exc:
            raise InvalidWeight(
                "Item weight must be a number.", details={"index": index}
            ) from exc
        if not (0 < weight <= 5000):
            raise InvalidWeight(
                "Item weight must be greater than 0 g and at most 5000 g.",
                details={"index": index, "weight_g": weight},
            )
        for key in _TOTAL_KEYS:
            try:
                value = float(item.get(key))
            except (TypeError, ValueError) as exc:
                raise InvalidRequest(
                    f"Meal item is missing a numeric '{key}'.",
                    details={"index": index, "field": key},
                ) from exc
            if value < 0:
                raise InvalidRequest(
                    f"'{key}' must not be negative.",
                    details={"index": index, "field": key},
                )
    return payload


def _int_arg(name: str, default: int, minimum: int, maximum: int) -> int:
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError) as exc:
        raise InvalidRequest(
            f"'{name}' must be an integer.", details={"field": name}
        ) from exc
    if not (minimum <= value <= maximum):
        raise InvalidRequest(
            f"'{name}' must be between {minimum} and {maximum}.",
            details={"field": name, "value": value},
        )
    return value


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@api_bp.post("/analyze")
def analyze():
    upload = request.files.get("image")
    if upload is None:
        raise InvalidRequest("A multipart 'image' file is required.")

    mimetype = (upload.mimetype or "").lower()
    if mimetype not in _ALLOWED_IMAGE_TYPES:
        raise UnsupportedMediaType(
            "Only JPEG, PNG and WebP images are supported.",
            details={"content_type": mimetype or None},
        )

    image_bytes = upload.read()
    if not image_bytes:
        raise InvalidImage("The uploaded image is empty.")
    max_bytes = current_app.config.get("MAX_IMAGE_BYTES", 10 * 1024 * 1024)
    if len(image_bytes) > max_bytes:
        raise ImageTooLarge(details={"max_bytes": max_bytes})

    draft = meal_service.analyze_image(image_bytes, mimetype)
    return jsonify(draft), 200


@api_bp.post("/meals")
def create_meal():
    payload = request.get_json(silent=True)
    _validate_meal_payload(payload)
    meal_id = repository.save_meal(payload)
    return jsonify(repository.get_meal(meal_id)), 201


@api_bp.get("/meals")
def list_meals():
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    if date_from is not None:
        _validate_date(date_from, "date_from")
    if date_to is not None:
        _validate_date(date_to, "date_to")

    if date_from or date_to:
        return jsonify(repository.get_meals(date_from, date_to)), 200

    limit = _int_arg("limit", default=50, minimum=1, maximum=200)
    offset = _int_arg("offset", default=0, minimum=0, maximum=1_000_000)
    return jsonify(repository.get_meal_page(limit, offset)), 200


@api_bp.get("/meals/<int:meal_id>")
def read_meal(meal_id: int):
    meal = repository.get_meal(meal_id)
    if meal is None:
        raise MealNotFound(details={"meal_id": meal_id})
    return jsonify(meal), 200


@api_bp.delete("/meals/<int:meal_id>")
def remove_meal(meal_id: int):
    if not repository.delete_meal(meal_id):
        raise MealNotFound(details={"meal_id": meal_id})
    return "", 204


@api_bp.get("/dashboard/daily")
def daily_summary():
    raw_date = request.args.get("date")
    target = _validate_date(raw_date, "date") if raw_date is not None else local_today()
    return jsonify(repository.get_daily_summary(target)), 200
