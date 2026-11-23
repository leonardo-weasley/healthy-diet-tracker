"""Prompt constants (step 2, see ``02`` §8.1).

Two hard requirements:
1. The word "json" plus a complete JSON example must appear, otherwise DeepSeek JSON Output does not take effect.
2. The prompt must explicitly forbid nutrition calculation, otherwise the model will always add calorie fields.
"""

import re

PROMPT_TEMPLATE = """You are a food recognition assistant for a calorie-tracking app.

Analyze the meal photograph and identify every distinct food item that is visible.

For each item estimate:
1. A standardized English identifier (lowercase snake_case).
2. The edible weight in grams.
3. A recognition confidence between 0 and 1.

Return ONLY one json object. No markdown fence, no commentary, no extra keys.
All human-readable text in the response must be in English.

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
- "display_name" must be an English name, 1-100 characters.
- "confidence" is recognition confidence, not portion accuracy, between 0 and 1.
- "notes" is optional: null when confident, a short English sentence when not.
- NEVER estimate calories, protein, carbohydrates or fat, and never add such fields.
  Nutrition is computed by another module.
- At most 20 items. If nothing edible is visible, return an empty "foods" list
  and one entry in "warnings".

Standard food names (the ONLY allowed values of "food_name"), with their usual
English names for reference:
{food_name_hints}
"""

# One-to-one with food_name values in app/nutrition/food_database.json (names only, not nutrition values).
# Source: the 29 initial foods in docs/03 §5.2. Keep this list in sync when the database changes.
# The English names help the model map dishes to identifiers.
FOOD_NAME_HINTS = """- cooked_white_rice (white rice)
- brown_rice_cooked (brown rice)
- rice_chicken_bowl (chicken rice bowl)
- cooked_noodles (noodles)
- cooked_pasta (pasta)
- white_bread (white bread)
- whole_wheat_bread (whole-wheat bread)
- oatmeal_cooked (oatmeal)
- grilled_chicken_breast (grilled chicken breast)
- beef_stir_fry (beef stir-fry)
- pork_belly_braised (braised pork belly)
- salmon_cooked (salmon)
- shrimp_cooked (shrimp)
- boiled_egg (boiled egg)
- fried_egg (fried egg / scrambled egg)
- tofu_firm (firm tofu)
- steamed_broccoli (broccoli)
- boiled_potato (potato)
- french_fries (french fries)
- lettuce (lettuce)
- tomato (tomato)
- cucumber (cucumber)
- milk_whole (whole milk)
- plain_yogurt (plain yogurt)
- banana (banana)
- apple (apple)
- vegetable_soup (vegetable soup)
- milk_tea (milk tea)
- cola (cola)"""


def food_name_hints() -> list[str]:
    """All valid food_name values in FOOD_NAME_HINTS, in prompt order."""
    return re.findall(r"^\s*-\s*([a-z0-9_]+)", FOOD_NAME_HINTS, re.M)


def build_prompt() -> str:
    """Build the final prompt.

    Uses replace instead of str.format: the JSON example contains many { } characters,
    which format would treat as placeholders (KeyError), and escaping them as {{ }} is hard to maintain.
    """
    return PROMPT_TEMPLATE.replace("{food_name_hints}", FOOD_NAME_HINTS)
