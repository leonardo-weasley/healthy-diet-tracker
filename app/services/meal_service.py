"""Analysis pipeline: AI detection -> nutrition snapshots -> meal payload.

The route layer calls :func:`analyze_image`; member 1 can reuse
:func:`build_meal_payload` when the user confirms a draft.  The module-level
``analyze_food`` name is the seam the tests monkeypatch.
"""

from __future__ import annotations

import logging

from ..ai.service import analyze_food
from ..nutrition.calculator import build_meal_items, sum_items
from ..utils.errors import InvalidAIResponse

log = logging.getLogger(__name__)


def _validate_ai_result(raw: object) -> dict:
    if not isinstance(raw, dict):
        raise InvalidAIResponse("AI response must be a JSON object.")

    detected = raw.get("detected")
    if not isinstance(detected, list) or not detected:
        raise InvalidAIResponse(
            "AI response must contain a non-empty 'detected' list."
        )

    cleaned: list[dict] = []
    for index, detection in enumerate(detected):
        if not isinstance(detection, dict):
            raise InvalidAIResponse(
                "Every detected item must be a JSON object.",
                details={"index": index},
            )
        food_name = detection.get("food_name")
        if not isinstance(food_name, str) or not food_name.strip():
            raise InvalidAIResponse(
                "Detected item is missing 'food_name'.",
                details={"index": index},
            )
        try:
            weight = float(detection.get("weight_g"))
        except (TypeError, ValueError) as exc:
            raise InvalidAIResponse(
                "Detected item has a non-numeric weight.",
                details={"index": index},
            ) from exc
        cleaned.append(
            {
                "food_name": food_name.strip(),
                "display_name": detection.get("display_name") or food_name.strip(),
                "weight_g": weight,
                "confidence": detection.get("confidence"),
            }
        )

    return {"provider": raw.get("provider") or "unknown", "detected": cleaned}


def analyze_image(image_bytes: bytes, content_type: str) -> dict:
    """Run the AI boundary and return a draft meal (nothing is saved)."""
    raw = analyze_food(image_bytes, content_type)
    analysis = _validate_ai_result(raw)
    items, warnings = build_meal_items(analysis["detected"])
    draft = {
        "provider": analysis["provider"],
        "items": items,
        "totals": sum_items(items),
        "warnings": warnings,
    }
    log.info(
        "analyzed image: %d item(s), %d warning(s)", len(items), len(warnings)
    )
    return draft


def build_meal_payload(
    draft: dict,
    *,
    meal_type: str,
    meal_datetime_utc: str,
    meal_date: str,
    image_path: str | None = None,
) -> dict:
    """Attach meal metadata to an analysis draft, ready for ``save_meal``."""
    return {
        "meal_type": meal_type,
        "meal_datetime_utc": meal_datetime_utc,
        "meal_date": meal_date,
        "image_path": image_path,
        "items": draft["items"],
        "warnings": draft.get("warnings", []),
    }
