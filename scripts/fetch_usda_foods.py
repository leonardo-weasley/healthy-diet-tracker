"""从 USDA FoodData Central 拉取真实营养数据，重建 ``app/nutrition/food_database.json``。

用法（在仓库根目录）::

    python scripts/fetch_usda_foods.py            # 拉取并写回 JSON
    python scripts/fetch_usda_foods.py --dry-run  # 只打印匹配结果，不改文件

设计要点：

* 每个食物显式声明查询词与必须命中的关键词，避免搜到品牌/婴儿食品等无关条目；
* 只接受 ``Foundation`` / ``SR Legacy`` 两类公共领域基础数据；
* 每 100 g 取 Energy(kcal) / Protein / Carbohydrate / Total lipid(fat)；
* 原始响应缓存到 ``scripts/usda_cache/``，重复运行不重复请求（DEMO_KEY 限流）；
* 复合菜（炒牛肉、红烧肉、鸡肉饭碗、蔬菜汤、奶茶）没有可靠的单一 USDA 条目，
  保留本地估算值并标记 ``source=local``。

数据来源：https://fdc.nal.usda.gov/ （公有领域）。
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "app" / "nutrition" / "food_database.json"
CACHE_DIR = ROOT / "scripts" / "usda_cache"
API = "https://api.nal.usda.gov/fdc/v1/foods/search"
API_KEY = "DEMO_KEY"
ALLOWED_TYPES = {"Foundation", "SR Legacy"}
USER_AGENT = "healthy-diet-tracker/1.0 (course project; data build)"

# food_name -> (query, must_have_tokens, avoid_tokens)
QUERIES: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
    "cooked_white_rice": (
        "rice white long-grain regular cooked enriched",
        ("rice", "white", "cooked"),
        ("flour", "babyfood", "restaurant", "cereal", "cake", "bread"),
    ),
    "brown_rice_cooked": (
        "rice brown long-grain cooked",
        ("rice", "brown", "cooked"),
        ("flour", "babyfood", "oil", "bran"),
    ),
    "cooked_noodles": (
        "noodles egg cooked enriched",
        ("noodles", "cooked"),
        ("dry", "unprepared", "babyfood", "cup", "chinese"),
    ),
    "cooked_pasta": (
        "pasta cooked enriched without added salt",
        ("pasta", "cooked"),
        ("dry", "unprepared", "babyfood", "corn", "rice", "with"),
    ),
    "white_bread": (
        "bread white commercially prepared",
        ("bread", "white"),
        ("toasted", "crumbs", "stuffing", "roll", "bun", "wheat", "low", "sodium", "diet"),
    ),
    "whole_wheat_bread": (
        "bread whole-wheat commercially prepared",
        ("bread", "whole", "wheat"),
        ("toasted", "crumbs", "stuffing", "roll", "bun"),
    ),
    "oatmeal_cooked": (
        "cereals oats regular and quick cooked with water",
        ("oats", "cooked"),
        ("instant", "fortified", "babyfood", "dry"),
    ),
    "grilled_chicken_breast": (
        "chicken broilers fryers breast meat only cooked grilled",
        ("chicken", "breast", "grilled"),
        ("skin", "fried", "rotisserie", "deli", "ground"),
    ),
    "salmon_cooked": (
        "fish salmon atlantic farmed cooked dry heat",
        ("salmon", "cooked"),
        ("smoked", "canned", "roe", "raw"),
    ),
    "shrimp_cooked": (
        "crustaceans shrimp mixed species cooked moist heat",
        ("shrimp", "cooked"),
        ("canned", "breaded", "fried", "raw"),
    ),
    "boiled_egg": (
        "egg whole cooked hard-boiled",
        ("egg", "hard", "boiled"),
        ("dried", "white", "yolk", "substitute"),
    ),
    "fried_egg": (
        "egg whole cooked fried",
        ("egg", "fried"),
        ("dried", "white", "yolk", "substitute"),
    ),
    "tofu_firm": (
        "tofu raw firm prepared with calcium sulfate",
        ("tofu", "firm"),
        ("fried", "silken", "dried"),
    ),
    "steamed_broccoli": (
        "broccoli cooked boiled drained without salt",
        ("broccoli", "cooked"),
        ("frozen", "raw", "babyfood", "with"),
    ),
    "boiled_potato": (
        "potatoes boiled cooked in skin flesh without salt",
        ("potatoes", "boiled"),
        ("french", "chips", "mashed", "dehydrated", "canned", "with"),
    ),
    "french_fries": (
        "fast foods potato french fried in vegetable oil",
        ("potato", "french", "fried"),
        ("shrimp", "chicken", "onion", "sweet"),
    ),
    "lettuce": (
        "lettuce cos or romaine raw",
        ("lettuce", "raw"),
        ("iceberg", "head", "butterhead"),
    ),
    "tomato": (
        "tomatoes red ripe raw year round average",
        ("tomatoes", "raw"),
        ("canned", "paste", "sauce", "juice", "sun-dried"),
    ),
    "cucumber": (
        "cucumber with peel raw",
        ("cucumber", "raw"),
        ("pickle", "peeled"),
    ),
    "milk_whole": (
        "milk whole 3.25% milkfat with added vitamin D",
        ("milk", "whole"),
        ("chocolate", "evaporated", "powder", "dry", "condensed", "buttermilk", "goat"),
    ),
    "plain_yogurt": (
        "yogurt plain whole milk",
        ("yogurt", "plain"),
        ("fruit", "vanilla", "greek", "lowfat", "nonfat"),
    ),
    "banana": ("bananas raw", ("bananas", "raw"), ("dehydrated", "chips", "babyfood")),
    "apple": ("apples raw with skin", ("apples", "raw"), ("without", "fuji", "gala", "honeycrisp", "granny", "delicious", "golden", "juice", "dried", "canned", "sauce")),
    "cola": (
        "beverages carbonated cola regular",
        ("cola", "carbonated"),
        ("diet", "low calorie", "cherry", "vanilla"),
    ),
}

ENERGY_IDS = (1008, 2047, 2048)
NUTRIENT_IDS = {"protein": 1003, "carbs": 1005, "fat": 1004}


def _tokens(text: str) -> set[str]:
    cleaned = "".join(ch.lower() if ch.isalnum() or ch in "-%" else " " for ch in text)
    return {t for t in cleaned.replace("-", " ").split() if t}


def _fetch(query: str) -> dict:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / (urllib.parse.quote(query, safe="")[:120] + ".json")
    if cache.is_file():
        return json.loads(cache.read_text(encoding="utf-8"))
    params = urllib.parse.urlencode(
        {
            "query": query,
            "pageSize": 25,
            "pageNumber": 1,
            "dataType": ",".join(sorted(ALLOWED_TYPES)),
            "api_key": API_KEY,
        }
    )
    request = urllib.request.Request(f"{API}?{params}", headers={"User-Agent": USER_AGENT})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                payload = json.loads(response.read().decode("utf-8"))
            cache.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            return payload
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < 2:
                print(f"    rate limited, sleeping 65s ...")
                time.sleep(65)
                continue
            raise
    raise RuntimeError("unreachable")


STOPWORDS = {
    "with", "without", "added", "and", "or", "in", "the", "of", "all", "types",
    "year", "round", "average", "prepared", "regular", "quick", "meat", "only",
}


def _score(description: str, query: str, must: tuple[str, ...],
           avoid: tuple[str, ...]) -> float:
    """Hard-filter on ``must``/``avoid``, then rank by query-token coverage."""
    desc_tokens = _tokens(description)
    if any(token not in desc_tokens for token in must):
        return -1.0
    if any(token in desc_tokens for token in avoid):
        return -1.0
    query_tokens = _tokens(query) - STOPWORDS
    if not query_tokens:
        return -1.0
    coverage = len(desc_tokens & query_tokens) / len(query_tokens)
    return coverage * 10 - len(description) / 300


def _nutrient(food: dict, nutrient_id: int) -> float | None:
    for item in food.get("foodNutrients", []):
        if item.get("nutrientId") == nutrient_id:
            value = item.get("value")
            if value is not None:
                return float(value)
    return None


def _energy(food: dict) -> float | None:
    for nutrient_id in ENERGY_IDS:
        value = _nutrient(food, nutrient_id)
        if value is not None:
            return value
    return None


def _round(value: float, places: int) -> float | int:
    rounded = round(value, places)
    return int(rounded) if abs(rounded - round(rounded)) < 1e-9 else rounded


def _pick(payload: dict, query: str, must: tuple[str, ...],
          avoid: tuple[str, ...]) -> dict | None:
    best, best_score = None, -1.0
    for food in payload.get("foods", []):
        if food.get("dataType") not in ALLOWED_TYPES:
            continue
        score = _score(food.get("description", ""), query, must, avoid)
        if score > best_score:
            best, best_score = food, score
    if best is None or best_score < 0:
        return None
    if None in (_energy(best), _nutrient(best, 1003), _nutrient(best, 1005), _nutrient(best, 1004)):
        return None
    return best


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--only", nargs="*", default=None)
    args = parser.parse_args()

    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    today = date.today().isoformat()
    changed = 0
    for row in payload["foods"]:
        name = row["food_name"]
        if name not in QUERIES or (args.only and name not in args.only):
            continue
        query, must, avoid = QUERIES[name]
        print(f"[{name}] query={query!r}")
        try:
            data = _fetch(query)
        except Exception as exc:  # 网络/限流失败时保留原值
            print(f"    !! fetch failed: {exc}; keeping current values")
            continue
        food = _pick(data, query, must, avoid)
        if food is None:
            print("    !! no acceptable match; keeping current values")
            continue
        calories = _energy(food)
        protein = _nutrient(food, NUTRIENT_IDS["protein"])
        carbs = _nutrient(food, NUTRIENT_IDS["carbs"])
        fat = _nutrient(food, NUTRIENT_IDS["fat"])
        if not (0 <= calories <= 900 and 0 <= protein <= 100 and 0 <= carbs <= 100 and 0 <= fat <= 100):
            print(f"    !! implausible values for {food['description']!r}; skipped")
            continue
        print(
            f"    -> {food['fdcId']} [{food['dataType']}] {food['description']}\n"
            f"       {calories} kcal / P {protein} / C {carbs} / F {fat}"
        )
        if args.dry_run:
            continue
        row.update(
            calories_per_100g=_round(calories, 1),
            protein_per_100g=_round(protein, 2),
            carbs_per_100g=_round(carbs, 2),
            fat_per_100g=_round(fat, 2),
            source="USDA",
            is_verified=1,
            usda={
                "fdc_id": food["fdcId"],
                "description": food["description"],
                "data_type": food["dataType"],
                "fetched_at": today,
            },
        )
        changed += 1

    if not args.dry_run:
        payload["source_note"] = (
            "Values per 100 g edible portion. Fetched from USDA FoodData Central "
            f"(Foundation / SR Legacy) on {today}; see each item's usda.fdc_id. "
            "Composite dishes without a single reliable USDA record keep local estimates "
            "(source=local)."
        )
        DATA_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"\nupdated {changed} foods -> {DATA_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
