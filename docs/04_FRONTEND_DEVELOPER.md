# 04 — 前端开发指南（成员 4）

> 上位文档：[`00_MAIN_TECHNICAL_ROUTE.md`](00_MAIN_TECHNICAL_ROUTE.md)。冲突时以主路线为准。
> 前端只做两件事：**把用户的操作变成请求**，**把后端返回的数字变成画面**。不做任何营养计算。

## 1. 角色与目标

### 1.1 你的职责

| 你负责 | 你不负责 |
|---|---|
| 4 个页面 + 1 个基础模板 | 算卡路里/蛋白质（后端算） |
| 图片选择与本地预览 | 上传落盘（后端做） |
| 用 Fetch 调 6 个接口 | 连数据库、连 AI 供应商 |
| 展示识别结果、允许改名字与重量 | 改接口字段名 |
| 加载 / 空 / 错误 / 成功 四种状态 | 改契约（需全组同意） |
| Chart.js 图表（环形 + 进度条） | 后端逻辑 |
| 手机宽度可用 | — |

### 1.2 最终交付物（一句话）

> 四个页面串成一条完整链路：**首页看数据 → 上传照片 → 编辑识别结果 → 保存 → 回首页看到变化**，且每种失败都有中文提示、每种空状态都有引导。

### 1.3 成功标准

- 全站只有一个地方写 `fetch()`（`api.js`）。
- 每个页面都能在"没有数据 / 请求中 / 请求失败"三种情况下正常显示。
- 改一次重量后保存，首页卡路里确实变了（证明后端在重算）。
- 375 px 宽度不横向滚动。

---

## 2. 要构建什么

### 2.1 五个模板 + 五个脚本

| 文件 | 页面 | 调用的接口 |
|---|---|---|
| `templates/base.html` | 公共骨架（导航、页脚免责声明） | — |
| `templates/index.html` + `js/dashboard.js` | 今日概览（首页） | `GET /api/v1/dashboard/daily`、`GET /api/v1/meals?limit=5` |
| `templates/upload.html` + `js/upload.js` | 选择照片并分析 | `POST /api/v1/analyze` |
| `templates/result.html` + `js/result.js` | 编辑识别结果并保存 | `POST /api/v1/meals` |
| `templates/history.html` + `js/history.js` | 历史列表、筛选、删除 | `GET /api/v1/meals`、`GET /api/v1/meals/{id}`、`DELETE /api/v1/meals/{id}` |

### 2.2 明确不做

- ❌ 不用 React / Vue / jQuery / 任何打包工具
- ❌ 不在 JS 里做营养计算（只格式化显示：取整、加单位）
- ❌ 不做登录、主题切换、i18n、离线缓存
- ❌ 不做复杂的动画与手势
- ❌ 不直接拼 `/api/v1` 以外的地址

### 2.3 页面职责一句话

| 页面 | 一句话 |
|---|---|
| 首页 | 今天吃了多少、还剩多少额度、最近吃了什么 |
| 上传 | 选图 + 选餐型 + 点分析 |
| 结果 | 看 AI 认出了什么，改错的名字和重量，保存 |
| 历史 | 按日期找记录，看明细，删记录 |

---

## 3. 技术要用的东西

### 3.1 技术栈

| 项 | 规定 |
|---|---|
| HTML | HTML5，语义标签（`<main>`、`<nav>`、`<section>`） |
| CSS | 原生 CSS，一个 `style.css`；用 CSS 变量定义颜色与间距 |
| JS | ES2020+，原生模块或普通 `<script defer>`，**不引入框架** |
| 图表 | Chart.js 4.x，CDN 引入（`<script src="https://cdn.jsdelivr.net/npm/chart.js">`） |
| 请求 | `fetch`，统一封装在 `api.js` |
| 图片预览 | `URL.createObjectURL(file)` |
| 跨页传数据 | `sessionStorage`（结果页刷新不丢） |

### 3.2 需要理解的概念

| 概念 | 用途 |
|---|---|
| `FormData` | 上传文件必须用它，不能把文件塞进 JSON |
| `multipart/form-data` | 浏览器自动设，别手写 `Content-Type` |
| `response.ok` | 4xx/5xx 时不会 reject，必须自己判断 |
| `URL.createObjectURL` | 本地预览，不请求后端 |
| `sessionStorage` | 同标签页内跨页面传数据，刷新保留 |
| `canvas` 尺寸 | Chart.js 需要容器有明确高度，否则画不出来 |
| 事件委托 | 结果页行数动态变化，用容器监听更稳 |

---

## 4. 你拥有的文件

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
    ├── api.js        # 唯一写 fetch 的地方
    ├── dashboard.js
    ├── upload.js
    ├── result.js
    └── history.js
```

### 4.1 别人怎么用你

| 他人 | 与你交互 | 注意 |
|---|---|---|
| 成员1 | 提供 6 个接口 + 4 个页面路由 | 字段名变了要提前一天告诉你 |
| 成员5 | 端到端测试会走 `test_client` 检查页面能渲染 | 保证模板不依赖未定义变量 |
| 成员2/3 | 无直接交互 | 你只看到最终 JSON |

**反向约束**：你**不能**要求后端为你加接口。要展示的东西必须用现有 6 个接口能拿到。

---

## 5. 输入输出契约

完整定义见 `00` §E、§F。以下是"你实际要用到的那部分"。

### 5.1 通用信封

```json
{ "status": "success", "data": { } }
```

```json
{ "status": "error", "error": { "code": "INVALID_IMAGE", "message": "...", "details": null } }
```

**判定顺序**：`res.ok` → `body.status` → 取 `data` 或抛错。

### 5.2 POST /api/v1/analyze（上传页用）

请求：`FormData`，字段 `image`（文件）、`meal_type`（字符串）。

响应 `data`：

```json
{
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
```

你要用的字段：`image_path`、`status`、`foods[]`、`warnings[]`。

### 5.3 POST /api/v1/meals（结果页用）

请求体（严格照抄字段名）：

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

响应 `data`：契约 D（`meal_id`、`items`、`totals`、`meal_date` 等）。保存后只用来提示成功，然后跳首页。

### 5.4 GET /api/v1/dashboard/daily（首页用）

```json
{ "date": "2026-11-01",
  "totals": { "calories_kcal": 1650.0, "protein_g": 80.0, "carbs_g": 190.0, "fat_g": 55.0 },
  "meal_count": 3,
  "by_meal_type": { "breakfast": 350.0, "lunch": 780.0, "dinner": 520.0, "snack": 0.0 } }
```

`by_meal_type` 是**可选**字段，你的代码必须能容忍它缺失。

### 5.5 GET /api/v1/meals（首页与历史页用）

```json
{ "meals": [
    { "meal_id": 101, "meal_type": "lunch",
      "meal_datetime": "2026-11-01T12:30:00+08:00", "meal_date": "2026-11-01",
      "display_summary": "White rice, Grilled chicken breast",
      "calories_kcal": 432.0, "item_count": 2 } ],
  "pagination": { "limit": 50, "offset": 0, "count": 1 } }
```

### 5.6 GET /api/v1/meals/{meal_id}

返回契约 D，历史页展开明细时用。

### 5.7 DELETE /api/v1/meals/{meal_id}

```json
{ "meal_id": 101, "deleted": true }
```

---

## 6. 必须实现的接口（JS 函数）

### 6.1 `api.js`

```javascript
const API_BASE = "/api/v1";

async function apiFetch(path, options = {}) { /* 返回 data，失败抛 Error(code) */ }
function errorText(code) { /* 错误码 → 中文文案 */ }
function formatKcal(value) { /* 1650.0 → "1,650" */ }
function formatMacro(value) { /* 80.0 → "80.0 g" */ }
```

### 6.2 `upload.js`

```javascript
function initUploadPage()                  // 绑定选图、餐型、分析按钮
function onFileSelected(file)              // 本地预览 + 大小校验
function guessMealType(now = new Date())   // 按时间猜餐型
async function analyzeMeal(file, mealType) // 调 POST /analyze，成功跳结果页
function setLoading(isLoading)             // 按钮禁用 + "识别中…"
function showError(code)                   // 显示中文提示
```

### 6.3 `result.js`

```javascript
function initResultPage()                      // 读 sessionStorage，渲染行
function renderFoodRows(foods)                 // 逐项渲染可编辑行
function updateRow(index, changes)             // 改名字/重量
function removeRow(index)                      // 删掉一行
function syncSaveButtonState()                 // 有非法重量则禁用
function buildMealPayload()                    // 组装契约 B
async function saveMeal(payload)               // 调 POST /meals，成功跳首页
```

### 6.4 `dashboard.js`

```javascript
async function loadDashboard(date)   // 调 /dashboard/daily
async function loadRecentMeals()     // 调 /meals?limit=5
function renderProgress(totals)      // 卡路里进度条 + 百分比
function renderMacroChart(totals)    // Chart.js doughnut
function renderRecentList(meals)     // 最近餐食列表
function renderEmptyState()          // 空数据
```

### 6.5 `history.js`

```javascript
async function loadHistory(params)   // 日期/区间/分页
async function openMealDetail(id)    // 调 GET /meals/{id} 展开明细
async function deleteMeal(id)        // confirm → DELETE → 刷新
function renderMealList(meals)
function renderEmptyState()
```

---

## 7. 实施步骤

### 7.0 六周交付节奏（你的部分）

| 周 | 你要交付 | 验收 |
|---|---|---|
| 1 | `base.html` + 4 个页面骨架 + `style.css` 基础样式 + `api.js` | 页面能打开、导航能跳、样式统一 |
| 2 | 上传页完整（预览、校验、加载态）+ 调 mock 接口 | 选图能预览，点分析能看到返回 JSON |
| 3 | 结果页渲染识别结果（只读） | 能把 `foods` 显示成列表 |
| 4 | 结果页可编辑 + 保存 + 首页看板接通 | 改重量保存后首页数字变化 |
| 5 | 历史页 + 图表 + 四态补齐 + 错误文案 | 空/错/加载都对；手机宽度可用 |
| 6 | 视觉打磨 + 演示彩排 | 演示无卡顿、无乱码 |

### 步骤 1：骨架（第 1 周）

1. `base.html`：`<head>` 引 `style.css` 与 Chart.js；导航四项；页脚免责声明。
2. 4 个页面用 `{% extends "base.html" %}`，先放占位内容。
3. `style.css`：定义 `--color-*`、`--space-*`、卡片、按钮、输入框四种基础类。
4. `api.js`：`apiFetch` + `ERROR_TEXT`。

**完成标准**：四个 URL 都能打开，导航高亮正确，控制台无报错。

### 步骤 2：上传页（第 2 周）

1. `<input type="file" id="meal-image" accept="image/jpeg,image/png,image/webp">`
2. 选中后 `URL.createObjectURL` 显示到 `<img id="preview">`。
3. 本地校验：大小 > 8 MB 直接提示；类型不合法直接提示。
4. 餐型按钮组，`guessMealType()` 设默认。
5. 点分析：`setLoading(true)` → `FormData` → `apiFetch("/analyze")` → 存 `sessionStorage.analysisResult` → `location.href = "/result"`。

**完成标准**：上传真实照片能跳到结果页；传 9 MB 文件显示"图片超过 8 MB"。

### 步骤 3：结果页（第 3–4 周）

1. 读 `sessionStorage.analysisResult`；为空则 `location.href = "/upload"`。
2. `renderFoodRows()`：每行三个输入（名称、重量）+ 置信度标签 + 删除按钮。
3. `food_name === null` 的行：名称输入框高亮黄色，提示"请手动填写或选择"。
4. 重量为空/≤0：`syncSaveButtonState()` 禁用保存按钮。
5. 保存：`buildMealPayload()` → `apiFetch("/meals", {method:"POST", ...})` → 清 `sessionStorage` → 跳 `/`。

**完成标准**：改重量后保存成功；清空重量后按钮变灰。

### 步骤 4：首页看板（第 4 周）

1. 并行请求 `/dashboard/daily` 与 `/meals?limit=5`。
2. 卡路里：显示整数 + 千分位；目标写死 2000；进度条宽度 `min(x/2000,1)*100%`，超 100% 变红。
3. 宏量营养素三个数字。
4. `renderMacroChart()`：Chart.js doughnut，三片按克数；容器 `height: 220px`。
5. 最近餐食列表：每行 `display_summary` + 餐型中文 + 时间 + 卡路里。

**完成标准**：无数据时显示引导文案；有数据时进度与数字一致。

### 步骤 5：历史页 + 收口（第 5 周）

1. 日期输入 + 区间输入 + 查询按钮。
2. 列表行点击展开明细（`GET /meals/{id}`）。
3. 删除按钮：`confirm` → `DELETE` → 重载列表。
4. 补齐四态：加载骨架/文案、空状态、错误条、成功 toast。
5. 手机宽度检查：导航折叠、卡片单列、按钮不溢出。

**完成标准**：§9 手动清单全过。

### 步骤 6：打磨（第 6 周）

1. 数字格式统一（卡路里整数 + `,`；营养素 1 位小数 + ` g`）。
2. 免责声明常驻页脚。
3. 演示彩排：按 `00` §L.3 的脚本走三遍。

---

## 8. 代码示例

### 8.1 `api.js`（唯一请求入口）

```javascript
const API_BASE = "/api/v1";

const ERROR_TEXT = {
  INVALID_REQUEST: "请求有误，请检查输入。",
  INVALID_IMAGE: "这张图片无法识别，请换一张。",
  IMAGE_TOO_LARGE: "图片超过 8 MB，请压缩后再上传。",
  UNSUPPORTED_MEDIA_TYPE: "只支持 JPG / PNG / WebP。",
  INVALID_WEIGHT: "请填写有效的重量（1–5000 克）。",
  FOOD_NOT_FOUND: "数据库里没有这种食物，请手动选择或新增。",
  MEAL_NOT_FOUND: "这条记录不存在，可能已被删除。",
  AI_PROVIDER_ERROR: "AI 服务暂时不可用，请稍后重试。",
  INVALID_AI_RESPONSE: "AI 返回了无法解析的结果，请重试。",
  DATABASE_ERROR: "保存失败，请重试。",
  INTERNAL_ERROR: "服务器出错了，请稍后重试。",
};

function errorText(code) {
  return ERROR_TEXT[code] || "出错了，请重试。";
}

async function apiFetch(path, options = {}) {
  const res = await fetch(API_BASE + path, options);

  let body = null;
  try {
    body = await res.json();
  } catch (_) {
    throw Object.assign(new Error("响应不是 JSON"), { code: "INTERNAL_ERROR" });
  }

  if (!res.ok || body.status === "error") {
    const code = body?.error?.code || "INTERNAL_ERROR";
    const message = body?.error?.message || `HTTP ${res.status}`;
    throw Object.assign(new Error(message), {
      code,
      httpStatus: res.status,
      details: body?.error?.details ?? null,
    });
  }
  return body.data;
}

function formatKcal(value) {
  return Math.round(Number(value) || 0).toLocaleString("en-US");
}

function formatMacro(value) {
  return `${(Number(value) || 0).toFixed(1)} g`;
}
```

### 8.2 上传页（`upload.js` 关键片段）

```javascript
const MAX_BYTES = 8 * 1024 * 1024;
const ALLOWED = ["image/jpeg", "image/png", "image/webp"];
const DRAFT_KEY = "analysisResult";

function guessMealType(now = new Date()) {
  const h = now.getHours();
  if (h >= 6 && h < 11) return "breakfast";
  if (h >= 11 && h < 15) return "lunch";
  if (h >= 17 && h < 21) return "dinner";
  return "snack";
}

function onFileSelected(file) {
  if (!file) return;
  if (!ALLOWED.includes(file.type)) return showError("UNSUPPORTED_MEDIA_TYPE");
  if (file.size > MAX_BYTES) return showError("IMAGE_TOO_LARGE");
  document.getElementById("preview").src = URL.createObjectURL(file);
}

async function analyzeMeal(file, mealType) {
  setLoading(true);
  try {
    const form = new FormData();
    form.append("image", file);
    form.append("meal_type", mealType);

    const data = await apiFetch("/analyze", { method: "POST", body: form });
    sessionStorage.setItem(DRAFT_KEY, JSON.stringify(data));
    location.href = "/result";
  } catch (err) {
    showError(err.code);
  } finally {
    setLoading(false);
  }
}
```

> `FormData` 时**不要**手动设 `Content-Type`，浏览器会自己加 boundary。手写会导致后端解析失败——这是新手最常见的坑。

### 8.3 结果页（`result.js` 关键片段）

```javascript
const DRAFT_KEY = "analysisResult";
let state = { foods: [], imagePath: null, mealType: "lunch" };

function initResultPage() {
  const raw = sessionStorage.getItem(DRAFT_KEY);
  if (!raw) return (location.href = "/upload");

  const draft = JSON.parse(raw);
  state.imagePath = draft.image_path || null;
  state.foods = (draft.foods || []).map((f) => ({
    food_name: f.food_name,
    display_name: f.display_name || "",
    weight_g: f.estimated_weight_g,
    confidence: f.confidence,
  }));

  renderFoodRows(state.foods);
  syncSaveButtonState();
}

function renderFoodRows(foods) {
  const host = document.getElementById("food-rows");
  host.innerHTML = "";

  if (!foods.length) {
    host.innerHTML = `<p class="empty">没有识别到食物，请手动添加。</p>`;
    return;
  }

  foods.forEach((food, index) => {
    const row = document.createElement("div");
    row.className = "food-row" + (food.food_name ? "" : " is-unknown");
    row.dataset.index = index;
    row.innerHTML = `
      <input class="food-name" value="${escapeHtml(food.display_name)}" maxlength="100">
      <input class="food-weight" type="number" min="1" max="5000" step="1"
             value="${food.weight_g ?? ""}" placeholder="重量 g">
      <span class="food-confidence">${food.confidence != null ? Math.round(food.confidence * 100) + "%" : "—"}</span>
      <button class="food-remove" type="button">删除</button>`;
    host.appendChild(row);
  });
}

function syncSaveButtonState() {
  const invalid = [...document.querySelectorAll(".food-weight")]
    .some((input) => !input.value || Number(input.value) <= 0 || Number(input.value) > 5000);
  document.getElementById("save-btn").disabled = invalid;
}

function buildMealPayload() {
  return {
    meal_type: state.mealType,
    meal_datetime: new Date().toISOString(),   // 后端会按 APP_TIMEZONE 解释
    image_path: state.imagePath,
    items: [...document.querySelectorAll(".food-row")].map((row, i) => ({
      food_name: state.foods[i]?.food_name ?? null,
      display_name: row.querySelector(".food-name").value.trim(),
      weight_g: Number(row.querySelector(".food-weight").value),
    })),
  };
}

async function saveMeal() {
  const btn = document.getElementById("save-btn");
  btn.disabled = true;
  try {
    const data = await apiFetch("/meals", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(buildMealPayload()),
    });
    sessionStorage.removeItem(DRAFT_KEY);
    location.href = `/?saved=${data.meal_id}`;
  } catch (err) {
    showError(err.code);
    btn.disabled = false;
  }
}
```

> `escapeHtml()` 自己写一个 6 行函数即可（替换 `& < > " '`），避免用户输入破坏 DOM。

### 8.4 首页看板（`dashboard.js` 关键片段）

```javascript
const DAILY_TARGET_KCAL = 2000;

async function loadDashboard() {
  try {
    const [daily, recent] = await Promise.all([
      apiFetch("/dashboard/daily"),
      apiFetch("/meals?limit=5"),
    ]);
    renderProgress(daily.totals);
    renderMacroChart(daily.totals);
    renderRecentList(recent.meals);
    document.getElementById("today-date").textContent = daily.date;
  } catch (err) {
    showError(err.code);
  }
}

function renderProgress(totals) {
  const kcal = Number(totals.calories_kcal) || 0;
  const pct = Math.min((kcal / DAILY_TARGET_KCAL) * 100, 100);

  document.getElementById("calories-value").textContent = formatKcal(kcal);
  document.getElementById("calorie-target").textContent = formatKcal(DAILY_TARGET_KCAL);
  document.getElementById("calorie-percent").textContent = `${Math.round(pct)}%`;

  const bar = document.getElementById("calorie-progress");
  bar.style.width = `${pct}%`;
  bar.classList.toggle("is-over", kcal > DAILY_TARGET_KCAL);

  document.getElementById("protein-value").textContent = formatMacro(totals.protein_g);
  document.getElementById("carbs-value").textContent = formatMacro(totals.carbs_g);
  document.getElementById("fat-value").textContent = formatMacro(totals.fat_g);
}

function renderMacroChart(totals) {
  const canvas = document.getElementById("macro-chart");
  new Chart(canvas, {
    type: "doughnut",
    data: {
      labels: ["蛋白质", "碳水", "脂肪"],
      datasets: [{
        data: [totals.protein_g, totals.carbs_g, totals.fat_g],
        backgroundColor: ["#3b82f6", "#f59e0b", "#ef4444"],
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { position: "bottom" } },
    },
  });
}
```

> `maintainAspectRatio: false` + 容器固定高度（如 `220px`）是 Chart.js 不"越画越大"的关键。

### 8.5 历史页删除（`history.js` 关键片段）

```javascript
async function deleteMeal(mealId) {
  if (!confirm("确定删除这条记录？删除后无法恢复。")) return;
  try {
    await apiFetch(`/meals/${mealId}`, { method: "DELETE" });
    await loadHistory(getCurrentFilters());
  } catch (err) {
    showError(err.code);
  }
}
```

---

## 9. 测试要求

### 9.1 手动用例（前端以手动为主）

| # | 操作 | 期望 |
|---|---|---|
| F1 | 打开首页（无数据） | 显示 0 与空状态引导，无报错 |
| F2 | 打开上传页，选一张正常照片 | 立即出现预览，无网络请求 |
| F3 | 选 9 MB 文件 | 本地提示"超过 8 MB"，不发请求 |
| F4 | 选 PDF 改名 `.jpg` | 提示"无法识别" |
| F5 | 点分析 | 按钮禁用 + "识别中…"；成功后跳结果页 |
| F6 | 结果页刷新 | 数据还在（sessionStorage） |
| F7 | 清空某个重量 | 保存按钮变灰 |
| F8 | 改重量 180 → 200 保存 | 首页卡路里按新值变化 |
| F9 | 直接访问 `/result`（无草稿） | 跳回 `/upload` |
| F10 | 上传风景照 | 提示"没识别到食物"，不崩 |
| F11 | 历史页选日期 | 只显示当天记录 |
| F12 | 删除一条 | 确认后列表少一条，首页合计变小 |
| F13 | 375 px 宽度 | 无横向滚动 |
| F14 | F12 面板检查所有请求 | 全部是 `/api/v1/*`，无第三方域名（Chart.js CDN 除外） |

### 9.2 代码级检查（Review 时用）

```bash
grep -rn "fetch(" app/static/js        # 只应命中 api.js
grep -rn "calories\|protein\|carbs" app/static/js   # 只应出现在格式化和字段读取处
```

### 9.3 可选：Playwright（第 6 周有余力再做）

录一条"上传 → 保存 → 首页"的脚本即可，不要为它引入构建链。

---

## 10. 集成说明

### 10.1 你的依赖

| 依赖 | 提供者 | 没完成时怎么办 |
|---|---|---|
| 6 个接口 | 成员1 | 用 `00` §F 的示例 JSON 造本地 mock（临时改成 `apiFetch` 内返回固定数据，别提交） |
| 页面路由 `/`、`/upload`、`/result`、`/history` | 成员1 | 先约定好，他写 4 行 `render_template` |
| 字段名 | `00` §E | **以文档为准**，不要按记忆写 |

### 10.2 依赖你的

| 模块 | 用你什么 | 你如何配合 |
|---|---|---|
| 成员5 端到端测试 | 页面能渲染（200 + 含关键 id） | 模板不依赖未传入变量，保持 `id` 稳定 |
| 全组 | 演示时的脸面 | 错误文案、空状态必须写 |

### 10.3 什么时候合并

| 时机 | 内容 |
|---|---|
| 第 1 周末 | 骨架 + 样式 + `api.js`（让成员1 能验证页面路由） |
| 第 2 周末 | 上传页（可先接 mock） |
| 第 3 周末 | 结果页只读渲染 |
| 第 4 周末 | 结果页可编辑 + 首页看板 |
| 第 5 周末 | 历史页 + 四态 + 手机适配 |

### 10.4 接口要变怎么办

1. 先看 `00` 是否已改。
2. 只改自己的解析逻辑与字段引用，**不要**自己在 JS 里补别名（如 `calories ?? calories_kcal`）。
3. 在 PR 描述里写"跟随契约 `xxx` 字段变更"。

---

## 11. GitHub 工作流

```bash
git checkout develop && git pull
git checkout -b feature/frontend
git add app/templates app/static
git commit -m "feat(frontend): add upload page with preview and loading state"
git push -u origin feature/frontend
```

提交示例：
- `feat(frontend): add apiFetch wrapper with error mapping`
- `feat(frontend): add editable result rows`
- `fix(frontend): disable save button on empty weight`
- `style(frontend): tighten spacing on 375px viewport`

PR 描述必须含：
1. 涉及的页面与元素 id；
2. 调用了哪些接口；
3. 四态截图或描述（加载/空/错/成功）。

**永不提交**：`node_modules`（本项目也不该有）、构建产物、真实照片。

---

## 12. 最终交付清单

### 12.1 页面与交互

- [ ] `base.html` + 4 个页面，导航互跳正常
- [ ] 上传：预览、类型/大小校验、餐型默认值、加载态
- [ ] 结果：可编辑名称与重量、未知行高亮、非法重量禁用保存
- [ ] 首页：卡路里进度、宏量环形图、最近 5 餐、空状态
- [ ] 历史：日期/区间筛选、明细展开、删除确认
- [ ] 页脚常驻"营养数据为估算值，仅供参考"

### 12.2 健壮性

- [ ] 全站 `fetch(` 只在 `api.js`
- [ ] 每个错误码都有中文文案 + 兜底文案
- [ ] 所有接口调用都有 `try/catch`，失败不白屏
- [ ] 无 `sessionStorage` 时结果页能正确回退

### 12.3 体验

- [ ] 375 px 无横向滚动
- [ ] 数字格式统一（卡路里整数 + 千分位，营养素 1 位小数）
- [ ] 加载中有反馈（按钮禁用 + 文案）
- [ ] 键盘可用：Tab 能走完表单，Enter 能提交

### 12.4 自检问题

1. 为什么上传不能用 `JSON.stringify`？因为文件必须走 `FormData`。
2. `fetch` 在 500 时会 reject 吗？不会，必须自己查 `res.ok`。
3. 结果页刷新为什么还在？`sessionStorage`。
4. 你在哪里算了卡路里？**哪里都没有**——只做 `Math.round` 和千分位。
5. Chart.js 画不出/越画越大？容器没高度或没关 `maintainAspectRatio`。
