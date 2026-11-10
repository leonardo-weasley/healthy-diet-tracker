# 测试报告 — 数据库与测试层（成员 5）

| 项 | 值 |
|---|---|
| 日期 | 2026-11-07 |
| Python | 3.12.14 |
| Flask / Flask-SQLAlchemy | 3.1.3 / 3.1.1 |
| SQLAlchemy | 2.1.8 |
| pytest | 9.2.0 |
| 命令 | `.\.venv\Scripts\python.exe -m pytest -q` |
| 结果 | **31 passed**，pytest 计时 **0.44 s**（进程总耗时约 2 s） |
| 外部依赖 | 无网络、无 API Key、无 `.env`、无真实 AI |

```text
...............................                                          [100%]
31 passed in 0.44s
```

## 1. 分层统计

| 层 | 文件 | 条数 | 说明 |
|---|---|---|---|
| 数据库单元 | `tests/unit/test_repository.py` | 11 | D1–D9 + 日期过滤/分页 + items 数量校验 |
| 集成（AI→营养→DB） | `tests/integration/test_pipeline.py` | 4 | I1–I4 |
| API 错误码 | `tests/integration/test_api_errors.py` | 12 | 11 个错误码（`MEAL_NOT_FOUND` 覆盖 GET/DELETE 两条） |
| 端到端 | `tests/e2e/test_workflow.py` | 4 | E1–E4 |
| 合计 | | **31** | |

## 2. 数据库用例（D1–D9）

| # | 测试 | 断言要点 | 状态 |
|---|---|---|---|
| D1 | `test_d1_save_meal_then_get_meal_round_trips` | 返回 int id；字段、数量、时区、totals 全部对齐 | ☑ |
| D2 | `test_d2_deleting_meal_cascades_at_database_level` | `PRAGMA foreign_keys == 1`；Core DELETE 后明细为 0 | ☑ |
| D3 | `test_d3_deleting_food_keeps_history_and_nulls_food_id` | 明细仍在，`food_id` 为 `None`，快照数值不变 | ☑ |
| D4 | `test_d4_zero_weight_fails_check_constraint` | 抛 `DatabaseError` 且事务回滚、无残留行 | ☑ |
| D5 | `test_d5_duplicate_food_name_fails_unique_constraint` | `IntegrityError`，仍只有 1 行 | ☑ |
| D6 | `test_d6_empty_day_summary_is_all_zeros` | `meal_count == 0`，totals 全 `0.0`（不是 `None`） | ☑ |
| D7 | `test_d7_two_meals_same_day_are_summed` | `meal_count == 2`，卡路里/蛋白/碳水/脂肪为两者之和 | ☑ |
| D8 | `test_d8_delete_meal_reports_existence_and_removes_items` | 存在返回 `True` + 级联；不存在返回 `False` | ☑ |
| D9 | `test_d9_seed_foods_is_idempotent` | 第一次 3 条，第二次 0 条，总数仍为 3 | ☑ |
| — | `test_get_meals_filters_dates_and_orders_newest_first` | 日期闭区间过滤、倒序、分页 | ☑ |
| — | `test_items_count_must_be_between_one_and_twenty` | 0 条 / 21 条均抛 `InvalidRequest` | ☑ |

## 3. 集成用例（I1–I4）

| # | 测试 | 断言要点 | 状态 |
|---|---|---|---|
| I1 | `test_i1_mock_ai_produces_nutrition_and_database_rows` | mock AI 2 项 → 1 餐 2 明细；180 g 米饭 = 234.0 kcal | ☑ |
| I2 | `test_i2_unknown_food_is_dropped_with_a_warning` | 明细少一条；warning code `FOOD_NOT_FOUND` | ☑ |
| I3 | `test_i3_snapshot_does_not_change_when_food_values_change` | 改 `food` 表数值后，历史 meal_item 不变 | ☑ |
| I4 | `test_i4_malformed_ai_response_raises` | 空 `detected` → `INVALID_AI_RESPONSE` | ☑ |

> I3 用修改 `food` 行来模拟"食物库数值变化"；`meal_item` 的快照不依赖读取时重算，
> 因此与直接改 `food_database.json` 后重新导入等价（幂等导入会跳过已存在行）。

## 4. 端到端用例（E1–E4）

| # | 测试 | 断言要点 | 状态 |
|---|---|---|---|
| E1 | `test_e1_analyze_then_save_then_dashboard` | analyze → POST /meals → 看板卡路里 == 保存时求和（481.5） | ☑ |
| E2 | `test_e2_delete_returns_dashboard_to_zero` | 保存 → 删除 → 看板 `meal_count == 0`、卡路里 0 | ☑ |
| E3 | `test_e3_two_meals_are_summed_on_the_dashboard` | 同一天两餐 → `meal_count == 2`、totals 为和 | ☑ |
| E4 | `test_e4_ai_provider_error_returns_502_and_writes_nothing` | 502 信封 + 库中无新增 | ☑ |

## 5. 错误码覆盖表（11/11）

| 错误码 | 覆盖测试 | 状态 |
|---|---|---|
| `INVALID_REQUEST` | `test_invalid_request_for_empty_items` | ☑ |
| `INVALID_IMAGE` | `test_invalid_image_from_provider` | ☑ |
| `IMAGE_TOO_LARGE` | `test_image_too_large` | ☑ |
| `UNSUPPORTED_MEDIA_TYPE` | `test_unsupported_media_type` | ☑ |
| `INVALID_WEIGHT` | `test_invalid_weight` | ☑ |
| `FOOD_NOT_FOUND` | `test_food_not_found_when_no_detection_matches` | ☑ |
| `MEAL_NOT_FOUND` | `test_meal_not_found_on_get` / `test_meal_not_found_on_delete` | ☑ |
| `AI_PROVIDER_ERROR` | `test_ai_provider_error` / `test_e4_ai_provider_error_returns_502_and_writes_nothing` | ☑ |
| `INVALID_AI_RESPONSE` | `test_invalid_ai_response` | ☑ |
| `DATABASE_ERROR` | `test_database_error` | ☑ |
| `INTERNAL_ERROR` | `test_internal_error` | ☑ |

## 6. 测试纪律核对

- [x] 每个测试只断言 1–2 类事实，失败信息可定位。
- [x] 每个测试独立创建内存库，互不共享数据。
- [x] 不打真实 AI、不联网、不读 `.env`。
- [x] 浮点统一 `pytest.approx(abs=0.01)`（默认容差）。
- [x] 单条测试可单独运行、可乱序运行。
- [x] `pytest -q` 远低于 10 秒。

## 7. 已知缺口 / 交接

1. `00/01/02` 文档未随附，`app/__init__.py`、`app/api/routes.py`、
   `app/ai/service.py`、`app/nutrition/calculator.py` 是参考实现；成员 1/2/3
   替换时保留同名函数与错误信封即可，测试会继续作为契约回归。
2. 上传校验只做到"MIME 白名单 + 非空 + 10 MiB"，没有解码图片校验真实格式；
   成员 2 接入真实 AI 后应在 `analyze_food` 内抛 `INVALID_IMAGE`。
3. 未实现 `by_meal_type`（`05` §10.2 明确"缺失也能用"）；成员 4 需要时再加
   `GROUP BY`，不影响现有契约。
4. 不做 Alembic 迁移、多用户、软删除、缓存层（与 `05` §2.4 一致）。
5. 真实 `food_database.json` 由成员 3 提供；当前
   `app/nutrition/food_database.json` 是 3 条占位数据，字段名与
   `scripts/seed_foods.py` 已对齐。
