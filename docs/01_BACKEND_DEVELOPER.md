# 01 — 后端与集成开发指南（成员 1）

> 上位文档：[`00_MAIN_TECHNICAL_ROUTE.md`](00_MAIN_TECHNICAL_ROUTE.md)。本文件与它冲突时，以主路线为准。
> 你是**协调者**，不是"把所有逻辑都写一遍的人"。AI、营养、数据库的算法都属于别人，你只负责把它们的接口接起来。

## 1. 角色与目标

### 1.1 你的职责

| 你负责 | 你不负责 |
|---|---|
| Flask 应用初始化、配置、扩展装配 | 识别食物的提示词、调用 Gemini（成员2） |
| 6 个 REST 路由的请求解析与响应序列化 | 营养计算公式、食物库数值（成员3） |
| 服务层编排：校验 → 调模块 → 组装 → 提交 | 建表、仓储实现、聚合 SQL（成员5） |
| 上传文件校验（类型/大小/EXIF/缩放/落盘） | 页面结构、CSS、Chart.js（成员4） |
| 统一异常体系与错误响应翻译 | 改契约（需全组同意） |
| 集成、联调、`develop` 分支健康 | — |

### 1.2 最终交付物（一句话）

> 一个 `python run.py` 就能启动的 Flask 应用，提供 `00_MAIN_TECHNICAL_ROUTE.md` §F 规定的 6 个接口，接上 AI、营养、数据库三个模块，所有错误都走统一信封。

### 1.3 成功标准

- 别人 clone 下来，照 README 三步就能跑。
- 前端只读 `00` 的 §F 就能对接，不需要问你。
- 你不在时，任何人能读懂 `meal_service.py` 的编排顺序。
- 所有错误响应都是契约 F，没有一处返回 HTML 错误页或裸 500。

---

## 2. 要构建什么

### 2.1 六个接口（一个不多，一个不少）

| # | 方法 | 路径 | 归属文件 |
|---|---|---|---|
| 1 | POST | `/api/v1/analyze` | `app/routes/analysis.py` |
| 2 | POST | `/api/v1/meals` | `app/routes/meals.py` |
| 3 | GET | `/api/v1/meals` | `app/routes/meals.py` |
| 4 | GET | `/api/v1/meals/<int:meal_id>` | `app/routes/meals.py` |
| 5 | DELETE | `/api/v1/meals/<int:meal_id>` | `app/routes/meals.py` |
| 6 | GET | `/api/v1/dashboard/daily` | `app/routes/dashboard.py` |

另有 4 个**页面路由**（只渲染模板，不返回 JSON）：`GET /`、`GET /upload`、`GET /result`、`GET /history`。

### 2.2 明确不做

- ❌ 不做 `PATCH`/`PUT`（v1 非目标，改数据请删除后重存）
- ❌ 不做用户注册、登录、会话、权限
- ❌ 不做分页游标、排序参数、模糊搜索
- ❌ 不在路由里写营养计算或 SQL
- ❌ 不引入 Flask-RESTful、Flask-Marshmallow 等额外框架

### 2.3 六个接口的行为要点

| 接口 | 关键行为 |
|---|---|
| `POST /analyze` | 保存图片 → 调 `analyze_food()` → 返回 `image_path` + 契约 A；**认不出也返回 200** |
| `POST /meals` | Pydantic 校验 → 调 `calculate_meal_nutrition()` → 组装 → `save_meal()` → 返回契约 D，状态码 201 |
| `GET /meals` | 解析 `date_from`/`date_to`/`limit`/`offset` → `get_meals()` → 返回摘要 + `pagination` |
| `GET /meals/{id}` | `get_meal()` → 契约 D；不存在返回 404 |
| `DELETE /meals/{id}` | `delete_meal()` → `{meal_id, deleted: true}`；不存在返回 404 |
| `GET /dashboard/daily` | 缺省日期 = `APP_TIMEZONE` 的今天 → `get_daily_summary()` → 契约 E |

---

## 3. 技术要用的东西

### 3.1 依赖

```bash
pip install "Flask>=3.0" "Flask-SQLAlchemy>=3.1" "pydantic>=2.6" "python-dotenv>=1.0" "Pillow>=10.0"
```

### 3.2 需要理解的概念（只需这些）

| 概念 | 在本项目里的用途 | 一句话说明 |
|---|---|---|
| Application Factory | `create_app()` | 让测试能造出独立 app 实例，不污染全局 |
| Blueprint | 4 个蓝图 | 把路由按领域拆开，`__init__.py` 里统一注册 |
| `request.files` | 上传 | 读 multipart 文件，**不要**从 JSON 里读 base64 |
| `jsonify` | 响应 | 返回 JSON，注意 `charset=utf-8` |
| `errorhandler` | 统一错误 | 把 `ApiError` 翻成契约 F |
| Pydantic BaseModel | 请求体校验 | 在进入业务逻辑前拦掉脏数据 |
| 蓝图 `url_prefix` | `/api/v1` | 版本化前缀只在一处拼接 |
| `app.config` | 配置 | 从 `.env` 读，不要在代码里硬编码 |

---

## 4. 你拥有的文件

```text
run.py                              # 启动入口
app/__init__.py                     # create_app()
app/config.py                       # Config 类
app/routes/__init__.py              # register_blueprints(app)
app/routes/pages.py                 # 4 个页面路由
app/routes/analysis.py              # POST /api/v1/analyze
app/routes/meals.py                 # 4 个 meals 路由
app/routes/dashboard.py             # GET /api/v1/dashboard/daily
app/services/__init__.py
app/services/meal_service.py        # 编排（核心文件）
app/services/schemas.py             # 请求体 Pydantic 模型
app/utils/__init__.py
app/utils/errors.py                 # ApiError 体系
app/utils/images.py                 # 上传校验与落盘
app/utils/timeutil.py               # UTC ↔ 本地时间
tests/unit/test_api.py              # 你的 API 测试
tests/integration/test_api_errors.py
```

**别人可以怎么用你的东西**

| 他人 | 用法 | 禁止 |
|---|---|---|
| 成员2 | 什么都不用你做；你调他的 `analyze_food()` | 不要你去改 `ai/` |
| 成员3 | 你调 `calculate_meal_nutrition()`、`match_food()` | 不要在路由里重算营养 |
| 成员4 | 只通过 HTTP 调你的 6 个接口 | 不读你的 Python 代码 |
| 成员5 | 你调 `save_meal`/`get_meal`/`get_meals`/`get_daily_summary` | 不在路由里直接 `db.session` |

---

## 5. 输入输出契约

完整定义见 `00` §E。你只需要**原样搬运**，不要改写字段名。

### 5.1 POST /api/v1/analyze

输入：`multipart/form-data`

| 字段 | 类型 | 必填 | 校验 |
|---|---|---|---|
| `image` | file | 是 | JPEG/PNG/WebP，≤8 MB，Pillow 可打开 |
| `meal_type` | string | 是 | `breakfast`/`lunch`/`dinner`/`snack` |

输出 `200`：

```json
{
  "status": "success",
  "data": {
    "image_path": "uploads/2026/11/6f1c9a2e.jpg",
    "schema_version": "1.0",
    "status": "partial",
    "foods": [
      { "food_name": "cooked_white_rice", "display_name": "White rice",
        "estimated_weight_g": 180.0, "confidence": 0.95, "notes": null },
      { "food_name": null, "display_name": "某种深色酱汁",
        "estimated_weight_g": null, "confidence": 0.42, "notes": "Cannot identify" }
    ],
    "warnings": ["food_unrecognized: 某种深色酱汁"]
  }
}
```

错误：`INVALID_REQUEST`(400)、`INVALID_IMAGE`(400)、`IMAGE_TOO_LARGE`(413)、`UNSUPPORTED_MEDIA_TYPE`(415)、`AI_PROVIDER_ERROR`(502)、`INVALID_AI_RESPONSE`(502)、`INTERNAL_ERROR`(500)。

### 5.2 POST /api/v1/meals

输入：契约 B（JSON）

```json
{
  "meal_type": "lunch",
  "meal_datetime": "2026-11-01T12:30:00+08:00",
  "image_path": "uploads/2026/11/6f1c9a2e.jpg",
  "items": [
    { "food_name": "cooked_white_rice", "display_name": "White rice", "weight_g": 180.0 }
  ]
}
```

输出 `201`：契约 D（`meal_id` + 明细 + `totals` + `warnings`）。

错误：`INVALID_REQUEST`(400)、`INVALID_WEIGHT`(422)、`FOOD_NOT_FOUND`(422，**全部**未匹配时)、`DATABASE_ERROR`(500)。

### 5.3 GET /api/v1/meals

输入（query）：`date_from`、`date_to`（`YYYY-MM-DD`）、`limit`(1–200，默认 50)、`offset`(≥0，默认 0)。

输出 `200`：

```json
{
  "status": "success",
  "data": {
    "meals": [
      { "meal_id": 101, "meal_type": "lunch",
        "meal_datetime": "2026-11-01T12:30:00+08:00", "meal_date": "2026-11-01",
        "display_summary": "White rice, Grilled chicken breast",
        "calories_kcal": 432.0, "item_count": 2 }
    ],
    "pagination": { "limit": 50, "offset": 0, "count": 1 }
  }
}
```

错误：`INVALID_REQUEST`(400，日期参数不成对或格式错)。

### 5.4 GET /api/v1/meals/{meal_id}

输出 `200`：契约 D。错误：`INVALID_REQUEST`(400)、`MEAL_NOT_FOUND`(404)。

### 5.5 DELETE /api/v1/meals/{meal_id}

输出 `200`：`{"status":"success","data":{"meal_id":101,"deleted":true}}`
错误：`MEAL_NOT_FOUND`(404)、`DATABASE_ERROR`(500)。

### 5.6 GET /api/v1/dashboard/daily

输入（query）：`date`（可选，默认今天）。
输出 `200`：契约 E。空数据日 ⇒ 全 0，仍是 200。

---

## 6. 必须实现的函数接口

### 6.1 服务层（`app/services/meal_service.py`）

```python
def analyze_uploaded_meal(image_path: str, meal_type: str) -> dict:
    """调用 AI 模块，返回 {image_path, **契约A}。异常原样上抛。"""

def create_meal(payload: dict) -> dict:
    """payload 已通过 Pydantic 校验。返回契约 D（含 meal_id）。"""

def get_meal_detail(meal_id: int) -> dict:
    """返回契约 D；不存在抛 MealNotFound。"""

def list_meals(date_from: str | None, date_to: str | None,
               limit: int, offset: int) -> dict:
    """返回 {meals: [...], pagination: {...}}。"""

def delete_meal(meal_id: int) -> dict:
    """返回 {meal_id, deleted: True}；不存在抛 MealNotFound。"""

def get_daily_dashboard(date: str | None) -> dict:
    """date 为 None 时用 APP_TIMEZONE 的今天。返回契约 E。"""
```

### 6.2 工具层

```python
# app/utils/errors.py
class ApiError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 400, details=None): ...
# 以及 InvalidImage / ImageTooLarge / UnsupportedMediaType / InvalidRequest /
#     InvalidWeight / FoodNotFound / MealNotFound / AiProviderError /
#     InvalidAiResponse / DatabaseError

# app/utils/images.py
def save_upload(file_storage) -> str:
    """校验 → EXIF 修正 → 缩放 → 存 uploads/YYYY/MM/<uuid>.jpg → 返回相对路径"""

def is_safe_image_path(rel_path: str) -> bool:
    """确认是 uploads/ 下的相对路径且不含 '..'、文件存在"""

# app/utils/timeutil.py
def to_utc_iso(dt_str: str | None) -> str:
    """'2026-11-01T12:30:00+08:00' → '2026-11-01T04:30:00Z'（无偏移按 APP_TIMEZONE）"""

def to_local_iso(utc_iso: str) -> str:
    """UTC → APP_TIMEZONE 带偏移的字符串"""

def local_date_of(dt_str: str | None) -> str:
    """返回本地日期 'YYYY-MM-DD'"""

def today_local() -> str:
    """APP_TIMEZONE 下的今天"""
```

### 6.3 错误行为约定

| 场景 | 谁抛 | 路由行为 |
|---|---|---|
| 缺 `image` 字段 | 路由 | 抛 `InvalidRequest` |
| Pillow 打不开 | `save_upload` | 抛 `InvalidImage` |
| 超过 8 MB | Flask 先拦 | 注册 413 handler 转 `ImageTooLarge` |
| `analyze_food` 抛 `AiProviderError` | 成员2 | 不包装，直接上抛 |
| 全部食物未匹配 | `calculate_meal_nutrition` 返回 `items: []` | 你检查后抛 `FoodNotFound` |
| 写入失败 | 成员5 抛 `DatabaseError` | 上抛 |

---

## 7. 实施步骤

### 7.0 六周交付节奏（你的部分）

| 周 | 你要交付 | 验收 |
|---|---|---|
| 1 | 仓库骨架、`create_app()`、4 个页面路由、6 个空路由返回 mock JSON、`utils/errors.py` | 五人都能跑起来；`curl` 六个接口都能返回 mock |
| 2 | 上传校验与落盘、Pydantic 请求模型、真实调用 AI（可用 mock 兜底）、错误翻译 | 上传坏图返回标准信封；`pytest tests/unit/test_api.py` 绿 |
| 3 | 串起 `analyze → nutrition → save_meal`，写 `tests/integration/test_pipeline.py` | 一条命令跑通完整流水线 |
| 4 | 六个接口全部对接真实实现；联调前端 | 浏览器上传到保存全通，F12 无 500 |
| 5 | 全部错误码有测试；统一日志；`413/404/500` handler 补齐 | 错误码覆盖表全打勾 |
| 6 | 冻结、修 bug、补 README、演示彩排 | 演示脚本 3 分钟不翻车 |

### 步骤 1：搭骨架（第 1 周，约 3 小时）

**目标**：`python run.py` 能起服务，首页能渲染。

1. 建目录（照 `00` §C）。
2. 写 `app/config.py`（从 `.env` 读配置）。
3. 写 `app/__init__.py` 的 `create_app()`：装配 `db`、注册蓝图、注册错误处理器。
4. 写 `app/routes/pages.py`，4 个页面先返回占位 HTML。
5. 写 6 个空 API 路由，直接返回契约形状的 mock JSON。

**完成标准**：`curl http://127.0.0.1:5000/api/v1/dashboard/daily` 返回 `{"status":"success","data":{...}}`。

### 步骤 2：错误体系与上传（第 2 周上半）

1. `errors.py`：定义 `ApiError` 与 10 个子类，每个带 `code` 与 `http_status`。
2. `__init__.py` 注册 `@app.errorhandler(ApiError)`、`@app.errorhandler(413)`、`@app.errorhandler(404)`（仅 `/api/*` 走 JSON）、`@app.errorhandler(Exception)`。
3. `images.py`：MIME 白名单 → `PIL.Image.open` 校验 → `ImageOps.exif_transpose` → 长边缩到 1024 → 存 `uploads/YYYY/MM/<uuid4>.jpg`。
4. `analysis.py`：接上 `save_upload()` 和 `analyze_food()`（AI 没好之前返回 mock）。

**完成标准**：传 `.md` 文件得到 `INVALID_IMAGE`；传 9 MB 得到 `IMAGE_TOO_LARGE`，且响应体是 JSON。

### 步骤 3：请求校验与服务编排（第 2 周下半）

1. `app/services/schemas.py` 定义 `MealItemInput`、`CreateMealRequest`。
2. `meal_service.create_meal()`：校验已通过 → `to_utc_iso`/`local_date_of` → `calculate_meal_nutrition(items)` → 若 `items` 为空抛 `FoodNotFound` → 组装 `meal_data` → `save_meal()` → `get_meal()` 返回。
3. 组装时**不要**自己补 `food_id`：把 `nutrition["items"]` 原样放进 `meal_data["items"]`，`food_id` 由成员5 的 `save_meal()` 按 `food_name` 查库填充（查不到就存 `NULL`）。这样营养模块不需要知道数据库主键。

**完成标准**：`POST /meals` 能存进去，`GET /meals` 能查出来，`totals` 与手算一致。

### 步骤 4：查询、删除、看板（第 3–4 周）

1. `GET /meals`：日期参数配对校验 → `get_meals()` → `display_summary` 拼接 → `pagination`。
2. `GET /meals/{id}`：`get_meal()` → None 抛 `MealNotFound`。
3. `DELETE /meals/{id}`：`delete_meal()` 返回 False 抛 `MealNotFound`。
4. `GET /dashboard/daily`：`date` 缺省用 `today_local()`。

**完成标准**：删一条后看板合计下降；不存在的 id 返回 404 信封。

### 步骤 5：收口（第 5 周）

1. 给每个错误码写至少一个测试（见 §9）。
2. 加日志（见 `00` §H.4），确认不泄漏 Key。
3. 检查所有响应 `Content-Type: application/json; charset=utf-8`。
4. 用 `curl` 把 `00` §F 的所有示例跑一遍。

**完成标准**：`pytest` 全绿；错误码表 100% 覆盖。

### 步骤 6：接入与文档（第 6 周）

1. 与成员4 过一遍 `04_FRONTEND_DEVELOPER.md` 的接口对照表。
2. 补 README 的"常见问题"。
3. 演示彩排两遍。

---

## 8. 代码示例

> 以下片段可直接作为起点，但**不要**整段复制后就当完成——按步骤逐块落地。

### 8.1 应用工厂

```python
# app/__init__.py
import logging
from pathlib import Path

from flask import Flask, jsonify
from werkzeug.exceptions import RequestEntityTooLarge

from .config import Config
from .extensions import db
from .utils.errors import ApiError, ImageTooLarge


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    from .routes import register_blueprints
    register_blueprints(app)

    _register_error_handlers(app)
    _ensure_directories(app)
    logging.basicConfig(level=logging.INFO)
    return app


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(err: ApiError):
        return jsonify({"status": "error",
                        "error": {"code": err.code, "message": err.message,
                                  "details": err.details}}), err.http_status

    @app.errorhandler(RequestEntityTooLarge)
    def handle_too_large(_):
        return jsonify({"status": "error",
                        "error": {"code": "IMAGE_TOO_LARGE",
                                  "message": "Image exceeds the 8 MB limit.",
                                  "details": None}}), 413

    @app.errorhandler(Exception)
    def handle_unexpected(err: Exception):
        app.logger.exception("unhandled error")
        return jsonify({"status": "error",
                        "error": {"code": "INTERNAL_ERROR",
                                  "message": "Unexpected server error.",
                                  "details": None}}), 500


def _ensure_directories(app: Flask) -> None:
    for sub in ("instance", "uploads"):
        (Path(app.root_path).parent / sub).mkdir(exist_ok=True)
```

### 8.2 蓝图注册

```python
# app/routes/__init__.py
from flask import Blueprint
from . import analysis, dashboard, meals, pages


def register_blueprints(app) -> None:
    api = Blueprint("api_v1", __name__, url_prefix="/api/v1")
    api.register_blueprint(analysis.bp)
    api.register_blueprint(meals.bp)
    api.register_blueprint(dashboard.bp)
    app.register_blueprint(api)
    app.register_blueprint(pages.bp)
```

### 8.3 分析路由

```python
# app/routes/analysis.py
from flask import Blueprint, jsonify, request

from ..services import meal_service
from ..utils.errors import InvalidRequest
from ..utils.images import save_upload

bp = Blueprint("analysis", __name__)

MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}


@bp.post("/analyze")
def analyze():
    if "image" not in request.files:
        raise InvalidRequest("Field 'image' is required.", details={"field": "image"})

    meal_type = request.form.get("meal_type", "")
    if meal_type not in MEAL_TYPES:
        raise InvalidRequest("Invalid meal_type.",
                             details={"field": "meal_type", "allowed": sorted(MEAL_TYPES)})

    image_path = save_upload(request.files["image"])
    data = meal_service.analyze_uploaded_meal(image_path, meal_type)
    return jsonify({"status": "success", "data": data}), 200
```

### 8.4 保存餐食路由

```python
# app/routes/meals.py
from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from ..services import meal_service
from ..services.schemas import CreateMealRequest
from ..utils.errors import InvalidRequest

bp = Blueprint("meals", __name__)


@bp.post("/meals")
def create_meal():
    body = request.get_json(silent=True)
    if body is None:
        raise InvalidRequest("Request body must be JSON.")
    try:
        payload = CreateMealRequest.model_validate(body)
    except ValidationError as exc:
        raise InvalidRequest("Invalid request body.", details={"errors": exc.errors(include_url=False)})

    data = meal_service.create_meal(payload.model_dump())
    return jsonify({"status": "success", "data": data}), 201
```

对应的 Pydantic 模型：

```python
# app/services/schemas.py
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MealItemInput(BaseModel):
    food_name: str | None = None
    display_name: str = Field(min_length=1, max_length=100)
    weight_g: float = Field(gt=0, le=5000)


class CreateMealRequest(BaseModel):
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"]
    meal_datetime: datetime
    image_path: str | None = None
    items: list[MealItemInput] = Field(min_length=1, max_length=20)
```

> `meal_datetime: datetime` 让 Pydantic 帮忙解析 ISO 8601；你再交给 `timeutil.to_utc_iso()` 统一时区。

### 8.5 服务编排（核心）

```python
# app/services/meal_service.py
import logging

from ..ai.image_analyzer import analyze_food
from ..database.repository import (delete_meal as delete_meal_repo,
                                    get_meal, get_meals, save_meal, get_daily_summary)
from ..nutrition.calculator import calculate_meal_nutrition
from ..utils.errors import FoodNotFound, MealNotFound
from ..utils.timeutil import local_date_of, to_utc_iso

log = logging.getLogger(__name__)


def analyze_uploaded_meal(image_path: str, meal_type: str) -> dict:
    ai_result = analyze_food(image_path)          # 契约 A，异常直接上抛
    log.info("analyzed image=%s status=%s foods=%d",
             image_path, ai_result["status"], len(ai_result["foods"]))
    return {"image_path": image_path, **ai_result}


def create_meal(payload: dict) -> dict:
    meal_datetime = payload["meal_datetime"]
    nutrition = calculate_meal_nutrition(payload["items"])   # 契约 C

    if not nutrition["items"]:
        raise FoodNotFound("No food could be matched.",
                           details={"warnings": nutrition["warnings"]})

    meal_data = {
        "meal_type": payload["meal_type"],
        "meal_datetime_utc": to_utc_iso(meal_datetime),
        "meal_date": local_date_of(meal_datetime),
        "image_path": payload.get("image_path"),
        "items": nutrition["items"],      # food_id 由仓储层按 food_name 解析
        "warnings": nutrition["warnings"],
    }
    meal_id = save_meal(meal_data)
    return get_meal(meal_id)


def delete_meal(meal_id: int) -> dict:
    """删除餐食。不存在抛 MealNotFound，成功返回 {meal_id, deleted: True}。"""
    found = delete_meal_repo(meal_id)
    if not found:
        raise MealNotFound(f"Meal {meal_id} not found.",
                           details={"meal_id": meal_id})
    log.info("deleted meal_id=%d", meal_id)
    return {"meal_id": meal_id, "deleted": True}
```

> 注意：`match_food()` 是给营养模块内部用的，你**不需要**在服务层再调一次；`save_meal()` 会用 `food_name` 自己去参考表里找 `food_id`。服务层的 `delete_meal` 调用仓储层的同名函数（为避免名字冲突，import 时用 `delete_meal_repo` 别名）。

### 8.6 上传校验与落盘

```python
# app/utils/images.py
import uuid
from datetime import datetime
from pathlib import Path

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError

from .errors import InvalidImage, UnsupportedMediaType

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def save_upload(file_storage) -> str:
    if file_storage.mimetype not in ALLOWED_MIME:
        raise UnsupportedMediaType("Only JPEG, PNG and WebP are allowed.",
                                   details={"content_type": file_storage.mimetype})
    try:
        img = Image.open(file_storage.stream)
        img.load()
    except (UnidentifiedImageError, OSError):
        raise InvalidImage("The uploaded file is not a valid image.")

    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((current_app.config["UPLOAD_MAX_SIDE"],
                   current_app.config["UPLOAD_MAX_SIDE"]))

    now = datetime.now()
    rel_dir = Path("uploads") / f"{now:%Y}" / f"{now:%m}"
    abs_dir = Path(current_app.root_path).parent / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex[:12]}.jpg"
    img.save(abs_dir / filename, format="JPEG", quality=85, optimize=True)
    return (rel_dir / filename).as_posix()
```

### 8.7 时间工具

```python
# app/utils/timeutil.py
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from flask import current_app


def _tz() -> ZoneInfo:
    return ZoneInfo(current_app.config["APP_TIMEZONE"])


def to_utc_iso(dt: datetime | str) -> str:
    dt = datetime.fromisoformat(str(dt)) if isinstance(dt, str) else dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_tz())
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_local_iso(utc_iso: str) -> str:
    dt = datetime.fromisoformat(utc_iso.replace("Z", "+00:00"))
    return dt.astimezone(_tz()).isoformat(timespec="seconds")


def local_date_of(dt: datetime | str) -> str:
    dt = datetime.fromisoformat(str(dt)) if isinstance(dt, str) else dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_tz())
    return dt.astimezone(_tz()).date().isoformat()


def today_local() -> str:
    return datetime.now(_tz()).date().isoformat()
```

### 8.8 删除与看板

```python
# app/routes/meals.py（续——DELETE /meals/<int:meal_id>）
@bp.delete("/meals/<int:meal_id>")
def delete(meal_id):
    data = meal_service.delete_meal(meal_id)
    return jsonify({"status": "success", "data": data}), 200
```

```python
# app/routes/dashboard.py
from flask import Blueprint, jsonify, request

from ..services import meal_service

bp = Blueprint("dashboard", __name__)


@bp.get("/dashboard/daily")
def daily():
    date = request.args.get("date") or None
    return jsonify({"status": "success", "data": meal_service.get_daily_dashboard(date)}), 200
```

---

## 9. 测试要求

### 9.1 必须覆盖的用例

| # | 用例 | 请求 | 期望 |
|---|---|---|---|
| B1 | 分析成功（AI 打桩） | `POST /analyze` + 真实小图 | 200，`data.foods` 非空，含 `image_path` |
| B2 | 缺 image | 空 multipart | 400 `INVALID_REQUEST` |
| B3 | 文本文件冒充图片 | `README.md` | 400 `INVALID_IMAGE` |
| B4 | 9 MB 文件 | 大图 | 413 `IMAGE_TOO_LARGE`，响应是 JSON |
| B5 | `meal_type=pizza` | — | 400 `INVALID_REQUEST` |
| B6 | 保存成功 | 契约 B | 201，`data.meal_id` 为整数，`totals` 与手算一致 |
| B7 | `weight_g=0` | — | 422 `INVALID_WEIGHT` |
| B8 | 全部食物未匹配 | `food_name: "xxx"` | 422 `FOOD_NOT_FOUND` |
| B9 | 一条未匹配一条正常 | — | 201，`warnings` 非空 |
| B10 | 查不存在 | `GET /meals/99999` | 404 `MEAL_NOT_FOUND` |
| B11 | 删除 | `DELETE /meals/{id}` | 200；再 GET → 404 |
| B12 | 日期不成对 | `?date_from=2026-11-01` | 400 `INVALID_REQUEST` |
| B13 | 看板 | `GET /dashboard/daily?date=` | 200，`meal_count` 正确 |
| B14 | 前端提交假卡路里 | `items[0].calories_kcal=99999` | 被忽略，返回服务端算的值 |
| B15 | 空 body 的 POST | `{}` | 400 `INVALID_REQUEST` |

### 9.2 测试骨架

```python
# tests/unit/test_api.py
def test_create_meal_ignores_client_calories(client):
    payload = {"meal_type": "lunch",
               "meal_datetime": "2026-11-01T12:30:00+08:00",
               "items": [{"food_name": "cooked_white_rice",
                          "display_name": "White rice",
                          "weight_g": 180,
                          "calories_kcal": 99999}]}
    res = client.post("/api/v1/meals", json=payload)
    assert res.status_code == 201
    assert res.get_json()["data"]["totals"]["calories_kcal"] == pytest.approx(234.0, abs=0.01)
```

`conftest.py` 提供 `client` 与内存数据库（成员5 负责），你直接用。

### 9.3 判定标准

- 15 个用例全部实现且通过。
- 每个错误码至少一条用例。
- 测试不依赖真实 API Key、不访问网络。

---

## 10. 集成说明

### 10.1 你的依赖（上游）

| 依赖 | 接口 | 没完成时怎么办 |
|---|---|---|
| 成员2 AI | `analyze_food(image_path)` | 自己造 `mock_ai_result.json` 返回，路由照常跑 |
| 成员3 营养 | `calculate_meal_nutrition(foods)`、`match_food(name)` | 用固定返回 `{"items":[],"totals":{...0},"warnings":[]}` 的假实现 |
| 成员5 数据库 | `save_meal`、`get_meal`、`get_meals`、`delete_meal`、`get_daily_summary` | 用一个内存字典假仓储 |

**原则**：永远不要"等别人写完"。你至少能先把 HTTP 层和错误处理完整测通。

### 10.2 依赖你的模块（下游）

| 模块 | 用你什么 | 你怎么配合 |
|---|---|---|
| 成员4 前端 | 6 个接口的 JSON | 字段名不改；有变化提前一天通知 |
| 成员5 测试 | Flask `test_client` | 保证 app 工厂可注入 `TESTING` 配置与内存库 |
| 全组 | `develop` 能跑 | 合并前自己先 `pytest` |

### 10.3 什么时候合并

| 时机 | 合并内容 |
|---|---|
| 第 1 周末 | 骨架 + mock 路由（让全组能开工） |
| 第 2 周末 | 上传校验 + 错误体系 + Pydantic |
| 第 3 周末 | 服务编排串通流水线 |
| 每周至少一次 | 小步合并，不要攒到最后一天 |

### 10.4 接口要变怎么办

1. 先在 `00_MAIN_TECHNICAL_ROUTE.md` 提 PR 改契约。
2. 群里通知受影响的人（至少成员3、成员4、成员5）。
3. 同步改 `mock_ai_result.json`、前端字段、测试断言。
4. 同一个 PR 里带一条"契约变更"说明。
5. **绝不**先改代码后补文档。

---

## 11. GitHub 工作流

### 11.1 分支与提交

```bash
git checkout develop && git pull
git checkout -b feature/backend
git add app/ tests/ docs/
git commit -m "feat(backend): add analyze endpoint with upload validation"
git push -u origin feature/backend
```

提交示例：
- `feat(backend): add create_meal service orchestration`
- `fix(backend): return 413 as JSON envelope`
- `test(backend): cover all error codes`
- `docs: add timezone section to main route`

### 11.2 PR 要求

- 标题用 `type(backend): summary`。
- 描述含：改了什么、是否动契约（期望"没有"）、怎么验证（命令 + 结果）、截图或 curl 输出。
- 至少 1 人 Review。
- 列出你跑过的命令：

```bash
pytest -q
curl -s -X POST localhost:5000/api/v1/analyze -F "image=@tests/fixtures/sample_meal.jpg" -F "meal_type=lunch" | head -c 300
```

### 11.3 需要提交的文件

`app/__init__.py`、`app/config.py`、`app/routes/**`、`app/services/**`、`app/utils/**`、`tests/unit/test_api.py`、`tests/integration/test_api_errors.py`、`.env.example`、`run.py`、`requirements.txt`。

**永不提交**：`.env`、`instance/*.db`、`uploads/*`。

---

## 12. 最终交付清单

### 12.1 代码

- [ ] `run.py` 一行命令启动，端口可配置
- [ ] `create_app()` 支持 `test_config` 注入
- [ ] 6 个 API 路由 + 4 个页面路由
- [ ] `service` 层串通 AI / 营养 / 数据库
- [ ] `utils/errors.py` 完整 11 个错误码
- [ ] `utils/images.py` 完成 MIME 校验、EXIF 修正、缩放、落盘
- [ ] `utils/timeutil.py` 完成 UTC/本地转换与 `meal_date` 推导
- [ ] 413/404/500 都返回契约 F（`/api/*` 下）

### 12.2 测试

- [ ] `tests/unit/test_api.py` ≥10 条
- [ ] `tests/integration/test_api_errors.py` 覆盖每个错误码
- [ ] `pytest -q` 全绿，<10 秒，无需 Key/网络

### 12.3 文档与协作

- [ ] `.env.example` 含全部变量且无真实值
- [ ] README 的"常见问题"至少 5 条
- [ ] 所有契约变更已同步到 `00_MAIN_TECHNICAL_ROUTE.md`
- [ ] `develop` 随时可运行，CI/本地测试绿
- [ ] 演示脚本能跑通，且你能解释每一步的数据流

### 12.4 自检问题（答不出就还没做完）

1. 前端提交了假的 `calories_kcal`，为什么最终数字是对的？
2. 分析接口什么情况下返回 200 但 `status` 是 `error`？
3. `413` 为什么必须返回 JSON 而不是 Flask 默认 HTML？
4. `meal_date` 为什么要单独存一列，不能查的时候算？
5. 你的路由里有没有任何一处营养计算或 SQL？（答案必须是"没有"）
