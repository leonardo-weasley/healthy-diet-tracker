# Android USDA 补录 + 底部导航（2026-11-19）

本目录是对 **2026-11-19 未提交改动** 的盘点，以及从旧文件里抽出的“新前端”代码，
方便你直接拿去重写。原始文件仍在 `android/` 下，抽取件只是阅读副本。

- 本目录文件：
  - `usda.js`：新功能主体，`android/web/js/usda.js` 的逐字节副本（466 行）。
  - `app.js.additions.js`：老文件 `android/web/js/app.js` 里新增的 6 段代码（带源行号）。
  - `app.css.additions.css`：`android/web/css/app.css` 603–840 行新增样式块。
  - `build_www.tabbar.py`：`android/tools/build_www.py` 里新增的底部导航生成逻辑。
  - 注意：抽取件是 **2026-11-19 功能改动时的快照**；之后的安全修复（强制 https、CSP、
    Keystore 密钥存储等）没有回写进来，重写时请以仓库里的真实文件为准。
- 生成物：`android/app/src/main/assets/www/`（被 `.gitignore` 忽略），
  重建命令：`python android/tools/build_www.py`。

---

## 1. 今天做了什么（功能层面）

1. **未匹配食物的 USDA 补录**
   - 确认餐食页里，AI 识别后在本地库匹配不到的行（`.food-row.is-unknown`）会出现
     「USDA 匹配」按钮。
   - 弹窗支持：手动搜索 USDA FoodData Central、取第一条结果、整页「自动匹配全部」。
   - 选中条目后写入 `localStorage["hdt.customFoods"]`（最多保留 200 条），
     合并进 `window.HDT_FOOD_DB.foods` 与 `window.FOOD_OPTIONS`，立即参与营养计算，
     并随餐食写入 IndexedDB；下次启动可直接匹配。
   - 自定义食物 ID 形如 `usda_<fdcId>`，保留 `usda.fdc_id / description / data_type / fetched_at`。
2. **设置页新增 USDA API Key**
   - 新增 `settings.usdaApiKey`，默认 `DEMO_KEY`；留空也回落 `DEMO_KEY`。
3. **手机端底部导航**
   - 顶部站点导航隐藏（`.site-nav{display:none}`），底部浮动胶囊导航：
     今日 / 记录 / 历史；`result.html` 高亮“记录”。
   - Apple 液态玻璃风格：半透明、backdrop-filter、高光边缘、安全区适配；
     保存条与 toast 上移避免遮挡。
4. **原生 USDA 桥**
   - `AndroidHost.usdaSearch(id, query, apiKey, pageSize)`，由 Java 发请求绕开 CORS，
     回调 `window.__hdtUsdaResult(id, ok, payloadJsonString)`。
   - 固定请求 `https://api.nal.usda.gov/fdc/v1/foods/search`，`pageSize` 限制 1–25，
     带 429/401/超时/网络错误分类。
5. **构建脚本**
   - 四个页面统一注入底部导航、`usda.js`、离线 `chart.umd.min.js`。
   - 复制/写文件后逐字节校验（应对 FUSE 卷把新写入文件尾部清零的问题）。

### 改动文件清单

| 文件 | 状态 | 说明 |
|---|---|---|
| `android/web/js/usda.js` | 新增（466 行） | USDA 检索、归一化、页面接入、自动匹配 |
| `android/web/js/app.js` | 修改（6 处） | 自定义食物库、setting、`window.HDT` 导出、init 重合并 |
| `android/web/css/app.css` | 修改（+239 行，602–840） | 底部导航 + USDA UI + 顶栏玻璃化 |
| `android/tools/build_www.py` | 修改 | tabbar 注入、usda.js 注入、verified copy/write |
| `android/app/src/main/java/com/hdt/diettracker/AiBridge.java` | 修改 | `usdaSearch()` + `get()` 辅助 |
| `android/build.sh` | 修改 | 发布包 README 增加 USDA 使用说明 |
| `android/README.md` | 修改 | 功能、目录结构补充 |

> `android/web/js/core.js`、`boot.js`、`vendor/chart.umd.min.js`、`tests/*` 今天**没有**改动。

---

## 2. 新前端在哪（重写时看这里）

### 2.1 真正的源码位置

新功能只在 **`android/web/`**，不是 `app/static/`：

- `android/web/js/usda.js` **全部是新的**。
- `android/web/js/app.js` 里只有下面几段是新的（行号为当前文件）：
  - `19`：`CUSTOM_FOODS_KEY`
  - `42`：`DEFAULT_SETTINGS.usdaApiKey`
  - `126–181`：`readCustomFoods / mergeCustomFoods / getCustomFoods / registerCustomFood`
  - `833–837`：设置弹窗的 USDA Key 输入框与说明
  - `854–856`：`collect()` 写入 `usdaApiKey`
  - `1241–1243`：`init()` 里重新合并（解决 `food-options.js` 延迟加载覆盖的问题）
  - `1263–1269`：`window.HDT` 新导出（`getCustomFoods/registerCustomFood/toast/openModal/closeModal/el/button`）
- `android/web/css/app.css` 的新增块在源文件 `602–840` 行（603 行起是样式本体）。
- 底部导航的 HTML **不在 Jinja 模板里**，由 `build_www.py` 在构建时插入：
  - `83–114`：`TABBAR_ICONS / TAB_LABELS / build_tabbar`
  - `139`：脚本顺序 `app.js → usda.js → api.js`
  - `165–171`：插到 `#toast-region` 之前

### 2.2 旧文件 / 不要误改的地方

- `app/static/js/*.js` 是旧 Web 版；构建时只做 URL 重写（`/result` → `result.html`、
  `` `/?saved= `` → `` `index.html?saved= ``），见 `build_www.py:48–53`。
- 生成物里的 `upload.js`、`result.js` 与 `app/static/js/` 的差异**只有 4 行跳转路径**，
  不是今天的新逻辑；不要拿生成物当源码改。
- `android/web/js/boot.js`、`core.js`、`app/static/js/dashboard.js`、`history.js`、
  `food-options.js` 今天没改。

### 2.3 重写必须保留的“契约”

`usda.js` 是“外挂”到旧页面上的，依赖以下 DOM / 全局对象，重写时要么保留，要么同步改：

- DOM：
  `#food-rows`、`.food-row.is-unknown`、`.food-row-head`、`.row-remove`、
  `.food-name`（input）、`.food-standard`（select）、`#unmatched-note`
- 全局：
  `window.HDT` 需提供 `getSettings()`、`registerCustomFood(food)`、`toast()`、
  `openModal()`、`closeModal()`、`el()`、`button()`
  （当前 `window.HDT` 定义在 `app.js:1255–1270`）
- 数据：
  - `window.HDT_FOOD_DB.foods[]`
  - `window.FOOD_OPTIONS[]`（`{food_name,label}`）
  - 自定义食物字段：`food_name/display_name/calories_per_100g/protein_per_100g/
    carbs_per_100g/fat_per_100g/source/aliases/is_verified/usda{...}`
- 事件：`applyFood()` 后必须 `select.dispatchEvent(new Event("change"))`，
  否则 result.js 不会重算营养。
- 脚本顺序：`app.js`（普通脚本，先执行）→ `usda.js`（普通脚本）→ 页面脚本（defer）；
  `usda.js` 在 `DOMContentLoaded` 才挂 DOM，所以顺序对了才拿得到 `window.HDT`。
- 原生：`window.AndroidHost.usdaSearch(id, query, apiKey, pageSize)` →
  `window.__hdtUsdaResult(id, ok, payloadJsonString)`。
- 密钥：`AndroidHost.setSecret(name, value)` / `getSecret(name)` / `removeSecret(name)`，
  `name` 只允许 `aiApiKey`、`usdaApiKey`（空值表示删除）。APK 内 Key 由 Keystore 加密，
  浏览器环境没有桥时回退 `localStorage`。
  如果要搬回 Flask Web 版，**不能**直接用 `requestWeb()` 的 fetch 兜底：
  浏览器直连 USDA 会 CORS，而且不应该把 key 放查询串；需要加一个后端代理路由。

---

## 3. 旧/不一致的地方（重写前先确认）

1. **`app.js:15` 的 `APP_BUILD` 仍是 `2026-11-18`**，关于页会显示旧日期；
   `APP_VERSION` 也还是 `1.0.0`，功能已加但版本没动。
2. **`THIRD_PARTY_NOTICES.md:34–37` 已过时**：还写 Chart.js 只从 jsDelivr CDN 引入、
   “仓库中不包含其源码”，但 `android/vendor/chart.umd.min.js` 已经是入库文件。
   第 46 行 USDA 只写“食物营养参考值”，没写运行时的 USDA 搜索/自定义食物。
3. **`app/static/js/food-options.js` 头部注释**仍写死 29 条、与文档 §5.2 一致；
   现在运行时会追加 USDA 自定义食物，注释与实现不再一致。
4. **新逻辑没有单测**：`usda.js` 的 `toFood / normalizeResults / nutrientValue`
   是纯函数，但没被任何测试覆盖；`build_www.py` 的 tabbar/usda 注入也没有测试，
   而 `assets/www` 被 gitignore，CI 看不到回归。
   建议把纯函数拆成 UMD 模块（像 `core.js`）并加进 `android/tests/`。
5. **`build_www.py:256–258` 用 `write_text` 写 `data/food_database.json`**，
   Windows 上会写成 CRLF（本次重建后只有这个文件 hash 变了）。
   其它文件走 `write_bytes`，建议这里也用 `write_verified(..., newline="\n")`。
6. `android/README.md` 已同步；根 `README.md:506–511` 只做链接，不用改。

---

## 4. 安全审查（Android / 新功能）

> 结论：没有发现“可直接远程利用”的漏洞；主要问题是**纵深防御不足**和**明文 HTTP 允许**。
> 前端对 AI/USDA 返回文本的渲染全部走 `textContent` / `input.value`（`result.js`、
> `history.js`、`usda.js`），未发现 DOM XSS 注入点；重写时请保持这个约束。

### 修复状态（本次已应用到代码）

| 项 | 修复内容 |
|---|---|
| H1 | `AndroidManifest.xml` 改为 `usesCleartextTraffic="false"`；`app.js` 的 `collect()` 与 `requestCompletion()` 只接受 `https://`；`AiBridge.chatUrl()/get()` 在原生层再校验一次。 |
| H2 | `AiBridge` 构造时注入允许的 origin 与当前主文档 URL（`MainActivity` 在 `onPageStarted/onPageFinished` 更新）；`chat/test/usdaSearch/openExternal/toast/getVersion` 全部先过 `isTrustedCall()`；`shouldInterceptRequest` 对非 app host 的 `http/https/ftp/file` 一律返回 403；`shouldOverrideUrlLoading` 只放行 app host 主框架，其余远程主框架交给系统浏览器，远程子框架直接丢弃。 |
| H3 | HTML 响应新增 CSP（`default-src 'self'`、`connect-src 'none'`、`script-src 'self'`、`frame-src 'none'` 等）、`X-Frame-Options: DENY`、`Referrer-Policy: no-referrer`；删除 `el()` 的 `html`/`innerHTML` 分支。 |
| M1 | Key 已迁移到 Android Keystore（`SecureStore.java`，AES-256/GCM；`SharedPreferences` 只存 IV + 密文，旧 localStorage 明文自动迁移并清除）；另加 `FLAG_SECURE`、关闭 WebView 远程调试。 |
| M2 | `readAll()` 限制 5 MB，超限抛错。 |
| M4 | `LocalFileProvider` 抽出统一的 `resolveFile()` 校验（`/`、`\\`、`..`、NUL）；启动时清理 24 小时前的相机缓存，取消拍照时立即删除临时文件。 |
| M5 | `openExternal`（Java 与 `MainActivity` 两条路径）只允许 `https://`。 |
| 未改 | M3（USDA API 本身要求 key 在查询串）、L1–L4（Keystore 迁移、Chart.js 哈希、命名空间、`SECURITY.md` 补充）见下方说明。 |

> 说明：`@JavascriptInterface` 无法直接拿到“调用方 frame”的 URL，这里用“主文档必须是 app origin”
> 作为门槛；远程子框架已被 CSP + `shouldInterceptRequest` 双重拦截，因此当前组合足够。

### 高

> 以下为修复前的发现记录，行号对应修改前的文件；当前代码状态见上表。

**H1 允许 http:// + 明文流量标志**
- `AndroidManifest.xml:19`：`android:usesCleartextTraffic="true"`
- `app.js:843`：只校验 `^https?://`，允许用户填 `http://...`
- `AiBridge.chatUrl()`（`AiBridge.java:293–302`）不校验 scheme
- 影响：用户把 API 地址填成 `http://` 时，**API Key、提示词、照片 base64 全部明文**，
  同网段可被 MITM 截获。
- 建议：默认只允许 `https://`；确实要支持局域网 `http://`（Ollama 等）时，
  在保存/测试连接前弹明确警告，并考虑移除 `usesCleartextTraffic` 或改用
  `networkSecurityConfig` 限定范围。

**H2 JS 桥没有来源/主框架校验**
- `MainActivity.java:97` 把 `AiBridge` 注入为 `AndroidHost`
- `AiBridge.java:45–138` 的 `chat/test/usdaSearch/openExternal/toast` 都可被调用
- `shouldInterceptRequest` 对**非** `appassets.androidplatform.net` 的请求返回 `null`
  （放行），见 `MainActivity.java:157–159`
- 影响：WebView 内任何 frame / 被注入脚本都能调用原生桥；`chat()` 接受任意 endpoint，
  成功时把**完整响应体**回传 JS（`AiBridge.java:165–167`），等于一个 SSRF/代理原语。
  当前页面全离线、无 XSS 注入点，所以这是纵深防御问题；但以后一旦引入远程脚本、
  第三方 SDK 或可注入内容，就会变成可用的数据外泄通道。
- 建议：
  - 每个 `@JavascriptInterface` 方法先校验当前页面 origin（UI 线程取 `webView.getUrl()`），
    只接受 `https://appassets.androidplatform.net/www/`；
  - `shouldOverrideUrlLoading` 拒绝非主框架远程导航；
  - `shouldInterceptRequest` 对非 APP_HOST 直接返回 403（APK 不需要 WebView 远程网络，
    AI/USDA 都走原生）；
  - 给桥加一次性 token（页面加载时注入，JS 调用时带上）也可以。

**H3 没有 CSP**
- `MainActivity.java:170–173` 只加了 `X-Content-Type-Options: nosniff`；
  HTML 里也没有 `<meta http-equiv="Content-Security-Policy">`。
- 建议给 HTML 响应加：
  `default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline';
  script-src 'self'; connect-src 'none'; object-src 'none'; base-uri 'none'`
  （APK 内 AI/USDA 都走原生，`connect-src 'none'` 可行；若要保留浏览器调试，
  再放宽到具体域名）。
- 顺手删掉 `app.js:56` 的 `el()` `html` 分支（`innerHTML`），目前没有调用点，
  留着容易在重写时被误用。

### 中

**M1 API Key 明文存 localStorage**
- `app.js:283–298`（`hdt.settings` 里的 AI Key 与 USDA Key）
- `android:allowBackup="false"` 已做，但 root/调试/备份工具仍可读；也没有 `FLAG_SECURE`，
  最近任务截图会暴露饮食记录和设置页。
- 建议：长期用 Android Keystore / EncryptedSharedPreferences（需要桥）；
  短期至少加 `FLAG_SECURE`，并确保 release 不开 WebView 调试。

**M2 响应体无上限**
- `AiBridge.readAll()`（`AiBridge.java:278–291`）无大小上限；成功响应全量回传。
- 错误响应只截 600 字符（`errorPayload`），但成功响应没有。
- 影响：错误/恶意 endpoint 或 MITM 返回超大 body → OOM 崩溃。
- 建议：限制 2–5 MB，超限断开。

**M3 USDA Key 放在 URL 查询串**
- `AiBridge.java:77–81`、`usda.js:85–89`
- HTTPS 下可接受（USDA 接口要求 `api_key` 查询参数），但会进访问日志/代理日志；
  `DEMO_KEY` 是公共 key，限速共享。
- 建议：文档里说明不要复用高权限 key；如需更强隔离，可让用户申请专用 key。

**M4 LocalFileProvider 校验不一致 + 照片残留**
- `openFile` 校验了 `/` 和 `..`（`LocalFileProvider.java:36`），
  `query` 没校验（`LocalFileProvider.java:54–58`）。
- provider `exported="false"`（manifest:37），风险低。
- 相机临时文件写在 `cache/camera`，用完不删（`MainActivity.buildCameraIntent`），
  会残留餐食照片，属于隐私/磁盘问题。
- 建议：`query` 复用同一套校验；识别完成后删除临时文件，或在 `onDestroy` 清理。

**M5 任意 http(s) 链接直开系统浏览器**
- `MainActivity.java:189–191`、`AiBridge.openExternal()`（`AiBridge.java:112–129`）
- 低危钓鱼面。建议对 `openExternal` 做域名白名单（GitHub / USDA / 已配置 provider），
  或至少弹确认。

### 低 / 提示

- **L1 签名密钥**：`android/keystore/release.jks` 只在本地，已被 `.gitignore` 忽略，
  也确认没有进 git 历史。发布前确认它是正式 key、密码不在脚本/CI 日志里；
  `build.sh` 里的 md5 只做完整性校验，不是安全校验。
- **L2 供应链**：`android/vendor/chart.umd.min.js` 直接入库但没有来源校验。
  建议在文档里记录官方 SHA-256，构建时校验（本地文件用不了 CDN 的 SRI）。
- **L3 自定义食物覆盖**：`mergeCustomFoods` 会先按 `food_name` 过滤内置食物，
  同名自定义条目会覆盖内置条目。当前用 `usda_<fdcId>` 前缀，冲突概率低；
  重写时建议加命名空间校验。
- **L4 `SECURITY.md` 只覆盖 Flask/后端**，没提 Android WebView 桥、API Key 存储、
  明文流量；建议补一节。

---

## 5. 本次验证结果

- 安全修改后：`python android/tools/build_www.py` 重建成功（22 files），四个页面仍包含
  `hdt-tabbar` 与 `usda.js`；`node android/tests/core.test.js` → **8 tests passed**。
- **Java 侧本机没有 JDK / Android SDK，未实际编译**；改动按 `-source 11` 语法自查，
  需要在构建机执行 `android/build.sh` 验证（`javac` 会检查 `Supplier`、`Bitmap` 等导入）。
- M1 的 Keystore 路径同理需要真机验证：首次启动迁移旧明文 Key、保存后重启仍能读到、
  卸载/清除数据后要求重新填写。
- 重建后 `data/food_database.json` 仍是 CRLF（见 3.5），其余资源与源码一致。
- 编码检查：`android/` 下所有 `.js/.css/.html/.py/.java/.md/.xml/.json` 均为合法 UTF-8，
  无 U+FFFD。终端里看到的乱码是控制台 GBK 显示问题，不是文件损坏。
- `git status`：Android 源码本身只有 7 个文件变更（6 改 1 新增），`assets/www`、`build/`、
  `keystore/` 都被正确忽略（本目录的盘点文档不计入应用代码）。

---

## 6. 建议顺序

1. **H1/H2/H3、M2/M4/M5 已修**；下一步在构建机上跑 `android/build.sh` 做一次真机回归
   （重点：设置页 `http://` 应被拒绝、外部链接只开 https、拍照/选图仍正常、四页底部导航正常）。
2. 再修 3.1 / 3.2 / 3.5（改日期、同步第三方声明、统一换行），成本低。
3. 剩余安全项：L1 确认发布 keystore；L2 给 Chart.js 记录 SHA-256；
   L3 自定义食物命名空间（L4 的 `SECURITY.md` 已补 Android 小节）。
4. 重写前端时保留第 2.3 节的契约；把 `usda.js` 的纯函数抽出来加单测。
5. 想把 USDA 功能搬回 Flask Web 版：加后端代理路由（不要在前端直连、不要把 key
   放查询串），再复用 `usda.js` 的 `toFood/normalizeResults`。
