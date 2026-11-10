"""Turn AI detections into ``meal_item`` snapshots.

Member 3 owns the nutrition formula; this module implements the exact
per-100 g scaling needed by the pipeline tests:

    value = per_100g * weight_g / 100

Matched foods are read from the ``food`` table, which is populated by
``scripts/seed_foods.py``.  Unknown detections produce a warning and are
dropped; if *every* detection is unknown the caller gets ``FOOD_NOT_FOUND``.
"""

from __future__ import annotations

from ..database.models import Food
from ..extensions import db
from ..utils.errors import FoodNotFound, InvalidWeight

TOTAL_KEYS = ("calories_kcal", "protein_g", "carbs_g", "fat_g")
_ROUND_DIGITS = {
    "calories_kcal": 1,
    "protein_g": 2,
    "carbs_g": 2,
    "fat_g": 2,
}


def _lookup(food_names: list[str | None]) -> dict[str, Food]:
    names = {name for name in food_names if name}
    if not names:
        return {}
    rows = db.session.query(Food).filter(Food.food_name.in_(names)).all()
    return {row.food_name: row for row in rows}


def build_meal_items(detected: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return ``(items, warnings)`` for the detections that matched food rows."""
    foods = _lookup([detection.get("food_name") for detection in detected])
    items: list[dict] = []
    warnings: list[dict] = []

    for detection in detected:
        food_name = detection.get("food_name")
        weight = float(detection.get("weight_g") or 0.0)
        if not (0 < weight <= 5000):
            raise InvalidWeight(
                "Item weight must be greater than 0 g and at most 5000 g.",
                details={"food_name": food_name, "weight_g": weight},
            )

        food = foods.get(food_name)
        if food is None:
            warnings.append(
                {
                    "code": "FOOD_NOT_FOUND",
                    "food_name": food_name,
                    "message": f"'{food_name}' is not in the food database.",
                }
            )
            continue

        factor = weight / 100.0
        items.append(
            {
                "food_name": food.food_name,
                "display_name": detection.get("display_name") or food.display_name,
                "weight_g": round(weight, 1),
                "calories_kcal": round(food.calories_per_100g * factor, 1),
                "protein_g": round(food.protein_per_100g * factor, 2),
                "carbs_g": round(food.carbs_per_100g * factor, 2),
                "fat_g": round(food.fat_per_100g * factor, 2),
                "food_data_source": food.source,
            }
        )

    if not items:
        raise FoodNotFound(
            "None of the detected foods exists in the food database.",
            details={"detected": [d.get("food_name") for d in detected]},
        )
    return items, warnings


def sum_items(items: list[dict]) -> dict:
    """Snapshot totals for a list of item dicts (empty list -> zeros)."""
    return {
        key: round(sum(float(item[key]) for item in items), _ROUND_DIGITS[key])
        for key in TOTAL_KEYS
    }
