# 膳食记录后端 — 数据库与测试层（成员 5）

对应 `05_DATABASE_AND_TESTING_DEVELOPER.md`。本目录已完成：

- 三张表：`food`、`meal`、`meal_item`（CHECK / UNIQUE / FK / 索引齐全）；
- 五个仓储函数：`save_meal` / `get_meal` / `get_meals` / `delete_meal` /
  `get_daily_summary`，外加分页辅助 `get_meal_page`；
- `scripts/init_db.py`、`scripts/seed_foods.py`（均可重复执行）；
- 测试体系：**31 条**用例，`pytest -q` 约 **0.4 秒**，不联网、不需要 Key、
  不读 `.env`。

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python scripts\init_db.py
python scripts\seed_foods.py     # 再跑一次应输出 inserted 0
pytest -q
```

本工作区已经装好依赖（`.venv/`，不入库），可直接：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## 目录

```text
app/
  __init__.py              # create_app（成员 1 的占位实现）
  extensions.py            # db + SQLite PRAGMA foreign_keys=ON
  utils/
    errors.py              # 11 个错误码与 HTTP 状态
    timeutil.py            # UTC -> 本地 ISO（默认 Asia/Shanghai）
  database/
    models.py              # Food / Meal / MealItem
    repository.py          # 五个仓储函数（唯一直接操作 db.session 的地方）
  nutrition/
    food_database.json     # 成员 3 数据的占位版本（3 条）
    calculator.py          # 按克数换算 + 未匹配食物 warnings
  ai/service.py            # 成员 2 的 AI 边界（占位）
  services/meal_service.py # analyze -> nutrition -> 草稿餐食
  api/                     # 成员 1 路由的参考实现（供集成/E2E 测试）
scripts/
  init_db.py               # create_all
  seed_foods.py            # 幂等导入 JSON
tests/
  conftest.py              # app / client / seeded_db / mock 数据夹具
  fixtures/                # mock AI JSON、样例 PNG
  unit/test_repository.py  # D1-D9 + 分页/日期过滤
  integration/test_pipeline.py
  integration/test_api_errors.py
  e2e/test_workflow.py
docs/TEST_REPORT.md        # 通过数、错误码覆盖表、已知缺口
```

## 关键规则（验收点）

| 规则 | 实现 / 证明 |
|---|---|
| 删餐食 → 明细消失 | `ON DELETE CASCADE` + ORM cascade；D2 用 Core DELETE 绕过 ORM 验证 |
| 删参考食物 → 历史明细保留，`food_id` 变 NULL | `ON DELETE SET NULL`；D3 |
| 改食物库数值 → 历史卡路里不变 | `meal_item` 存快照；I3 |
| SQLite 外键真的打开 | `app/extensions.py` 的 connect 事件；D2 断言 `PRAGMA foreign_keys == 1` |
| 一次事务写完餐食 | `save_meal`：`flush()` 拿 id → 写入全部明细 → 一次 `commit()`，异常回滚 |
| 空日期看板不返回 `None` | `COALESCE(SUM(...), 0)`；D6 |
| 种子幂等 | 已存在 `food_name` 跳过；D9 |
| 时区 | `meal_datetime_utc` 存 UTC，读取时转 `APP_TIMEZONE`（默认 `Asia/Shanghai`） |

## 契约假设与交接

本仓库只有 `05` 这一份文档，`00/01/02` 未随附，因此下面这些**他人文件**
目前是能通过全部测试的参考实现，成员 1/2/3 可以用自己的实现替换，但要保留
同名函数作为接缝：

| 文件 | 归属 | 当前形态 / 接缝 |
|---|---|---|
| `app/__init__.py` | 成员 1 | `create_app(config=None)`；`TESTING` 时用 `sqlite:///:memory:` |
| `app/api/routes.py` | 成员 1 | `POST /analyze`、`POST/GET/DELETE /meals`、`GET /dashboard/daily` |
| `app/ai/service.py` | 成员 2 | `analyze_food(image_bytes, content_type) -> dict` |
| `app/nutrition/calculator.py` | 成员 3 | `build_meal_items(detected) -> (items, warnings)`，按 `per_100g * g / 100` 换算 |

错误信封统一为：

```json
{ "error": { "code": "MEAL_NOT_FOUND", "message": "...", "details": {} } }
```

状态码：`INVALID_REQUEST` / `INVALID_IMAGE` / `INVALID_WEIGHT` 400，
`MEAL_NOT_FOUND` 404，`IMAGE_TOO_LARGE` 413，`UNSUPPORTED_MEDIA_TYPE` 415，
`FOOD_NOT_FOUND` 422，`AI_PROVIDER_ERROR` / `INVALID_AI_RESPONSE` 502，
`DATABASE_ERROR` / `INTERNAL_ERROR` 500。

`save_meal()` 只接受 `05` §5.2 的字段；未知 `food_name` 会存
`food_id = NULL` 且不报错，`totals` 永远由明细快照求和，不信任客户端。

## 测试说明

- 每条测试使用独立的内存库（`sqlite:///:memory:` + `StaticPool`），互不污染。
- AI 一律用 `monkeypatch` 打桩：`tests/fixtures/mock_ai_result*.json`。
- 浮点断言使用 `pytest.approx`。
- 单独运行某个测试也通过，例如：
  `pytest tests/unit/test_repository.py::test_d2_deleting_meal_cascades_at_database_level -q`
- 详细覆盖表见 [`docs/TEST_REPORT.md`](docs/TEST_REPORT.md)。
