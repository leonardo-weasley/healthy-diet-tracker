# 第三方组件与数据来源声明

本项目自身代码以 **MIT License** 发布（见 [`LICENSE`](LICENSE)）。
本文件列出项目在运行、构建或数据层面使用到的第三方组件与数据来源，以及它们各自的许可条款。

> 维护规则：新增依赖、替换 AI 供应商、或更新食物营养数据时，必须同步更新本文件。

---

## 1. 运行期依赖（Python 包）

以下依赖通过 `requirements.txt` 安装，**不随仓库分发源码**，由包管理器从 PyPI 获取：

| 组件 | 用途 | 许可证 | 项目主页 |
|---|---|---|---|
| Flask | Web 框架 | BSD-3-Clause | https://github.com/pallets/flask |
| Flask-SQLAlchemy | Flask 与 SQLAlchemy 集成 | BSD-3-Clause | https://github.com/pallets-eco/flask-sqlalchemy |
| SQLAlchemy | ORM | MIT | https://github.com/sqlalchemy/sqlalchemy |
| openai（Python SDK） | 调用 OpenAI 兼容接口 | Apache-2.0 | https://github.com/openai/openai-python |
| pydantic | 数据校验 | MIT | https://github.com/pydantic/pydantic |
| Pillow | 图片处理 | HPND | https://github.com/python-pillow/Pillow |
| python-dotenv | 读取 `.env` | BSD-3-Clause | https://github.com/theskumar/python-dotenv |
| pytest | 测试框架 | MIT | https://github.com/pytest-dev/pytest |
| tzdata | IANA 时区数据 | Apache-2.0 | https://github.com/python/tzdata |

许可证全文可从各项目仓库或已安装包的 `dist-info/` 目录获取。

---

## 2. 前端第三方库

| 组件 | 版本 | 引入方式 | 许可证 |
|---|---|---|---|
| [Chart.js](https://www.chartjs.org/) | 4.4.1 | `app/templates/index.html` 通过 jsDelivr CDN 引入 | MIT |

Chart.js 以 UMD 压缩包形式由 CDN 提供，仓库中**不包含**其源码。
离线环境下图表降级为数值条，不影响其余功能。

---

## 3. 外部服务（不随仓库分发）

| 服务 | 用途 | 条款 |
|---|---|---|
| [DeepSeek API](https://platform.deepseek.com/) | 多模态图像识别（OpenAI 兼容接口） | 受 DeepSeek 服务条款约束；本项目不转载、不分发其模型或输出数据集 |
| [USDA FoodData Central](https://fdc.nal.usda.gov/) | 食物营养成分参考值 | 美国联邦政府作品，**公有领域**；USDA 建议在使用时注明来源 |

### 关于 AI 输出

- AI 只返回「食物名 + 估算重量 + 置信度」，**不返回营养数值**；
- 仓库不保存任何真实用户的餐食照片（`tests/fixtures/*.jpg`、`uploads/` 均被 `.gitignore` 排除）；
- `scripts/mock_ai_provider.py` 为本地模拟实现，输出为固定场景，不调用第三方服务。

---

## 4. 数据来源与引用

### 4.1 营养数据（`app/nutrition/food_database.json`）

- 29 条食物，其中 24 条的每 100 g 营养值来自 **USDA FoodData Central**
  （Foundation / SR Legacy 数据集），每条记录 `usda.fdc_id`、原始描述、数据类型与抓取日期。
- 其余 5 条为复合菜（鸡肉饭碗、炒牛肉、红烧肉、蔬菜汤、奶茶），无单一可靠 USDA 条目，
  保留本地估算并标记 `"source": "local"`、`"is_verified": 0`。
- 数据由 `scripts/fetch_usda_foods.py` 生成，原始响应缓存于 `scripts/usda_cache/`（不提交）。

建议引用格式：

> U.S. Department of Agriculture, Agricultural Research Service.
> FoodData Central, 2026. https://fdc.nal.usda.gov/

### 4.2 截图与示例图片

- `docs/screenshots/*.png`：本项目实际运行截图，作者同本项目贡献者。
- `tests/fixtures/placeholder.jpg`：纯灰负样本，程序生成。
- `tests/fixtures/sample_meal.png`：测试用占位图，程序生成。
- 真实餐食照片仅保留在贡献者本地，不进入版本库。

---

## 5. 本项目原创内容

除上述第三方组件与数据外，以下内容均为本项目原创，并以 MIT License 发布：

- `app/` 下的应用代码、模板、样式与脚本
- `scripts/` 下的初始化、导入、模拟与联调脚本
- `tests/` 下的测试代码与测试数据
- `docs/` 下的技术文档（除明确引用的外部资料）

---

## 6. 商标声明

DeepSeek、OpenAI、GitHub、USDA 等名称与标识归各自权利人所有。
本项目与上述机构无隶属、赞助或背书关系，使用其名称仅用于说明技术依赖与数据来源。
