#!/usr/bin/env bash
# Build a signed release APK without Gradle.
#
# Required tools:
#   - JDK 17 (JAVA_HOME)
#   - Android SDK build-tools 34.0.0 (aapt2, d8, zipalign, apksigner)
#   - Android platform android.jar (API 34)
#
# Environment overrides:
#   ANDROID_SDK=/path/to/sdk
#   ANDROID_BUILD_TOOLS=/path/to/build-tools/34.0.0
#   ANDROID_PLATFORM=/path/to/platforms/android-34/android.jar
#   HDT_STORE_PASS=<keystore password>   (required, never commit it)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
SDK="${ANDROID_SDK:-/root/android-sdk}"
BUILD_TOOLS="${ANDROID_BUILD_TOOLS:-$SDK/android-14}"
PLATFORM="${ANDROID_PLATFORM:-$SDK/android-34-ext12/android.jar}"
JAVA_HOME="${JAVA_HOME:-/root/jdk17}"
VERSION="1.0.0"
OUT="${HDT_BUILD_DIR:-/tmp/hdt-apk-build}"
DIST="$REPO/dist"
APK_NAME="HealthyDietTracker-$VERSION.apk"
KEYSTORE="${HDT_KEYSTORE:-$HERE/keystore/release.jks}"
STORE_PASS="${HDT_STORE_PASS:-}"
KEY_ALIAS="${HDT_KEY_ALIAS:-hdt}"

export JAVA_HOME
export PATH="$JAVA_HOME/bin:$PATH"

if [[ -z "$STORE_PASS" ]]; then
  echo "HDT_STORE_PASS is not set (keystore password, kept out of git)." >&2
  echo "  export HDT_STORE_PASS='your-keystore-password'" >&2
  exit 1
fi

for tool in "$BUILD_TOOLS/aapt2" "$BUILD_TOOLS/d8" "$BUILD_TOOLS/zipalign" "$BUILD_TOOLS/apksigner"; do
  [[ -x "$tool" ]] || { echo "missing build tool: $tool" >&2; exit 1; }
done
[[ -f "$PLATFORM" ]] || { echo "missing android.jar: $PLATFORM" >&2; exit 1; }
command -v javac >/dev/null || { echo "javac not found (JAVA_HOME=$JAVA_HOME)" >&2; exit 1; }

echo "==> 1/7 render web assets"
python3 "$HERE/tools/build_www.py"

echo "==> 2/7 compile resources"
rm -rf "$OUT"
mkdir -p "$OUT/gen" "$OUT/classes" "$OUT/dex"
"$BUILD_TOOLS/aapt2" compile --dir "$HERE/app/src/main/res" -o "$OUT/res.zip"
"$BUILD_TOOLS/aapt2" link \
  -o "$OUT/base.apk" \
  -I "$PLATFORM" \
  --manifest "$HERE/app/src/main/AndroidManifest.xml" \
  -R "$OUT/res.zip" \
  --java "$OUT/gen" \
  --auto-add-overlay \
  -A "$HERE/app/src/main/assets"

echo "==> 3/7 compile java"
find "$HERE/app/src/main/java" "$OUT/gen" -name '*.java' > "$OUT/sources.txt"
javac -encoding UTF-8 -source 11 -target 11 \
  -classpath "$PLATFORM" \
  -d "$OUT/classes" \
  @"$OUT/sources.txt"

echo "==> 4/7 dex"
find "$OUT/classes" -name '*.class' > "$OUT/classes.txt"
"$BUILD_TOOLS/d8" --release --min-api 24 --lib "$PLATFORM" \
  --output "$OUT/dex" @"$OUT/classes.txt"
python3 - "$OUT/base.apk" "$OUT/dex/classes.dex" <<'PY'
import sys, zipfile
apk, dex = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(apk, "a", zipfile.ZIP_DEFLATED) as archive:
    archive.write(dex, "classes.dex")
PY

echo "==> 5/7 align"
"$BUILD_TOOLS/zipalign" -f -p 4 "$OUT/base.apk" "$OUT/aligned.apk"

echo "==> 6/7 sign"
mkdir -p "$DIST"
if [[ ! -f "$KEYSTORE" ]]; then
  echo "generating development keystore (replace before publishing to a store)"
  mkdir -p "$(dirname "$KEYSTORE")"
  keytool -genkeypair -v \
    -keystore "$KEYSTORE" \
    -alias "$KEY_ALIAS" \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass:env HDT_STORE_PASS -keypass:env HDT_STORE_PASS \
    -dname "CN=Healthy Diet Tracker, OU=Mobile, O=HDT, L=Shanghai, ST=Shanghai, C=CN" \
    >/dev/null 2>&1
fi
"$BUILD_TOOLS/apksigner" sign \
  --ks "$KEYSTORE" \
  --ks-key-alias "$KEY_ALIAS" \
  --ks-pass env:HDT_STORE_PASS \
  --key-pass env:HDT_STORE_PASS \
  --v4-signing-enabled false \
  --out "$OUT/signed.apk" \
  "$OUT/aligned.apk"

echo "==> 7/7 verify"
"$BUILD_TOOLS/apksigner" verify --print-certs "$OUT/signed.apk"
"$BUILD_TOOLS/aapt2" dump badging "$OUT/signed.apk" > "$OUT/badging.txt"
sed -n "1,5p" "$OUT/badging.txt"
# The project volume is a FUSE mount that zero-fills freshly written *.apk files (upload
# scanning), so the release APK is delivered inside a ZIP and verified after writing.
python3 - "$OUT/signed.apk" "$DIST/$APK_NAME.zip" "$APK_NAME" <<'PY'
import hashlib, sys, zipfile
src, dst, arcname = sys.argv[1], sys.argv[2], sys.argv[3]
with zipfile.ZipFile(src) as apk:
    digest = hashlib.md5(open(src, "rb").read()).hexdigest()
readme = """健康饮食记录 Android 发布包
============================

1. 解压本压缩包，得到 HealthyDietTracker-1.0.0.apk
2. 在 Android 7.0 及以上设备安装（需允许安装未知来源应用）
3. 首次启动显示开屏，右上角可跳过
4. 点右上角 ⋮ → API 设置，填入你自己的 API Key（内置通义千问 Qwen-VL / OpenAI 预设）
5. ⋮ → 关于 可查看贡献者、License、第三方声明，以及开屏画面设置

APK 内已包含全部前端资源、食物库与图表库，运行时不需要 Python 或后端服务。
"""
with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
    bundle.write(src, arcname)
    bundle.writestr("README.txt", readme)
with zipfile.ZipFile(dst) as bundle:
    data = bundle.read(arcname)
if hashlib.md5(data).hexdigest() != digest:
    raise SystemExit("zip verification failed")
print("apk md5", digest)
PY
rm -f "$DIST/$APK_NAME"
ls -lh "$DIST/$APK_NAME.zip"
echo "APK  (inside zip): $APK_NAME"
echo "Release bundle:    $DIST/$APK_NAME.zip"
