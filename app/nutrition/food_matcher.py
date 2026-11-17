"""食物名匹配（成员3）。

匹配三步：精确 → 归一化 → 别名（别名已在 load_food_index() 注册进同一字典）。
未知输入不抛异常，返回 None。
"""

from __future__ import annotations

import re

from .food_repository import load_food_index


def _normalize(name: str) -> str:
    """'Cooked White Rice ' → 'cooked_white_rice'。"""
    return re.sub(r"[\s\-]+", "_", name.strip().lower())


def match_food(food_name: str) -> dict | None:
    """精确 → 归一化 → 别名。命中返回 food_database 条目 dict，否则 None。"""
    if not food_name:
        return None
    index = load_food_index()

    if food_name in index:                     # 1. 精确
        return index[food_name]

    normalized = _normalize(food_name)         # 2. 归一化
    if normalized in index:
        return index[normalized]

    return None                                # 3. 别名已在 index 里注册
