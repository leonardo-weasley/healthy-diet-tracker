"""营养计算单元测试（成员3）——对应 03 文档 §9.1 的 N1–N5、N9–N12。

运行：在仓库根目录执行  pytest tests/unit -q
要求：不需要 API Key、不需要网络、不需要数据库。
"""

import json

import pytest

from app.nutrition.calculator import (
    MAX_WEIGHT_G,
    calculate_food_nutrition,
    calculate_meal_nutrition,
)
from app.nutrition.schemas import NutritionResult

RICE_180 = {"food_name": "cooked_white_rice", "display_name": "White rice",
            "estimated_weight_g": 180.0}
CHICKEN_120 = {"food_name": "grilled_chicken_breast", "display_name": "Chicken",
               "estimated_weight_g": 120.0}


# --- N1 / N2：米饭单项 + 碳水精度 -------------------------------------------
def test_rice_180g():
    result = calculate_food_nutrition("cooked_white_rice", 180)
    assert result["calories_kcal"] == pytest.approx(234.0, abs=0.01)
    assert result["protein_g"] == pytest.approx(4.86, abs=0.01)
    assert result["carbs_g"] == pytest.approx(50.76, abs=0.01)
    assert result["fat_g"] == pytest.approx(0.54, abs=0.01)


# --- N3 / N4：两项合计（米饭 180 + 鸡胸 120） --------------------------------
def test_meal_totals_calories():
    result = calculate_meal_nutrition([RICE_180, CHICKEN_120])
    assert len(result["items"]) == 2
    assert result["totals"]["calories_kcal"] == pytest.approx(432.0, abs=0.01)


def test_meal_totals_protein():
    result = calculate_meal_nutrition([RICE_180, CHICKEN_120])
    assert result["totals"]["protein_g"] == pytest.approx(42.06, abs=0.01)
    assert result["totals"]["carbs_g"] == pytest.approx(50.76, abs=0.01)
    assert result["totals"]["fat_g"] == pytest.approx(4.86, abs=0.01)


# --- N5：零卡食物（可乐 330g） -----------------------------------------------
def test_cola_330g():
    result = calculate_food_nutrition("cola", 330)
    assert result["calories_kcal"] == pytest.approx(138.6, abs=0.01)
    assert result["protein_g"] == pytest.approx(0.0, abs=0.01)


# --- 整餐计算使用输入里的 display_name（用户可能改过） ----------------------
def test_meal_uses_input_display_name():
    result = calculate_meal_nutrition([RICE_180])
    assert result["items"][0]["display_name"] == "White rice"


# --- N9：未匹配只进 warnings，不中断 -----------------------------------------
def test_unknown_food_goes_to_warnings():
    foods = [{"food_name": "dragon_fruit", "display_name": "火龙果",
              "estimated_weight_g": 100.0}]
    result = calculate_meal_nutrition(foods)
    assert result["items"] == []
    assert result["totals"]["calories_kcal"] == 0.0
    assert result["warnings"] == ["food_not_matched: dragon_fruit"]


def test_partial_failure_does_not_break_others():
    foods = [RICE_180, CHICKEN_120,
             {"food_name": None, "display_name": "酱汁", "estimated_weight_g": None}]
    result = calculate_meal_nutrition(foods)
    assert len(result["items"]) == 2
    assert result["totals"]["calories_kcal"] == pytest.approx(432.0, abs=0.01)
    assert any(w.startswith("food_not_matched:") for w in result["warnings"])


# --- N10：缺重量 --------------------------------------------------------------
def test_missing_weight_skipped():
    foods = [{"food_name": "cooked_white_rice", "display_name": "White rice",
              "estimated_weight_g": None}]
    result = calculate_meal_nutrition(foods)
    assert result["items"] == []
    assert result["warnings"] == ["missing_weight: White rice"]


# --- N11：非法重量（0 / 负数 / 超上限） --------------------------------------
@pytest.mark.parametrize("bad_weight", [-10, 0, MAX_WEIGHT_G + 1])
def test_invalid_weight_skipped(bad_weight):
    foods = [{"food_name": "cooked_white_rice", "display_name": "White rice",
              "estimated_weight_g": bad_weight}]
    result = calculate_meal_nutrition(foods)
    assert result["items"] == []
    assert result["warnings"] == [f"invalid_weight: White rice"]


# --- 全部失败也不抛异常（服务层据此转 422 FOOD_NOT_FOUND） -----------------
def test_all_failed_does_not_raise():
    foods = [{"food_name": "dragon_fruit", "display_name": "火龙果",
              "estimated_weight_g": 100.0}]
    result = calculate_meal_nutrition(foods)   # 不应抛异常
    assert result["items"] == []
    assert result["totals"]["calories_kcal"] == 0.0


# --- 空列表 -------------------------------------------------------------------
def test_empty_foods_list():
    result = calculate_meal_nutrition([])
    assert result["items"] == []
    assert result["totals"]["calories_kcal"] == 0.0
    assert result["warnings"] == []


# --- 输入不是 list 时抛 ValueError（程序员错误） -----------------------------
def test_non_list_input_raises_valueerror():
    with pytest.raises(ValueError):
        calculate_meal_nutrition({"food_name": "cooked_white_rice"})


# --- N12：纯函数——同输入跑 3 次完全一致 -------------------------------------
def test_pure_function_deterministic():
    foods = [RICE_180, CHICKEN_120]
    first = json.dumps(calculate_meal_nutrition(foods), sort_keys=True)
    second = json.dumps(calculate_meal_nutrition(foods), sort_keys=True)
    third = json.dumps(calculate_meal_nutrition(foods), sort_keys=True)
    assert first == second == third


# --- 输出形状符合契约 C（Pydantic 校验） -------------------------------------
def test_output_matches_contract_c_schema():
    result = calculate_meal_nutrition([RICE_180, CHICKEN_120])
    validated = NutritionResult.model_validate(result)
    assert validated.schema_version == "1.0"
    assert len(validated.items) == 2
    assert set(validated.totals.model_dump().keys()) == {
        "calories_kcal", "protein_g", "carbs_g", "fat_g",
    }
