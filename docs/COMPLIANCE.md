# 合规与文档一致性说明

检查日期：2026-11-17
检查范围：许可证、第三方引用、数据来源、仓库元数据、文档与实际代码的一致性。

---

## 1. 结论

| 项目 | 状态 | 说明 |
|---|---|---|
| 项目许可证 | ✅ 已有 | `LICENSE` 为 MIT，但此前 README 未明确声明，现已补齐 |
| 第三方组件声明 | ✅ 已补 | 新增 `THIRD_PARTY_NOTICES.md` |
| 数据来源与引用 | ✅ 已补 | USDA 逐条保留 `fdc_id`；README 增补引用建议 |
| 仓库元数据 | ✅ 已补 | 新增 `CITATION.cff`；README 顶部增加版本/许可证表 |
| 敏感文件 | ✅ 合规 | `.env`、`instance/`、`uploads/`、真实照片均被忽略 |
| 文档一致性 | ⚠️ 已修复主要问题 | 详见 §6；历史交接文档已标注"已过时" |

---

## 2. 许可证

- 项目代码、模板、样式、脚本、测试与文档：**MIT License**（`LICENSE`）。
- 版权行：`Copyright (c) 2026 leonardo-weasley`。
- README §14 现在明确写出许可证类型，并链接 `LICENSE`、`THIRD_PARTY_NOTICES.md` 与 `CITATION.cff`。
- `LICENSE` 正文保持 MIT 原文，不做改写。

> 注意：MIT 许可证要求保留版权声明与许可声明。再分发本项目时，
> 必须同时保留 `LICENSE` 与本文件、`THIRD_PARTY_NOTICES.md`。

---

## 3. 第三方组件

完整清单见 [`THIRD_PARTY_NOTICES.md`](../THIRD_PARTY_NOTICES.md)。摘要：

| 类别 | 组件 | 许可 |
|---|---|---|
| Python 依赖 | Flask / Flask-SQLAlchemy / SQLAlchemy / openai / pydantic / Pillow / python-dotenv / pytest / tzdata | BSD / MIT / Apache-2.0 / HPND |
| 前端 CDN | Chart.js 4.4.1 | MIT |
| 外部服务 | DeepSeek API | 服务条款约束，不转载模型与数据集 |
| 数据集 | USDA FoodData Central | 公有领域，建议注明来源 |

以下内容**不随仓库分发**，因此不涉及再分发许可：

- 真实餐食照片（`tests/fixtures/*.jpg`、`tests/fixtures/*.jpeg` 被 `.gitignore` 排除）
- 上传文件（`uploads/`）
- SQLite 数据库（`instance/`）
- API 密钥（`.env`）
- USDA 原始响应缓存（`scripts/usda_cache/`）

---

## 4. 数据来源与引用

- `app/nutrition/food_database.json` 共 29 条食物：
  - 24 条来自 USDA FoodData Central（Foundation / SR Legacy），均带 `usda.fdc_id`；
  - 5 条复合菜为本地估算，标记 `source=local`、`is_verified=0`，不冒充权威数据。
- README §15 与 `THIRD_PARTY_NOTICES.md` §4 均给出了 USDA 的引用格式与链接。
- `scripts/fetch_usda_foods.py` 保留可复现的抓取流程（含缓存与 `--dry-run`）。

---

## 5. 仓库元数据

| 元数据 | 位置 | 状态 |
|---|---|---|
| 项目名称 | `README.md` 标题、`CITATION.cff` | ✅ |
| 版本 | `1.0.0`（README 表格、`CITATION.cff`） | ✅ 新增 |
| 许可证 | `LICENSE`、README §14、`CITATION.cff` | ✅ |
| Python 版本要求 | README §6、`CITATION.cff` 摘要 | ✅ |
| 作者/团队 | `CITATION.cff`（团队署名）、README §9 | ✅ |
| 仓库地址 | README §7.1、`CITATION.cff` | ✅ 已改为真实地址 |
| 引用信息 | `CITATION.cff` | ✅ 新增 |
| 关键词/摘要 | `CITATION.cff` | ✅ 新增 |

**未添加 `pyproject.toml`**：本项目以源码方式运行（`python run.py` / `python scripts/start_dev.py`），
不通过 `pip install` 分发，也不发布到 PyPI。引入打包元数据会与现有 `pytest.ini`、
`requirements.txt` 流程重复，收益有限。若后续要打包，再补 `pyproject.toml`。

---

## 6. 发现的不一致与处理

| # | 位置 | 问题 | 处理 |
|---|---|---|---|
| 1 | `README.md` §5 文档导航 | 写"24 条初始数据"，实际为 29 条 | 已改为 29 条 |
| 2 | `README.md` §7.1 | 克隆地址为占位符 `YOUR-TEAM` | 已改为真实仓库地址 |
| 3 | `README.md` §11.1–11.3 | 分支写作 `develop`，实际为 `develop-test-branch` | 已改为实际分支名，并注明旧文档的简称 |
| 4 | `README.md` §11.4 | `.gitignore` 示例与实际文件不一致（`instance/*.db`、`!uploads/.gitkeep` 等） | 已按实际 `.gitignore` 重写 |
| 5 | `README.md` §14 | 只写"课程项目用途"，未声明 MIT | 已补许可证与致谢两节 |
| 6 | `docs/BACKEND_HANDOFF.md` | 称 `BACKEND_MODE=demo` 为默认、真实流程"尚未接通"、只有 140 项测试 | 文件顶部加"历史文档"横幅，指向 `INTEGRATION_REPORT.md` |
| 7 | `docs/TEST_REPORT.md` | 称"本次冲突解决没有运行测试"，不报告结果 | 文件顶部加"历史文档"横幅，指向 `INTEGRATION_REPORT.md` |
| 8 | `docs/00`–`05` | 流程中统一使用 `develop` 作为集成分支名 | 规范文档作为"流程约定"保留；README 已说明实际分支名，避免误操作 |
| 9 | `README.md` §2 | 写"本地 20–30 条食物库" | 属范围描述，与 29 条不冲突，未改 |

一致性基准（当前实测）：

| 指标 | 数值 | 核对方式 |
|---|---|---|
| 食物条目 | 29（USDA 24 + 本地 5） | `app/nutrition/food_database.json` |
| API 端点 | 6 个 `/api/v1/*` | `app/routes/` |
| 页面 | 4 个 | `app/routes/pages.py` |
| 数据表 | 3 张（`food` / `meal` / `meal_item`） | `app/database/models.py` |
| 测试 | 184 个用例 | `pytest --collect-only -q` |
| 默认运行模式 | `BACKEND_MODE=real` | `app/config.py`、`.env.example` |
| openai 版本 | `>=2.0,<3.0` | `requirements.txt` |

---

## 7. 仍需在 GitHub 网页完成

以下属于仓库设置，无法通过提交文件完成：

1. **About 区域**：填写 Description、Topics（如 `flask`、`nutrition`、`sqlite`、`computer-vision`）。
2. **License 识别**：GitHub 通常会自动识别 `LICENSE` 为 MIT；若未显示，在仓库设置中确认。
3. **Cite this repository**：`CITATION.cff` 推送后，仓库页右侧会出现引用按钮。
4. **分支保护**：对 `main` 开启 "Require a pull request before merging"。
5. **Security**：确认 `.env`、数据库、上传图片从未出现在历史提交中（当前工作区合规，
   但若历史提交曾包含密钥，需要在 GitHub 上轮换密钥）。

### 已知风险与可选项

- `app/templates/index.html` 通过 jsDelivr 引入 Chart.js 4.4.1，版本已固定，
  但**未设置子资源完整性（SRI）**。若需更严格，可下载到 `app/static/vendor/` 本地引入，
  或补充 `integrity` 与 `crossorigin` 属性。
- `LICENSE` 的版权行当前为个人账号 `leonardo-weasley`。若团队希望署名为全体贡献者，
  可在获得同意后改为团队名称，并在 README §15 保持一致。
- 仓库尚未配置 CI。建议至少对 `main` 与集成分支开启 "运行 `pytest`" 的工作流。

---

## 8. 维护规则

- 新增依赖或替换 AI 供应商 → 更新 `THIRD_PARTY_NOTICES.md` 与 `requirements.txt`。
- 更新营养数据 → 保留 `usda.fdc_id`，同步 README 中的条目数。
- 删除或重命名文档 → 同步 README §5 的文档导航。
- 每次发版 → 更新 README 顶部版本表与 `CITATION.cff` 的 `version` / `date-released`。
- 提交前确认 `git status` 不含 `.env`、`instance/`、`uploads/`、真实照片。
