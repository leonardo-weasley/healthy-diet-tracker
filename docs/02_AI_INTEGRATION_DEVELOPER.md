# 02 — AI 集成开发指南（成员 2）

> 上位文档：[`00_MAIN_TECHNICAL_ROUTE.md`](00_MAIN_TECHNICAL_ROUTE.md)。冲突时以主路线为准。
> 你的任务是**把照片变成一份可信的 JSON**，不是让它算卡路里。算数是成员3 的事。

## 1. 角色与目标

### 1.1 你的职责

| 你负责 | 你不负责 |
|---|---|
| 选一家多模态 AI 供应商并跑通 | 营养计算（成员3） |
| 图片预处理（尺寸、MIME、EXIF） | 上传校验与落盘（成员1 已做完，你只拿到路径） |
| 提示词设计与维护（`prompts.py`） | 保存餐食（成员5） |
| 请求结构化 JSON 输出 | 页面展示（成员4） |
| 解析 + Pydantic 校验 | 改契约（需全组同意） |
| 超时、重试、限流、坏响应的降级 | — |
| 未识别食物与缺失重量的表达 | — |

### 1.2 最终交付物（一句话）

> `analyze_food(image_path)` 对任意一张餐食照片返回**契约 A** 的 dict，且 `status` 能正确表达"全认得 / 部分认得 / 全认不出"，任何供应商故障都变成 `AI_PROVIDER_ERROR` 或 `INVALID_AI_RESPONSE`。

### 1.3 成功标准

- 成员1 的接口**不需要**为你写任何转换代码。
- 成员3 拿到你的 `food_name` 能直接 `match_food()` 命中。
- 拔掉 API Key、断网、传垃圾图，服务都不崩。
- 你自己能用 `pytest` 证明以上三点。

---

## 2. 要构建什么

### 2.1 必须实现

1. 供应商选择与鉴权（Key 只从 `.env` 读）。
2. 图片读取与预处理（校验、限尺寸、统一格式）。
3. 提示词：**强制 JSON、禁止算营养、字段名与我们契约一致**。
4. 调用供应商并拿到 JSON 文本。
5. 解析 + `json.loads` + Pydantic 校验。
6. 状态判定：`success` / `partial` / `error`。
7. 错误分级与重试策略。
8. `mock_ai_result.json` 供他人独立开发。

### 2.2 明确不做

- ❌ 不做上传接口、不碰 `uploads/` 落盘（成员1 负责，你只接收 `image_path`）
- ❌ 不算任何卡路里/蛋白质/碳水/脂肪，连"估算"都不许
- ❌ 不让 AI 决定 `meal_type`（用户选，成员1 传）
- ❌ 不做菜品分类枚举表校验（用 `^[a-z0-9_]+$` 就够）
- ❌ 不接第二家供应商（适配层留好，但 MVP 只接一家）
- ❌ 不做图片生成、翻译、聊天

### 2.3 三种状态如何判定（核心逻辑）

| 判定 | 条件 |
|---|---|
| `success` | `foods` 非空，且每项都有 `food_name` 和 `estimated_weight_g` |
| `partial` | 至少一项 `food_name is None` 或 `estimated_weight_g is None`，或 `warnings` 非空 |
| `error` | `foods` 为空（且 `warnings` 至少一条） |

> 不允许"AI 说认不出，我们偷偷猜一个最像的 ID"。宁可 `null`，让用户手动选。

---

## 3. 技术要用的东西

### 3.1 依赖

```bash
pip install "google-genai>=0.3" "pydantic>=2.6" "Pillow>=10.0" "python-dotenv>=1.0" "pytest>=8.0"
```

### 3.2 供应商与模型

| 项 | 值 |
|---|---|
| 供应商 | Google Gemini（MVP 只此一家） |
| SDK | `google-genai`（Python 官方新 SDK） |
| 图像理解文档 | `https://ai.google.dev/gemini-api/docs/image-understanding` |
| 结构化输出文档 | `https://ai.google.dev/gemini-api/docs/structured-output` |
| 模型名 | 从 `AI_MODEL` 读，默认填一个 **flash** 型号；**型号会更新，以官方文档为准** |
| 关键参数 | `response_mime_type="application/json"`、`temperature` 取低值（如 0.2） |
| 图片传法 | 读成 bytes，作为图片 part 与提示词一起放进 `contents` |
| 计费注意 | 每张图只调 **1 次**；不要在循环里重试同一张图 |

> **供应商相关代码必须集中在 `app/ai/client.py`**。上面这些参数、SDK 方法都属"provider-specific"，写错时先查官方文档，不要凭记忆改。

### 3.3 需要理解的概念

| 概念 | 用途 |
|---|---|
| 强制 JSON 输出（response mime type / structured output） | 让模型只返回 JSON，省掉正则清洗 |
| 低 temperature | 减少同一张图两次结果差异过大 |
| base64 / bytes part | 图片不一定有公网 URL，直接传字节 |
| Pydantic `Literal` | 校验 `status`、字段类型 |
| 超时 | Flask 是同步的，30 秒不返回就必须放弃 |
| 图片缩放 | 1024 px 长边足够识别，能显著降延迟与费用 |

---

## 4. 你拥有的文件

```text
app/ai/__init__.py           # 导出 analyze_food
app/ai/client.py             # 唯一允许 import google.* 的文件
app/ai/image_analyzer.py     # analyze_food()：编排 + 校验 + 状态判定
app/ai/prompts.py            # PROMPT_TEMPLATE 常量
app/ai/schemas.py            # AIAnalysis, DetectedFood（Pydantic v2）
tests/unit/test_ai_schema.py # 你的校验测试
tests/fixtures/mock_ai_result.json   # 与他人共用的 mock（与成员5 共同维护）
```

### 4.1 别人怎么用你

| 他人 | 用法 | 禁止 |
|---|---|---|
| 成员1 | `from app.ai.image_analyzer import analyze_food` | 不许 import `app.ai.client` |
| 成员3 | 只消费返回值里的 `foods` | 不许依赖你内部的 Prompt |
| 成员5 | 在测试里 monkeypatch `analyze_food` | 不许在测试里真调 API |
| 成员4 | 只看到 `/analyze` 的 JSON | 不许直连 Gemini |

**边界**：`image_analyzer.py` 里**不许**出现 `google`、`openai`、`requests` 字样；写在 `client.py` 就够。

---

## 5. 输入输出契约

### 5.1 输入

```python
analyze_food(image_path: str) -> dict
```

| 项 | 说明 |
|---|---|
| 类型 | `str`，服务器本地可读路径，如 `uploads/2026/11/6f1c9a2e.jpg` |
| 是否一定存在 | 是（成员1 已校验并落盘） |
| 是否一定是图片 | 是（成员1 已用 Pillow 校验）；但你仍要防御性 `try` |
| 是否需要 `meal_type` | **不需要**。`meal_type` 由用户选择，成员1 在保存时使用；契约 A 里没有这个字段 |

### 5.2 输出：契约 A（一字不差）

```json
{
  "schema_version": "1.0",
  "status": "partial",
  "foods": [
    {
      "food_name": "cooked_white_rice",
      "display_name": "White rice",
      "estimated_weight_g": 180.0,
      "confidence": 0.95,
      "notes": null
    },
    {
      "food_name": null,
      "display_name": "某种深色酱汁",
      "estimated_weight_g": null,
      "confidence": 0.42,
      "notes": "Cannot identify from photo"
    }
  ],
  "warnings": ["food_unrecognized: 某种深色酱汁", "missing_weight: 某种深色酱汁"]
}
```

字段约束（与 `00` §E.1 完全一致）：

| 字段 | 类型 | 必填 | 约束 |
|---|---|---|---|
| `schema_version` | string | 是 | 固定 `"1.0"` |
| `status` | string | 是 | `success` / `partial` / `error` |
| `foods` | array | 是 | `0–20` 项 |
| `foods[].food_name` | string \| null | 是 | `^[a-z0-9_]+$`，≤60 字符；认不出填 `null` |
| `foods[].display_name` | string | 是 | 1–100 字符，可中文 |
| `foods[].estimated_weight_g` | number \| null | 是 | `0 < x ≤ 5000`；估不出填 `null` |
| `foods[].confidence` | number | 是 | `0 ≤ x ≤ 1` |
| `foods[].notes` | string \| null | 否 | ≤200 字符 |
| `warnings` | array[string] | 是 | 无告警填 `[]` |

### 5.3 错误行为

| 情况 | 抛出 | 谁接住 |
|---|---|---|
| Key 缺失/无效 | `AiProviderError(details={"reason": "auth"})` | 成员1 的路由 |
| 超时 | `AiProviderError(details={"reason": "timeout"})` | 同上 |
| 429 / 额度 | `AiProviderError(details={"reason": "rate_limited"})` | 同上 |
| 返回非 JSON | `InvalidAiResponse(details={"reason": "not_json"})` | 同上 |
| JSON 缺字段/类型错 | `InvalidAiResponse(details={"reason": "schema"})` | 同上 |
| 图中无食物 | **不抛异常**，返回 `status: "error"` | — |

---

## 6. 必须实现的函数接口

```python
# app/ai/client.py
def call_vision_api(image_path: str, prompt: str) -> dict:
    """输入：本地图片路径 + 提示词全文
       输出：模型返回的原始 dict（仅 json.loads，不做业务校验）
       抛出：AiProviderError（网络/超时/鉴权/额度）
             InvalidAiResponse（返回的不是 JSON）"""

# app/ai/image_analyzer.py
def analyze_food(image_path: str) -> dict:
    """输入：本地图片路径
       输出：契约 A（已通过 Pydantic 校验）
       抛出：AiProviderError / InvalidAiResponse"""
```

### 6.1 职责划分

| 文件 | 做什么 | 不做 |
|---|---|---|
| `client.py` | 装配 SDK、发请求、取文本、`json.loads` | 状态判定、字段改名、组装 warnings |
| `image_analyzer.py` | 读图预处理、填提示词、调 client、校验、判状态、组装 warnings | 任何 SDK 调用 |

### 6.2 重试策略（严格按此实现）

| 失败类型 | 是否重试 | 次数 |
|---|---|---|
| 超时 / 5xx / 网络错误 | 是 | 共 2 次尝试（1 次重试） |
| 429 限流 | 是 | 1 次，间隔 2 秒 |
| 返回非 JSON | 是 | 1 次（换个说法重发） |
| JSON 结构不符合契约 | 否 | 直接抛 `InvalidAiResponse` |
| 图中无食物 | 否（不是失败） | 返回 `error` 状态 |

**禁止**：无限重试、在 for 循环里重试同一张图超过 2 次、把重试当异常处理的主要手段。

---

## 7. 实施步骤

### 7.0 六周交付节奏（你的部分）

| 周 | 你要交付 | 验收 |
|---|---|---|
| 1 | 选供应商、拿 Key、写 `prompts.py`、`schemas.py`、mock JSON、函数骨架 | `pytest tests/unit/test_ai_schema.py` 能跑（哪怕只测 mock） |
| 2 | 真实调用跑通 10–20 张照片；`client.py` 与 `image_analyzer.py` 完成 | 每张图都能拿到合法契约 A |
| 3 | 错误分级与重试；与成员1 的 `/analyze` 联调 | 拔 Key/断网/传风景照 三种都不崩 |
| 4 | 未知食物与缺重量的表达打磨；配合前端联调 | 前端能把 `null` 行高亮出来 |
| 5 | 支撑 30 张照片测试；记录识别率与份量误差 | 回归表有数据 |
| 6 | 冻结提示词；整理"已知识别失败类型"清单 | 演示时能解释为什么会认错 |

### 步骤 1：选供应商，跑通最小调用（第 1 周）

1. 去 Google AI Studio 建 Key，写进 `.env` 的 `AI_API_KEY`。
2. 新建 `app/ai/client.py`，写最小可运行脚本（不是 Flask，先单独跑）。
3. 用一张鸡肉饭照片，打印返回文本。

**完成标准**：终端能打印出一段 JSON 文本。

### 步骤 2：写提示词与 Pydantic 模型（第 1 周末）

1. `prompts.py` 写 `PROMPT_TEMPLATE`（见 §8.1）。
2. `schemas.py` 写 `DetectedFood`、`AIAnalysis`（见 §8.2）。
3. 手工造 `tests/fixtures/mock_ai_result.json` 与 `mock_ai_partial.json`。

**完成标准**：`AIAnalysis.model_validate(mock)` 不报错；把 `estimated_weight_g` 改成 `"180g"` 会报错。

### 步骤 3：串起 `analyze_food()`（第 2 周）

1. 读图 → 校验 → 缩放（长边 ≤1024）→ 编码为 bytes。
2. 调 `call_vision_api()`。
3. `AIAnalysis.model_validate(raw)`。
4. 判 `status`（§2.3），补 `warnings`。
5. 返回 dict。

**完成标准**：对 10–20 张不同照片，每次返回都能被 `AIAnalysis` 校验通过。

### 步骤 4：错误分级（第 2 周末）

1. 把 SDK 抛的各种异常映射成 `AiProviderError`（带 `reason`）。
2. 区分"非 JSON"与"结构不符"。
3. 实现 §6.2 的重试。
4. 确保单次调用最长不超过 `AI_TIMEOUT_SECONDS`（默认 30 秒）。

**完成标准**：把 Key 改错、断网、传纯白图片，三种情况分别得到预期的错误码/状态。

### 步骤 5：未知食物打磨（第 3–4 周）

1. 提示词里强化："不确定时 `food_name` 必须为 null，不许猜"。
2. 至少构造 5 个"半认不出"的样例，确认输出 `partial` + `warnings`。
3. 与成员1 确认 `warnings` 格式：`food_unrecognized: <name>`、`missing_weight: <name>`。

### 步骤 6：30 张照片回归（第 5 周）

1. 拍/找 30 张真实餐食照片，放 `tests/fixtures/photos/`（**不入 Git**，本地保留）。
2. 记录：识别出几个、认错几个、份量误差。
3. 把结果填进 `docs/PORTION_EVAL.md`（或表格形式交给成员5）。

**完成标准**：至少 25/30 张能返回可用结果；能说清 5 类失败原因。

---

## 8. 代码示例

### 8.1 提示词（`app/ai/prompts.py`）

```python
PROMPT_TEMPLATE = """You are a food recognition assistant.

Analyze the uploaded meal photograph.

Identify each visible food item. For each item, estimate:
1. Food name (standardized identifier).
2. Estimated edible weight in grams.
3. Recognition confidence between 0 and 1.

Return ONLY JSON matching this schema:
{
  "schema_version": "1.0",
  "status": "success",
  "foods": [
    {
      "food_name": "snake_case_standard_id_or_null",
      "display_name": "Human readable name",
      "estimated_weight_g": 180.0,
      "confidence": 0.95,
      "notes": null
    }
  ],
  "warnings": []
}

Rules:
- Do not invent food items that are not visible.
- If a food cannot be identified, set food_name to null and describe it in display_name.
- If a weight cannot be estimated, set estimated_weight_g to null.
- Do not estimate calories, protein, carbohydrates or fat. Never.
- Use lowercase snake_case English identifiers for food_name, e.g. cooked_white_rice.
- status must be "success" (all items have name and weight),
  "partial" (some are missing), or "error" (nothing recognized).
- estimated_weight_g must be a JSON number, never a string like "180g".
"""
```

要点：
- 提示词里**直接写契约字段名**，模型输出就不用二次改名。
- 明确"不许算营养"，否则模型一定会附赠卡路里。
- 明确"重量必须是数字"，能挡掉 `"180g"`。

### 8.2 Pydantic 模型（`app/ai/schemas.py`）

```python
from typing import Literal

from pydantic import BaseModel, Field


class DetectedFood(BaseModel):
    food_name: str | None = Field(default=None, pattern=r"^[a-z0-9_]+$", max_length=60)
    display_name: str = Field(min_length=1, max_length=100)
    estimated_weight_g: float | None = Field(default=None, gt=0, le=5000)
    confidence: float = Field(ge=0, le=1)
    notes: str | None = Field(default=None, max_length=200)


class AIAnalysis(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    status: Literal["success", "partial", "error"]
    foods: list[DetectedFood] = Field(max_length=20)
    warnings: list[str] = []
```

> `food_name: None` 要通过校验——`str | None` 已经允许；但 `display_name` 不允许空串。

### 8.3 供应商调用（`app/ai/client.py`）

```python
import json
import os
from pathlib import Path

from google import genai
from google.genai import types

from ..utils.errors import AiProviderError, InvalidAiResponse

_MIME_BY_EXT = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".png": "image/png", ".webp": "image/webp"}


def _build_client() -> "genai.Client":
    api_key = os.getenv("AI_API_KEY", "").strip()
    if not api_key:
        raise AiProviderError("AI_API_KEY is not configured.",
                              details={"reason": "missing_api_key"})
    return genai.Client(api_key=api_key)


def call_vision_api(image_path: str, prompt: str) -> dict:
    client = _build_client()
    path = Path(image_path)
    mime = _MIME_BY_EXT.get(path.suffix.lower(), "image/jpeg")

    try:
        response = client.models.generate_content(
            model=os.getenv("AI_MODEL", "gemini-2.0-flash"),
            contents=[
                types.Part.from_bytes(data=path.read_bytes(), mime_type=mime),
                prompt,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
    except Exception as exc:                      # SDK 异常类型较杂，统一收口
        raise AiProviderError("The AI provider call failed.",
                              details={"reason": "provider_error",
                                       "error": type(exc).__name__}) from exc

    text = (response.text or "").strip()
    if not text:
        raise InvalidAiResponse("The AI provider returned an empty response.",
                                details={"reason": "empty"})
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidAiResponse("The AI response was not valid JSON.",
                                details={"reason": "not_json",
                                         "preview": text[:200]}) from exc
```

> 上面这段是**供应商相关实现**。SDK 的方法名/参数可能随版本变化，写不通就查官方文档；不要凭猜改参数。

### 8.4 编排与状态判定（`app/ai/image_analyzer.py`）

```python
import logging

from pydantic import ValidationError

from ..utils.errors import InvalidAiResponse
from .client import call_vision_api
from .prompts import PROMPT_TEMPLATE
from .schemas import AIAnalysis

log = logging.getLogger(__name__)


def _judge_status(analysis: AIAnalysis) -> str:
    if not analysis.foods:
        return "error"
    if any(f.food_name is None or f.estimated_weight_g is None for f in analysis.foods):
        return "partial"
    return "success"


def _collect_warnings(analysis: AIAnalysis) -> list[str]:
    warnings = list(analysis.warnings)
    for food in analysis.foods:
        if food.food_name is None:
            warnings.append(f"food_unrecognized: {food.display_name}")
        if food.estimated_weight_g is None:
            warnings.append(f"missing_weight: {food.display_name}")
    if not analysis.foods and not warnings:
        warnings.append("no_food_detected")
    return warnings


def analyze_food(image_path: str) -> dict:
    raw = call_vision_api(image_path, PROMPT_TEMPLATE)   # 已重试 1 次
    try:
        analysis = AIAnalysis.model_validate(raw)
    except ValidationError as exc:
        log.warning("invalid AI payload: %s", exc.errors(include_url=False))
        raise InvalidAiResponse("The AI response did not match the contract.",
                                details={"reason": "schema"}) from exc

    status = _judge_status(analysis)
    payload = {
        "schema_version": "1.0",
        "status": status,
        "foods": [f.model_dump() for f in analysis.foods],
        "warnings": _collect_warnings(analysis),
    }
    log.info("ai result status=%s foods=%d", status, len(payload["foods"]))
    return payload
```

### 8.5 图片预处理（可选但推荐）

若成员1 已经把图片缩到 1024 px，你可跳过；否则在调用前自己缩一次：

```python
from PIL import Image, ImageOps

def _prepare(image_path: str, max_side: int = 1024) -> None:
    with Image.open(image_path) as img:
        img = ImageOps.exif_transpose(img).convert("RGB")
        img.thumbnail((max_side, max_side))
        img.save(image_path, format="JPEG", quality=85, optimize=True)
```

> 不要在原图上做破坏性缩放却不告知成员1——要么提前约定，要么另存临时文件。

---

## 9. 测试要求

### 9.1 用例

| # | 用例 | 做法 | 期望 |
|---|---|---|---|
| AI1 | 合法 JSON 通过 | 喂 `mock_ai_result.json` | `AIAnalysis` 校验通过，`len(foods)==2` |
| AI2 | 重量是字符串 | 把 `180.0` 改 `"180g"` | `ValidationError` → `InvalidAiResponse` |
| AI3 | `confidence=1.5` | 改值 | 校验失败 |
| AI4 | 缺 `display_name` | 删字段 | 校验失败 |
| AI5 | 空 `foods` + warnings | `status: "error"` | 校验**通过**，状态判为 `error` |
| AI6 | 一项 `food_name: null` | `mock_ai_partial.json` | 状态判为 `partial`，warnings 含 `food_unrecognized` |
| AI7 | 一项缺重量 | 改 `estimated_weight_g: null` | 状态 `partial`，warnings 含 `missing_weight` |
| AI8 | 供应商抛异常 | monkeypatch `call_vision_api` 抛 `AiProviderError` | 原样上抛，不吞 |
| AI9 | 返回非 JSON | monkeypatch 返回文本 | `InvalidAiResponse(reason="not_json")` |
| AI10 | 重试只发生 1 次 | 计数 mock 调用次数 | `== 2`（首次 + 1 次重试） |

### 9.2 测试要点

- 全部用 `monkeypatch`，**不许**真调 API、不许要真实 Key。
- 断言 `model_dump()` 的字段集合，防止有人偷偷加字段。
- 用 `pytest.approx` 比浮点。

```python
# tests/unit/test_ai_schema.py
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.ai.schemas import AIAnalysis

MOCK = json.loads(Path("tests/fixtures/mock_ai_result.json").read_text(encoding="utf-8"))


def test_valid_payload_passes():
    analysis = AIAnalysis.model_validate(MOCK)
    assert analysis.status == "success"
    assert len(analysis.foods) == 2


def test_weight_as_string_is_rejected():
    bad = json.loads(json.dumps(MOCK))
    bad["foods"][0]["estimated_weight_g"] = "180g"
    with pytest.raises(ValidationError):
        AIAnalysis.model_validate(bad)
```

---

## 10. 集成说明

### 10.1 你的依赖

| 依赖 | 提供者 | 没完成时 |
|---|---|---|
| 落盘后的图片路径 | 成员1 | 自己拿一张本地图跑脚本，不经过 HTTP |
| `ApiError` / `AiProviderError` / `InvalidAiResponse` | 成员1 | 先按 `00` §G.2 的签名自己建，最终以他的为准 |
| `APP_TIMEZONE` 等配置 | 成员1 | 与 AI 无关，忽略 |

### 10.2 依赖你的

| 模块 | 用你什么 | 注意事项 |
|---|---|---|
| 成员1（`/analyze`） | `analyze_food(image_path)` | 返回值会原样放进 `data`，别忘了 `image_path` 由他补 |
| 成员3 | 只吃 `foods[]` 的 `food_name` / `display_name` / `estimated_weight_g` | 你的 `food_name` 必须能在他的库里命中 |
| 成员5 | 用 `monkeypatch` 替换你 | 你必须是**可替换的纯边界**：文件顶部 import 函数，不要内联调用 |

### 10.3 什么时候合并

| 时机 | 内容 |
|---|---|
| 第 1 周末 | `prompts.py`、`schemas.py`、mock JSON（让成员3 和 5 能开工） |
| 第 2 周末 | `client.py` + `image_analyzer.py` 真实可用 |
| 第 3 周末 | 错误分级与重试 |
| 之后 | 每改一次提示词就提一次 PR，并在描述里贴"用 5 张图前后对比" |

### 10.4 接口要变怎么办

- **改 `analyze_food` 签名**：不行。要先改 `00` §G。
- **加字段**（如 `alternative_names`）：先改 `00` §E.1，再改 `schemas.py`，再通知成员3 与成员1。
- **只改提示词**：可以自己提 PR，但要在描述里说明对 `status` 判定的影响。

---

## 11. GitHub 工作流

```bash
git checkout develop && git pull
git checkout -b feature/ai
git add app/ai tests/unit/test_ai_schema.py tests/fixtures/mock_ai_result.json
git commit -m "feat(ai): add image analyzer with contract validation"
git push -u origin feature/ai
```

提交示例：
- `feat(ai): add gemini client with json mode`
- `feat(ai): classify success/partial/error status`
- `fix(ai): map provider timeout to AI_PROVIDER_ERROR`
- `test(ai): add schema rejection cases`

PR 必须写清：
1. 是否改了提示词（是/否）；
2. 用几张图验证过；
3. 有没有改契约（默认"没有"）。

**永不提交**：`.env`、`tests/fixtures/photos/` 里的真实照片（会很大）、任何 Key。

---

## 12. 最终交付清单

### 12.1 代码

- [ ] `client.py`：唯一 import SDK 的文件，含 Key 检查、超时、异常收口
- [ ] `image_analyzer.py`：`analyze_food()` 完整实现，含状态判定与 warnings
- [ ] `prompts.py`：提示词常量，含"禁止算营养""重量必须是数字"
- [ ] `schemas.py`：`DetectedFood` / `AIAnalysis`，与契约 A 字段一致
- [ ] 重试策略按 §6.2 实现，最多 2 次尝试

### 12.2 测试与数据

- [ ] `tests/unit/test_ai_schema.py` ≥10 条，全绿
- [ ] `mock_ai_result.json`、`mock_ai_partial.json` 存在且能被他人直接使用
- [ ] 30 张照片回归表（第 5 周）

### 12.3 文档与协作

- [ ] 代码里 `grep -rn "google" app/ai` 只命中 `client.py`
- [ ] 代码里 `grep -rn "calories\|protein\|carbs\|fat" app/ai` 只出现在提示词的"禁止"句子中
- [ ] 与成员3 确认过：你的 `food_name` 能在他的库里命中（至少 10 个）
- [ ] 拔 Key / 断网 / 垃圾图三种情况都验证过

### 12.4 自检问题

1. 为什么契约 A 里没有 `meal_type`？
2. 模型返回 `"estimated_weight_g": "180g"` 时，你的代码会怎样？在哪一层拦住的？
3. "认不出食物"和"供应商挂了"，HTTP 表现分别是什么？
4. 重试为什么只允许 1 次？
5. 你的模块里有没有任何一行算营养？（必须是"没有"）
