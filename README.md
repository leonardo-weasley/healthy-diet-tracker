# Healthy Diet Tracker · 健康饮食追踪器

一个在**本地浏览器**运行的个人饮食追踪应用：上传一张餐食照片 → 多模态 AI 识别食物并估算份量 → **我们自己的 Python 算法**查本地营养库计算卡路里与宏量营养素 → 用户确认/修正 → 存入本地 SQLite → 仪表盘查看每日与历史统计。

- 团队：5 名大学生开发者，6 周
- 形态：本地 Web 应用（`http://127.0.0.1:5000`），单机单用户
- 用途：课程项目 / 个人记录，**所有营养数值都是估算值，不得当作医学营养测量**

---

## 1. 项目简介

### 1.1 要解决的问题

记录饮食很麻烦：手查食物重量、手翻营养表、手动累加。本应用把最费劲的三步交给程序：

1. **识别**——AI 看照片说"这是米饭和鸡胸肉，大概 180 g 和 120 g"。
2. **计算**——我们用受控的本地营养库做确定性计算，结果可复现、可单元测试。
3. **累计**——存库、按天汇总、画图。

### 1.2 核心架构原则

> **AI 只负责"是什么、大概多重"，绝不负责"多少卡路里"。**

所有营养计算都由我们自己的纯函数完成。这样做的原因：

| 原因 | 说明 |
|---|---|
| 可复现 | 同一输入永远同一输出，测试能精确断言到 0.01 |
| 可解释 | 答辩时能说清"234 kcal = 180 / 100 × 130" |
| 省钱 | 营养计算不发一次 API 请求 |
| 可替换 | 换 AI 供应商不影响营养模块 |

---

## 2. 主要功能

| 功能 | 说明 | MVP 级别 |
|---|---|---|
| 餐食照片上传 | JPEG/PNG/WebP，≤ 8 MB，带预览与餐型选择 | 必须 |
| AI 食物识别 | 返回结构化 JSON：食物名、估算重量、置信度 | 必须 |
| 营养计算 | 查本地 20–30 条食物库，算卡路里/蛋白/碳水/脂肪 | 必须 |
| 结果人工修正 | 保存前可改食物名与重量，后端**重新计算** | 必须 |
| 餐食日记 | 保存到 SQLite，含营养快照 | 必须 |
| 每日仪表盘 | 今日卡路里、目标进度、宏量营养素、最近餐食 | 必须 |
| 历史记录 | 按日期/区间查询、查看明细、删除 | 必须 |
| 图表 | Chart.js：宏量营养素环形图、卡路里进度 | 必须 |
| 未知食物处理 | 提示手动选择/录入，不静默填默认值 | 必须 |
| 自定义食物条目 | 用户新增食物到本地库 | 选做（Level 2） |
| 每周趋势图 | 复用区间查询，前端聚合 | 选做（Level 2） |
| 份量准确性实验 | 30 张照片对比实际称重，算 MAPE | 选做（Level 3） |

**明确不做**：注册登录、社交分享、移动 App、可穿戴同步、个性化营养建议、微服务、Docker。

---

## 3. 技术栈

| 层 | 技术 | 版本 | 用途 |
|---|---|---|---|
| 语言 | Python | 3.11+ | 后端与营养计算 |
| Web 框架 | Flask | 3.x | 路由、模板渲染、JSON 接口 |
| 前端 | HTML / CSS / 原生 JavaScript | — | 页面与交互，**不用框架** |
| 图表 | Chart.js | 4.x | 仪表盘可视化（CDN 引入） |
| AI | Google Gemini API（`google-genai` SDK） | 最新 | 图像理解 + 强制 JSON 输出 |
| 校验 | Pydantic | v2 | 模块边界数据校验 |
| 数据库 | SQLite | 3 | 本地持久化，单文件 |
| ORM | SQLAlchemy / Flask-SQLAlchemy | 2.x / 3.x | 模型与关系 |
| 测试 | pytest | 8.x | 单元/集成/端到端 |
| 配置 | python-dotenv | 1.x | 从 `.env` 读取密钥 |
| 协作 | Git + GitHub | — | 分支、PR、Review |

**不引入**：React、Vue、Node.js、Docker、Redis、Celery、消息队列、Alembic、前端构建工具。

---

## 4. 架构概览

```
浏览器（HTML/CSS/JS + Chart.js）
        │ HTTP + JSON / multipart
        ▼
Flask 路由层  routes/          ← 很薄：解析 → 调服务 → 序列化
        │ Python 函数调用
        ▼
服务层  services/meal_service.py   ← 编排、校验、事务边界
   │            │            │
   ▼            ▼            ▼
AI 模块      营养模块      数据库模块
ai/          nutrition/    database/
   │            │            │
   ▼            ▼            ▼
Gemini API   本地 JSON 营养库   SQLite
```

四条硬边界（违反即架构事故）：

1. **AI 不算营养**：`app/ai/**` 里不许出现 `calories`、`protein` 等字段的计算。
2. **营养不联网**：`app/nutrition/**` 里不许 import `requests` / `google.*` / `openai`。
3. **前端不碰数据层**：`app/static/**` 里只允许请求 `/api/v1/*`。
4. **供应商只在一处**：只有 `app/ai/client.py` 可以 import AI SDK。

完整架构、数据流图、契约定义见 [`docs/00_MAIN_TECHNICAL_ROUTE.md`](docs/00_MAIN_TECHNICAL_ROUTE.md)。

---

## 5. 文档导航

| 文件 | 谁必读 | 内容 |
|---|---|---|
| [`docs/00_MAIN_TECHNICAL_ROUTE.md`](docs/00_MAIN_TECHNICAL_ROUTE.md) | **全员** | 权威技术规范：架构、契约、6 个端点、7 个函数签名、错误码、Git 流程、里程碑、验收标准 |
| [`docs/01_BACKEND_DEVELOPER.md`](docs/01_BACKEND_DEVELOPER.md) | 成员1 | Flask 应用工厂、6 个路由、服务编排、上传校验、错误翻译 |
| [`docs/02_AI_INTEGRATION_DEVELOPER.md`](docs/02_AI_INTEGRATION_DEVELOPER.md) | 成员2 | 供应商接入、提示词、JSON 输出、Pydantic 校验、超时重试、mock |
| [`docs/03_NUTRITION_ENGINE_DEVELOPER.md`](docs/03_NUTRITION_ENGINE_DEVELOPER.md) | 成员3 | 食物库格式与 24 条初始数据、匹配策略、计算公式、取整、单测 |
| [`docs/04_FRONTEND_DEVELOPER.md`](docs/04_FRONTEND_DEVELOPER.md) | 成员4 | 四个页面、元素 id、Fetch 封装、加载/错误/空状态、Chart.js |
| [`docs/05_DATABASE_AND_TESTING_DEVELOPER.md`](docs/05_DATABASE_AND_TESTING_DEVELOPER.md) | 成员5 | 三张表、SQLAlchemy 模型、仓储函数、聚合查询、测试体系 |

**推荐的阅读顺序**

1. 所有人：本 README §1–§4 → `00_MAIN_TECHNICAL_ROUTE.md`（全文，约 40 分钟）。
2. 各人再读自己那份；只需预览直接上下游那一节（文档里已标注）。
3. 动代码前，确保能回答："我这个模块的输入是什么、输出是什么、错了返回什么"。

---

## 6. 环境要求

| 项 | 要求 |
|---|---|
| 操作系统 | Windows 10/11、macOS 12+、或 Linux（团队用 Windows 演示） |
| Python | **3.11 或更高**（`python --version` 确认） |
| pip | 随 Python 安装 |
| Git | 2.30+ |
| 编辑器 | VS Code（推荐，装 Python 扩展） |
| 浏览器 | Chrome / Edge 最新版 |
| 网络 | 只在调用 AI 时需要；其余功能可离线 |
| Gemini API Key | 免费额度足够，从 Google AI Studio 获取 |

检查环境：

```bash
python --version     # 需 ≥ 3.11
git --version
```

---

## 7. 快速开始

### 7.1 克隆并创建虚拟环境

```bash
git clone https://github.com/YOUR-TEAM/healthy-diet-tracker.git
cd healthy-diet-tracker

python -m venv .venv
```

激活虚拟环境：

```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Windows (CMD)
.venv\Scripts\activate.bat
# macOS / Linux
source .venv/bin/activate
```

> 若 PowerShell 报 "执行策略阻止脚本"，先运行：
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

### 7.2 安装依赖

```bash
pip install -r requirements.txt
```

`requirements.txt` 内容：

```text
Flask>=3.0
Flask-SQLAlchemy>=3.1
SQLAlchemy>=2.0
pydantic>=2.6
python-dotenv>=1.0
Pillow>=10.0
google-genai>=0.3
pytest>=8.0
```

### 7.3 配置环境变量

复制模板并填自己的 Key：

```bash
# Windows
copy .env.example .env
# macOS / Linux
cp .env.example .env
```

`.env`（**绝不提交**）：

```dotenv
FLASK_ENV=development
SECRET_KEY=change-me-locally
AI_PROVIDER=gemini
AI_API_KEY=你的真实key
AI_MODEL=gemini-2.0-flash
AI_TIMEOUT_SECONDS=30
DATABASE_URL=sqlite:///instance/diet_tracker.db
APP_TIMEZONE=Asia/Shanghai
```

> `AI_MODEL` 的具体型号会随供应商更新，以官方文档为准。没有 Key 也能起服务，只是上传分析会返回 `AI_PROVIDER_ERROR`——这方便前端先开发。

### 7.4 初始化数据库与食物库

```bash
python scripts/init_db.py      # 建三张表
python scripts/seed_foods.py   # 导入 20–30 条食物（幂等，可重复跑）
```

### 7.5 运行

```bash
python run.py
```

浏览器打开 <http://127.0.0.1:5000>。

### 7.6 跑测试

```bash
pytest -v                       # 全部
pytest tests/unit -v            # 只跑单元测试
pytest -k calculator            # 只跑名字含 calculator 的用例
```

预期：不需要真实 API Key、不需要网络，10 秒内全绿。

---

## 8. 仓库结构

```text
healthy-diet-tracker/
├── run.py                      # 启动入口
├── requirements.txt
├── .env.example                # 变量清单（无真实密钥）
├── .gitignore
├── README.md                   # 本文件
│
├── docs/                       # 全部规范文档（见 §5）
│
├── app/
│   ├── __init__.py             # create_app()
│   ├── config.py               # 配置
│   ├── extensions.py           # db = SQLAlchemy()
│   ├── routes/                 # HTTP 路由（成员1）
│   ├── services/               # 服务编排（成员1）
│   ├── ai/                     # AI 识别（成员2）
│   ├── nutrition/              # 营养引擎（成员3）
│   ├── database/               # 模型与仓储（成员5）
│   ├── utils/                  # errors / images / timeutil（成员1）
│   ├── templates/              # 5 个页面模板（成员4）
│   └── static/                 # CSS + JS（成员4）
│
├── tests/
│   ├── conftest.py             # 夹具
│   ├── fixtures/               # mock JSON、样例照片
│   ├── unit/
│   ├── integration/
│   └── e2e/
│
├── scripts/
│   ├── init_db.py
│   ├── seed_foods.py
│   └── evaluate_portions.py    # 选做：MAPE 实验
│
├── instance/                   # SQLite 文件（Git 忽略）
└── uploads/                    # 上传图片（Git 忽略）
```

每个文件的归属见 `00_MAIN_TECHNICAL_ROUTE.md` §C.1。**一个文件只能有一个所有者**，其他人通过接口调用。

---

## 9. 团队分工

| 成员 | 角色 | 主要负责 | 关键交付物 |
|---|---|---|---|
| 1 | 团队负责人 / 后端集成 | `app/routes/**`、`app/services/**`、`app/__init__.py`、`app/utils/**` | 一个能跑的 Flask 应用 + 六个接口 + 统一错误处理 |
| 2 | AI 集成 | `app/ai/**` | 照片 → 契约 A 的 JSON，失败能降级 |
| 3 | 营养引擎 | `app/nutrition/**` | 20+ 食物库 + 计算模块 + 单测 |
| 4 | 前端 | `app/templates/**`、`app/static/**` | 四个页面 + 图表 + 四态处理 |
| 5 | 数据库与测试 | `app/database/**`、`app/extensions.py`、`scripts/`、`tests/conftest.py` | 三张表 + 仓储函数 + 测试体系 |

每周目标见 `00_MAIN_TECHNICAL_ROUTE.md` §J。

---

## 10. 六周时间线（概要）

| 周 | 目标 | 验收 |
|---|---|---|
| 1 | 架构、契约、目录、骨架、能渲染的页面 | 五人都能 clone 并跑起来 |
| 2 | 三个模块各自独立可测 | 单测全绿，AI 对真实照片出 JSON |
| 3 | AI → 营养 → 数据库 串联 | 集成测试通过 |
| 4 | 浏览器完整流程 | 不写脚本也能用 |
| 5 | 看板、错误处理、30 张照片测试 | 错误码全覆盖 |
| 6 | 冻结功能、修 bug、文档、演示 | 3 分钟演示不翻车 |

---

## 11. 协作约定

### 11.1 分支

| 分支 | 用途 |
|---|---|
| `main` | 稳定可演示版，只接受来自 `develop` 的 PR |
| `develop` | 集成，随时可运行 |
| `feature/<模块>` | 个人开发分支 |

### 11.2 提交流程

```bash
git checkout develop && git pull
git checkout -b feature/ai
# 写代码
git add app/ai tests/unit/test_ai_schema.py
git commit -m "feat(ai): add image analyzer with schema validation"
git push -u origin feature/ai
# 开 PR → develop，找 1 人 Review
```

提交前缀：`feat` / `fix` / `docs` / `test` / `refactor` / `style` / `chore`。

### 11.3 五条纪律

1. **不许直接推 `main`**，也不许直接推 `develop`。
2. **不许把红着测试的代码合进 `develop`**。
3. **不许提交** `.env`、`instance/*.db`、`uploads/*`、真实餐食照片。
4. **不许单方面改契约**：改字段名 = 改 `00_MAIN_TECHNICAL_ROUTE.md` + 全组通知。
5. **不许在 PR 里顺手重构别人的模块**。

### 11.4 `.gitignore` 必须包含

```gitignore
.env
.venv/
__pycache__/
*.pyc
.pytest_cache/
instance/*.db
uploads/*
!uploads/.gitkeep
instance/.gitkeep
.DS_Store
Thumbs.db
```

---

## 12. 常见问题

| 现象 | 原因 | 解决 |
|---|---|---|
| `ModuleNotFoundError: flask` | 虚拟环境没激活 | 重新激活 `.venv` 后 `pip install -r requirements.txt` |
| 上传后提示 "AI 服务不可用" | 没配 `AI_API_KEY`，或额度用尽 | 检查 `.env`；换 Key 或稍后重试 |
| 端口 5000 被占用 | 另一个进程在用 | 改 `run.py` 里的 `port=5001`，或用 `Get-NetTCPConnection -LocalPort 5000` 找进程 |
| 数据库表不存在 | 没跑初始化 | `python scripts/init_db.py && python scripts/seed_foods.py` |
| 保存后卡路里没变 | 后端没重算，或前端算了假数 | 见 `01_BACKEND_DEVELOPER.md` §7；前端禁止提交营养字段 |
| 历史页显示不了中文 | 响应头缺 charset | 确认 `Content-Type: application/json; charset=utf-8` |
| `pytest` 报找不到模块 | 没在仓库根目录运行 | 在仓库根目录执行 `pytest` |

---

## 13. 免责声明

本项目所有营养数值均为**基于公开数据的估算**：

- 食物重量由 AI 从单张照片估算，误差可达 ±20% 以上；
- 营养值来自本地参考库，不能反映具体烹饪用油、配料与品牌差异；
- 不得用于医疗、疾病管理或专业营养干预。

界面上必须常驻一句提示：**"营养数据为估算值，仅供参考。"**

---

## 14. 许可证与致谢

课程项目用途。营养参考数据来自 [USDA FoodData Central](https://fdc.nal.usda.gov/)（公有领域），AI 能力由 Google Gemini API 提供。


## 成员 1 后端联调入口

后端应用工厂、6 个 API、上传与错误处理已接入。默认 BACKEND_MODE=demo，使用固定 AI、两条营养测试数据和内存仓储；记录重启后清空。

Windows 完整解压后可双击 start.cmd；新电脑需要先安装 Python 3.11+ 并勾选 Add python.exe to PATH，首次安装依赖需联网。也可按本 README 的虚拟环境步骤安装依赖后执行 python run.py。

后端说明见 docs/BACKEND_HANDOFF.md。真实模式仍需要成员 3 的营养模块和成员 5 的数据库模块；成员 2 已有的 AI 代码保持原样。
