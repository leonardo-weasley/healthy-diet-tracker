"""营养模块的 Pydantic 输出模型（成员3，建议有）。

与 00_MAIN_TECHNICAL_ROUTE.md §E.3（契约 C）字段一一对应，
用于在模块边界校验计算结果的形状。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class NutritionItem(BaseModel):
    food_name: str = Field(min_length=1, max_length=60)
    display_name: str = Field(min_length=1, max_length=100)
    weight_g: float = Field(gt=0, le=5000)
    calories_kcal: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)
    food_data_source: Literal["USDA", "local", "custom"] = "local"


class NutritionTotals(BaseModel):
    calories_kcal: float = Field(ge=0)
    protein_g: float = Field(ge=0)
    carbs_g: float = Field(ge=0)
    fat_g: float = Field(ge=0)


class NutritionResult(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    items: list[NutritionItem] = Field(max_length=20)
    totals: NutritionTotals
    warnings: list[str] = []
