"""食物匹配单元测试（成员3）——对应 03 文档 §9.1 的 N6–N8 + 额外边界。

运行：在仓库根目录执行  pytest tests/unit -q
要求：不需要 API Key、不需要网络、不需要数据库。
"""

import pytest

from app.nutrition.food_matcher import match_food
from app.nutrition.food_repository import load_food_index, reset_cache


def _entry_of(food_name: str) -> dict:
    """返回索引中 food_name 对应的条目，便于断言。"""
    entry = match_food(food_name)
    assert entry is not None
    return entry


# --- N6：精确匹配 -------------------------------------------------------------
def test_exact_match():
    entry = _entry_of("cooked_white_rice")
    assert entry["food_name"] == "cooked_white_rice"
    assert entry["calories_per_100g"] == 130


# --- N7：归一化匹配 -----------------------------------------------------------
def test_normalized_match():
    entry = _entry_of("Cooked White Rice")
    assert entry["food_name"] == "cooked_white_rice"


def test_normalized_match_with_dashes_and_spaces():
    entry = _entry_of("  grilled-chicken-breast ")
    assert entry["food_name"] == "grilled_chicken_breast"


# --- N8：别名匹配 -------------------------------------------------------------
def test_alias_match():
    entry = _entry_of("white_rice")
    assert entry["food_name"] == "cooked_white_rice"


def test_alias_match_case_insensitive():
    entry = _entry_of("Rice")
    assert entry["food_name"] == "cooked_white_rice"


# --- N9：未匹配返回 None，不抛异常 -------------------------------------------
def test_unmatched_returns_none():
    assert match_food("dragon_fruit") is None


def test_empty_name_returns_none():
    assert match_food("") is None
    assert match_food(None) is None


# --- 别名不覆盖主 food_name --------------------------------------------------
def test_alias_does_not_shadow_food_name():
    index = load_food_index()
    # "egg" 是 boiled_egg 的别名，不能作为主键覆盖任何 food_name
    assert index["boiled_egg"]["food_name"] == "boiled_egg"
    assert index["egg"]["food_name"] == "boiled_egg"


# --- 数据文件基础体检 ----------------------------------------------------------
def test_database_has_at_least_20_foods():
    reset_cache()
    index = load_food_index()
    # 每个 food_name 都有 entry，且至少 20 条（当前 29 条）
    assert len([k for k in index if not any(k == a for e in index.values()
                                             for a in (e.get("aliases") or []))]) >= 20


def test_food_names_are_unique_and_well_formed():
    reset_cache()
    index = load_food_index()
    import re
    pattern = re.compile(r"^[a-z0-9_]+$")
    for entry in index.values():
        if pattern.fullmatch(entry["food_name"]):
            continue
        # 别名也会出现在索引里，不要求别名符合主键格式
    foods = [e for e in index.values() if not any(
        e is v for v in index.values())]
    # 直接对原始 JSON 检查主键唯一性
    import json
    from pathlib import Path
    raw = json.loads((Path(__file__).parents[2] / "app" / "nutrition"
                      / "food_database.json").read_text(encoding="utf-8"))
    names = [f["food_name"] for f in raw["foods"]]
    assert len(names) == len(set(names))
    assert all(pattern.fullmatch(n) for n in names)
    assert len(names) >= 20
