# Android 发布包（无需 Python）

本目录把仓库里的 Flask 前端构建成一个**完全离线**的 Android APK：营养计算、食物库、
历史记录、图表全部在 WebView 内运行，不需要 Python、Flask 或任何后端服务器。

## 交付物

| 文件 | 说明 |
| --- | --- |
| `dist/HealthyDietTracker-1.0.0.apk.zip` | 发布包。解压后得到 `HealthyDietTracker-1.0.0.apk`，直接安装。 |

> 项目云盘会把新写入的 `*.apk` 文件清零，所以 APK 以 zip 形式交付；zip 内 APK 的 md5
> 由构建脚本校验，解压后的文件与签名产物完全一致。

## 安装

1. 在手机上解压 `HealthyDietTracker-1.0.0.apk.zip`。
2. 点击 `HealthyDietTracker-1.0.0.apk` 安装；如系统提示，请允许“安装未知来源应用”。
3. 首次启动会显示开屏画面（默认 3 秒，可点右上角“跳过”）。

最低 Android 7.0（API 24），目标 API 34；需要网络权限用于调用你自己配置的 AI 接口。

## 功能

- **开屏画面**：右上角“跳过”；`⋮ → 开屏画面` 可上传 JPG / PNG / WebP / GIF / SVG，
  本机保存，下次启动生效，可一键恢复默认。
- **AI 接口切换**：`⋮ → API 设置` 内置通义千问 Qwen-VL、OpenAI 预设，也可填任意
  OpenAI 兼容的 `/chat/completions` 视觉接口；API Key 只存本机，支持“测试连接”。
- **拍照 / 相册**：上传页提供“拍照”和“从相册选择”，使用系统相机与文件选择器，
  不申请存储权限。
- **关于**：`⋮ → 关于`，含仓库贡献者名单、MIT License 全文、第三方组件与数据来源、
  隐私说明，以及 API 设置 / 开屏画面入口。
- **本地数据**：餐食记录写入 WebView 的 IndexedDB，卸载即清除；营养计算复用仓库的
  USDA 食物库与 Python 后端一致的舍入规则。

## 技术结构

```
android/
├── build.sh                  # 无 Gradle 构建：aapt2 → javac → d8 → zipalign → apksigner
├── tools/build_www.py        # Jinja2 渲染四个页面 + 注入离线 JS/CSS + 生成食物库
├── tools/make_icons.py       # 生成各密度启动图标
├── web/                      # WebView 专用前端层
│   ├── js/boot.js            # 开屏（自定义图片、倒计时、跳过）
│   ├── js/core.js            # 纯营养计算/校验逻辑（UMD，可被 Node 单测）
│   ├── js/app.js             # 本地 /api/v1 实现、IndexedDB、设置/开屏/关于 UI、相机入口
│   └── css/app.css
├── app/src/main/
│   ├── AndroidManifest.xml
│   ├── java/com/hdt/diettracker/
│   │   ├── MainActivity.java      # WebView 壳、assets 虚拟 https 源、文件选择/拍照
│   │   ├── AiBridge.java          # 原生 HTTP 调 AI，规避 CORS
│   │   └── LocalFileProvider.java # 相机输出 content:// URI
│   └── res/                       # 图标、主题、Android 12 开屏
└── tests/                    # core.js 与 Python Decimal 的一致性测试
```

关键取舍：

- **不用 Gradle/AndroidX**：环境里只有 JDK 与 build-tools，手写构建链更可控，APK 约 200 KB。
- **虚拟 https 源**：`shouldInterceptRequest` 把 `https://appassets.androidplatform.net/www/`
  映射到 `assets/www`，让 localStorage / IndexedDB 在正常 origin 下可用。
- **原生 AI 桥**：WebView 直接请求第三方接口会受 CORS 限制，改由 Java `HttpURLConnection`
  发送，再把结果回调给页面；API Key 不经过任何中间服务器。
- **自定义 ContentProvider**：相机输出用 `content://com.hdt.diettracker.files/...`，
  避免 Android 7+ 的 `FileUriExposedException`，也不需要存储权限。

## 重新构建

依赖：

- JDK 17（`JAVA_HOME`）
- Android build-tools 34（`aapt2`、`d8`、`zipalign`、`apksigner`）
- Android platform 34 的 `android.jar`
- Python 3 + Jinja2 + Pillow

```bash
cd android
export JAVA_HOME=/path/to/jdk17
export ANDROID_BUILD_TOOLS=/path/to/build-tools/34.0.0
export ANDROID_PLATFORM=/path/to/platforms/android-34/android.jar
./build.sh
```

产物：`dist/HealthyDietTracker-1.0.0.apk.zip`。

签名默认使用 `android/keystore/release.jks`（开发自签名，密码在 `build.sh` 中）。
正式对外发布请替换为自己的 keystore，并妥善保管。

## 测试

```bash
cd android/tests
python3 gen_expected.py            # 生成 Python Decimal 期望值
node core.test.js                  # 29 种食物 × 6 种重量 + 组合餐/校验用例
```

## 已知边界

- 营养数值是估算值，不能替代医疗或专业营养建议。
- AI 识别质量取决于你配置的模型；必须是支持图片输入的 OpenAI 兼容模型。
- 应用不包含任何内置 API Key；未配置时“分析照片”会提示前往设置。
