# 安全说明

本项目是**本地单用户**应用，默认只监听 `127.0.0.1`，不对外提供网络服务。
但它会读取 AI API 密钥、接收上传图片并写入本地数据库，因此仍需注意以下事项。

## 报告问题

如果你发现安全问题（例如路径穿越、任意文件写入、密钥泄露、依赖漏洞），
请**不要**在公开 Issue 中贴出可利用细节或真实密钥，改为通过 GitHub 仓库的
Security 页面私下联系维护者。

## 使用须知

1. **不要提交 `.env`**：`.gitignore` 已排除 `.env` / `.env.*` / `*.pem` / `*.key`。
   提交前用 `git status` 确认。
2. **API 密钥只放在本机 `.env`**：仓库中的 `.env.example` 仅含变量名与 mock 默认值。
3. **不要把应用暴露到公网**：`run.py` 使用 Flask 开发服务器，没有生产级防护。
   如需局域网访问，请自行加反向代理、认证与 HTTPS。
4. **上传目录与数据库在本地**：`uploads/` 与 `instance/` 均被忽略，
   但其中可能包含个人饮食记录，分享或备份时请注意隐私。
5. **谨慎使用未知图片**：上传内容会交给配置的 AI 供应商处理，
   请确认你接受该供应商的数据处理条款。

## Android 客户端（APK）

1. **只允许 https**：设置页只接受 `https://` 的 AI API 地址，`AndroidManifest.xml` 关闭明文流量
   （`usesCleartextTraffic="false"`）；USDA 检索固定访问 `https://api.nal.usda.gov`。
   局域网自建服务请使用 https 或反向代理。
2. **WebView 全离线**：`shouldInterceptRequest` 只放行 `appassets.androidplatform.net/www/`，
   远程子资源返回 403；HTML 响应带 CSP（含 `connect-src 'none'`），AI/USDA 请求全部走原生桥。
3. **原生桥校验**：`AndroidHost` 的每个方法先检查主文档是否为 app origin；
   远程主框架导航交给系统浏览器，远程子框架不加载。
4. **密钥存储**：AI/USDA Key 由 Android Keystore 中的 AES-256/GCM 密钥加密，
   `SharedPreferences`（`hdt_secure`）只保存 IV + 密文；`localStorage` 不再保存密钥，
   旧版本残留会在首次读取设置时迁移并清除。这是**静态加密**，应用运行时仍会在自己的
   进程内解密使用。同时开启 `FLAG_SECURE`（禁截图/最近任务预览）、关闭 WebView 远程调试、
   `allowBackup="false"`。
5. **照片**：相机临时文件位于 `cache/camera`，启动时清理 24 小时前的文件，取消拍照立即删除。
6. **签名**：发布密钥通过 `HDT_STORE_PASS` 环境变量传入，不写入脚本；
   `android/keystore/`、`android/build/`、`*.apk` 均被 `.gitignore` 排除。

## 依赖更新

依赖版本记录在 `requirements.txt`，许可信息见 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)。
升级依赖后请重新运行 `pytest -q`，并确认第三方声明仍然准确。
