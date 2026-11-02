"""提示词常量（步骤 2，见 ``02`` §8.1）。

两条硬性约束：
1. 必须出现 "json" 字样 + 一个完整的 JSON 示例，否则 DeepSeek 的 JSON Output 不生效。
2. 必须明确"禁止计算营养"，否则模型一定附赠卡路里字段。
"""

import re

PROMPT_TEMPLATE = """You are a food recognition assistant for a calorie-tracking app.

Analyze the meal photograph and identify every distinct food item that is visible.

For each item estimate:
1. A standardized English identifier (lowercase snake_case).
2. The edible weight in grams.
3. A recognition confidence between 0 and 1.

Return ONLY one json object. No markdown fence, no commentary, no extra keys.

{
  "schema_version": "1.0",
  "status": "success",
  "foods": [
    {
      "food_name": "cooked_white_rice",
      "display_name": "White rice",
      "estimated_weight_g": 180.0,
      "confidence": 0.95,
      "notes": null
    }
  ],
  "warnings": []
}

Rules:
- Do not invent food items that are not visible in the photograph.
- List each distinct dish ONCE. Do not split one dish into components.
- Do NOT list sauces, gravies, oils, dressings, dips, garnish or aromatics
  (spring onion, chili, cinnamon, star anise, ...) as separate items.
  Fold them into the dish they belong to. Only a clearly separate dish counts.
- "food_name" MUST be copied exactly from the standard list below.
  If the item is not in that list, set "food_name" to null.
  NEVER invent a new snake_case identifier.
- If a food cannot be identified, set "food_name" to null and describe it in "display_name".
- If a weight cannot be estimated, set "estimated_weight_g" to null.
- "estimated_weight_g" must be a json number (180.0), never a string like "180g".
- "display_name" may be Chinese, 1-100 characters.
- "confidence" is recognition confidence, not portion accuracy, between 0 and 1.
- "notes" is optional: null when confident, a short sentence when not.
- NEVER estimate calories, protein, carbohydrates or fat, and never add such fields.
  Nutrition is computed by another module.
- At most 20 items. If nothing edible is visible, return an empty "foods" list
  and one entry in "warnings".

Standard food names (the ONLY allowed values of "food_name"), with their usual
Chinese names for reference:
{food_name_hints}
"""

# 与 app/nutrition/food_database.json 的 food_name 一一对应（只同步名字，不同步营养数值）。
# 来源：docs/03 §5.2 的 29 条初始数据。成员3 改库时必须同步这里（同一个 PR 或紧随其后的 PR）；
# tests/unit/test_ai_schema.py 里有一条防漂移测试，库落地后会红给你看。
# 附中文名是给模型做映射用的：红烧肉 -> pork_belly_braised，比只给英文 ID 命中率高得多。
FOOD_NAME_HINTS = """- cooked_white_rice（白米饭）
- brown_rice_cooked（糙米饭）
- rice_chicken_bowl（鸡肉饭碗）
- cooked_noodles（面条）
- cooked_pasta（意面）
- white_bread（白面包）
- whole_wheat_bread（全麦面包）
- oatmeal_cooked（燕麦粥）
- grilled_chicken_breast（鸡胸肉）
- beef_stir_fry（炒牛肉）
- pork_belly_braised（红烧肉）
- salmon_cooked（三文鱼）
- shrimp_cooked（虾）
- boiled_egg（水煮蛋）
- fried_egg（煎蛋／炒蛋）
- tofu_firm（北豆腐）
- steamed_broccoli（西兰花）
- boiled_potato（土豆）
- french_fries（薯条）
- lettuce（生菜）
- tomato（番茄）
- cucumber（黄瓜）
- milk_whole（全脂牛奶）
- plain_yogurt（原味酸奶）
- banana（香蕉）
- apple（苹果）
- vegetable_soup（蔬菜汤）
- milk_tea（奶茶）
- cola（可乐）"""


def food_name_hints() -> list[str]:
    """FOOD_NAME_HINTS 里所有合法的 food_name（顺序即提示词里的顺序）。"""
    return re.findall(r"^\s*-\s*([a-z0-9_]+)", FOOD_NAME_HINTS, re.M)


def build_prompt() -> str:
    """拼出最终提示词。

    用 replace 而不是 str.format：提示词里的 JSON 示例带大量 { }，
    走 format 会被当成占位符（KeyError），escape 成 {{ }} 又极难维护。
    """
    return PROMPT_TEMPLATE.replace("{food_name_hints}", FOOD_NAME_HINTS)
