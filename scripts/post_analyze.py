"""命令行发一次 /api/v1/analyze 请求（不用 curl、不用 Postman）。

先开一个窗口跑服务：
    py -3.14 -u scripts/mock_analyze_server.py
再开另一个窗口发请求：
    py -3.14 scripts/post_analyze.py tests/fixtures/rice.jpeg
    py -3.14 scripts/post_analyze.py tests/fixtures/red-braised-pork.jpg dinner
    py -3.14 scripts/post_analyze.py 图.jpg lunch --url http://127.0.0.1:5000/api/v1/analyze

等成员1 的正式路由上线后，把 --url 换成 5000 端口即可，参数完全一样。
"""

import argparse
import json
import mimetypes
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

DEFAULT_URL = "http://127.0.0.1:5001/api/v1/analyze"


def build_multipart(image: Path, meal_type: str) -> tuple[bytes, str]:
    boundary = "----hdt" + uuid.uuid4().hex
    mime = mimetypes.guess_type(image.name)[0] or "application/octet-stream"
    parts: list[bytes] = []

    parts.append(
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="meal_type"\r\n\r\n'
        f"{meal_type}\r\n".encode()
    )
    parts.append(
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="image"; filename="{image.name}"\r\n'
        f"Content-Type: {mime}\r\n\r\n".encode()
        + image.read_bytes()
        + b"\r\n"
    )
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def main() -> int:
    parser = argparse.ArgumentParser(description="POST /api/v1/analyze")
    parser.add_argument("image", help="图片路径")
    parser.add_argument("meal_type", nargs="?", default="lunch",
                        choices=["breakfast", "lunch", "dinner", "snack"])
    parser.add_argument("--url", default=DEFAULT_URL)
    args = parser.parse_args()

    sys.stdout.reconfigure(errors="replace")
    image = Path(args.image)
    if not image.is_file():
        print(f"[x] 图片不存在：{image}")
        return 2

    body, content_type = build_multipart(image, args.meal_type)
    request = urllib.request.Request(
        args.url, data=body, method="POST",
        headers={"Content-Type": content_type, "Accept": "application/json"},
    )

    print(f"POST {args.url}  ({image.name}, {args.meal_type})")
    # 本机开着系统代理时会连 127.0.0.1 也走代理，直接被掐断；本地调试必须绕开
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=120) as response:
            status, raw = response.status, response.read()
    except urllib.error.HTTPError as exc:          # 4xx / 5xx 也有正常 JSON 信封
        status, raw = exc.code, exc.read()
    except urllib.error.URLError as exc:
        print(f"[x] 连不上：{exc.reason}")
        print("    服务没启动？先跑：py -3.14 -u scripts/mock_analyze_server.py")
        return 3

    payload = json.loads(raw.decode("utf-8"))
    print(f"HTTP {status}")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if payload.get("status") == "success":
        data = payload["data"]
        print(f"\nOK: status={data.get('status')} foods={len(data.get('foods', []))} "
              f"无提示={not data.get('warnings')}")
    return 0 if status == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
