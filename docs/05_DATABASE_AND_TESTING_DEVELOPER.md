# 05 — 数据库与测试开发指南（成员 5）

> 上位文档：[`00_MAIN_TECHNICAL_ROUTE.md`](00_MAIN_TECHNICAL_ROUTE.md)。冲突时以主路线为准。
> 你负责两件事：**让数据存得住、查得对**，以及**让全组敢改代码**（测试体系）。

## 1. 角色与目标

### 1.1 你的职责

| 你负责 | 你不负责 |
|---|---|
| 三张表的设计与 SQLAlchemy 模型 | 营养公式（成员3） |
| 仓储函数（增删查、聚合） | AI 识别（成员2） |
| 营养快照的存储规则 | 页面（成员4） |
| `scripts/init_db.py`、`seed_foods.py` | 路由与业务编排（成员1） |
| 测试基础设施（`conftest.py`、夹具、mock） | 改契约（需全组同意） |
| 集成测试、端到端测试、错误码覆盖表 | — |
| 为 Chart.js 提供聚合数据 | — |

### 1.2 最终交付物（一句话）

> 一个可重复初始化的 SQLite 库（三张表 + 唯一约束 + 级联），五个仓储函数（`save_meal` / `get_meal` / `get_meals` / `delete_meal` / `get_daily_summary`）全部可用，以及一套**不联网、不需要 Key、10 秒跑完**的测试体系。

### 1.3 成功标准

- `python scripts/init_db.py && python scripts/seed_foods.py` 跑两遍结果一致（幂等）。
- 删一条餐食，明细跟着消失；删一条参考食物，历史明细仍在（`food_id` 变 `NULL`）。
- 改 `food_database.json` 的数值，历史餐食的卡路里**不变**。
- `pytest -q` 全绿，且没有任何测试依赖真实 AI 或网络。

---

## 2. 要构建什么

### 2.1 三张表

| 表 | 作用 | 一句话 |
|---|---|---|
| `food` | 参考营养库（每 100 g） | 只读数据源，由成员3 的 JSON 导入 |
| `meal` | 一次确认形成的餐食 | 一条记录 = 用户保存的一顿饭 |
| `meal_item` | 餐食明细（含快照） | 保存那一刻的营养值被冻结在这里 |

### 2.2 仓储函数

| 函数 | 用途 |
|---|---|
| `save_meal(meal_data)` | 事务内写 `meal` + 全部 `meal_item`，返回 `meal_id` |
| `get_meal(meal_id)` | 取契约 D；不存在返回 `None` |
| `get_meals(date_from, date_to)` | 历史摘要列表（给 `GET /meals`） |
| `delete_meal(meal_id)` | 级联删除餐食及其全部明细；存在返回 `True`，不存在返回 `False` |
| `get_daily_summary(date)` | 契约 E（给看板） |

### 2.3 测试体系

| 层 | 文件 | 数量下限 |
|---|---|---|
| 数据库单元 | `tests/unit/test_repository.py` | 6 |
| 集成（AI→营养→DB） | `tests/integration/test_pipeline.py` | 3 |
| API 错误码 | `tests/integration/test_api_errors.py`（与成员1 共同） | 每个错误码 1 条 |
| 端到端 | `tests/e2e/test_workflow.py` | 4 |
| 夹具 | `tests/conftest.py`、`tests/fixtures/**` | — |

### 2.4 明确不做

- ❌ 不做 Alembic 迁移（改表就删库重建，第 1 周说清楚）
- ❌ 不做多用户、权限、软删除
- ❌ 不做缓存层（Redis 等）
- ❌ 不手写裸 SQL 拼字符串（参数化或 ORM）
- ❌ 不在读取时重算营养（快照原则）

---

## 3. 技术要用的东西

### 3.1 依赖

```bash
pip install "Flask-SQLAlchemy>=3.1" "SQLAlchemy>=2.0" "pytest>=8.0"
```

### 3.2 关键概念

| 概念 | 用途 |
|---|---|
| `db = SQLAlchemy()` 单例 | 避免循环 import；在 `extensions.py` 定义，`create_app()` 里 `init_app` |
| `db.create_all()` | 建表；不处理迁移 |
| `ForeignKey(..., ondelete="CASCADE")` | 删餐食时删明细 |
| `ForeignKey(..., ondelete="SET NULL")` | 删参考食物时保留历史 |
| `PRAGMA foreign_keys=ON` | SQLite 默认**不开**外键，必须显式打开 |
| `db.session` 事务 | 一次 `commit()` 写完整餐食 |
| `relationship(cascade="all, delete-orphan")` | ORM 层的级联，双保险 |
| `func.coalesce(func.sum(...), 0)` | 空数据返回 0 而不是 NULL |
| `sqlite:///:memory:` | 测试库，进程内、零污染 |
| `monkeypatch` | 打桩 AI、打桩时间 |

### 3.3 目录与文件

```text
app/extensions.py                 # db = SQLAlchemy()
app/database/__init__.py
app/database/models.py            # Food / Meal / MealItem
app/database/repository.py        # 五个仓储函数
scripts/init_db.py                # create_all()
scripts/seed_foods.py             # 幂等导入 JSON → food 表
tests/conftest.py                 # app / client / db fixtures
tests/fixtures/                   # mock JSON、样例图片
tests/unit/test_repository.py
tests/integration/test_pipeline.py
tests/e2e/test_workflow.py
```

---

## 4. 你拥有的文件

| 路径 | 说明 |
|---|---|
| `app/extensions.py` | `db = SQLAlchemy()` |
| `app/database/models.py` | 三张表的 ORM 模型 |
| `app/database/repository.py` | 五个共享函数 + 辅助查询 |
| `scripts/init_db.py` | 建表脚本 |
| `scripts/seed_foods.py` | 种子数据 |
| `tests/conftest.py` | 全组共用的夹具 |
| `tests/fixtures/**` | mock 与样例数据 |
| `tests/unit/test_repository.py` | 你的单元测试 |
| `tests/integration/test_pipeline.py` | 集成测试 |
| `tests/e2e/test_workflow.py` | 端到端测试 |

### 4.1 别人怎么用你

| 他人 | 用法 | 禁止 |
|---|---|---|
| 成员1 | `from app.database.repository import save_meal, get_meal, get_meals, delete_meal, get_daily_summary` | 在路由里直接 `db.session` |
| 成员3 | 不直接使用；他的 JSON 由你的 `seed_foods.py` 导入 | 改你的模型 |
| 成员2 | 不相关 | — |
| 成员4 | 只看到聚合后的 JSON | 让你为图表加专用接口 |
| 全组 | 用你的 `conftest.py` 夹具写测试 | 改夹具不告知 |

---

## 5. 输入输出契约

### 5.1 表结构

#### `food`（参考营养库）

| 列 | 类型 | 约束 |
|---|---|---|
| `id` | INTEGER | PK, AUTOINCREMENT |
| `food_name` | TEXT | NOT NULL, UNIQUE（标准 ID） |
| `display_name` | TEXT | NOT NULL |
| `calories_per_100g` | REAL | NOT NULL, `0–900` |
| `protein_per_100g` | REAL | NOT NULL, `0–100` |
| `carbs_per_100g` | REAL | NOT NULL, `0–100` |
| `fat_per_100g` | REAL | NOT NULL, `0–100` |
| `source` | TEXT | NOT NULL, 默认 `'local'` |
| `aliases` | TEXT | NULL，逗号分隔 |
| `is_verified` | INTEGER | NOT NULL, 默认 0 |
| `created_at` | TEXT | NOT NULL, UTC |

#### `meal`（餐食）

| 列 | 类型 | 约束 |
|---|---|---|
| `id` | INTEGER | PK（即 `meal_id`） |
| `meal_type` | TEXT | NOT NULL, IN (`breakfast`,`lunch`,`dinner`,`snack`) |
| `meal_datetime_utc` | TEXT | NOT NULL，`...Z` |
| `meal_date` | TEXT | NOT NULL，本地 `YYYY-MM-DD`，**建索引** |
| `image_path` | TEXT | NULL |
| `created_at` | TEXT | NOT NULL, UTC |

#### `meal_item`（明细 + 快照）

| 列 | 类型 | 约束 |
|---|---|---|
| `id` | INTEGER | PK |
| `meal_id` | INTEGER | NOT NULL, FK → `meal.id` **ON DELETE CASCADE** |
| `food_id` | INTEGER | NULL, FK → `food.id` **ON DELETE SET NULL** |
| `food_name` | TEXT | NULL（快照，防参考表改名） |
| `display_name` | TEXT | NOT NULL |
| `weight_g` | REAL | NOT NULL, `0 < x ≤ 5000` |
| `calories_kcal` | REAL | NOT NULL, `≥ 0` |
| `protein_g` | REAL | NOT NULL, `≥ 0` |
| `carbs_g` | REAL | NOT NULL, `≥ 0` |
| `fat_g` | REAL | NOT NULL, `≥ 0` |
| `food_data_source` | TEXT | NOT NULL, 默认 `'local'` |
| `sort_order` | INTEGER | NOT NULL, 默认 0 |

索引：`idx_meal_date (meal_date)`、`idx_meal_item_meal (meal_item.meal_id)`、`food.food_name` 唯一索引。

### 5.2 `save_meal()` 的输入

成员1 传进来的 dict（**注意字段名**）：

```json
{
  "meal_type": "lunch",
  "meal_datetime_utc": "2026-11-01T04:30:00Z",
  "meal_date": "2026-11-01",
  "image_path": "uploads/2026/11/6f1c9a2e.jpg",
  "items": [
    {
      "food_name": "cooked_white_rice",
      "display_name": "White rice",
      "weight_g": 180.0,
      "calories_kcal": 234.0,
      "protein_g": 4.86,
      "carbs_g": 50.76,
      "fat_g": 0.54,
      "food_data_source": "USDA"
    }
  ],
  "warnings": []
}
```

你要做的：

1. 校验 `items` 非空（`1–20`），否则抛 `InvalidRequest`。
2. 对每条 item 用 `food_name` 查 `food` 表拿 `food_id`；查不到则 `food_id=None`（不报错）。
3. 一个事务内写 `meal` + 全部 `meal_item`。
4. 返回 `meal.id`。

**不要**在这里重算营养，也**不要**接受客户端传的 `totals`。

### 5.3 `get_meal()` 的输出（契约 D）

```json
{
  "meal_id": 101,
  "meal_type": "lunch",
  "meal_datetime": "2026-11-01T12:30:00+08:00",
  "meal_date": "2026-11-01",
  "image_path": "uploads/2026/11/6f1c9a2e.jpg",
  "created_at": "2026-11-01T04:30:12Z",
  "items": [ { "food_name": "cooked_white_rice", "display_name": "White rice",
               "weight_g": 180.0, "calories_kcal": 234.0, "protein_g": 4.86,
               "carbs_g": 50.76, "fat_g": 0.54, "food_data_source": "USDA" } ],
  "totals": { "calories_kcal": 234.0, "protein_g": 4.86, "carbs_g": 50.76, "fat_g": 0.54 },
  "warnings": []
}
```

- `meal_datetime` 由 `meal_datetime_utc` 转本地时区（用成员1 的 `timeutil.to_local_iso()`）。
- `totals` 是**明细快照之和**，不是重新计算。
- `warnings` 在 v1 里恒为 `[]`（保存时已被成员1 消费），保留字段以便未来扩展。

### 5.4 `get_meals()` 的输出

```json
[
  { "meal_id": 101, "meal_type": "lunch",
    "meal_datetime": "2026-11-01T12:30:00+08:00", "meal_date": "2026-11-01",
    "display_summary": "White rice, Grilled chicken breast",
    "calories_kcal": 432.0, "item_count": 2 }
]
```

按 `meal_datetime_utc` 倒序（最新在前）。

### 5.5 `get_daily_summary()` 的输出

```json
{
  "date": "2026-11-01",
  "totals": { "calories_kcal": 1650.0, "protein_g": 80.0, "carbs_g": 190.0, "fat_g": 55.0 },
  "meal_count": 3
}
```

空数据日：`totals` 全 `0.0`、`meal_count` 为 `0`——**不允许返回 `None`**。

### 5.6 错误行为

| 情况 | 抛出 |
|---|---|
| `items` 为空或超过 20 | `InvalidRequest` |
| 写库异常 | `DatabaseError` |
| 查询异常 | `DatabaseError` |
| 查不到 `meal` | 返回 `None`（由成员1 转 404） |

---

## 6. 必须实现的函数接口

```python
# app/database/repository.py
def save_meal(meal_data: dict) -> int: ...
def get_meal(meal_id: int) -> dict | None: ...
def get_meals(date_from: str | None = None, date_to: str | None = None) -> list[dict]: ...
def delete_meal(meal_id: int) -> bool: ...
def get_daily_summary(date: str) -> dict: ...
```

辅助函数（你自用，可自由组织）：

```python
def _resolve_food_id(food_name: str | None) -> int | None
def _item_to_dict(item: "MealItem") -> dict
def _sum_items(items: list["MealItem"]) -> dict
def get_meal_page(limit: int, offset: int) -> list[dict]   # 供 GET /meals 无日期时用
```

> `get_meals()` 只接受日期区间。成员1 若需要 `limit/offset`，请用分页辅助函数或先全取再切片——**不要**擅自改 `get_meals` 的签名（`00` §G 已固定）。

---

## 7. 实施步骤

### 7.0 六周交付节奏（你的部分）

| 周 | 你要交付 | 验收 |
|---|---|---|
| 1 | `extensions.py`、`models.py`、`init_db.py`、`conftest.py` 骨架 | 建表成功；`pytest` 能收集到用例 |
| 2 | `save_meal` / `get_meal`；`seed_foods.py`；6 条仓储测试 | 能存能取一条样例餐食 |
| 3 | `get_meals` / `get_daily_summary`；集成测试 | 流水线测试通过 |
| 4 | 支持成员1 联调（分页、空数据、级联） | 删餐食后明细消失 |
| 5 | 端到端测试 + 错误码覆盖表 + 30 张照片回归配合 | 覆盖表全打勾 |
| 6 | 全量测试稳定、测试文档 | `pytest -q` 10 秒内全绿 |

### 步骤 1：建表（第 1 周）

1. `app/extensions.py`：`db = SQLAlchemy()`。
2. `app/database/models.py`：三个模型，含 `ForeignKey(ondelete=...)`、`CheckConstraint`、`Index`。
3. `app/__init__.py`（成员1 的文件）里加一行：连接时 `PRAGMA foreign_keys=ON`。**必须与他确认由谁加**。
4. `scripts/init_db.py`：`create_all()`。

**完成标准**：`sqlite3 instance/diet_tracker.db ".tables"` 看到 `food meal meal_item`。

### 步骤 2：仓储基础（第 2 周）

1. `_resolve_food_id()`：按 `food_name` 查 `id`，查不到返回 `None`。
2. `save_meal()`：一个事务，先 `flush()` 拿 `meal.id`，再批量插入 items。
3. `get_meal()`：一次查询 + 关联加载；`items` 转 dict；`totals` 求和。
4. `seed_foods.py`：读成员3 的 JSON，`food_name` 已存在则跳过（幂等）。

**完成标准**：存进去再读出来，字段与 `00` §E.4 完全一致。

### 步骤 3：查询与聚合（第 3 周）

1. `get_meals(date_from, date_to)`：`WHERE meal_date BETWEEN ...`，倒序；`display_summary` 由前三个 `display_name` 拼。
2. `get_daily_summary(date)`：`LEFT JOIN` + `COALESCE(SUM(...), 0)` + `COUNT(DISTINCT meal.id)`。
3. `get_meal_page(limit, offset)`：无日期时用。

**完成标准**：同一天两餐，`meal_count == 2`，`totals` 等于两餐之和。

### 步骤 4：联调（第 4 周）

1. 与成员1 对齐：他要不要 `by_meal_type`？如果要，你在 `get_daily_summary` 里加一次 `GROUP BY`（或让他在服务层聚合）。
2. 确认级联：删餐食后 `meal_item` 数量为 0。
3. 确认时区：`meal_date` 不信任前端，由成员1 传（你只存）。

### 步骤 5：测试体系（第 5 周）

1. `conftest.py`：`app` / `client` / `db` / `seeded_db` 夹具。
2. `test_repository.py`：7 条（§9.1）。
3. `test_pipeline.py`：3 条（AI 打桩 → 营养 → 存库）。
4. `test_workflow.py`：4 条端到端。
5. `test_api_errors.py`：与成员1 一起把 11 个错误码覆盖。
6. 维护"错误码覆盖表"（可放 `docs/TEST_REPORT.md`）。

**完成标准**：`pytest -q` 全绿；不需要 Key/网络；10 秒内完成。

### 步骤 6：稳定（第 6 周）

1. 修掉所有偶发失败（通常是共享缓存或未清理 session）。
2. 检查每个测试独立（单独跑、乱序跑都过）。
3. 输出一份测试报告（通过数、覆盖的错误码、已知缺口）。

---

## 8. 代码示例

### 8.1 扩展与模型

```python
# app/extensions.py
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
```

```python
# app/database/models.py
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Index

from ..extensions import db


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Food(db.Model):
    __tablename__ = "food"

    id = db.Column(db.Integer, primary_key=True)
    food_name = db.Column(db.Text, nullable=False, unique=True)
    display_name = db.Column(db.Text, nullable=False)
    calories_per_100g = db.Column(db.Float, nullable=False)
    protein_per_100g = db.Column(db.Float, nullable=False)
    carbs_per_100g = db.Column(db.Float, nullable=False)
    fat_per_100g = db.Column(db.Float, nullable=False)
    source = db.Column(db.Text, nullable=False, default="local")
    aliases = db.Column(db.Text)
    is_verified = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.Text, nullable=False, default=_utcnow_iso)

    __table_args__ = (
        CheckConstraint("calories_per_100g >= 0 AND calories_per_100g <= 900",
                        name="ck_food_calories"),
        CheckConstraint("protein_per_100g >= 0 AND protein_per_100g <= 100",
                        name="ck_food_protein"),
    )


class Meal(db.Model):
    __tablename__ = "meal"

    id = db.Column(db.Integer, primary_key=True)
    meal_type = db.Column(db.Text, nullable=False)
    meal_datetime_utc = db.Column(db.Text, nullable=False)
    meal_date = db.Column(db.Text, nullable=False)
    image_path = db.Column(db.Text)
    created_at = db.Column(db.Text, nullable=False, default=_utcnow_iso)

    items = db.relationship(
        "MealItem", back_populates="meal", cascade="all, delete-orphan",
        order_by="MealItem.sort_order", lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint("meal_type IN ('breakfast','lunch','dinner','snack')",
                        name="ck_meal_type"),
        Index("idx_meal_date", "meal_date"),
    )


class MealItem(db.Model):
    __tablename__ = "meal_item"

    id = db.Column(db.Integer, primary_key=True)
    meal_id = db.Column(db.Integer,
                        db.ForeignKey("meal.id", ondelete="CASCADE"), nullable=False)
    food_id = db.Column(db.Integer,
                        db.ForeignKey("food.id", ondelete="SET NULL"), nullable=True)
    food_name = db.Column(db.Text)
    display_name = db.Column(db.Text, nullable=False)
    weight_g = db.Column(db.Float, nullable=False)
    calories_kcal = db.Column(db.Float, nullable=False)
    protein_g = db.Column(db.Float, nullable=False)
    carbs_g = db.Column(db.Float, nullable=False)
    fat_g = db.Column(db.Float, nullable=False)
    food_data_source = db.Column(db.Text, nullable=False, default="local")
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    meal = db.relationship("Meal", back_populates="items")

    __table_args__ = (
        CheckConstraint("weight_g > 0 AND weight_g <= 5000", name="ck_item_weight"),
        Index("idx_meal_item_meal", "meal_id"),
    )
```

### 8.2 打开外键（与成员1 协同）

```python
# app/__init__.py —— 由成员1 落文件，你提供片段
from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "connect")
def _enable_sqlite_fk(dbapi_connection, _record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
```

> 这一行不加，`ON DELETE CASCADE` 就只是一句注释。写完必须用 §9.1 的 D2 验证。

### 8.3 仓储实现

```python
# app/database/repository.py
import logging

from ..extensions import db
from ..utils.errors import DatabaseError, InvalidRequest
from ..utils.timeutil import to_local_iso
from .models import Food, Meal, MealItem

log = logging.getLogger(__name__)

_TOTAL_KEYS = ("calories_kcal", "protein_g", "carbs_g", "fat_g")


def _resolve_food_id(food_name: str | None) -> int | None:
    if not food_name:
        return None
    row = Food.query.filter_by(food_name=food_name).first()
    return row.id if row else None


def save_meal(meal_data: dict) -> int:
    items = meal_data.get("items") or []
    if not (1 <= len(items) <= 20):
        raise InvalidRequest("A meal must contain 1-20 items.",
                             details={"count": len(items)})
    try:
        meal = Meal(
            meal_type=meal_data["meal_type"],
            meal_datetime_utc=meal_data["meal_datetime_utc"],
            meal_date=meal_data["meal_date"],
            image_path=meal_data.get("image_path"),
        )
        db.session.add(meal)
        db.session.flush()                      # 拿到 meal.id

        for order, item in enumerate(items):
            db.session.add(MealItem(
                meal_id=meal.id,
                food_id=_resolve_food_id(item.get("food_name")),
                food_name=item.get("food_name"),
                display_name=item["display_name"],
                weight_g=float(item["weight_g"]),
                calories_kcal=float(item["calories_kcal"]),
                protein_g=float(item["protein_g"]),
                carbs_g=float(item["carbs_g"]),
                fat_g=float(item["fat_g"]),
                food_data_source=item.get("food_data_source", "local"),
                sort_order=order,
            ))
        db.session.commit()
        return meal.id
    except Exception as exc:
        db.session.rollback()
        log.exception("save_meal failed")
        raise DatabaseError("Failed to save the meal.") from exc


def delete_meal(meal_id: int) -> bool:
    """级联删除餐食及其全部明细。存在返回 True，不存在返回 False。"""
    meal = db.session.get(Meal, meal_id)
    if meal is None:
        return False
    try:
        db.session.delete(meal)   # cascade="all, delete-orphan" 自动删明细
        db.session.commit()
        log.info("deleted meal_id=%d", meal_id)
        return True
    except Exception as exc:
        db.session.rollback()
        log.exception("delete_meal failed")
        raise DatabaseError("Failed to delete the meal.") from exc
```

### 8.4 读取与聚合

```python
# app/database/repository.py（续）
def _item_to_dict(item: MealItem) -> dict:
    return {
        "food_name": item.food_name,
        "display_name": item.display_name,
        "weight_g": item.weight_g,
        "calories_kcal": item.calories_kcal,
        "protein_g": item.protein_g,
        "carbs_g": item.carbs_g,
        "fat_g": item.fat_g,
        "food_data_source": item.food_data_source,
    }


def get_meal(meal_id: int) -> dict | None:
    meal = db.session.get(Meal, meal_id)
    if meal is None:
        return None

    items = [_item_to_dict(i) for i in meal.items]
    totals = {k: round(sum(i[k] for i in items), 1 if k == "calories_kcal" else 2)
              for k in _TOTAL_KEYS}
    return {
        "meal_id": meal.id,
        "meal_type": meal.meal_type,
        "meal_datetime": to_local_iso(meal.meal_datetime_utc),
        "meal_date": meal.meal_date,
        "image_path": meal.image_path,
        "created_at": meal.created_at,
        "items": items,
        "totals": totals,
        "warnings": [],
    }


def get_meals(date_from: str | None = None, date_to: str | None = None) -> list[dict]:
    query = Meal.query
    if date_from:
        query = query.filter(Meal.meal_date >= date_from)
    if date_to:
        query = query.filter(Meal.meal_date <= date_to)
    meals = query.order_by(Meal.meal_datetime_utc.desc(), Meal.id.desc()).all()

    result = []
    for meal in meals:
        items = [_item_to_dict(i) for i in meal.items]
        names = [i["display_name"] for i in items]
        summary = ", ".join(names[:3]) + (f" +{len(names) - 3}" if len(names) > 3 else "")
        result.append({
            "meal_id": meal.id,
            "meal_type": meal.meal_type,
            "meal_datetime": to_local_iso(meal.meal_datetime_utc),
            "meal_date": meal.meal_date,
            "display_summary": summary,
            "calories_kcal": round(sum(i["calories_kcal"] for i in items), 1),
            "item_count": len(items),
        })
    return result


def get_daily_summary(date: str) -> dict:
    rows = (db.session.query(MealItem)
            .join(Meal, MealItem.meal_id == Meal.id)
            .filter(Meal.meal_date == date)
            .all())
    totals = {k: round(sum(getattr(r, k) for r in rows), 1 if k == "calories_kcal" else 2)
              for k in _TOTAL_KEYS}
    meal_ids = {r.meal_id for r in rows}
    return {"date": date, "totals": totals, "meal_count": len(meal_ids)}
```

> 空数据日自然得到全 `0.0` 与 `meal_count: 0`，无需特判。

### 8.5 初始化与种子

```python
# scripts/init_db.py
from app import create_app
from app.extensions import db

app = create_app()
with app.app_context():
    db.create_all()
    print("tables created")
```

```python
# scripts/seed_foods.py
import json
from pathlib import Path

from app import create_app
from app.extensions import db
from app.database.models import Food

DATA = Path(__file__).parent.parent / "app" / "nutrition" / "food_database.json"


def seed() -> int:
    app = create_app()
    inserted = 0
    with app.app_context():
        payload = json.loads(DATA.read_text(encoding="utf-8"))
        for row in payload["foods"]:
            if Food.query.filter_by(food_name=row["food_name"]).first():
                continue
            db.session.add(Food(
                food_name=row["food_name"],
                display_name=row["display_name"],
                calories_per_100g=row["calories_per_100g"],
                protein_per_100g=row["protein_per_100g"],
                carbs_per_100g=row["carbs_per_100g"],
                fat_per_100g=row["fat_per_100g"],
                source=row.get("source", "local"),
                aliases=",".join(row.get("aliases") or []),
                is_verified=int(row.get("is_verified", 0)),
            ))
            inserted += 1
        db.session.commit()
    return inserted


if __name__ == "__main__":
    print(f"inserted {seed()} foods")
```

### 8.6 测试夹具

```python
# tests/conftest.py
import pytest

from app import create_app
from app.extensions import db


@pytest.fixture
def app():
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "APP_TIMEZONE": "Asia/Shanghai",
    })
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def sample_meal_payload():
    return {
        "meal_type": "lunch",
        "meal_datetime_utc": "2026-11-01T04:30:00Z",
        "meal_date": "2026-11-01",
        "image_path": None,
        "items": [{
            "food_name": "cooked_white_rice",
            "display_name": "White rice",
            "weight_g": 180.0,
            "calories_kcal": 234.0,
            "protein_g": 4.86,
            "carbs_g": 50.76,
            "fat_g": 0.54,
            "food_data_source": "USDA",
        }],
    }
```

---

## 9. 测试要求

### 9.1 数据库单元测试（8 条）

| # | 用例 | 期望 |
|---|---|---|
| D1 | `save_meal` 后 `get_meal` | 返回整数 id；items 数量一致；字段逐个对得上 |
| D2 | 删 `meal` | `meal_item` 数量变 0（验证 PRAGMA 真的开了） |
| D3 | 删 `food` | 对应 `meal_item.food_id` 变 `None`，该 item **仍在** |
| D4 | `weight_g = 0` | 写入失败（CHECK 约束） |
| D5 | 重复 `food_name` 插入 `food` | 失败（UNIQUE） |
| D6 | `get_daily_summary` 空日期 | `totals` 全 `0.0`，`meal_count == 0` |
| D7 | 同一天两餐 | `meal_count == 2`，`totals` 为两者之和 |
| D8 | `delete_meal` 存在与不存在 | 存在 id 返回 `True`，明细级联消失；不存在 id 返回 `False` |

### 9.2 集成测试（3 条）

| # | 用例 | 做法 | 期望 |
|---|---|---|---|
| I1 | AI(mock) → 营养 → 存库 | monkeypatch `analyze_food` 返回 `mock_ai_result.json` | 库里出现 1 条餐食、2 条明细 |
| I2 | 未匹配食物 | mock 里含未知 `food_name` | 明细少一条，服务层收 warnings |
| I3 | 快照不变 | 存库后改 `food_database.json` 数值并重启缓存 | `get_meal` 数值不变 |

### 9.3 端到端测试（4 条）

| # | 用例 | 期望 |
|---|---|---|
| E1 | analyze(mock) → POST /meals → GET /dashboard/daily | 摘要卡路里 == 保存时算出的值 |
| E2 | 保存 → 删除 → 看板 | 看板回到 0 |
| E3 | 保存两条 → 看板 | `meal_count == 2`，`totals` 为和 |
| E4 | analyze 抛 `AI_PROVIDER_ERROR` | 返回 502 信封，库中无新增 |

### 9.4 错误码覆盖表（你要维护）

| 错误码 | 覆盖测试 | 状态 |
|---|---|---|
| `INVALID_REQUEST` | B2 / B5 / B12 / B15 | ☐ |
| `INVALID_IMAGE` | B3 | ☐ |
| `IMAGE_TOO_LARGE` | B4 | ☐ |
| `UNSUPPORTED_MEDIA_TYPE` | B3 的变体（传 `.gif`） | ☐ |
| `INVALID_WEIGHT` | B7 | ☐ |
| `FOOD_NOT_FOUND` | B8（全部未匹配） | ☐ |
| `MEAL_NOT_FOUND` | B10 / B11 | ☐ |
| `AI_PROVIDER_ERROR` | E4 | ☐ |
| `INVALID_AI_RESPONSE` | 02 文档的 AI9 | ☐ |
| `DATABASE_ERROR` | 注入异常（monkeypatch `db.session.commit` 抛错） | ☐ |
| `INTERNAL_ERROR` | 让某个 service 抛未捕获异常 | ☐ |

> 编号 B1–B15 见 [`01_BACKEND_DEVELOPER.md`](01_BACKEND_DEVELOPER.md) §9.1；AI1–AI10 见 [`02_AI_INTEGRATION_DEVELOPER.md`](02_AI_INTEGRATION_DEVELOPER.md) §9.1；D/I/E 见本文档 §9.1–§9.3。

### 9.5 测试纪律

- 一个测试只断言 1–2 件事，失败时能立刻定位。
- 测试之间不共享数据（每个测试新建内存库）。
- 不打真实 AI、不联网、不读 `.env`。
- 浮点用 `pytest.approx(abs=0.01)`。
- 修 bug 必须补一条回归测试。

---

## 10. 集成说明

### 10.1 你的依赖

| 依赖 | 提供者 | 没完成时 |
|---|---|---|
| `timeutil.to_local_iso()` | 成员1 | 先用 `datetime.fromisoformat` + 固定时区自己写，最终换成他的 |
| `ApiError` 体系 | 成员1 | 按 `00` §G.2 先建 |
| `food_database.json` | 成员3 | 先用 3 条假数据建表与测试 |
| 数据库连接配置 | 成员1（`config.py`） | 用 `TESTING` 配置注入内存库 |

### 10.2 依赖你的

| 模块 | 用你什么 | 你保证什么 |
|---|---|---|
| 成员1 | 五个仓储函数、`conftest.py` 夹具 | 返回值形状严格等于 `00` §E.4/E.5 |
| 成员4 | 看板聚合数值 | `by_meal_type` 缺失也能用（不返回它） |
| 全组 | 测试夹具、mock 文件 | 别人写测试不需要理解你的模型 |

### 10.3 什么时候合并

| 时机 | 内容 |
|---|---|
| 第 1 周末 | `models.py` + `init_db.py` + `conftest.py`（让全组能写测试） |
| 第 2 周末 | `save_meal` / `get_meal` + 种子脚本 |
| 第 3 周末 | `get_meals` / `get_daily_summary` + 集成测试 |
| 第 5 周末 | 端到端 + 错误码覆盖 |
| 第 6 周 | 测试报告 |

### 10.4 表结构要变怎么办

1. 先改 `00` §E.4 与 §C（如果你在 §C 里写了列）。
2. 群里通知全组"需删库重建"。
3. 改 `models.py`，本地 `rm instance/diet_tracker.db` 后重建。
4. 更新 `test_repository.py` 的断言。
5. **不要**悄悄加列然后指望别人删库。

---

## 11. GitHub 工作流

```bash
git checkout develop && git pull
git checkout -b feature/database
git add app/extensions.py app/database scripts tests
git commit -m "feat(database): add models, repository and seed script"
git push -u origin feature/database
```

提交示例：
- `feat(database): add meal and meal_item models with cascade`
- `feat(database): add idempotent food seeding`
- `fix(database): enable sqlite foreign keys on connect`
- `test(database): cover cascade and snapshot rules`

PR 描述必须含：
1. 是否改了表结构（是则说明"需删库重建"）；
2. 受影响的契约（预期"没有"）；
3. `pytest -q` 输出；
4. 若改了 `conftest.py`，说明影响哪些测试。

---

## 12. 最终交付清单

### 12.1 数据库

- [ ] 三张表建好，约束（CHECK / UNIQUE / FK）齐全
- [ ] `PRAGMA foreign_keys=ON` 生效（D2 证明）
- [ ] 五个仓储函数签名与 `00` §G 一致
- [ ] `save_meal` 一个事务写完，失败回滚
- [ ] `get_meal` 返回契约 D，`totals` 来自快照
- [ ] `get_daily_summary` 空数据返回全 0，不是 `None`
- [ ] `seed_foods.py` 幂等（跑两遍条数不变）
- [ ] `instance/*.db`、`uploads/*` 在 `.gitignore` 中

### 12.2 测试

- [ ] `tests/unit/test_repository.py` ≥8 条
- [ ] `tests/integration/test_pipeline.py` ≥3 条
- [ ] `tests/e2e/test_workflow.py` ≥4 条
- [ ] 11 个错误码全部有测试覆盖
- [ ] `pytest -q` < 10 秒，无需 Key / 网络 / `.env`
- [ ] 测试互不依赖（单独跑也过）

### 12.3 文档与协作

- [ ] `conftest.py` 有注释说明夹具用途
- [ ] `docs/TEST_REPORT.md`（或 PR 描述）含通过数、覆盖表、已知缺口
- [ ] 与成员1 确认过：他不再直接操作 `db.session`
- [ ] 与成员3 确认过：`food_database.json` 字段与 `seed_foods.py` 一致

### 12.4 自检问题

1. 删一条 `meal` 之后，`meal_item` 会怎样？怎么证明？（写 D2 测试）
2. 为什么 `meal_item` 要存营养值，而不是查询时重算？
3. `PRAGMA foreign_keys` 不打开会发生什么？
4. 为什么测试用 `:memory:` 而不是 `instance/diet_tracker.db`？
5. 改了 `food` 表里米饭的热量，历史餐食会变吗？（不会）
