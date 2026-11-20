# 由 android/tools/build_www.py 抽取（2026-11-19 新增）。
# 底部导航不是写在 Jinja 模板里的，而是构建时注入到四个 HTML 页面。
# 真实文件仍是 android/tools/build_www.py。

# --- 源文件 build_www.py:83-114（导航配置与 HTML 生成） ---
TABBAR_ICONS = {
    "index.html": '<path d="M4 10.5 12 4l8 6.5"/><path d="M6 9.5V20h12V9.5"/><path d="M10 20v-5h4v5"/>',
    "upload.html": '<path d="M12 5v14"/><path d="M5 12h14"/>',
    "history.html": '<path d="M4 6h16"/><path d="M4 12h16"/><path d="M4 18h10"/>',
}

TAB_LABELS = {
    "index.html": "今日",
    "upload.html": "记录",
    "history.html": "历史",
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
        '<nav class="hdt-tabbar" aria-label="底部导航">\n'
        + "\n".join(items)
        + '\n  </nav>\n  '
    )

# --- 源文件 build_www.py:132-141（脚本顺序：app.js -> usda.js -> api.js） ---
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

# --- 源文件 build_www.py:165-171（把 tabbar 插到 toast-region 之前） ---
    # Bottom tab bar: native-app navigation for phones (top links are hidden by app.css).
    if filename:
        html = html.replace(
            '<div id="toast-region"',
            build_tabbar(filename) + '<div id="toast-region"',
            1,
        )
