"""契约模拟器：把 app/ai 包成 00 §F.1 的 /api/v1/analyze，供本机手工联调。

只用标准库（本机 pip 暂时装不上 Flask，见 README 的说明），所以它不依赖 Flask，
但也**不是**正式实现——正式实现归成员1（app/routes/analysis.py + utils/images.py）。

做三件事：
  1. 校验 multipart（image + meal_type）、大小、MIME、能否被 Pillow 打开；
  2. 落盘到 uploads/YYYY/MM/<uuid>.jpg（与正式约定一致）；
  3. 调 analyze_food()，按契约 F 的信封返回。

用法：
    py -3.14 scripts/mock_analyze_server.py          # http://127.0.0.1:5001
浏览器打开 http://127.0.0.1:5001/ 就是上传表单，也可以：
    curl -X POST http://127.0.0.1:5001/api/v1/analyze \
      -F "image=@tests/fixtures/rice.jpeg" -F "meal_type=lunch"
"""

import argparse
import io
import json
import sys
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(errors="replace")

from dotenv import load_dotenv  # noqa: E402
from PIL import Image  # noqa: E402

load_dotenv(ROOT / ".env")

from app.ai import analyze_food  # noqa: E402
from app.utils.errors import ApiError  # noqa: E402

UPLOAD_DIR = ROOT / "uploads"
MAX_BYTES = 8 * 1024 * 1024
MEAL_TYPES = {"breakfast", "lunch", "dinner", "snack"}
ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
PORT = 5001

FORM_HTML = """<!doctype html>
<meta charset="utf-8">
<title>analyze 模拟请求</title>
<style>
 body{font-family:system-ui,sans-serif;max-width:640px;margin:40px auto;padding:0 16px}
 select,button,input{padding:8px;font-size:15px;margin:8px 0}
 pre{background:#111;color:#eee;padding:16px;border-radius:8px;overflow:auto}
</style>
<h2>POST /api/v1/analyze（模拟）</h2>
<form method="post" action="/api/v1/analyze" enctype="multipart/form-data">
  <input type="file" name="image" accept="image/*" required><br>
  <select name="meal_type">{options}</select>
  <button type="submit">发送</button>
</form>
<p>等价 curl：</p>
<pre>curl -X POST http://127.0.0.1:{port}/api/v1/analyze \\
  -F "image=@tests/fixtures/rice.jpeg" -F "meal_type=lunch"</pre>
"""


def parse_multipart(body: bytes, boundary: bytes) -> dict[str, dict]:
    """极简 multipart/form-data 解析：返回 {name: {filename, content_type, data}}。"""
    parts: dict[str, dict] = {}
    delimiter = b"--" + boundary
    for chunk in body.split(delimiter):
        chunk = chunk.strip(b"\r\n")
        if not chunk or chunk == b"--":
            continue
        head, _, data = chunk.partition(b"\r\n\r\n")
        if not _:
            continue
        name = filename = None
        content_type = "application/octet-stream"
        for line in head.split(b"\r\n"):
            text = line.decode("utf-8", "replace")
            if text.lower().startswith("content-disposition:"):
                for item in text.split(";")[1:]:
                    key, _, value = item.strip().partition("=")
                    value = value.strip().strip('"')
                    if key == "name":
                        name = value
                    elif key == "filename":
                        filename = value
            elif text.lower().startswith("content-type:"):
                content_type = text.split(":", 1)[1].strip()
        if name:
            parts[name] = {"filename": filename, "content_type": content_type, "data": data}
    return parts


def error_body(code: str, message: str, details=None) -> dict:
    return {"status": "error",
            "error": {"code": code, "message": message, "details": details}}


class Handler(BaseHTTPRequestHandler):
    server_version = "HDTMock/0.1"

    def log_message(self, fmt, *args):  # 安静一点，只留一行
        sys.stderr.write("[mock] " + (fmt % args) + "\n")

    def _send(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _send_html(self, html: str) -> None:
        raw = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):  # noqa: N802
        if self.path == "/":
            options = "".join(f'<option value="{m}">{m}</option>' for m in sorted(MEAL_TYPES))
            self._send_html(FORM_HTML.format(port=PORT, options=options))
        elif self.path == "/health":
            self._send(200, {"status": "success", "data": {"ok": True}})
        else:
            self._send(404, error_body("MEAL_NOT_FOUND", "Not found.", None))

    def do_POST(self):  # noqa: N802
        if self.path != "/api/v1/analyze":
            self._send(404, error_body("INVALID_REQUEST", "Only POST /api/v1/analyze is simulated.", None))
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BYTES + 65536:
            self._send(413, error_body("IMAGE_TOO_LARGE", "Image exceeds 8 MB.", None))
            return
        body = self.rfile.read(length)

        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            self._send(415, error_body("UNSUPPORTED_MEDIA_TYPE",
                                       "Use multipart/form-data.", None))
            return
        boundary = content_type.split("boundary=", 1)[-1].strip().strip('"').encode()
        parts = parse_multipart(body, boundary)

        meal_type = parts.get("meal_type", {}).get("data", b"").decode("utf-8", "replace").strip()
        if meal_type not in MEAL_TYPES:
            self._send(400, error_body("INVALID_REQUEST",
                                       "meal_type must be one of breakfast/lunch/dinner/snack.",
                                       {"field": "meal_type", "value": meal_type}))
            return

        upload = parts.get("image")
        if not upload or not upload["filename"]:
            self._send(400, error_body("INVALID_REQUEST", "image is required.",
                                       {"field": "image"}))
            return
        if upload["content_type"] not in ALLOWED_MIME:
            self._send(415, error_body("UNSUPPORTED_MEDIA_TYPE",
                                       "Only JPEG, PNG and WebP are accepted.",
                                       {"mime_type": upload["content_type"]}))
            return
        if len(upload["data"]) > MAX_BYTES:
            self._send(413, error_body("IMAGE_TOO_LARGE", "Image exceeds 8 MB.",
                                       {"size_bytes": len(upload["data"])}))
            return
        try:
            Image.open(io.BytesIO(upload["data"])).verify()
        except Exception:
            self._send(400, error_body("INVALID_IMAGE",
                                       "The uploaded file is not a decodable image.", None))
            return

        stamp = datetime.now()
        folder = UPLOAD_DIR / f"{stamp:%Y}" / f"{stamp:%m}"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{uuid.uuid4().hex[:12]}.jpg"
        target.write_bytes(upload["data"])

        try:
            result = analyze_food(str(target))
        except ApiError as exc:
            self._send(exc.http_status, error_body(exc.code, exc.message, exc.details))
            return

        self._send(200, {"status": "success",
                         "data": {"image_path": target.relative_to(ROOT).as_posix(), **result}})


class Server(ThreadingHTTPServer):
    # Windows 上 SO_REUSEADDR 会允许两个进程同时绑同一端口，
    # 请求可能落到一个已经僵死的旧进程上，表现为 RemoteDisconnected。
    # 关掉它，端口被占时直接报错。
    allow_reuse_address = False
    daemon_threads = True


def main() -> int:
    global PORT
    parser = argparse.ArgumentParser(description="契约模拟器：POST /api/v1/analyze")
    parser.add_argument("--port", type=int, default=PORT)
    args = parser.parse_args()
    PORT = args.port

    try:
        server = Server(("127.0.0.1", PORT), Handler)
    except OSError as exc:
        print(f"[x] 端口 {PORT} 被占用（{exc}）。")
        print("    先关掉旧进程，或换端口：py -3.14 -u scripts/mock_analyze_server.py --port 5002")
        return 2

    print(f"模拟接口  : http://127.0.0.1:{PORT}/api/v1/analyze")
    print(f"浏览器表单: http://127.0.0.1:{PORT}/")
    print("Ctrl+C 停止")
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
