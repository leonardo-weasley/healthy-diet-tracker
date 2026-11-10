"""Repository: the only place that touches ``db.session`` for meals.

Public functions (contract in ``05`` §6):

``save_meal``, ``get_meal``, ``get_meals``, ``delete_meal``,
``get_daily_summary`` plus the pagination helper ``get_meal_page``.

Routes and services must go through these functions instead of issuing
queries themselves.  Nutrition values are always read from the ``meal_item``
snapshot; nothing is recalculated here.
"""

from __future__ import annotations

import logging

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..utils.errors import DatabaseError, InvalidRequest
from ..utils.timeutil import to_local_iso
from .models import Food, Meal, MealItem

log = logging.getLogger(__name__)

TOTAL_KEYS = ("calories_kcal", "protein_g", "carbs_g", "fat_g")
_ROUND_DIGITS = {
    "calories_kcal": 1,
    "protein_g": 2,
    "carbs_g": 2,
    "fat_g": 2,
}
_REQUIRED_ITEM_FIELDS = (
    "display_name",
    "weight_g",
    "calories_kcal",
    "protein_g",
    "carbs_g",
    "fat_g",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _resolve_food_id(food_name: str | None) -> int | None:
    """Return ``food.id`` for a canonical name, or ``None`` when unknown."""
    if not food_name:
        return None
    row = Food.query.filter_by(food_name=food_name).first()
    return row.id if row else None


def _item_to_dict(item: MealItem) -> dict:
    return {
        "food_name": item.food_name,
        "display_name": item.display_name,
        "weight_g": item.weight_g,
        "calories_kcal": item.calories_kcal,
        "protein_g": item.protein_g,
        "carbs_g": item.carbs_g,
        "fat_g": item.fat_g,
        "food_data_source": item.food_data_source,
    }


def _sum_items(items: list[MealItem] | list[dict]) -> dict:
    """Sum snapshot values; empty input yields all-zero totals."""
    def value(item, key):
        return item[key] if isinstance(item, dict) else getattr(item, key)

    return {
        key: round(sum(float(value(item, key)) for item in items), _ROUND_DIGITS[key])
        for key in TOTAL_KEYS
    }


def _normalize_item(item: dict, order: int) -> dict:
    missing = [field for field in _REQUIRED_ITEM_FIELDS if field not in item]
    if missing:
        raise InvalidRequest(
            "Meal item is missing required fields.",
            details={"index": order, "missing": missing},
        )
    try:
        normalized = {
            "food_name": item.get("food_name"),
            "display_name": str(item["display_name"]),
            "weight_g": float(item["weight_g"]),
            "calories_kcal": float(item["calories_kcal"]),
            "protein_g": float(item["protein_g"]),
            "carbs_g": float(item["carbs_g"]),
            "fat_g": float(item["fat_g"]),
            "food_data_source": item.get("food_data_source") or "local",
            "sort_order": order,
        }
    except (TypeError, ValueError) as exc:
        raise InvalidRequest(
            "Meal item contains a non-numeric nutrition value.",
            details={"index": order},
        ) from exc
    return normalized


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------
def save_meal(meal_data: dict) -> int:
    """Write one meal and all of its items in a single transaction.

    Returns the new ``meal.id``.  Unknown ``food_name`` values are allowed and
    stored as ``food_id = NULL`` (the historical snapshot is still valid).
    Nutritional values are persisted exactly as supplied; they are never
    recalculated here.
    """
    if not isinstance(meal_data, dict):
        raise InvalidRequest("Meal payload must be a JSON object.")

    items = meal_data.get("items") or []
    if not isinstance(items, list) or not (1 <= len(items) <= 20):
        raise InvalidRequest(
            "A meal must contain 1-20 items.", details={"count": len(items)}
        )
    for field in ("meal_type", "meal_datetime_utc", "meal_date"):
        if not meal_data.get(field):
            raise InvalidRequest(
                "Meal payload is missing a required field.",
                details={"field": field},
            )

    normalized_items = [_normalize_item(item, order) for order, item in enumerate(items)]

    try:
        meal = Meal(
            meal_type=meal_data["meal_type"],
            meal_datetime_utc=meal_data["meal_datetime_utc"],
            meal_date=meal_data["meal_date"],
            image_path=meal_data.get("image_path"),
        )
        db.session.add(meal)
        db.session.flush()  # materialise meal.id before inserting children

        for item in normalized_items:
            db.session.add(
                MealItem(
                    meal_id=meal.id,
                    food_id=_resolve_food_id(item["food_name"]),
                    food_name=item["food_name"],
                    display_name=item["display_name"],
                    weight_g=item["weight_g"],
                    calories_kcal=item["calories_kcal"],
                    protein_g=item["protein_g"],
                    carbs_g=item["carbs_g"],
                    fat_g=item["fat_g"],
                    food_data_source=item["food_data_source"],
                    sort_order=item["sort_order"],
                )
            )
        db.session.commit()
        return meal.id
    except InvalidRequest:
        db.session.rollback()
        raise
    except Exception as exc:  # IntegrityError, OperationalError, ...
        db.session.rollback()
        log.exception("save_meal failed")
        raise DatabaseError("Failed to save the meal.") from exc


def delete_meal(meal_id: int) -> bool:
    """Delete a meal and its items.  ``True`` if it existed."""
    try:
        meal = db.session.get(Meal, meal_id)
        if meal is None:
            return False
        db.session.delete(meal)  # ORM cascade; DB FK cascade is the backstop
        db.session.commit()
        log.info("deleted meal_id=%s", meal_id)
        return True
    except SQLAlchemyError as exc:
        db.session.rollback()
        log.exception("delete_meal failed")
        raise DatabaseError("Failed to delete the meal.") from exc


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
def get_meal(meal_id: int) -> dict | None:
    """Return contract D for one meal, or ``None`` when it does not exist."""
    try:
        meal = db.session.get(Meal, meal_id)
        if meal is None:
            return None
        items = [_item_to_dict(item) for item in meal.items]
    except SQLAlchemyError as exc:
        log.exception("get_meal failed")
        raise DatabaseError("Failed to load the meal.") from exc

    return {
        "meal_id": meal.id,
        "meal_type": meal.meal_type,
        "meal_datetime": to_local_iso(meal.meal_datetime_utc),
        "meal_date": meal.meal_date,
        "image_path": meal.image_path,
        "created_at": meal.created_at,
        "items": items,
        "totals": _sum_items(items),
        "warnings": [],
    }


def _meal_to_summary(meal: Meal) -> dict:
    items = [_item_to_dict(item) for item in meal.items]
    names = [item["display_name"] for item in items]
    summary = ", ".join(names[:3])
    if len(names) > 3:
        summary += f" +{len(names) - 3}"
    return {
        "meal_id": meal.id,
        "meal_type": meal.meal_type,
        "meal_datetime": to_local_iso(meal.meal_datetime_utc),
        "meal_date": meal.meal_date,
        "display_summary": summary,
        "calories_kcal": round(
            sum(item["calories_kcal"] for item in items), _ROUND_DIGITS["calories_kcal"]
        ),
        "item_count": len(items),
    }


def get_meals(date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    """History summaries ordered newest first, optionally filtered by date."""
    try:
        query = Meal.query
        if date_from:
            query = query.filter(Meal.meal_date >= date_from)
        if date_to:
            query = query.filter(Meal.meal_date <= date_to)
        meals = query.order_by(Meal.meal_datetime_utc.desc(), Meal.id.desc()).all()
        return [_meal_to_summary(meal) for meal in meals]
    except SQLAlchemyError as exc:
        log.exception("get_meals failed")
        raise DatabaseError("Failed to load meal history.") from exc


def get_meal_page(limit: int, offset: int = 0) -> list[dict]:
    """Pagination helper for ``GET /meals`` when no date range is given.

    ``get_meals`` keeps its fixed two-argument signature (00 §G).
    """
    if limit < 1:
        raise InvalidRequest("limit must be at least 1.", details={"limit": limit})
    if offset < 0:
        raise InvalidRequest("offset must not be negative.", details={"offset": offset})
    try:
        meals = (
            Meal.query.order_by(Meal.meal_datetime_utc.desc(), Meal.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [_meal_to_summary(meal) for meal in meals]
    except SQLAlchemyError as exc:
        log.exception("get_meal_page failed")
        raise DatabaseError("Failed to load meal history.") from exc


def get_daily_summary(date: str) -> dict:
    """Contract E.  An empty day returns zero totals and ``meal_count == 0``."""
    try:
        calories, protein, carbs, fat = (
            db.session.query(
                func.coalesce(func.sum(MealItem.calories_kcal), 0.0),
                func.coalesce(func.sum(MealItem.protein_g), 0.0),
                func.coalesce(func.sum(MealItem.carbs_g), 0.0),
                func.coalesce(func.sum(MealItem.fat_g), 0.0),
            )
            .join(Meal, MealItem.meal_id == Meal.id)
            .filter(Meal.meal_date == date)
            .one()
        )
        meal_count = (
            db.session.query(func.count(Meal.id))
            .filter(Meal.meal_date == date)
            .scalar()
            or 0
        )
    except SQLAlchemyError as exc:
        log.exception("get_daily_summary failed")
        raise DatabaseError("Failed to load the daily summary.") from exc

    values = {
        "calories_kcal": calories,
        "protein_g": protein,
        "carbs_g": carbs,
        "fat_g": fat,
    }
    totals = {
        key: round(float(values[key] or 0.0), _ROUND_DIGITS[key]) for key in TOTAL_KEYS
    }
    return {"date": date, "totals": totals, "meal_count": int(meal_count)}
