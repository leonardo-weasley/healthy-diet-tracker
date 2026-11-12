"""营养数据加载与索引（成员3）。

只读本地 food_database.json，启动后缓存；运行时绝不联网。
对外只暴露 load_food_index() 与 reset_cache()（reset 仅供测试）。
"""

from __future__ import annotations

import json
from pathlib import Path

_DATA_PATH = Path(__file__).with_name("food_database.json")
_CACHE: dict[str, dict] | None = None


def load_food_index() -> dict[str, dict]:
    """读 food_database.json → {food_name: entry}，并把 aliases 也注册进去。

    只在首次调用时读文件，之后返回缓存。
    """
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    raw = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    index: dict[str, dict] = {}
    for entry in raw["foods"]:
        index[entry["food_name"]] = entry
    for entry in raw["foods"]:
        for alias in entry.get("aliases") or []:
            index.setdefault(alias.lower(), entry)

    _CACHE = index
    return _CACHE


def reset_cache() -> None:
    """仅供测试使用：清空缓存，让下一次调用重新读文件。"""
    global _CACHE
    _CACHE = None
