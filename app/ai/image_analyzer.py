"""编排层：调用供应商 → Pydantic 校验 → 重算状态 → 组装 warnings（见 ``02`` §8.4）。"""

import logging
import os
import time

from pydantic import ValidationError

from ..utils.errors import InvalidAiResponse
from .client import DEFAULT_MODEL, call_vision_api
from .prompts import build_prompt
from .schemas import AIAnalysis

log = logging.getLogger(__name__)


def _collect_warnings(analysis: AIAnalysis) -> list[str]:
    """warnings 只由我们派生，不使用模型自由发挥的文案。

    理由：模型写的告警每次都不一样（同一张图可能多一句"not in standard list"），
    会同时污染 warnings 和 status；派生规则让这两者都变成 foods 的纯函数。
    """
    if analysis.warnings:
        log.debug("model warnings ignored: %s", analysis.warnings)
    warnings: list[str] = []
    for food in analysis.foods:
        if food.food_name is None:
            warnings.append(f"food_unrecognized: {food.display_name}")
        if food.estimated_weight_g is None:
            warnings.append(f"missing_weight: {food.display_name}")
    if not analysis.foods:
        warnings.append("no_food_detected")
    return warnings


def _judge_status(analysis: AIAnalysis, warnings: list[str]) -> str:
    """判定规则见 02 §2.3；模型自报的 status 不参与。"""
    if not analysis.foods:
        return "error"
    if any(f.food_name is None or f.estimated_weight_g is None for f in analysis.foods):
        return "partial"
    return "success"


def analyze_food(image_path: str) -> dict:
    """输入：本地图片路径（成员1 已落盘的最终文件）。

    输出：契约 A（``00`` §E.1），``status`` 已按 foods/warnings 重算。
    抛出：AiProviderError / InvalidAiResponse
    """
    started = time.perf_counter()
    raw = call_vision_api(image_path, build_prompt())
    try:
        analysis = AIAnalysis.model_validate(raw)
    except ValidationError as exc:
        log.warning(
            "invalid AI payload image=%s reason=schema errors=%s",
            image_path,
            exc.errors(include_url=False),
        )
        raise InvalidAiResponse(
            "The AI response did not match the contract.",
            details={"reason": "schema"},
        ) from exc

    warnings = _collect_warnings(analysis)
    status = _judge_status(analysis, warnings)
    payload = {
        "schema_version": "1.0",
        "status": status,
        "foods": [f.model_dump() for f in analysis.foods],
        "warnings": warnings,
    }
    log.info(
        "ai analyze image=%s model=%s status=%s foods=%d elapsed_ms=%d",
        image_path,
        os.getenv("AI_MODEL", DEFAULT_MODEL) or DEFAULT_MODEL,
        status,
        len(payload["foods"]),
        int((time.perf_counter() - started) * 1000),
    )
    return payload
