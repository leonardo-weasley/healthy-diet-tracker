#!/usr/bin/env python3
"""Build the offline WebView bundle for the Android app.

The Flask app is not shipped to the phone.  This script renders the existing
Jinja templates into plain HTML, copies the static assets, and generates the
JavaScript data files (food database + AI prompt) so the whole product can run
inside a WebView with no Python runtime.

Run from anywhere:

    python3 android/tools/build_www.py
"""

from __future__ import annotations

import importlib.util
import json
import re
import shutil
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader, select_autoescape

ANDROID_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = ANDROID_DIR.parent
TEMPLATES = REPO_ROOT / "app" / "templates"
STATIC = REPO_ROOT / "app" / "static"
FOOD_DB = REPO_ROOT / "app" / "nutrition" / "food_database.json"
PROMPT_PY = REPO_ROOT / "app" / "ai" / "prompts.py"
OUT = ANDROID_DIR / "app" / "src" / "main" / "assets" / "www"

PAGES = {
    "index.html": "/",
    "upload.html": "/upload",
    "result.html": "/result",
    "history.html": "/history",
}

LINK_MAP = {
    'href="/"': 'href="index.html"',
    'href="/upload"': 'href="upload.html"',
    'href="/result"': 'href="result.html"',
    'href="/history"': 'href="history.html"',
}

# Strings inside the frontend JS that assume an HTTP server with routes.
JS_REWRITES = {
    'window.location.href = "/result"': 'window.location.href = "result.html"',
    'window.location.href = "/upload"': 'window.location.href = "upload.html"',
    'window.location.href = "/history"': 'window.location.href = "history.html"',
    '`/?saved=': '`index.html?saved=',
}


def load_prompt_module():
    spec = importlib.util.spec_from_file_location("hdt_prompts", PROMPT_PY)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["url_for"] = lambda endpoint, **values: f"static/{values['filename']}"
    return env


def render_pages(env: Environment) -> dict[str, str]:
    rendered = {}
    for filename, path in PAGES.items():
        template = env.get_template(filename)
        html = template.render(request=SimpleNamespace(path=path))
        rendered[filename] = html
    return rendered


def inject_shell(html: str) -> str:
    """Add the native-app shell (splash, menu, app.css, app.js) to a page."""
    html = html.replace(
        '<link rel="stylesheet" href="static/css/style.css">',
        '<link rel="stylesheet" href="static/css/style.css">\n'
        '  <link rel="stylesheet" href="static/css/app.css">',
    )
    # Chart.js is loaded from a CDN in the web app; the APK must work offline.
    html = html.replace(
        '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" defer></script>',
        '<script src="static/js/chart.umd.min.js" defer></script>',
    )
    for source, target in LINK_MAP.items():
        html = html.replace(source, target)

    # app.js must run before the deferred api.js so the fetch shim is in place.
    html = html.replace(
        '<script src="static/js/api.js" defer></script>',
        '<script src="static/js/food-data.js"></script>\n'
        '  <script src="static/js/core.js"></script>\n'
        '  <script src="static/js/ai-prompt.js"></script>\n'
        '  <script src="static/js/app.js"></script>\n'
        '  <script src="static/js/api.js" defer></script>',
    )

    splash = (
        '<div id="hdt-splash" class="hdt-splash" aria-label="开屏画面">\n'
        '  <div class="hdt-splash-media" id="hdt-splash-media"></div>\n'
        '  <div class="hdt-splash-shade"></div>\n'
        '  <div class="hdt-splash-brand">\n'
        '    <span class="hdt-splash-logo" aria-hidden="true">\n'
        '      <svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" '
        'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">\n'
        '        <path d="M12 21c4.2 0 7.5-3.2 7.5-7.2 0-4.2-2.9-7.1-5.6-8.8C11.5 3.6 9 2.4 6.5 3c.2 2.6 1.3 5 3.2 6.7"/>'
        '\n        <path d="M12 21c-4.2 0-7.5-3.2-7.5-7.2 0-1.6.4-3 1.2-4.2"/>'
        '\n        <path d="M12 21c0-4.5 1.5-8.2 4.5-10.5"/>\n'
        '      </svg>\n'
        '    </span>\n'
        '    <strong>健康饮食记录</strong>\n'
        '    <small>拍一张，记一餐</small>\n'
        '  </div>\n'
        '  <button type="button" id="hdt-splash-skip" class="hdt-splash-skip">跳过 <span id="hdt-splash-count">3</span></button>\n'
        '</div>\n'
        '<script src="static/js/boot.js"></script>\n'
    )
    html = re.sub(r"(<body[^>]*>)", r"\1\n" + splash.replace("\\", "\\\\"), html, count=1)
    return html


def rewrite_js(source: str) -> str:
    for old, new in JS_REWRITES.items():
        source = source.replace(old, new)
    return source


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "static" / "js").mkdir(parents=True)
    (OUT / "static" / "css").mkdir(parents=True)
    (OUT / "data").mkdir(parents=True)

    env = build_environment()
    for filename, html in render_pages(env).items():
        (OUT / filename).write_text(inject_shell(html), encoding="utf-8")

    for item in STATIC.iterdir():
        if item.is_dir():
            shutil.copytree(item, OUT / "static" / item.name, dirs_exist_ok=True)
        else:
            shutil.copy2(item, OUT / "static" / item.name)

    # Android shell assets (splash, menu, local API, native bridge glue).
    for item in (ANDROID_DIR / "web").iterdir():
        if item.is_dir():
            shutil.copytree(item, OUT / "static" / item.name, dirs_exist_ok=True)
        else:
            shutil.copy2(item, OUT / "static" / item.name)

    for js in (OUT / "static" / "js").glob("*.js"):
        js.write_text(rewrite_js(js.read_text(encoding="utf-8")), encoding="utf-8")

    shutil.copy2(ANDROID_DIR / "vendor" / "chart.umd.min.js", OUT / "static" / "js" / "chart.umd.min.js")

    food_payload = json.loads(FOOD_DB.read_text(encoding="utf-8"))
    (OUT / "static" / "js" / "food-data.js").write_text(
        "/* Generated by android/tools/build_www.py — do not edit. */\n"
        "window.HDT_FOOD_DB = " + json.dumps(food_payload, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )

    prompts = load_prompt_module()
    (OUT / "static" / "js" / "ai-prompt.js").write_text(
        "/* Generated by android/tools/build_www.py — do not edit. */\n"
        "window.HDT_PROMPT = " + json.dumps(prompts.build_prompt(), ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )

    (OUT / "data" / "food_database.json").write_text(
        FOOD_DB.read_text(encoding="utf-8"), encoding="utf-8"
    )

    total = sum(1 for _ in OUT.rglob("*") if _.is_file())
    print(f"built {OUT} ({total} files)")


if __name__ == "__main__":
    main()
