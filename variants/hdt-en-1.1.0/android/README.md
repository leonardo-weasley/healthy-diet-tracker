# Android release package (no Python required)

This directory builds the repository's Flask frontend into a **fully offline** Android APK.
Nutrition calculations, the food database, history, and charts all run inside a WebView;
no Python, Flask, or backend server is required.

## Deliverable

| File | Description |
| --- | --- |
| `dist/HealthyDietTracker-1.1.0.apk.zip` | Release package. Unzip to get `HealthyDietTracker-1.1.0.apk` and install it directly. |

> The project cloud drive zeroes newly written `*.apk` files, so the APK is delivered inside a zip.
> The build script verifies the md5 of the APK inside the zip, so the extracted file matches the signed artifact exactly.

## Install

1. Unzip `HealthyDietTracker-1.1.0.apk.zip` on the phone.
2. Tap `HealthyDietTracker-1.1.0.apk` to install. If prompted, allow "Install unknown apps".
3. The first launch shows a splash screen (3 seconds by default; tap "Skip" in the top-right corner).

Minimum Android 7.0 (API 24), target API 34. Network permission is used only to call the AI endpoint you configure.

## Features

- **Mobile UI**: the navigation bar sits at the bottom (Today / Log / History) as a floating
  Apple Liquid Glass capsule (translucent, blurred background, highlighted edges, safe-area aware).
  Page content matches the desktop version.
- **USDA backfill**: when an AI-recognized food has no match in the local food database, that row
  shows a "USDA match" button. Search USDA FoodData Central manually and pick an item, or use
  "Auto-pick first result"; the page also offers "Auto-match all". Selected foods are written to
  the local custom food store, count toward nutrition immediately, and are saved with the meal to
  IndexedDB so they can be matched directly next time.
- **Splash screen**: "Skip" in the top-right corner; `⋮ → Splash screen` lets you upload
  JPG / PNG / WebP / GIF / SVG, stored on the device and applied on the next launch, with a
  one-tap restore to default.
- **AI endpoint switching**: `⋮ → API settings` includes Qwen-VL and OpenAI presets, and accepts
  any OpenAI-compatible `/chat/completions` vision endpoint. The API key stays on the device and
  "Test connection" is supported.
- **Camera / gallery**: the upload page offers "Take photo" and "Choose from gallery" using the
  system camera and file picker; no storage permission is requested.
- **About**: `⋮ → About` shows repository contributors, the full MIT License, third-party
  components and data sources, privacy notes, and entries to API settings / splash settings.
- **Local data**: meals are stored in the WebView's IndexedDB and cleared on uninstall. Nutrition
  calculations reuse the repository's USDA food database and the same rounding rules as the Python backend.

## Technical structure

```
android/
├── build.sh                  # Gradle-free build: aapt2 → javac → d8 → zipalign → apksigner
├── tools/build_www.py        # Renders four pages with Jinja2 + injects offline JS/CSS + generates the food database
├── tools/make_icons.py       # Generates launcher icons for each density
├── web/                      # WebView-specific frontend layer
│   ├── js/boot.js            # Splash (custom image, countdown, skip)
│   ├── js/keyboard.js        # Hides bottom navigation/save bar when the keyboard opens (CSP-friendly external script)
│   ├── js/core.js            # Pure nutrition calculation/validation logic (UMD, Node-testable)
│   ├── js/app.js             # Local /api/v1 implementation, IndexedDB, settings/splash/about UI, camera entry
│   ├── js/usda.js            # USDA lookup, auto-match, and custom food storage for unmatched foods
│   └── css/app.css
├── app/src/main/
│   ├── AndroidManifest.xml
│   ├── java/com/hdt/diettracker/
│   │   ├── MainActivity.java      # WebView shell, virtual https asset origin, file picker/camera
│   │   ├── AiBridge.java          # Native HTTP for AI / USDA to avoid CORS; key bridge
│   │   ├── SecureStore.java       # Android Keystore AES/GCM encrypted key storage
│   │   └── LocalFileProvider.java # content:// URI for camera output
│   └── res/                       # Icons, theme, Android 12 splash
└── tests/                    # Consistency tests for core.js and Python Decimal
```

Key decisions:

- **No Gradle/AndroidX**: the environment only provides a JDK and build-tools; a hand-written build
  chain is more controllable and keeps the APK around 200 KB.
- **Virtual https origin**: `shouldInterceptRequest` maps
  `https://appassets.androidplatform.net/www/` to `assets/www`, so localStorage / IndexedDB work
  under a normal origin.
- **Native AI bridge**: direct requests from the WebView to third-party endpoints are blocked by
  CORS, so Java `HttpURLConnection` sends them and returns the result to the page. The API key never
  passes through an intermediate server.
- **HTTPS only + fully offline assets**: the WebView loads only `assets/www`; remote subresources
  are blocked with 403 and HTML responses carry CSP (`connect-src 'none'`). AI and USDA requests go
  through the native bridge over HTTPS, and the settings page rejects `http://`.
- **Origin checks on the native bridge**: every `AndroidHost` method first verifies that the main
  document is the app origin. Remote pages are opened only in the system browser, and only over `https://`.
- **Encrypted key storage**: AI/USDA keys are encrypted with an AES-256/GCM key from the Android
  Keystore and written to `SharedPreferences` (ciphertext only), never to WebView `localStorage`.
  Plaintext left by older versions is migrated automatically and removed the first time settings are read.
- **Custom ContentProvider**: camera output uses `content://com.hdt.diettracker.files/...`, avoiding
  Android 7+ `FileUriExposedException` and requiring no storage permission.

## Rebuilding

Dependencies:

- JDK 17 (`JAVA_HOME`)
- Android build-tools 34 (`aapt2`, `d8`, `zipalign`, `apksigner`)
- `android.jar` from Android platform 34
- Python 3 + Jinja2 + Pillow

```bash
cd android
export JAVA_HOME=/path/to/jdk17
export ANDROID_BUILD_TOOLS=/path/to/build-tools/34.0.0
export ANDROID_PLATFORM=/path/to/platforms/android-34/android.jar
export HDT_STORE_PASS='your-keystore-password'   # required, never committed
./build.sh
```

Output: `dist/HealthyDietTracker-1.1.0.apk.zip`.

Signing uses `android/keystore/release.jks` by default (a development self-signed key; neither the
keystore nor the password is committed). If the keystore does not exist, the script generates one
with `HDT_STORE_PASS`. Replace it with your own keystore for public releases and keep the password
safe. `HDT_KEYSTORE` / `HDT_KEY_ALIAS` select another path and alias.

## Tests

```bash
cd android/tests
python3 gen_expected.py            # Generate Python Decimal expected values
node core.test.js                  # 29 foods × 6 weights + combination/validation cases
```

## Known limits

- Nutrition values are estimates and cannot replace medical or professional dietary advice.
- AI recognition quality depends on the configured model; it must be an OpenAI-compatible model
  that accepts image input.
- The app ships with no built-in API key; without one, "Analyze photo" prompts you to open settings.
- API keys are encrypted by the system Keystore. If the Keystore entry becomes invalid (new device,
  restored backup, or cleared secure data), the key must be entered again.
