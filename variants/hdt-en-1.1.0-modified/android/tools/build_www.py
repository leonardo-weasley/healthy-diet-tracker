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
    # Recent-meals rows in the Today page build an <a href>. The absolute path
    # "/history?date=..." is not a real asset in the WebView (path must start
    # with /www/), so clicking it showed "not found". Map it to the bundled page.
    '`/history?date=': '`history.html?date=',
    '"/history?date=': '"history.html?date=',
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


TABBAR_ICONS = {
    "index.html": '<path d="M4 10.5 12 4l8 6.5"/><path d="M6 9.5V20h12V9.5"/><path d="M10 20v-5h4v5"/>',
    "upload.html": '<path d="M12 5v14"/><path d="M5 12h14"/>',
    "history.html": '<path d="M4 6h16"/><path d="M4 12h16"/><path d="M4 18h10"/>',
}

TAB_LABELS = {
    "index.html": "Today",
    "upload.html": "Log",
    "history.html": "History",
}


def build_tabbar(filename: str) -> str:
    items = []
    # The result page belongs to the "record a meal" flow, so keep that tab highlighted.
    active_page = "upload.html" if filename == "result.html" else filename
    for page in ("index.html", "upload.html", "history.html"):
        active = " is-active" if page == active_page else ""
        current = ' aria-current="page"' if page == active_page else ""
        items.append(
            f'    <a class="hdt-tab{active}" href="{page}"{current}>'
            f'<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" '
            f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'{TABBAR_ICONS[page]}</svg>'
            f'<span>{TAB_LABELS[page]}</span></a>'
        )
    return (
        '<nav class="hdt-tabbar" aria-label="Bottom navigation">\n'
        + "\n".join(items)
        + '\n  </nav>\n  '
    )


def inject_shell(html: str, filename: str = "") -> str:
    """Add the native-app shell (splash, menu, app.css, app.js) to a page."""
    html = html.replace(
        '<link rel="stylesheet" href="static/css/style.css">',
        '<link rel="stylesheet" href="static/css/style.css">\n'
        '  <link rel="stylesheet" href="static/css/app.css">',
    )
    # Chart.js is loaded from a CDN in the web app; the APK must work offline.
    html = html.replace(
        '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js" defer></script>',
        '  <script src="static/js/chart.umd.min.js" defer></script>',
    )
    for source, target in LINK_MAP.items():
        html = html.replace(source, target)

    # Same-origin helper for the on-screen keyboard; CSP keeps script-src 'self',
    # so this must not be an inline <script>.
    html = html.replace(
        "</head>",
        '  <script src="static/js/keyboard.js"></script>\n</head>',
        1,
    )

    # app.js must run before the deferred api.js so the fetch shim is in place.
    html = html.replace(
        '<script src="static/js/api.js" defer></script>',
        '<script src="static/js/food-data.js"></script>\n'
        '  <script src="static/js/core.js"></script>\n'
        '  <script src="static/js/ai-prompt.js"></script>\n'
        '  <script src="static/js/app.js"></script>\n'
        '  <script src="static/js/usda.js"></script>\n'
        '  <script src="static/js/api.js" defer></script>',
    )

    splash = (
        '<div id="hdt-splash" class="hdt-splash" aria-label="Splash screen">\n'
        '  <div class="hdt-splash-media" id="hdt-splash-media"></div>\n'
        '  <div class="hdt-splash-shade"></div>\n'
        '  <div class="hdt-splash-brand">\n'
        '    <span class="hdt-splash-title">\n'
        '      <span class="hdt-splash-logo" aria-hidden="true">\n'
        '        <svg viewBox="0 0 24 24" width="40" height="40" fill="none" stroke="currentColor" '
        'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">\n'
        '          <path d="M12 21c4.2 0 7.5-3.2 7.5-7.2 0-4.2-2.9-7.1-5.6-8.8C11.5 3.6 9 2.4 6.5 3c.2 2.6 1.3 5 3.2 6.7"/>'
        '\n          <path d="M12 21c-4.2 0-7.5-3.2-7.5-7.2 0-1.6.4-3 1.2-4.2"/>'
        '\n          <path d="M12 21c0-4.5 1.5-8.2 4.5-10.5"/>\n'
        '        </svg>\n'
        '      </span>\n'
        '      <strong>Healthy Diet Tracker</strong>\n'
        '    </span>\n'
        '    <small>Snap a photo, log a meal</small>\n'
        '  </div>\n'
        '  <button type="button" id="hdt-splash-skip" class="hdt-splash-skip">Skip <span id="hdt-splash-count">3</span></button>\n'
        '</div>\n'
        '<script src="static/js/boot.js"></script>\n'
    )
    html = re.sub(r"(<body[^>]*>)", r"\1\n" + splash.replace("\\", "\\\\"), html, count=1)

    # Bottom tab bar: native-app navigation for phones (top links are hidden by app.css).
    if filename:
        html = html.replace(
            '<div id="toast-region"',
            build_tabbar(filename) + '<div id="toast-region"',
            1,
        )
    return html


def copy_verified(src: Path, dst: Path, attempts: int = 4) -> None:
    """Copy bytes and verify them.

    The project volume is a FUSE mount that can zero-fill the tail of a freshly written
    file. A byte comparison after each write keeps the APK assets intact.
    """
    data = src.read_bytes()
    for _ in range(attempts):
        dst.write_bytes(data)
        if dst.read_bytes() == data:
            return
    raise SystemExit(f"copy verification failed: {dst}")


def write_verified(path: Path, text: str, attempts: int = 4) -> None:
    data = text.encode("utf-8")
    for _ in range(attempts):
        path.write_bytes(data)
        if path.read_bytes() == data:
            return
    raise SystemExit(f"write verification failed: {path}")


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
        write_verified(OUT / filename, inject_shell(html, filename))

    for item in STATIC.iterdir():
        target = OUT / "static" / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
            for child in item.rglob("*"):
                if child.is_file():
                    copy_verified(child, target / child.relative_to(item))
        else:
            copy_verified(item, target)

    # Android shell assets (splash, menu, local API, native bridge glue).
    for item in (ANDROID_DIR / "web").iterdir():
        target = OUT / "static" / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
            for child in item.rglob("*"):
                if child.is_file():
                    copy_verified(child, target / child.relative_to(item))
        else:
            copy_verified(item, target)

    for js in (OUT / "static" / "js").glob("*.js"):
        if js.name not in ("food-data.js", "ai-prompt.js"):
            write_verified(js, rewrite_js(js.read_text(encoding="utf-8")))

    copy_verified(ANDROID_DIR / "vendor" / "chart.umd.min.js", OUT / "static" / "js" / "chart.umd.min.js")

    food_payload = json.loads(FOOD_DB.read_text(encoding="utf-8"))
    write_verified(
        OUT / "static" / "js" / "food-data.js",
        "/* Generated by android/tools/build_www.py — do not edit. */\n"
        "window.HDT_FOOD_DB = " + json.dumps(food_payload, ensure_ascii=False, indent=2) + ";\n",
    )

    prompts = load_prompt_module()
    write_verified(
        OUT / "static" / "js" / "ai-prompt.js",
        "/* Generated by android/tools/build_www.py — do not edit. */\n"
        "window.HDT_PROMPT = " + json.dumps(prompts.build_prompt(), ensure_ascii=False) + ";\n",
    )

    (OUT / "data" / "food_database.json").write_text(
        FOOD_DB.read_text(encoding="utf-8"), encoding="utf-8"
    )

    total = sum(1 for _ in OUT.rglob("*") if _.is_file())
    print(f"built {OUT} ({total} files)")


if __name__ == "__main__":
    main()
