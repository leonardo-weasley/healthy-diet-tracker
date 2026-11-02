"""契约 A 的 Pydantic 模型（步骤 2，见 ``02`` §8.2）。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DetectedFood(BaseModel):
    model_config = ConfigDict(extra="ignore")

    food_name: str | None = Field(default=None, pattern=r"^[a-z0-9_]+$", max_length=60)
    display_name: str = Field(min_length=1, max_length=100)
    estimated_weight_g: float | None = Field(default=None, gt=0, le=5000)
    confidence: float = Field(ge=0, le=1)
    notes: str | None = Field(default=None, max_length=200)


class AIAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: Literal["1.0"] = "1.0"
    # 模型自报状态仅供参考：最终状态由 image_analyzer._judge_status 重算，
    # 所以这里不校验枚举值——避免模型写个 "unknown" 就白白 502。
    status: str | None = None
    foods: list[DetectedFood] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list)
