# 健康饮食记录 · Android 构建交接说明

> **适用版本**：`1.0.0`（versionCode `1`，package `com.hdt.diettracker`）
>
> **源码基线**：`d99866d feat(android): harden WebView and ship rewritten glass UI`（打包时以 `git rev-parse HEAD` 为准）
>
> **构建方式**：**无 Gradle / 无 AndroidX**，由 `android/build.sh` 直接调用 JDK 17 + Android build-tools 34
>
> **目标环境**：Linux、macOS 或 Windows WSL2（不要用 Windows cmd/PowerShell 直接跑）

---

## 0. 先读：只打包 `android/` 是不够的

`android/tools/build_www.py` 会把 Flask 的模板和静态资源渲染进 APK。它按下面的相对路径取文件：

```text
android/..                        ← 仓库根目录
├── app/templates/                ← 4 个 Jinja 页面
├── app/static/                   ← style.css、页面脚本
├── app/nutrition/food_database.json
└── app/ai/prompts.py
```

**如果只把 `android/` 目录拷到构建机，第 1 步 `build_www.py` 就会因为找不到 `app/...` 失败。**

### 推荐：用 `git archive` 打出最小构建包

在仓库根目录执行（Git 会保留 LF、自动排除 `keystore/`、`build/`、`dist/`、`assets/www/` 等被忽略文件）：

```bash
git archive --format=zip -o hdt-android-build.zip HEAD \
  android \
  app/templates \
  app/static \
  app/nutrition/food_database.json \
  app/ai/prompts.py
```

> 本文件在 `android/BUILD_HANDOFF.md`，会一起进入 zip。
> 如果源码还有未提交改动，请先 `git add` + `git commit`，否则 `git archive HEAD` 不会包含它们。

### 手动打包时的目录结构

```text
hdt-android-build/
├── android/
│   ├── BUILD_HANDOFF.md          ← 本文件
│   ├── build.sh
│   ├── README.md
│   ├── tools/                    ← build_www.py、make_icons.py
│   ├── web/                      ← 开屏、底部导航、本地 API、Keystore 桥、USDA
│   ├── vendor/chart.umd.min.js
│   ├── tests/                    ← 可选，Node 单测
│   └── app/src/main/
│       ├── AndroidManifest.xml
│       ├── java/com/hdt/diettracker/
│       └── res/
└── app/
    ├── templates/
    ├── static/                   ← css/style.css、js/*.js
    ├── nutrition/food_database.json
    └── ai/prompts.py
```

**不要打包**（可重新生成或属于本机机密）：

```text
android/build/
android/dist/
android/app/src/main/assets/www/     ← build.sh 会重新生成
android/keystore/                    ← 签名密钥，单独安全传递
**/__pycache__/
```

### 签名密钥怎么处理

`android/keystore/release.jks` 被 `.gitignore` 排除，**不会**进入 `git archive`。三种做法：

1. **推荐（开发/测试包）**：不带旧 keystore。构建机设置 `HDT_STORE_PASS`，`build.sh` 会自动生成新的 `android/keystore/release.jks`。把这个新 keystore 和密码保存好，后续升级要用同一把。
2. **沿用现有 keystore**：把 `release.jks` 通过安全渠道单独传给构建机，密码通过环境变量提供。密码不要写进 zip、文档或 Git。
3. **用你自己的正式 keystore**：设置 `HDT_KEYSTORE`、`HDT_KEY_ALIAS`、`HDT_STORE_PASS`。

> 换签名密钥后，**无法覆盖安装**用旧密钥签名的 APK，只能先卸载旧版。正式发布前请确认密钥归属。

---

## 1. 构建产物

构建成功后生成：

```text
dist/HealthyDietTracker-1.0.0.zip
├── HealthyDietTracker-1.0.0.apk     ← 已签名 release APK
└── README.txt
```

APK 关键信息：

| 项 | 值 |
|---|---|
| package | `com.hdt.diettracker` |
| versionName / versionCode | `1.0.0` / `1` |
| minSdk / targetSdk | `24` / `34` |
| 签名 | `apksigner`，v1/v2（`--v4-signing-enabled false`） |
| 运行时依赖 | 无 Python、无后端、无远程前端资源 |

APK 之所以再套一层 zip，是沿用原项目的交付方式：脚本会在写入后校验 APK 的 MD5，避免某些挂载卷写坏文件。

---

## 2. 构建机要求

| 组件 | 版本 / 说明 |
|---|---|
| JDK | **17**（必须是 JDK，含 `javac`、`keytool`；JRE 不够） |
| Android build-tools | **34.0.0**：`aapt2`、`d8`、`zipalign`、`apksigner` |
| Android platform | **android-34** 的 `android.jar` |
| Python | 3.9+，并安装 `jinja2` |
| Shell 工具 | `bash`、`find`、`sed`、`rm`、`zip`/`unzip` |
| Node.js | 18+，仅用于可选的 `android/tests/core.test.js` |
| 路径 | 仓库路径**不要含空格或中文**（`javac @sources.txt` 不逐个加引号） |

安装 Python 依赖：

```bash
python3 -m pip install --user jinja2
# 或在虚拟环境里：
# python3 -m venv .venv && . .venv/bin/activate && pip install jinja2
```

如果构建机已有 Android Studio / 标准 SDK，常见位置：

```text
Linux:   ~/Android/Sdk
macOS:   ~/Library/Android/sdk
Windows: %LOCALAPPDATA%\Android\Sdk   （在 WSL 里用 /mnt/c/Users/<你>/AppData/Local/Android/Sdk）
```

没有 SDK 时，用 `sdkmanager` 安装：

```bash
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"
```

> 本项目不需要 `platform-tools` 也能构建；它只在 `adb install` 时有用。

---

## 3. 环境变量（重要）

`build.sh` 的默认路径是作者本机的非标准布局：

```text
SDK 默认        /root/android-sdk
build-tools 默认  $SDK/android-14
platform 默认     $SDK/android-34-ext12/android.jar
JDK 默认          /root/jdk17
```

**在标准 SDK 布局下，只设置 `ANDROID_SDK` 往往不够**，必须显式指定下面两个变量：

```bash
export JAVA_HOME=/opt/jdk-17

export ANDROID_SDK=/opt/android-sdk
export ANDROID_BUILD_TOOLS="$ANDROID_SDK/build-tools/34.0.0"
export ANDROID_PLATFORM="$ANDROID_SDK/platforms/android-34/android.jar"

# 签名密码：不要写进仓库、文档或构建日志
export HDT_STORE_PASS='请替换为强密码'

# 可选
export HDT_KEYSTORE=/secure/path/release.jks   # 默认 android/keystore/release.jks
export HDT_KEY_ALIAS=hdt                       # 默认 hdt
export HDT_BUILD_DIR=/tmp/hdt-apk-build        # 默认 /tmp/hdt-apk-build
```

说明：

- `ANDROID_PLATFORM` 要指向 **`android.jar` 文件本身**，不是目录。
- `ANDROID_BUILD_TOOLS` 要指向包含 `aapt2`、`d8`、`zipalign`、`apksigner` 的目录。
- 如果 `HDT_KEYSTORE` 不存在，脚本会用 `HDT_STORE_PASS` 自动生成一个开发用 keystore。
- `HDT_STORE_PASS` 为空时脚本会直接退出，这是故意的。

---

## 4. 构建前自检

```bash
"$JAVA_HOME/bin/java" -version
"$JAVA_HOME/bin/javac" -version
python3 --version
python3 -c "import jinja2; print('jinja2', jinja2.__version__)"

test -x "$ANDROID_BUILD_TOOLS/aapt2"     && echo "aapt2 ok"
test -x "$ANDROID_BUILD_TOOLS/d8"        && echo "d8 ok"
test -x "$ANDROID_BUILD_TOOLS/zipalign"  && echo "zipalign ok"
test -x "$ANDROID_BUILD_TOOLS/apksigner" && echo "apksigner ok"
test -f "$ANDROID_PLATFORM"              && echo "android.jar ok"

test -f app/templates/base.html
test -f app/static/css/style.css
test -f app/nutrition/food_database.json
test -f app/ai/prompts.py
test -f android/web/js/keyboard.js
```

全部输出 `ok` 再继续。

---

## 5. 开始构建

在仓库根目录（包含 `android/` 和 `app/` 的那一层）：

```bash
bash android/build.sh
```

脚本会依次执行：

```text
1/7  python3 android/tools/build_www.py      ← 重新生成 assets/www（23 个文件）
2/7  aapt2 compile / link                    ← 资源 + Manifest + assets
3/7  javac -source 11 -target 11             ← 针对 android.jar 编译
4/7  d8 --min-api 24                         ← 生成 classes.dex 并塞回 APK
5/7  zipalign -f -p 4
6/7  apksigner sign                          ← 使用 HDT_STORE_PASS
7/7  apksigner verify + aapt2 dump badging   ← 自检
     打包 dist/HealthyDietTracker-1.0.0.zip
```

正常结束时最后几行类似：

```text
APK  (inside zip): HealthyDietTracker-1.0.0.apk
Release bundle:    dist/HealthyDietTracker-1.0.0.zip
```

> `javac` 可能提示 `source/target value 11 is obsolete` 或 bootstrap classpath 警告，可以忽略；只要没有 `error:` 即可。

---

## 6. 构建后验证

### 6.1 检查签名与清单

```bash
unzip -l dist/HealthyDietTracker-1.0.0.zip

unzip -p dist/HealthyDietTracker-1.0.0.zip HealthyDietTracker-1.0.0.apk > /tmp/hdt.apk
"$ANDROID_BUILD_TOOLS/apksigner" verify --print-certs /tmp/hdt.apk
"$ANDROID_BUILD_TOOLS/aapt2" dump badging /tmp/hdt.apk | head -n 12
```

预期看到：

```text
package: name='com.hdt.diettracker' versionCode='1' versionName='1.0.0'
sdkVersion:'24'
targetSdkVersion:'34'
```

### 6.2 检查前端资源是否完整

`build.sh` 会重新生成 `android/app/src/main/assets/www`，正常应有 **23 个文件**：

```bash
find android/app/src/main/assets/www -type f | wc -l
# 23
```

关键文件大小（本快照）：

```text
static/css/style.css          42986
static/css/app.css            18322
static/js/app.js              54569
static/js/keyboard.js          1057
static/js/chart.umd.min.js   205399
static/js/food-data.js        13768
static/js/ai-prompt.js         3048
```

再确认没有远程资源和内联脚本：

```bash
grep -RIn '@import' android/app/src/main/assets/www/static/css || echo "no @import"
grep -RIn 'url(http' android/app/src/main/assets/www/static/css || echo "no remote url()"
grep -RInE '<script[^>]*>[^<]' android/app/src/main/assets/www/*.html || echo "no inline script"
```

### 6.3 安装到设备

```bash
adb install -r /tmp/hdt.apk
# 或直接安装 zip 里的 APK
```

---

## 7. 真机验收清单

构建成功不等于功能通过，请至少走一遍：

- [ ] 飞行模式下冷启动：开屏出现，可跳过，首页不白屏。
- [ ] 右上角 `⋮` → API 设置：保存 Key；杀进程重开，Key 仍在。
- [ ] 设置页保存 Key 后，杀进程重开仍可用；页面源码和日志里不应出现 Key 明文。
- [ ] 上传页：相册选择、拍照入口都能打开；取消选择不崩溃。
- [ ] 上传照片 → AI 识别 → 结果页：食物行、重量、标准食物下拉正常。
- [ ] 未匹配行点「USDA 匹配」：搜索、选择、自动匹配；选择后营养值立即重算。
- [ ] 修改「标准食物」后，热量/蛋白/碳水/脂肪随之变化（`change` 事件未丢）。
- [ ] 保存餐食 → 历史记录可见 → 展开详情；删除/分页正常。
- [ ] 焦点进入输入框、弹出输入法时，底部胶囊导航与保存条向下隐藏；收起键盘后恢复。
- [ ] 首页图表、宏量营养素、按餐型拆分正常；无 Chart.js 远程请求。
- [ ] 返回键、底部导航「今日 / 记录 / 历史」切换正常。
- [ ] 截图被 `FLAG_SECURE` 拦截（这是预期行为，不是 bug）。

---

## 8. 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| `missing build tool: .../aapt2` | `ANDROID_BUILD_TOOLS` 指错；确认目录里有 `aapt2`、`d8`、`zipalign`、`apksigner` |
| `missing android.jar` | `ANDROID_PLATFORM` 要指向文件本身，不是 `platforms/android-34/` 目录 |
| `javac not found` | `JAVA_HOME` 指向了 JRE 或错误目录；检查 `$JAVA_HOME/bin/javac` |
| `invalid source release: 11` | JDK 太旧；换 JDK 17 |
| `No module named jinja2` | `python3 -m pip install jinja2` |
| `python3: command not found` | 安装 Python 3，或让 `python3` 指向 `python` |
| `HDT_STORE_PASS is not set` | `export HDT_STORE_PASS='...'` |
| `keystore password was incorrect` | 现有 `release.jks` 的密码与 `HDT_STORE_PASS` 不一致；换正确密码，或删掉旧 keystore 重新生成 |
| `Permission denied` 执行 `build.sh` | `bash android/build.sh`，或 `chmod +x android/build.sh` |
| `bad interpreter: /usr/bin/env bash^M` | 打包时被转成了 CRLF；用 `git archive` 重新打包，或在构建机执行 `sed -i 's/\r$//' android/build.sh` |
| `FileNotFoundError: app/templates/...` | 只打包了 `android/`；按第 0 节补齐 `app/` 的四个路径 |
| `aapt2`/`d8` 报 Java 版本错误 | build-tools 太旧或 JDK 太新/太旧；用 build-tools 34.0.0 + JDK 17 |
| `zipalign` 后安装失败 | 确认没有用 `HDT_BUILD_DIR` 指向只读目录；重新完整构建 |

---

## 9. 安全与交付注意

- **不要把 `android/keystore/`、`HDT_STORE_PASS`、任何 API Key 放进 zip/Git/聊天记录。**
- APK 内不内置 AI/USDA Key；Key 由用户在设置页填写，Android 上用 Android Keystore AES-256/GCM 加密后写入 `SharedPreferences`（`hdt_secure`）。
- 应用只允许 HTTPS 原生请求；WebView 侧 CSP 为 `script-src 'self'`，没有 `unsafe-inline`，也没有远程脚本/字体/图片。
- `FLAG_SECURE` 会阻止截屏/录屏，这是安全设计。
- 本构建的 `android/keystore/release.jks` 如果沿用，必须确认密码；否则请按第 0 节重新生成并妥善保存。

---

## 10. 本次构建包含的改动

- 新版「液态玻璃」前端：`style.css`、`app.css`、4 个页面模板、开屏结构。
- 新增 `android/web/js/keyboard.js`：输入法弹出时隐藏底部导航/保存条；改为外链脚本，以通过 CSP。
- API Key 迁移到 Android Keystore（AES-256/GCM），旧 `localStorage` 明文自动迁移并清除。
- USDA 匹配、自动匹配、自定义食物入库。
- 安全加固：HTTPS-only 桥、来源校验、5 MB 响应上限、CSP、安全响应头、相机缓存清理、`FLAG_SECURE`、provider 路径校验。

---

## 11. 可选：CI 要点

如果放到 GitHub Actions / 其他 CI：

1. 使用 `ubuntu-latest` + Temurin JDK 17。
2. 安装/确认 `build-tools;34.0.0` 和 `platforms;android-34`。
3. 把 `HDT_STORE_PASS`（以及 base64 后的 keystore，如果需要固定签名）放进 CI Secrets，构建时解码到临时目录。
4. 设置 `ANDROID_BUILD_TOOLS`、`ANDROID_PLATFORM`、`JAVA_HOME` 后执行 `bash android/build.sh`。
5. 上传 `dist/HealthyDietTracker-1.0.0.zip` 作为 artifact。
6. 不要把 Secret 打进日志；签名命令的输出只保留证书指纹。

---

## 12. 最短路径（复制粘贴版）

假设已装好 JDK 17、build-tools 34、platform 34、Python 3 + jinja2：

```bash
cd /path/to/repo            # 含 android/ 与 app/ 的仓库根目录

export JAVA_HOME=/opt/jdk-17
export ANDROID_BUILD_TOOLS=/opt/android-sdk/build-tools/34.0.0
export ANDROID_PLATFORM=/opt/android-sdk/platforms/android-34/android.jar
export HDT_STORE_PASS='请替换为强密码'

bash android/build.sh

# 产物
ls -lh dist/HealthyDietTracker-1.0.0.zip
```
