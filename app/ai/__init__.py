"""AI 模块（成员2）。

对外只暴露一个函数：``analyze_food(image_path) -> dict``，返回契约 A（见 ``00`` §E.1）。
"""

from .image_analyzer import analyze_food

__all__ = ["analyze_food"]
