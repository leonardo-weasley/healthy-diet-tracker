"""营养计算（成员3）。

公式：单项 = weight / 100 × 每100g值。
用 Decimal 做乘加、最后一次性取整（kcal 1 位，宏量 2 位），totals 用未取整值累加。
单条失败不中断，全部失败也不抛异常（由服务层统一转 FOOD_NOT_FOUND）。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from ..utils.errors import FoodNotFound, InvalidWeight
from .food_matcher import match_food

MAX_WEIGHT_G = 5000

_TOTAL_KEYS = ("calories_kcal", "protein_g", "carbs_g", "fat_g")


def _round(value: Decimal, places: int) -> float:
    quant = Decimal(1).scaleb(-places)
    return float(value.quantize(quant, rounding=ROUND_HALF_UP))


def calculate_food_nutrition(food_name: str, weight_g: float) -> dict:
    """单项计算（按食物名直接查库的场景：测试 / 未来的手动录入）。

    返回 items[] 里的一条（不含 schema_version），display_name 用库里的名字。
    抛出：FoodNotFound（未匹配）、InvalidWeight（重量不合法）。
    """
    entry = match_food(food_name)
    if entry is None:
        raise FoodNotFound(f"Food not found: {food_name}",
                           details={"food_name": food_name})
    if not isinstance(weight_g, (int, float)) or not (0 < weight_g <= MAX_WEIGHT_G):
        raise InvalidWeight(f"Invalid weight: {weight_g}",
                            details={"weight_g": weight_g})

    ratio = Decimal(str(weight_g)) / Decimal(100)
    return {
        "food_name": entry["food_name"],
        "display_name": entry["display_name"],   # 单独调用时用库里的名字
        "weight_g": float(weight_g),
        "calories_kcal": _round(ratio * Decimal(str(entry["calories_per_100g"])), 1),
        "protein_g": _round(ratio * Decimal(str(entry["protein_per_100g"])), 2),
        "carbs_g": _round(ratio * Decimal(str(entry["carbs_per_100g"])), 2),
        "fat_g": _round(ratio * Decimal(str(entry["fat_per_100g"])), 2),
        "food_data_source": entry.get("source", "local"),
    }


def calculate_meal_nutrition(foods: list[dict]) -> dict:
    """输入契约 A 的 foods 列表，返回契约 C（schema_version / items / totals / warnings）。

    - 单条失败不中断：未匹配、缺重量、非法重量都只进 warnings；
    - 全部失败也不抛异常，返回 items: []、totals 全 0；
    - 只有输入不是 list 时抛 ValueError（这是程序员错误，不是用户错误）。
    """
    if not isinstance(foods, list):
        raise ValueError("foods must be a list")

    items: list[dict] = []
    warnings: list[str] = []
    exact = {key: Decimal(0) for key in _TOTAL_KEYS}

    for food in foods:
        name = food.get("food_name")
        display = food.get("display_name") or "unknown"
        weight = food.get("estimated_weight_g")

        if not name:
            warnings.append(f"food_not_matched: {display}")
            continue
        if weight is None:
            warnings.append(f"missing_weight: {display}")
            continue
        if not isinstance(weight, (int, float)) or not (0 < weight <= MAX_WEIGHT_G):
            warnings.append(f"invalid_weight: {display}")
            continue

        entry = match_food(name)
        if entry is None:
            warnings.append(f"food_not_matched: {name}")
            continue

        ratio = Decimal(str(weight)) / Decimal(100)
        item = {
            "food_name": entry["food_name"],
            "display_name": display,            # 整餐计算时用输入里的名字（用户可能改过）
            "weight_g": float(weight),
            "calories_kcal": ratio * Decimal(str(entry["calories_per_100g"])),
            "protein_g": ratio * Decimal(str(entry["protein_per_100g"])),
            "carbs_g": ratio * Decimal(str(entry["carbs_per_100g"])),
            "fat_g": ratio * Decimal(str(entry["fat_per_100g"])),
            "food_data_source": entry.get("source", "local"),
        }
        for key in _TOTAL_KEYS:
            exact[key] += item[key]

        items.append({
            **item,
            "calories_kcal": _round(item["calories_kcal"], 1),
            "protein_g": _round(item["protein_g"], 2),
            "carbs_g": _round(item["carbs_g"], 2),
            "fat_g": _round(item["fat_g"], 2),
        })

    totals = {key: _round(exact[key], 1 if key == "calories_kcal" else 2)
              for key in _TOTAL_KEYS}

    return {
        "schema_version": "1.0",
        "items": items,
        "totals": totals,
        "warnings": warnings,
    }
