"""页面路由与本地 mock AI 服务的接线测试。

这些测试覆盖集成阶段修复的两个真实缺口：

1. ``app/routes/pages.py`` 曾经把四个页面全部渲染成 ``placeholder.html``，
   前端模板和 JS 完全没有被使用。这里断言每个页面返回的是真实模板。
2. 项目没有 API Key，联调依赖 ``scripts/mock_ai_provider.py``。
   这里用 Flask test client 直接验证它返回符合契约 A 的 JSON。
"""

from __future__ import annotations

import base64
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

PAGES = {
    "/": "dashboard.js",
    "/upload": "upload.js",
    "/result": "result.js",
    "/history": "history.js",
}


def _load_mock_module():
    path = ROOT / "scripts" / "mock_ai_provider.py"
    spec = importlib.util.spec_from_file_location("mock_ai_provider", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("path,script", sorted(PAGES.items()))
def test_page_renders_real_template(client, path, script):
    response = client.get(path)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "这是后端联调占位页面" not in html
    assert script in html


def test_static_assets_are_served(client):
    for name in ("css/style.css", "js/api.js", "js/food-options.js"):
        assert client.get(f"/static/{name}").status_code == 200


def test_mock_provider_returns_contract_payload():
    module = _load_mock_module()
    image = base64.b64encode(b"fake-jpeg-bytes").decode("ascii")
    payload = {
        "model": "mock-vision",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "识别这份餐食"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image}"},
                    },
                ],
            }
        ],
    }
    response = module.app.test_client().post("/v1/chat/completions", json=payload)
    assert response.status_code == 200

    body = response.get_json()
    content = body["choices"][0]["message"]["content"]
    analysis = json.loads(content)
    assert analysis["foods"], "mock 至少返回一项食物"
    for item in analysis["foods"]:
        assert isinstance(item["food_name"], str) and item["food_name"]
        assert 1 <= item["estimated_weight_g"] <= 2000
    assert module.app.test_client().get("/health").status_code == 200
