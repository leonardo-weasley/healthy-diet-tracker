"""本地模拟的 OpenAI 兼容视觉接口，用于无 API Key 的开发与联调。

它实现 ``POST /v1/chat/completions``，返回与真实供应商相同结构的响应，
内容是一份符合契约 A 的食物识别 JSON。同一张图片每次得到相同结果
（按图片字节的 SHA-256 选择场景并微调重量），方便复现和截图。

启动::

    python scripts/mock_ai_provider.py            # http://127.0.0.1:5100

配合 ``.env``::

    AI_API_KEY=mock-local-key
    AI_BASE_URL=http://127.0.0.1:5100/v1
    AI_MODEL=mock-vision

浏览器打开 http://127.0.0.1:5100/ 可以看到服务说明与可用场景。
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import time
import uuid
from datetime import datetime

from flask import Flask, jsonify, request

PORT = int(os.getenv("MOCK_AI_PORT", "5100"))
HOST = os.getenv("MOCK_AI_HOST", "127.0.0.1")

app = Flask(__name__)

# (food_name, display_name, 基准重量 g)
SCENARIOS: list[tuple[str, list[tuple[str, str, float]]]] = [
    ("家常套餐", [
        ("cooked_white_rice", "白米饭", 180),
        ("grilled_chicken_breast", "烤鸡胸肉", 120),
        ("steamed_broccoli", "西兰花", 80),
    ]),
    ("面食早餐", [
        ("cooked_noodles", "面条", 220),
        ("fried_egg", "煎蛋", 55),
        ("tomato", "番茄", 70),
    ]),
    ("西式早餐", [
        ("white_bread", "白面包", 60),
        ("boiled_egg", "水煮蛋", 50),
        ("milk_whole", "全脂牛奶", 200),
    ]),
    ("轻食晚餐", [
        ("salmon_cooked", "三文鱼", 150),
        ("boiled_potato", "水煮土豆", 150),
        ("lettuce", "生菜", 60),
    ]),
    ("素食午餐", [
        ("brown_rice_cooked", "糙米饭", 150),
        ("tofu_firm", "北豆腐", 120),
        ("cucumber", "黄瓜", 80),
    ]),
    ("燕麦早餐", [
        ("oatmeal_cooked", "燕麦粥", 250),
        ("banana", "香蕉", 100),
        ("plain_yogurt", "原味酸奶", 150),
    ]),
    ("快餐组合", [
        ("french_fries", "炸薯条", 110),
        ("cola", "可乐", 330),
    ]),
]


def _extract_image(payload: dict) -> tuple[bytes | None, str | None]:
    """从 messages 中取出第一张 base64 图片。"""
    for message in payload.get("messages") or []:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if not isinstance(part, dict) or part.get("type") != "image_url":
                continue
            url = (part.get("image_url") or {}).get("url", "")
            if not isinstance(url, str) or not url.startswith("data:"):
                continue
            try:
                header, encoded = url.split(",", 1)
                mime = header.split(";")[0].removeprefix("data:") or "image/jpeg"
                return base64.b64decode(encoded), mime
            except (ValueError, TypeError):
                return None, None
    return None, None


def _analysis_for(image: bytes) -> dict:
    digest = hashlib.sha256(image).digest()
    name, items = SCENARIOS[digest[0] % len(SCENARIOS)]
    foods = []
    for index, (food_name, display_name, base_weight) in enumerate(items):
        # ±10 g 的确定性抖动，5 g 为一档，模拟模型估算误差
        step = (digest[1 + index] % 5) - 2
        weight = max(20.0, base_weight + step * 5)
        foods.append({
            "food_name": food_name,
            "display_name": display_name,
            "estimated_weight_g": float(weight),
            "confidence": round(0.86 + (digest[2 + index] % 12) / 100, 2),
            "notes": None,
        })
    print(
        f"[mock-ai] {datetime.now():%H:%M:%S} image={len(image)}B "
        f"scenario={name!r} foods={len(foods)}",
        flush=True,
    )
    return {"schema_version": "1.0", "status": "success", "foods": foods, "warnings": []}


@app.post("/v1/chat/completions")
def chat_completions():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": {"message": "body must be JSON", "type": "invalid_request_error"}}), 400

    image, _mime = _extract_image(payload)
    if image is None:
        content = json.dumps(
            {"schema_version": "1.0", "status": "error", "foods": [],
             "warnings": ["no_food_detected"]},
            ensure_ascii=False,
        )
    else:
        content = json.dumps(_analysis_for(image), ensure_ascii=False)

    return jsonify({
        "id": f"chatcmpl-mock-{uuid.uuid4().hex[:16]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": payload.get("model") or "mock-vision",
        "choices": [{
            "index": 0,
            "message": {"role": "assistant", "content": content},
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": 800,
            "completion_tokens": 120,
            "total_tokens": 920,
        },
    })


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "mock-ai-provider", "scenarios": len(SCENARIOS)})


@app.get("/")
def index():
    rows = "\n".join(
        f"<tr><td>{i + 1}</td><td>{name}</td><td>{'、'.join(d for _, d, _ in items)}</td></tr>"
        for i, (name, items) in enumerate(SCENARIOS)
    )
    return f"""<!doctype html>
<meta charset="utf-8">
<title>Mock AI Provider</title>
<style>
 body{{font-family:system-ui,sans-serif;max-width:760px;margin:40px auto;padding:0 18px;color:#111}}
 code,pre{{background:#f3f4f6;border-radius:6px;padding:2px 6px}}
 table{{border-collapse:collapse;width:100%;margin:16px 0}}
 th,td{{border-bottom:1px solid #e5e7eb;text-align:left;padding:8px}}
 .ok{{color:#0f766e;font-weight:600}}
</style>
<h1>模拟 AI 视觉接口 <span class="ok">运行中</span></h1>
<p>OpenAI 兼容端点：<code>POST /v1/chat/completions</code>；健康检查：<code>GET /health</code></p>
<p>按图片内容的 SHA-256 稳定选择下列场景，同一张图结果一致。只用于本地调试，不产生真实识别。</p>
<table><thead><tr><th>#</th><th>场景</th><th>识别结果</th></tr></thead><tbody>{rows}</tbody></table>
<p>项目 <code>.env</code> 配置：</p>
<pre>AI_API_KEY=mock-local-key
AI_BASE_URL=http://127.0.0.1:{PORT}/v1
AI_MODEL=mock-vision</pre>
"""


if __name__ == "__main__":
    print(f"[mock-ai] listening on http://{HOST}:{PORT}", flush=True)
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)
