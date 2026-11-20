"""Generate nutrition fixtures from food_database.json using Decimal ROUND_HALF_UP."""
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
db = json.loads((ROOT / "app/nutrition/food_database.json").read_text(encoding="utf-8"))
WEIGHTS = [1, 37.5, 100, 123.4, 250, 5000]
KEYS = {
    "calories_kcal": ("calories_per_100g", 1),
    "protein_g": ("protein_per_100g", 2),
    "carbs_g": ("carbs_per_100g", 2),
    "fat_g": ("fat_per_100g", 2),
}

def q(value, places):
    return float(Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP))

cases = []
for food in db["foods"]:
    for weight in WEIGHTS:
        item = {}
        for key, (per100, places) in KEYS.items():
            item[key] = q(Decimal(str(food[per100])) * Decimal(str(weight)) / Decimal(100), places)
        cases.append({"food_name": food["food_name"], "weight": weight, "expected": item})

combo = db["foods"][:5]
combo_case = {"items": [], "totals": {}}
exact = {key: Decimal(0) for key in KEYS}
for food in combo:
    weight = 180
    entry = {}
    for key, (per100, places) in KEYS.items():
        raw = Decimal(str(food[per100])) * Decimal(str(weight)) / Decimal(100)
        exact[key] += raw
        entry[key] = q(raw, places)
    combo_case["items"].append({"food_name": food["food_name"], "weight": weight, "expected": entry})
for key, (_, places) in KEYS.items():
    combo_case["totals"][key] = q(exact[key], places)

Path(__file__).with_name("expected.json").write_text(
    json.dumps({"cases": cases, "combo": combo_case}, ensure_ascii=False), encoding="utf-8"
)
print(f"wrote {len(cases)} cases")
