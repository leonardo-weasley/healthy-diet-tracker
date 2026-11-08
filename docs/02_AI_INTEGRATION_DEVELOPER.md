# 02 — AI 集成开发指南（成员 2）

> 上位文档：[`00_MAIN_TECHNICAL_ROUTE.md`](00_MAIN_TECHNICAL_ROUTE.md)。冲突时以主路线为准。
> 你的任务是**把照片变成一份可信的 JSON**，不是让它算卡路里。算数是成员3 的事。
> 供应商：**DeepSeek 官方 API**（OpenAI 兼容格式，`google-genai` 已全面废弃）。

## 1. 角色与目标

### 1.1 你的职责

| 你负责 | 你不负责 |
|---|---|
| 选一家多模态 AI 供应商并跑通 | 营养计算（成员3） |
| 防御性图片读取校验（文件存在性、可读性） | 上传校验与落盘与预处理（成员1 已全部完成，你只拿到已处理的路径） |
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
2. 读取已经落盘的图片字节（**不缩放、不转格式、不改 EXIF**，见 §8.5）。
3. 提示词：**强制 JSON、禁止算营养、字段名与我们契约一致**。
4. 调用供应商并拿到 JSON 文本。
5. `json.loads` + Pydantic 校验。
6. 状态判定：`success` / `partial` / `error`。
7. 错误分级与重试策略。
8. `mock_ai_result.json` 供他人独立开发。

### 2.2 明确不做

- ❌ 不做上传接口、不碰 `uploads/` 落盘（成员1 负责，你只接收 `image_path`）
- ❌ 不做图片缩放 / EXIF 修正 / 统一格式（成员1 的 `utils/images.py` 已完成）
- ❌ 不算任何卡路里/蛋白质/碳水/脂肪，连"估算"都不许
- ❌ 不让 AI 决定 `meal_type`（用户选，成员1 传）
- ❌ 不做菜品分类枚举表校验（用 `^[a-z0-9_]+$` 就够）
- ❌ 不接第二家供应商（适配层留好，但 MVP 只接一家）
- ❌ 不做图片生成、翻译、聊天

### 2.3 三种状态如何判定（核心逻辑）

| 判定 | 条件 |
|---|---|
| `error` | `foods` 为空（`warnings` 必有 `no_food_detected`） |
| `partial` | 至少一项 `food_name is None` 或 `estimated_weight_g is None` |
| `success` | `foods` 非空，且每项都有 `food_name` 和 `estimated_weight_g` |

> 与 `00` §E.1 一致：`success` 必然 `warnings: []`。
> **模型自报的 `status` 与 `warnings` 一律丢弃**：模型写的告警每次都不一样（同一张图可能多一句 "not in standard list"），会同时污染 warnings 与 status。改为**派生**：`food_name` 为 null → `food_unrecognized: <name>`，重量为 null → `missing_weight: <name>`，无 foods → `no_food_detected`。这样 `status` 和 `warnings` 都是 `foods` 的纯函数，同一张图跑两次可复现。
> 不允许"AI 说认不出，我们偷偷猜一个最像的 ID"。宁可 `null`，让用户手动选。

---

## 3. 技术要用的东西

### 3.1 依赖

```bash
pip install "openai>=3.0,<4.0" "pydantic>=2.6" "Pillow>=10.0" "python-dotenv>=1.0" "pytest>=8.0"
```

> 用 **OpenAI 官方 SDK 的 Python 包**访问 DeepSeek，只改 `base_url` 与 `model`。DeepSeek 官方文档的示例代码就是这个写法。
> `Pillow` 是整个项目（成员1 用）的依赖，**你的模块不 import 它**。
> 本文按 `openai` 3.42 验证过下列 API：`OpenAI(...)`、`client.chat.completions.create(...)`、`extra_body`、`response_format`、`timeout`、`max_retries`。

### 3.2 供应商与模型

| 项 | 值 |
|---|---|
| 供应商 | DeepSeek 官方 API（MVP 只此一家） |
| OpenAI 兼容 base_url | `https://api.deepseek.com` |
| 鉴权 | `Authorization: Bearer $AI_API_KEY`（Key 在 `https://platform.deepseek.com/api_keys` 申请） |
| 模型名 | `deepseek-flash`（实际型号 DeepSeek-V4.1-Flash-1017） |
| 视觉能力 | `deepseek-flash` **支持**图片输入；`deepseek-v4-pro` **不支持**，别选错 |
| 图片格式 | 后端按**文件内容**识别，支持 JPEG / PNG / GIF / WebP（MIME 只是参考） |
| 结构化输出 | `response_format={"type": "json_object"}`，提示词里必须出现 "json" 字样并给示例 |
| 思考模式 | **默认开启**，必须显式关掉：`extra_body={"thinking": {"type": "disabled"}}` |
| 采样 | 非思考模式下 `temperature=0.0` 有效（0 最可复现）；思考模式下该参数无效 |
| 输出上限 | `max_tokens=2048`（不显式给会被默认成 8K，浪费且不利于排错） |
| 超时 | 30 秒（`AI_TIMEOUT_SECONDS`），Flask 是同步的，不能等 |
| SDK 内建重试 | 必须 `max_retries=0`，否则 SDK 自己偷偷重试，与 §6.2 冲突 |

文档链接（写死在这里，避免凭记忆）：

- 总入口 / 首次调用：<https://api-docs.deepseek.com/>
- **图片输入（Vision）**：<https://api-docs.deepseek.com/guides/vision/>
- **JSON Output**：<https://api-docs.deepseek.com/guides/json_mode>
- 思考模式：<https://api-docs.deepseek.com/guides/thinking_mode>
- Chat Completions 参数表：<https://api-docs.deepseek.com/api/create-chat-completion>
- 错误码：<https://api-docs.deepseek.com/quick_start/error_codes>
- 模型与价格：<https://api-docs.deepseek.com/quick_start/pricing>

### 3.3 需要理解的概念

| 概念 | 用途 |
|---|---|
| `response_format={"type":"json_object"}` | 让模型只返回 JSON。**但**：输出被判定不是 JSON 时，API 会把非 JSON 内容替换成空格，`content` 可能只有空格而 `finish_reason` 仍是 `stop` —— 必须把"空白 content"当成 `not_json` 处理并重试一次 |
| 提示词里写 "json" + 示例 | JSON 模式的硬性要求，不写就等于没开 |
| `thinking: disabled` | 思考模式默认开、会先吐 `reasoning_content`，同一张图更慢更贵；本任务是"看图填表"，关掉更稳 |
| base64 data URL | 本地文件没法给公网 URL，直接 `data:image/jpeg;base64,...` 内联（请求体上限 48 MiB，我们的图 ~1 MB 以内） |
| 图片计费 | 每张图按尺寸折 token，**单图上限 1024 tokens**；后端会把图缩到约 1300×1300 再推理，所以成员1 缩到 1024 px 已经足够，你**不需要**再缩 |
| `finish_reason` | `length` 表示 JSON 被截断（不是合法 JSON）；`content_filter` 表示被内容过滤；两者都要单独处理 |
| 图片只能放在 `user` 消息里 | 放 `system`/`assistant` 会直接 `400` |
| Pydantic `Literal` | 校验 `schema_version`、类型；模型自报的 `status` 不校验（反正要重算） |
| 超时 | 单次调用 ≤ `AI_TIMEOUT_SECONDS`；重试 1 次后整体 ≈ 60 秒上限 |
| 成本 | flash 高峰 $0.30/百万 输入、$1.20/百万 输出 → 一张图约 1500 输入 + 400 输出 ≈ **$0.001**，30 张照片回归 << $0.1 |

---

## 4. 你拥有的文件

```text
app/ai/__init__.py           # 导出 analyze_food
app/ai/client.py             # 唯一允许 import openai 的文件
app/ai/image_analyzer.py     # analyze_food()：编排 + 校验 + 状态判定
app/ai/prompts.py            # PROMPT_TEMPLATE、FOOD_NAME_HINTS
app/ai/schemas.py            # AIAnalysis, DetectedFood（Pydantic v2）
tests/unit/test_ai_schema.py # 你的校验测试
tests/unit/test_ai_client.py # 你的供应商适配测试（打桩，不联网）
tests/fixtures/mock_ai_result.json   # 与他人共用的 mock（与成员5 共同维护）
tests/fixtures/mock_ai_partial.json  # 部分识别的 mock（同上）
tests/fixtures/photos.json           # 照片清单：file / dish / note（照片本身不入 Git）
scripts/evaluate_portions.py         # 照片回归跑批：--repeat 2 --markdown docs/PORTION_EVAL.md
```

> `tests/fixtures/**` 的所有者是成员5（`00` §C.1）。你改这两个 mock 时**提 PR** 并 @成员5 合并，不要直接推。

### 4.1 别人怎么用你

| 他人 | 用法 | 禁止 |
|---|---|---|
| 成员1 | `from app.ai.image_analyzer import analyze_food` | 不许 import `app.ai.client` |
| 成员3 | 只消费返回值里的 `foods` | 不许依赖你内部的 Prompt |
| 成员5 | 在测试里 monkeypatch `analyze_food` | 不许在测试里真调 API |
| 成员4 | 只看到 `/analyze` 的 JSON | 不许直连 DeepSeek |

**边界**：`image_analyzer.py` 里**不许**出现 `openai`、`google`、`requests`、`httpx` 字样；写在 `client.py` 就够。

---

## 5. 输入输出契约

### 5.1 输入

```python
def analyze_food(image_path: str) -> dict: ...
```

| 项 | 说明 |
|---|---|
| 类型 | `str`，服务器本地可读路径，如 `uploads/2026/11/6f1c9a2e.jpg` |
| 是否一定存在 | 是（成员1 已校验并落盘） |
| 是否一定是图片 | 是（成员1 已用 Pillow 校验）；但你仍要防御性 `try` |
| 是否已预处理 | 是（EXIF 已修正、长边 ≤1024、已转 JPEG）；你**原样读字节**即可 |
| 是否需要 `meal_type` | **不需要**。`meal_type` 由用户选择，成员1 在保存时使用；契约 A 里没有这个字段 |
| 路径基准 | 相对路径按**仓库根目录**解析；成员1 保证 Flask 从根目录启动。测试里用 `Path(__file__)` 拼绝对路径，别依赖 CWD |

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
| `status` | string | 是 | `success` / `partial` / `error`，**由你重算** |
| `foods` | array | 是 | `0–20` 项 |
| `foods[].food_name` | string \| null | 是 | `^[a-z0-9_]+$`，≤60 字符；认不出填 `null` |
| `foods[].display_name` | string | 是 | 1–100 字符，可中文 |
| `foods[].estimated_weight_g` | number \| null | 是 | `0 < x ≤ 5000`；估不出填 `null` |
| `foods[].confidence` | number | 是 | `0 ≤ x ≤ 1` |
| `foods[].notes` | string \| null | 否 | ≤200 字符 |
| `warnings` | array[string] | 是 | 无告警填 `[]` |

**warnings 前缀（你这一侧）**：`food_unrecognized: <display_name>`、`missing_weight: <display_name>`、`no_food_detected`。
营养模块（`00` §E.3）用的是 `food_not_matched:` / `missing_weight:` / `invalid_weight:`，**两套前缀分属不同契约**，前端分阶段展示，不要混进同一个列表。

### 5.3 错误行为

| 情况 | 抛出 | `details.reason` | 是否重试 | 谁接住 |
|---|---|---|---|---|
| `AI_API_KEY` 未配置 | `AiProviderError` | `missing_api_key` | 否 | 成员1 的路由 |
| 401 Key 无效 | `AiProviderError` | `auth` | 否 | 同上 |
| 402 余额不足 | `AiProviderError` | `insufficient_balance` | 否 | 同上 |
| 429 限流 | `AiProviderError` | `rate_limited` | 是，等 2 秒 1 次 | 同上 |
| 500 / 503 供应商故障 | `AiProviderError` | `provider_5xx` | 是，1 次 | 同上 |
| 400 / 422 请求参数错 | `AiProviderError` | `provider_4xx` | 否 | 同上（**这是你的 bug，先看文档**） |
| 超时 | `AiProviderError` | `timeout` | 是，1 次 | 同上 |
| 连不上网 | `AiProviderError` | `network` | 是，1 次 | 同上 |
| 图片文件不见了 | `AiProviderError` | `file_missing` | 否 | 同上 |
| 返回空白 / 非 JSON | `InvalidAiResponse` | `not_json` | 是，1 次（同 prompt） | 同上 |
| JSON 被 `max_tokens` 截断 | `InvalidAiResponse` | `truncated` | 否 | 同上 |
| 被内容过滤 | `InvalidAiResponse` | `content_filtered` | 否 | 同上 |
| JSON 缺字段/类型错 | `InvalidAiResponse` | `schema` | 否 | 同上 |
| 图中无食物 | **不抛异常**，返回 `status: "error"` | — | — | — |

---

## 6. 必须实现的函数接口

```python
# app/ai/client.py
def call_vision_api(image_path: str, prompt: str) -> dict: ...


# app/ai/image_analyzer.py
def analyze_food(image_path: str) -> dict: ...
```

| 函数 | 输入 | 输出 | 抛出 |
|---|---|---|---|
| `call_vision_api(image_path, prompt)` | 本地图片路径 + 提示词全文 | 模型返回的原始 dict（**仅** `json.loads`，不做业务校验） | `AiProviderError`（网络/超时/鉴权/额度/参数）、`InvalidAiResponse`（非 JSON / 截断 / 被过滤） |
| `analyze_food(image_path)` | 本地图片路径 | 契约 A（已通过 Pydantic 校验，`status` 已重算） | `AiProviderError` / `InvalidAiResponse` |

### 6.1 职责划分

| 文件 | 做什么 | 不做 |
|---|---|---|
| `client.py` | 装配 SDK、base64 编码、发请求、取文本、判 `finish_reason`、`json.loads`、异常映射 | 状态判定、字段改名、组装 warnings |
| `image_analyzer.py` | 填提示词、调 client、Pydantic 校验、重算状态、组装 warnings、日志 | 任何 SDK 调用 |

### 6.2 重试策略（严格按此实现）

| 失败类型 | 是否重试 | 次数 |
|---|---|---|
| 超时 / 网络 / 5xx（500、503） | 是 | 共 2 次尝试（1 次重试） |
| 429 限流 | 是 | 1 次，间隔 2 秒 |
| 返回空白或非 JSON | 是 | 1 次，**同一 prompt**（不改提示词） |
| 401 / 402 / 400 / 422 | 否 | 直接抛 —— 重试也不会好 |
| 被 `max_tokens` 截断 | 否 | 直接抛（要改的是 `max_tokens`，不是重试） |
| JSON 结构不符合契约 | 否 | 直接抛 `InvalidAiResponse(reason="schema")` |
| 图中无食物 | 否（不是失败） | 返回 `error` 状态 |

**禁止**：无限重试、在 for 循环里重试同一张图超过 2 次、把重试当异常处理的主要手段、依赖 SDK 内建重试（必须 `max_retries=0`）。

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

### 步骤 1：拿 Key，跑通最小调用（第 1 周）

1. 去 `platform.deepseek.com` 建 Key，写进 `.env` 的 `AI_API_KEY`（变量名沿用 `00` §K.1，值填 DeepSeek 的 Key）。
2. **先用 curl 验证一次**（比写代码快，能立刻定位是 Key 问题还是代码问题）：

```bash
curl https://api.deepseek.com/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AI_API_KEY" \
  -d '{
    "model": "deepseek-flash",
    "messages": [{
      "role": "user",
      "content": [
        {"type": "text", "text": "这张图里有哪些食物？用 json 返回 {\"foods\": []} 结构"},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,'"$(base64 -w0 tests/fixtures/sample_meal.jpg)"'"}}
      ]
    }],
    "response_format": {"type": "json_object"},
    "thinking": {"type": "disabled"},
    "max_tokens": 2048
  }'
```

3. 再写 `app/ai/client.py` 的最小脚本（不是 Flask，先单独跑），打印 `json.loads(...)` 的结果。

> PowerShell 里没有 `$(base64 -w0 ...)`，等价写法：
> `$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes("tests\fixtures\sample_meal.jpg"))`，
> 再把它拼进 JSON 字符串。也可以干脆跳过 curl，直接用第 3 步的 Python 脚本验证。

**完成标准**：终端能打印出一段 JSON 文本；`curl` 与 Python 两条路都通。

### 步骤 2：写提示词与 Pydantic 模型（第 1 周末）

1. `prompts.py` 写 `PROMPT_TEMPLATE`（见 §8.1）。
2. `schemas.py` 写 `DetectedFood`、`AIAnalysis`（见 §8.2）。
3. 手工造 `tests/fixtures/mock_ai_result.json` 与 `mock_ai_partial.json`。

**完成标准**：`AIAnalysis.model_validate(mock)` 不报错；把 `estimated_weight_g` 改成 `"180g"` 会报错。

### 步骤 3：串起 `analyze_food()`（第 2 周）

1. `read_bytes()` → base64 → data URL（**不缩放、不改格式**）。
2. 调 `call_vision_api()`。
3. `AIAnalysis.model_validate(raw)`。
4. 重算 `status`（§2.3），补 `warnings`。
5. 返回 dict，并按 `00` §H.4 打日志。

**完成标准**：对 10–20 张不同照片，每次返回都能被 `AIAnalysis` 校验通过。

### 步骤 4：错误分级（第 2 周末）

1. 把 SDK 抛的异常映射成 `AiProviderError`（带 `reason`，见 §5.3 与 §8.3 的 `_classify`）。
2. 区分"空白 content"、"被截断"、"结构不符"。
3. 实现 §6.2 的重试，并确认 `max_retries=0`。
4. 确保单次调用最长不超过 `AI_TIMEOUT_SECONDS`（默认 30 秒）。

**完成标准**：把 Key 改错、断网、传纯白图片，三种情况分别得到预期的错误码/状态。

### 步骤 5：未知食物打磨（第 3–4 周）

1. 提示词里强化："不确定时 `food_name` 必须为 null，不许猜"。
2. 提示词里带上 `FOOD_NAME_HINTS`（与成员3 对齐的标准 ID，见 §8.1），提高 `match_food()` 命中率。
3. 至少构造 5 个"半认不出"的样例，确认输出 `partial` + `warnings`。
4. 与成员1 确认 `warnings` 格式：`food_unrecognized: <name>`、`missing_weight: <name>`。

### 步骤 6：30 张照片回归（第 5 周）

1. 拍/找 30 张真实餐食照片，放 `tests/fixtures/photos/`（**不入 Git**，本地保留）。
2. 用 `scripts/evaluate_portions.py` 记录：识别出几个、认错几个、份量误差。
3. 把结果填进 `docs/PORTION_EVAL.md`（或表格形式交给成员5）。

**完成标准**：至少 25/30 张能返回可用结果；能说清 5 类失败原因。

---

## 8. 代码示例

### 8.1 提示词（`app/ai/prompts.py`）

```python
PROMPT_TEMPLATE = """You are a food recognition assistant for a calorie-tracking app.

Analyze the meal photograph and identify every distinct food item that is visible.

For each item estimate:
1. A standardized English identifier (lowercase snake_case).
2. The edible weight in grams.
3. A recognition confidence between 0 and 1.

Return ONLY one json object. No markdown fence, no commentary, no extra keys.

{
  "schema_version": "1.0",
  "status": "success",
  "foods": [
    {
      "food_name": "cooked_white_rice",
      "display_name": "White rice",
      "estimated_weight_g": 180.0,
      "confidence": 0.95,
      "notes": null
    }
  ],
  "warnings": []
}

Rules:
- Do not invent food items that are not visible in the photograph.
- List each distinct dish ONCE. Do not split one dish into components.
- Do NOT list sauces, gravies, oils, dressings, dips, garnish or aromatics
  (spring onion, chili, cinnamon, star anise, ...) as separate items.
  Fold them into the dish they belong to. Only a clearly separate dish counts.
- "food_name" MUST be copied exactly from the standard list below.
  If the item is not in that list, set "food_name" to null.
  NEVER invent a new snake_case identifier.
- If a food cannot be identified, set "food_name" to null and describe it in "display_name".
- If a weight cannot be estimated, set "estimated_weight_g" to null.
- "estimated_weight_g" must be a json number (180.0), never a string like "180g".
- "display_name" may be Chinese, 1-100 characters.
- "confidence" is recognition confidence, not portion accuracy, between 0 and 1.
- "notes" is optional: null when confident, a short sentence when not.
- NEVER estimate calories, protein, carbohydrates or fat, and never add such fields.
  Nutrition is computed by another module.
- At most 20 items. If nothing edible is visible, return an empty "foods" list
  and one entry in "warnings".

Standard food names (the ONLY allowed values of "food_name"), with their usual
Chinese names for reference:
{food_name_hints}
"""
```

`FOOD_NAME_HINTS` 单独一个常量，与 `food_database.json` 的 `food_name` 一一对应（**只同步名字，不同步任何营养数值**）。当前这 29 条来自 `03` 文档 §5.2 的初始数据：

```python
# 与 app/nutrition/food_database.json 的 food_name 一一对应。
# 成员3 改库时必须同步这里（同一个 PR 或紧随其后的 PR）。
# 附中文名是给模型做映射用的：红烧肉 -> pork_belly_braised，命中率远高于只给英文 ID。
FOOD_NAME_HINTS = """- cooked_white_rice（白米饭）
- brown_rice_cooked（糙米饭）
- rice_chicken_bowl（鸡肉饭碗）
- cooked_noodles（面条）
- cooked_pasta（意面）
- white_bread（白面包）
- whole_wheat_bread（全麦面包）
- oatmeal_cooked（燕麦粥）
- grilled_chicken_breast（鸡胸肉）
- beef_stir_fry（炒牛肉）
- pork_belly_braised（红烧肉）
- salmon_cooked（三文鱼）
- shrimp_cooked（虾）
- boiled_egg（水煮蛋）
- fried_egg（煎蛋／炒蛋）
- tofu_firm（北豆腐）
- steamed_broccoli（西兰花）
- boiled_potato（土豆）
- french_fries（薯条）
- lettuce（生菜）
- tomato（番茄）
- cucumber（黄瓜）
- milk_whole（全脂牛奶）
- plain_yogurt（原味酸奶）
- banana（香蕉）
- apple（苹果）
- vegetable_soup（蔬菜汤）
- milk_tea（奶茶）
- cola（可乐）"""


def food_name_hints() -> list[str]:
    """解析出所有合法 food_name——测试和回归脚本共用这一份解析，别再各写一套。"""
    return re.findall(r"^\s*-\s*([a-z0-9_]+)", FOOD_NAME_HINTS, re.M)


def build_prompt() -> str:
    # 用 replace 而不是 str.format：提示词里的 JSON 示例带大量 { }，
    # 走 format 会被当成占位符（KeyError），escape 成 {{ }} 又极难维护。
    return PROMPT_TEMPLATE.replace("{food_name_hints}", FOOD_NAME_HINTS)
```

要点：

- 提示词里**直接写契约字段名**，模型输出就不用二次改名。
- 明确"不许算营养"，否则模型一定会附赠卡路里。
- 明确"重量必须是数字"，能挡掉 `"180g"`。
- 必须出现 **json** 字样 + 一个完整示例，这是 JSON 模式的硬性开关条件。
- 白名单只给"名字"，不给数值，避免与成员3 的数据形成第二份营养库。
- **漂移防护**（写进 `tests/unit/test_ai_schema.py`，测试里跨模块读文件不算模块依赖）：

```python
# 追加到 tests/unit/test_ai_schema.py
from app.ai.prompts import food_name_hints


def test_food_name_hints_exist_in_database():
    # food_database.json 的形状是 {"foods": [ {...}, ... ]}（见 03 文档 §5.1）
    db = json.loads(Path("app/nutrition/food_database.json").read_text(encoding="utf-8"))
    known = {row["food_name"] for row in db["foods"]}
    hints = set(food_name_hints())
    assert hints <= known, f"not in food_database.json: {sorted(hints - known)}"
```

### 8.2 Pydantic 模型（`app/ai/schemas.py`）

```python
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
    # 模型自报状态仅供参考，最终状态由 image_analyzer._judge_status 重算，
    # 所以这里不校验枚举值——避免模型写个 "unknown" 就白白 502。
    status: str | None = None
    foods: list[DetectedFood] = Field(default_factory=list, max_length=20)
    warnings: list[str] = Field(default_factory=list)
```

> `food_name: None` 要通过校验——`str | None` 已经允许；但 `display_name` 不允许空串。
> `extra="ignore"`：模型偶尔会附赠 `calories` 之类字段，直接丢弃，不要因此报 502。
> 注意 `food_name` / `estimated_weight_g` 有 `default=None`，意味着模型**完全漏掉这个键**也能通过校验。契约要求"键必须存在"，因此测试里要断言 `model_dump().keys()`（§9.1 AI1）。

### 8.3 供应商调用（`app/ai/client.py`）

```python
"""DeepSeek 适配层——全项目唯一允许 import openai 的文件。"""

import base64
import json
import logging
import os
import time
from pathlib import Path

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from ..utils.errors import AiProviderError, InvalidAiResponse

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_OUTPUT_TOKENS = 2048
RATE_LIMIT_BACKOFF_SECONDS = 2.0

# 只有这些 reason 允许重试（与文档 §6.2 一一对应）
RETRYABLE_REASONS = {"timeout", "network", "rate_limited", "provider_5xx", "not_json"}

_MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """懒初始化单例。Key 缺失时立即抛出，不延到请求时。"""
    global _client
    if _client is not None:
        return _client
    api_key = os.getenv("AI_API_KEY", "").strip()
    if not api_key:
        raise AiProviderError(
            "AI_API_KEY is not configured.",
            details={"reason": "missing_api_key"},
        )
    _client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("AI_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
        timeout=float(os.getenv("AI_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)),
        # 重试由 call_vision_api 统一实现；SDK 内建重试会破坏"最多 2 次尝试"
        max_retries=0,
    )
    return _client


def _classify(exc: Exception) -> str:
    """把 SDK 的异常翻译成契约里的 reason（见 §5.3）。"""
    if isinstance(exc, APITimeoutError):          # 注意：它也是 APIConnectionError 的子类
        return "timeout"
    if isinstance(exc, APIConnectionError):
        return "network"
    if isinstance(exc, APIStatusError):
        code = exc.status_code
        if code == 401:
            return "auth"
        if code == 402:
            return "insufficient_balance"
        if code == 429:
            return "rate_limited"
        if 500 <= code <= 599:
            return "provider_5xx"
        return "provider_4xx"
    return "unknown"


def _build_user_content(image_path: str, prompt: str) -> list[dict]:
    """图片必须是 base64 data URL，且只能放在 user 消息里。"""
    path = Path(image_path)
    if not path.is_file():
        raise AiProviderError(
            "Image file not found on disk.",
            details={"reason": "file_missing", "path": str(path)},
        )
    mime = _MIME_BY_SUFFIX.get(path.suffix.lower(), "image/jpeg")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
    ]


def _call_sdk_once(image_path: str, prompt: str) -> dict:
    """发一次请求。仅 json.loads，不做业务校验。"""
    client = _get_client()
    content = _build_user_content(image_path, prompt)
    try:
        response = client.chat.completions.create(
            model=os.getenv("AI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
            messages=[{"role": "user", "content": content}],
            response_format={"type": "json_object"},
            temperature=0.0,          # 非思考模式才有效；0 让同一张图的结果尽量可复现
            max_tokens=MAX_OUTPUT_TOKENS,
            extra_body={"thinking": {"type": "disabled"}},   # 默认是开的，必须显式关
        )
    except Exception as exc:          # SDK 异常类型较杂，统一收口后再细分
        raise AiProviderError(
            "The AI provider call failed.",
            details={"reason": _classify(exc), "status_code": getattr(exc, "status_code", None)},
        ) from exc

    choice = response.choices[0] if response.choices else None
    if choice is None:
        raise InvalidAiResponse(
            "The AI provider returned no choices.",
            details={"reason": "not_json"},
        )
    if choice.finish_reason == "length":
        raise InvalidAiResponse(
            "The AI response was truncated by max_tokens.",
            details={"reason": "truncated"},
        )
    if choice.finish_reason == "content_filter":
        raise InvalidAiResponse(
            "The AI response was blocked by the content filter.",
            details={"reason": "content_filtered"},
        )

    text = (choice.message.content or "").strip()
    if not text:
        # JSON 模式下输出不是 JSON 时，API 会用空格替换 → content 可能全空
        raise InvalidAiResponse(
            "The AI returned empty content.",
            details={"reason": "not_json"},
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidAiResponse(
            "The AI response was not valid JSON.",
            details={"reason": "not_json", "preview": text[:200]},
        ) from exc


def call_vision_api(image_path: str, prompt: str) -> dict:
    """输入：本地图片路径 + 提示词全文
       输出：模型返回的原始 dict（仅 json.loads，不做业务校验）
       重试策略（与 §6.2 一致）：最多 2 次尝试，只有 RETRYABLE_REASONS 才重试。
       抛出：AiProviderError / InvalidAiResponse"""
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            return _call_sdk_once(image_path, prompt)
        except (AiProviderError, InvalidAiResponse) as exc:
            last_exc = exc
            reason = (exc.details or {}).get("reason", "")
            if attempt == 0 and reason in RETRYABLE_REASONS:
                if reason == "rate_limited":
                    time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
                log.warning("retrying AI call reason=%s attempt=%d", reason, attempt + 2)
                continue
            raise
    raise last_exc  # pragma: no cover - 循环必然 return 或 raise
```

> 这段是**供应商相关实现**。参数名以 <https://api-docs.deepseek.com/api/create-chat-completion> 为准；写不通先查文档，不要凭猜改参数。

### 8.4 编排与状态判定（`app/ai/image_analyzer.py`）

```python
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

    理由：模型写的告警每次都不一样（同一张图可能多一句 "not in standard list"），
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
    """§2.3：error / partial / success，模型自报的 status 不参与。"""
    if not analysis.foods:
        return "error"
    if any(f.food_name is None or f.estimated_weight_g is None for f in analysis.foods):
        return "partial"
    return "success"


def analyze_food(image_path: str) -> dict:
    """调 call_vision_api（内含重试）→ Pydantic 校验 → 判状态 → 组 warnings。"""
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
```

> 日志字段（`image_path`、`model`、`status`、`foods` 数、`elapsed_ms`）按 `00` §H.4 的要求给全，别只记一个 status。

### 8.5 图片预处理——**你不需要做**

成员 1 的 `utils/images.py` 已经在 `/analyze` 路由中一次性完成了：

- MIME 白名单校验（JPEG / PNG / WebP）
- 文件大小检查（≤ 8 MB）
- EXIF 方向修正（`ImageOps.exif_transpose`）
- 长边缩放到 1024 px
- 落盘到 `uploads/YYYY/MM/uuid.jpg`

你拿到的 `image_path` **已经是可直接发送给 API 的最终文件**。你的代码里**不许**再对图片做任何缩放、EXIF 修正或覆盖保存——这些操作写在 `client.py` 或 `image_analyzer.py` 里会与成员 1 的逻辑冲突，且可能破坏原图。

另外：DeepSeek 后端自己也会把图缩到约 1300×1300 再推理（单图 ≤1024 tokens），所以 1024 px 已经足够，再缩只会损失细节。

你唯一需要做的防御性检查是确认文件存在且可读（见 §8.3 `_build_user_content` 的 `path.is_file()` 判断）。

---

## 9. 测试要求

### 9.1 用例

| # | 用例 | 做法 | 期望 |
|---|---|---|---|
| AI1 | 合法 JSON 通过 | 喂 `mock_ai_result.json` | 校验通过，`len(foods)==2`，且 `model_dump()` 键集 == 契约 A 五键 |
| AI2 | 重量是字符串 | 把 `180.0` 改 `"180g"` | `ValidationError` → `InvalidAiResponse(reason="schema")` |
| AI3 | `confidence=1.5` | 改值 | 校验失败 |
| AI4 | 缺 `display_name` | 删字段 | 校验失败 |
| AI5 | 空 `foods` + warnings | `status: "error"` | 校验通过，状态判为 `error` |
| AI6 | 一项 `food_name: null` | `mock_ai_partial.json` | `partial`，warnings 含 `food_unrecognized` |
| AI7 | 一项缺重量 | 改 `estimated_weight_g: null` | `partial`，warnings 含 `missing_weight` |
| AI8 | 供应商抛异常 | monkeypatch `call_vision_api` 抛 `AiProviderError` | 原样上抛，不吞 |
| AI9 | 空白 content（JSON 模式兜底） | 打桩 `client.chat.completions.create` 返回 `content="   "` | `InvalidAiResponse(reason="not_json")`，重试 1 次后上抛 |
| AI10 | 截断 | 打桩 `finish_reason="length"` | `InvalidAiResponse(reason="truncated")`，**不重试** |
| AI11 | 重试只发生 1 次 | 打桩 `_call_sdk_once` 持续抛 `timeout`，计数 | 调用 2 次后上抛 |
| AI12 | 401 不重试 | 打桩 `_call_sdk_once` 抛 `auth` | 调用 1 次即上抛 |
| AI13 | 模型自报 status 乱写 | `foods` 完整但 `status: "unknown"` | 不 502，最终 `success` |
| AI14 | 模型自写 warnings | `foods` 完整 + `warnings: ["blurry_image"]` | warnings 被丢弃，最终 `success`，`warnings: []` |
| AI15 | 模型编造标准 ID | 喂 `food_name: "pork_intestine"`（不在白名单） | schema 只校验格式，**能过**；命中率问题靠提示词与离线回归表把关（§7 步骤 5） |

### 9.2 测试要点

- 全部用 `monkeypatch`，**不许**真调 API、不许要真实 Key。
- 断言 `model_dump()` 的字段集合，防止有人偷偷加字段。
- 用 `pytest.approx` 比浮点。
- 打桩 SDK 时用 `SimpleNamespace` 造响应，不要造真对象：

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
    assert set(analysis.foods[0].model_dump()) == {
        "food_name", "display_name", "estimated_weight_g", "confidence", "notes",
    }


def test_weight_as_string_is_rejected():
    bad = json.loads(json.dumps(MOCK))
    bad["foods"][0]["estimated_weight_g"] = "180g"
    with pytest.raises(ValidationError):
        AIAnalysis.model_validate(bad)
```

```python
# tests/unit/test_ai_client.py —— 打桩 SDK，不联网
from types import SimpleNamespace

import pytest

from app.ai import client as ai_client
from app.utils.errors import AiProviderError, InvalidAiResponse


def _stub(monkeypatch, *, content="", finish_reason="stop"):
    fake = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kw: SimpleNamespace(
                    choices=[SimpleNamespace(
                        finish_reason=finish_reason,
                        message=SimpleNamespace(content=content),
                    )]
                )
            )
        )
    )
    monkeypatch.setattr(ai_client, "_get_client", lambda: fake)


def test_blank_content_is_not_json(tmp_path, monkeypatch):
    img = tmp_path / "a.jpg"
    img.write_bytes(b"\xff\xd8\xff")
    _stub(monkeypatch, content="   ")
    with pytest.raises(InvalidAiResponse) as exc:
        ai_client.call_vision_api(str(img), "return json")
    assert exc.value.details["reason"] == "not_json"
```

> 注意 AI9/AI11 的计数断言：**重试发生在 `call_vision_api`，不在 `_call_sdk_once`**。测"重试次数"要打桩 `_call_sdk_once`；测"空白 content"要打桩 `_get_client` 返回的假 client。

---

## 10. 集成说明

### 10.1 你的依赖

| 依赖 | 提供者 | 没完成时 |
|---|---|---|
| 落盘后的图片路径 | 成员1 | 自己拿一张本地图跑脚本，不经过 HTTP |
| `ApiError` / `AiProviderError` / `InvalidAiResponse` | 成员1 | 先按 `00` §G.2 的签名本地建一个临时版本，最终以他的为准 |
| `APP_TIMEZONE` 等配置 | 成员1 | 与 AI 无关，忽略 |
| `.env` 里的变量名 | 成员1 | 见下表，缺哪个问他要 |

`.env` 里与 AI 相关的变量（请成员1 一并写进 `.env.example`）：

```text
AI_API_KEY=sk-...            # DeepSeek 的 Key，绝不提交
AI_BASE_URL=https://api.deepseek.com
AI_MODEL=deepseek-flash
AI_TIMEOUT_SECONDS=30
```

> 变量名沿用 `00` §K.1 的 `AI_API_KEY`（供应商无关的命名），值填 DeepSeek 的 Key。
> `AI_MODEL` 只填 `deepseek-flash` 或 `deepseek-v4-pro`；**`deepseek-v4-pro` 不支持图片**，别拿去跑 `/analyze`。

### 10.2 依赖你的

| 模块 | 用你什么 | 注意事项 |
|---|---|---|
| 成员1（`/analyze`） | `analyze_food(image_path)` | 返回值会原样放进 `data`，别忘了 `image_path` 由他补 |
| 成员3 | 只吃 `foods[]` 的 `food_name` / `display_name` / `estimated_weight_g` | 你的 `food_name` 必须能在他的库里命中 |
| 成员5 | 用 `monkeypatch` 替换你 | 你必须是**可替换的纯边界**：文件顶部 import 函数，不要内联调用 |
| 成员4 | `data.status` 与 `data.warnings` | `data.status` 可能是 `partial`/`error`，UI 要能处理 |

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
- **换供应商**：先改 `00` §B（技术选型）并全组确认，再改本文件 §3、§8.3。

---

## 11. GitHub 工作流

```bash
git checkout develop && git pull
git checkout -b feature/ai
git add app/ai tests/unit/test_ai_schema.py tests/unit/test_ai_client.py tests/fixtures/mock_ai_result.json
git commit -m "feat(ai): add deepseek vision client with contract validation"
git push -u origin feature/ai
```

提交示例：

- `feat(ai): switch provider to deepseek-flash`
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

- [ ] `client.py`：唯一 import SDK 的文件，含 Key 检查、`timeout`、`max_retries=0`、异常分级
- [ ] `image_analyzer.py`：`analyze_food()` 完整实现，含状态重算与 warnings
- [ ] `prompts.py`：提示词常量，含"禁止算营养""重量必须是数字""json 示例"
- [ ] `schemas.py`：`DetectedFood` / `AIAnalysis`，与契约 A 字段一致
- [ ] 重试策略按 §6.2 实现，最多 2 次尝试

### 12.2 测试与数据

- [ ] `tests/unit/test_ai_schema.py` + `test_ai_client.py` ≥10 条，全绿
- [ ] `mock_ai_result.json`、`mock_ai_partial.json` 存在且能被他人直接使用
- [ ] 30 张照片回归表（第 5 周）

### 12.3 文档与协作

- [ ] `grep -rn "openai" app/ai` 只命中 `client.py`
- [ ] `grep -rn "google\|gemini" app/ai` 无输出
- [ ] `grep -rn "calories\|protein\|carbs\|fat" app/ai` 只出现在提示词的"禁止"句子中
- [ ] 与成员3 确认过：你的 `food_name` 能在他的库里命中（至少 10 个），`FOOD_NAME_HINTS` 已对齐
- [ ] 拔 Key / 断网 / 垃圾图三种情况都验证过

### 12.4 自检问题

1. 为什么契约 A 里没有 `meal_type`？
2. 模型返回 `"estimated_weight_g": "180g"` 时，你的代码会怎样？在哪一层拦住的？
3. "认不出食物"和"供应商挂了"，HTTP 表现分别是什么？
4. 重试为什么只允许 1 次？为什么必须关掉 SDK 的 `max_retries`？
5. JSON 模式下 `content` 只有空格是怎么回事？你重试了吗？
6. 你的模块里有没有任何一行算营养？（必须是"没有"）

