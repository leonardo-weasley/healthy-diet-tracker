# 前端交接说明（成员 4）

> 上位文档：[`00_MAIN_TECHNICAL_ROUTE.md`](00_MAIN_TECHNICAL_ROUTE.md)、[`04_FRONTEND_DEVELOPER.md`](04_FRONTEND_DEVELOPER.md)。
> 本文只说明**前端模块怎么接进 Flask**、用了哪些接口、以及 v1 契约里目前接不上的地方。

## 1. 交付文件

```text
app/templates/
├── base.html
├── index.html
├── upload.html
├── result.html
└── history.html

app/static/
├── css/style.css
└── js/
    ├── api.js            # 全站唯一写 fetch() 的地方
    ├── food-options.js   # 标准食物下拉清单（只有 ID + 中文名，无营养数值）
    ├── dashboard.js
    ├── upload.js
    ├── result.js
    └── history.js
```

预览截图（用 mock 数据渲染，不是真实后端）：

| 桌面端首页 | 桌面端结果页 |
|---|---|
| ![首页](screenshots/dashboard.png) | ![结果页](screenshots/result.png) |

| 手机端首页 | 手机端历史页 |
|---|---|
| ![手机首页](screenshots/dashboard-mobile.png) | ![手机历史](screenshots/history-mobile.png) |

这些文件都属于成员 4 的目录范围，不需要改成员 1/2/3/5 的任何 Python 文件。

## 2. 与后端的最小接线

成员 1 只需保证 4 个页面路由渲染对应模板，静态目录保持 `app/static`：

```python
render_template("index.html")    # GET /
render_template("upload.html")   # GET /upload
render_template("result.html")   # GET /result
render_template("history.html")  # GET /history
```

模板**不依赖任何额外上下文变量**：导航高亮用 Flask 全局的 `request.path`，静态资源用
`url_for('static', filename=...)`。因此 `render_template("index.html")` 直接调用即可。

前端只调用 `00` §F 的 6 个接口：

| 页面 | 调用的接口 |
|---|---|
| 首页 | `GET /api/v1/dashboard/daily?date=`、`GET /api/v1/meals?limit=5` |
| 上传页 | `POST /api/v1/analyze`（multipart：`image` + `meal_type`） |
| 结果页 | `POST /api/v1/meals`（契约 B） |
| 历史页 | `GET /api/v1/meals`、`GET /api/v1/meals/{id}`、`DELETE /api/v1/meals/{id}` |

没有新增任何接口，也没有在前端直连数据库或 AI。

### 2.1 文字/手动记录（不经过 AI）

上传页底部有“直接手动记录这一餐”：它把一份 `foods: []` 的草稿写入
`sessionStorage.analysisResult`，跳到结果页，用户在标准食物下拉里选择并填重量，
最后仍然走 `POST /api/v1/meals`。这样“文字输入”不需要新接口，但只能选择
`food-options.js` 里已有的标准食物；完全自由的食物名需要后端新增食物接口，属 v2。

## 3. 前端内部约定

### 3.1 sessionStorage

| key | 写入方 | 读取方 | 内容 |
|---|---|---|---|
| `analysisResult` | `upload.js` | `result.js` | `/analyze` 的 `data`，额外补 `meal_type`、`requested_at` |
| `hdt.flash` | `result.js` / 其他页 | `dashboard.js` | 跨页一次性提示（`{type, message}`） |
| `hdt.historyFilters` | `history.js` | `history.js` | 历史页上次筛选的日期区间 |

`analysisResult` 为空时，直接访问 `/result` 会自动跳回 `/upload`。

### 3.2 错误处理

`api.js` 的 `apiFetch()` 负责：

1. 拼接 `/api/v1`；
2. 60 秒超时（`/analyze` 单独 90 秒）；
3. 解析 JSON 信封，区分“HTTP 失败”和“业务失败”；
4. 抛出带 `code` 的 `Error`，页面用 `errorText(code)` 转中文。

所有 11 个错误码都有中文文案；另外加了两个前端本地码：

- `NETWORK_ERROR`：连不上 Flask；
- `REQUEST_TIMEOUT`：请求超时。

### 3.3 给成员 5 的 e2e 选择器

成员 5 写 `test_client` 端到端测试时，可以断言这些稳定 id：

| 页面 | 关键 id |
|---|---|
| 首页 | `today-date`、`date-input`、`calories-value`、`calorie-progress`、`macro-chart`、`recent-list`、`dashboard-content` |
| 上传页 | `upload-form`、`file-input`、`drop-zone`、`preview`、`analyze-btn`、`upload-error` |
| 结果页 | `food-rows`、`food-row-template`、`add-food-btn`、`save-btn`、`save-hint`、`result-error` |
| 历史页 | `history-filters`、`date-from`、`date-to`、`history-list`、`pagination`、`history-empty` |

模板不依赖后端传入变量，所以 `test_client().get("/")` 等页面路由可以直接 200。

## 4. 必须和全组确认的 4 个契约缺口

### 4.1 保存前看不到卡路里（阻塞演示脚本 §L.3 第 3 步）

`00` §F 只有 6 个接口，**没有**“只计算、不保存”的接口；`04` 又明确禁止前端算营养。
所以结果页目前只能显示“营养数值由服务器在保存时统一计算”，无法在用户把 180 g 改成 200 g
时实时展示卡路里变化。

`00` §L.3 的演示脚本第 3 步因此**当前无法完成**。两个选项，必须选一个：

1. 新增 `POST /api/v1/nutrition/preview`（请求契约 B 的 `items`，返回契约 C），这是契约变更，需要先改 `00`；或
2. 改演示脚本：先保存，再在首页展示合计变化。

前端已经预留了位置：只要将来 `data` 里出现预览结果，结果页可以加一个只读汇总块；
但**不能**靠前端复制成员 3 的公式。

### 4.2 没有“搜索食物”的接口

结果页允许把 AI 认错的食物改成正确条目，但 v1 没有 `GET /api/v1/foods`。
为了让用户能修正，`food-options.js` 内置了 `03` §5.2 的 29 条 `food_name + 中文名`：

- 只有 ID 和名称，**没有任何营养数值**；
- 如果成员 3 增删食物，同步改这个文件即可；
- 不在清单里的 ID 会自动显示为“未收录”，仍可原样提交，不会被前端拦截。

如果以后加了食物搜索接口，可以把 `buildFoodSelect()` 换成异步搜索，其他逻辑不用动。

### 4.3 身高体重、单餐评价、长期规划不在 v1 契约里

`00` 的 6 个接口没有用户资料、评价、建议、长期规划字段。前端没有凭空造这些 UI，
否则接后端时会拿到 `undefined`。如果项目要加这些功能，需要先做契约 v2：

- 用户资料：`GET/PUT /api/v1/profile`（身高、体重、目标）；
- 单餐评价：在 `POST /meals` 的 `data` 里加 `evaluation`，或新增 `GET /meals/{id}/evaluation`；
- 长期规划：`GET /api/v1/insights?range=30d`。

这些都属于后端与契约变更，不在成员 4 的文件范围内。

### 4.4 分页没有总数

`GET /meals` 的 `pagination` 只有 `{limit, offset, count}`，`count` 是**本页条数**，不是总数。
历史页因此用“本页是否满 `limit`”判断还有没有下一页；如果最后一页刚好满 20 条，
用户点“下一页”会看到空页，再点“上一页”即可回来。要彻底解决需要后端加 `total`。

## 5. 自测命令

```bash
# 1. JS 语法
node --check app/static/js/api.js
node --check app/static/js/dashboard.js
node --check app/static/js/upload.js
node --check app/static/js/result.js
node --check app/static/js/history.js
node --check app/static/js/food-options.js

# 2. 启动后端后，浏览器打开
python run.py
# http://127.0.0.1:5000

# 3. 代码级约束
grep -rn "fetch(" app/static/js            # 只应命中 api.js
grep -rn "calories_kcal\|protein_g" app/static/js  # 只应出现在展示/字段读取处
```

## 6. 手动验收对照（`04` §9.1）

| # | 用例 | 当前实现 |
|---|---|---|
| F1 | 首页无数据 | 显示 0、空状态、引导上传 |
| F2 | 选正常照片 | 本地预览，无网络请求 |
| F3 | 选 9 MB 文件 | 本地提示“超过 8 MB”，不发请求 |
| F4 | PDF 改名 `.jpg` | 读取文件头，提示“无法识别” |
| F5 | 点分析 | 按钮禁用 + “正在识别…”，成功后跳结果页 |
| F6 | 结果页刷新 | `analysisResult` 仍在，食物行重新渲染 |
| F7 | 清空重量 | 保存按钮变灰，行内红字提示 |
| F8 | 180 → 200 保存 | 提交新重量，后端重算，首页合计变化 |
| F9 | 直接访问 `/result` | 无草稿时跳回 `/upload` |
| F10 | 上传风景照 | 结果页显示“没有识别到食物”，不崩 |
| F11 | 历史页选日期 | 请求带 `date_from`/`date_to`，只显示该区间 |
| F12 | 删除一条 | 确认后 `DELETE`，列表与首页合计更新 |
| F13 | 375 px | 已用真实 375 CSS 视口验证：`scrollWidth === 375`，无横向滚动 |
| F14 | 请求域名 | 只有 `/api/v1/*`；第三方只有 Chart.js CDN |
