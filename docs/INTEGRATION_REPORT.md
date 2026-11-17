# 整合联调报告（develop-test-branch）

日期：2026-11-17  
范围：拉取 `develop-test-branch` → 按文档核对功能 → 修依赖与集成缺口 → 建库 → 端到端联调。

## 1. 结论

项目已可完整运行：上传照片 → AI 识别 → 人工修正 → 服务端重算营养 → 写入 SQLite →
仪表盘/历史查询 → 删除。184 个自动化测试全部通过，真实 HTTP 链路已实际跑通。

无真实 AI Key 时，使用仓库自带的 OpenAI 兼容模拟服务，不影响上述流程。

## 2. 启动方式

```bash
# Linux / macOS
./start.sh
# Windows
start.cmd
# 或直接
python scripts/start_dev.py
```

打开 <http://127.0.0.1:5000>。

`start_dev.py` 会依次执行：建表 → 导入食物（幂等）→ 按 `.env` 拉起模拟 AI → 启动 Flask。

## 3. 环境与依赖

- Python 3.13.5（项目要求 ≥3.11）
- Flask 3.1.3 / Flask-SQLAlchemy 3.1.1 / SQLAlchemy 2.1.9 / Pydantic 2.14.3 / openai 2.54.0
- 数据库：`instance/diet_tracker.db`（SQLite）
- 上传目录：`uploads/YYYY/MM/<uuid>.jpg`

### 修复：`openai>=3.0,<4.0` 无法安装

`openai` 3.x 依赖尚未公开发布的 `httpx2`，在 PyPI 上没有任何可安装发行版，`pip install -r
requirements.txt` 会直接失败。项目实际只使用 `chat.completions` + 多模态 `image_url`，2.x 完全满足。
已将 `requirements.txt` 改为 `openai>=2.0,<3.0`。

## 4. 按文档核对功能

| 模块 | 文档要求 | 实际状态 | 处理 |
|---|---|---|---|
| 页面路由 | 四个页面 `/`、`/upload`、`/result`、`/history` | 四个路由全部返回 `placeholder.html` | 改为分别渲染 `index/upload/result/history.html` |
| 后端 API | 6 个 `/api/v1/*` 端点、统一信封与错误码 | 已实现，测试覆盖 | 无改动 |
| AI 模块 | 只输出食物与重量，不输出营养；失败可降级 | 已实现，Pydantic 校验 + 重试 | 无改动 |
| 营养引擎 | 本地库、确定性计算、未知食物进 warnings | 已实现，29 条食物 | 营养值改为 USDA 实际拉取 |
| 数据库 | 三张表、快照式明细、级联删除 | 已实现 | 初始化并导入真实数据 |
| 前端 | 四页面、四态、Chart.js、只调 `/api/v1` | 模板/JS 完整，但未被路由使用 | 接通路由后可用 |
| 默认模式 | 持久化运行 | `BACKEND_MODE` 默认 `demo`（内存、重启清空） | 默认改为 `real`；测试仍显式使用 `demo` |
| 配置 | `.env` 驱动 | 代码读取 `AI_BASE_URL` 等变量 | 补齐 `.env` 与 `.env.example` |

## 5. 数据库与食物库

### 5.1 数据来源

新增 `scripts/fetch_usda_foods.py`，从 **USDA FoodData Central**
（`Foundation` / `SR Legacy`，公有领域）按食物逐条检索：

- 每个食物声明查询词、必须命中的关键词与排除词，避免匹配到品牌、婴儿食品或无关条目；
- 取每 100 g 的 Energy(kcal)、Protein、Carbohydrate、Total lipid；
- 每条记录写入 `usda.fdc_id`、原始描述、数据类型与抓取日期；
- 原始响应缓存到 `scripts/usda_cache/`，重复运行不重复请求（`DEMO_KEY` 有速率限制）。

24 条有可靠 USDA 对应记录的食物已更新并标记 `is_verified=1`。
5 条复合菜（鸡肉饭碗、炒牛肉、红烧肉、蔬菜汤、奶茶）没有单一可靠条目，保留本地估算并标记
`source=local`，避免用错误数据冒充权威值。

### 5.2 落库

```bash
python scripts/init_db.py      # food / meal / meal_item
python scripts/seed_foods.py   # 29 条，幂等
```

实际结果：`food=29`，数值与 `app/nutrition/food_database.json` 一致。

## 6. 无 Key 的 AI 方案

新增 `scripts/mock_ai_provider.py`：

- 实现 `POST /v1/chat/completions`，响应结构与 OpenAI 一致；
- 从 messages 中解码 base64 图片，按图片 SHA-256 稳定选择 7 种餐食场景；
- 重量做 ±10 g 的确定性抖动，返回契约 A 的 `schema_version/status/foods/warnings`；
- 提供 `GET /health` 与说明页 `GET /`；
- `.env` 指向 `http://127.0.0.1:5100/v1`，模型名 `mock-vision`。

它只用于联调，不产生真实识别；切换到真实供应商只需改 `.env` 的三行。

## 7. 端到端联调结果

用 1200×900 JPEG 实际发起请求，结果如下（节选）：

| 步骤 | 结果 |
|---|---|
| `GET /`、`/upload`、`/result`、`/history` | 全部 200，返回对应页面标题 |
| `POST /api/v1/analyze` | 200，识别出「面条 210 g / 煎蛋 60 g / 番茄 80 g」 |
| 图片落盘 | `uploads/2026/11/f44e...jpg`，按年月分目录 |
| `POST /api/v1/meals` | 201，服务端返回营养快照，总热量 421.8 kcal |
| `GET /dashboard/daily` | `meal_count=1`，总热量 421.8 kcal |
| `GET /meals?date_from&date_to` | 1 条摘要，`item_count=3` |
| `GET /meals/<id>` | 明细与 totals 一致 |
| `DELETE /meals/<id>` | `deleted=true`，仪表盘回到 0 |

## 8. 测试

```bash
pytest -q
# 184 passed
```

营养值改为 USDA 实际数据后，`tests/unit/test_calculator.py` 中写死的旧数值（如米饭蛋白
2.7 g/100g）不再成立。已把该文件的期望值改为从 `food_database.json` 推导，仍然逐项校验
「重量 / 100 × 每 100 g 值」和取整规则，没有放宽断言。其余测试未改动。

另外新增 `tests/integration/test_page_wiring.py`，锁住本次修复的两个集成点：四个页面必须
渲染真实模板（不再是占位页）、静态资源可访问，以及 mock AI 服务返回的 JSON 符合契约 A。
这样以后再出现"路由回退到占位页"或"mock 输出结构漂移"会直接被测试拦住。

## 9. 已知边界

- 模拟 AI 是固定场景，不评估照片内容，不能用于识别准确率实验；
- 删除餐食只删数据库记录，上传图片保留（与 `00` §G 的约定一致，清理脚本属选做）；
- Chart.js 走 CDN，离线打开时图表降级为数值条（前端已有 fallback）；
- `run.py` 使用 Flask 开发服务器，仅适合本地单用户，符合项目定位。
