# variants — 非主线源码快照

本目录存放与主线并行、但**不参与主线构建**的完整源码快照。每个子目录都是一个可独立构建的工程（自带 `android/` 与 `app/`），互不覆盖。

| 位置 | 版本 | 语言 | 说明 |
| --- | --- | --- | --- |
| 仓库根目录（`android/` + `app/`） | 1.0.0（versionCode 1） | 中文 | 主线，GitHub 上发布的版本 |
| `variants/hdt-en-1.1.0/` | 1.1.0（versionCode 2） | 英文 | 构建机回传的英文版源码快照 |

---

## variants/hdt-en-1.1.0

### 来源与校验

- 来源：`D:\AI_projects\最终构建\hdt-en-1.1.0-modified-source英文版源码.zip`
- ZIP SHA-256：`b0b18f4cb5d77b9d3b16d174f239b9879a556946cdc96b2e379cc73cb5cb3668`
- 76 个文件，拷贝后与 ZIP 内容逐字节一致（SHA-256 全量比对通过）
- 自带英文版 `android/BUILD_HANDOFF.md`，构建步骤与主线文档一致

重建验证：在本机执行 `python android/tools/build_www.py`，23 个前端资源中 22 个与交付快照逐字节一致；`data/food_database.json` 仅因 Windows 的文本模式换行（`\n` → `\r\n`）不同，JSON 语义完全相等。在 Linux 构建机上应为逐字节一致。

### 独立构建

```bash
cd variants/hdt-en-1.1.0
export JAVA_HOME=/opt/jdk-17
export ANDROID_BUILD_TOOLS=/opt/android-sdk/build-tools/34.0.0
export ANDROID_PLATFORM=/opt/android-sdk/platforms/android-34/android.jar
export HDT_STORE_PASS='...'
bash android/build.sh
# 产物：dist/HealthyDietTracker-1.1.0.zip
```

它使用自己目录下的 `app/`，不要改指向仓库根目录的 `app/`。

### 与主线 1.0.0 的差异（摘要）

- `AndroidManifest.xml`：`versionCode 2` / `versionName 1.1.0`
- 界面文案全部英文化：`app/templates/*`、`app/static/js/*`、`android/web/js/*`、`res/values/strings.xml`，以及 Java 里的 Toast / 选择器标题
- `android/web/js/keyboard.js` 重写（1057 B → 2764 B）：主线版本比较 `window.innerHeight` 与 `visualViewport.height`，在 `adjustResize` 下两者同步缩小、差值恒为 0，`.kb-open` 因此从不触发；1.1.0 改为记录“无键盘时的可视高度基线”再比较，并加入输入框判定与阈值
- `android/tools/build_www.py`：新增 `"/history?date=` → `"history.html?date=` 的离线路径重写，修复「今日」页最近餐食条目点进去报 not found
- `android/build.sh`：版本号与发布包内 README 英文化
- `app/nutrition/food_database.json`、`assets/www/data/food_database.json`：数据条目与主线存在差异

### 未纳入 Git 的部分

按 `variants/hdt-en-1.1.0/android/.gitignore`：

- `android/app/src/main/assets/www/`（23 个文件）：构建期由 `build_www.py` 重新生成；本机保留了一份与交付包完全一致的副本，便于对比
- `android/keystore/release.jks`：签名密钥，**永久排除在版本库之外**

---

## 签名密钥（重要）

`variants/hdt-en-1.1.0/android/keystore/release.jks` 是目前本机唯一一份用于 1.0.0 / 1.1.0 发布的 keystore：

- SHA-256：`7b4efd88691f4dca633c51c42381a10e27c5210f4d9e2fd2fc21dc8bc51e5ea3`
- Alias：`hdt`（见 `最终构建/BUILD_INFO.txt`）
- 密码不在本仓库中，由构建机单独保管

**丢失这把 key 后，已安装的 1.1.0 将无法再被覆盖升级。** 请把它和密码备份到仓库之外的安全位置（密码管理器 / 加密备份），并且不要连同源码一起外发。`git archive` 与普通复制都会被 `.gitignore` 排除，需要时请手工、单独传递。
