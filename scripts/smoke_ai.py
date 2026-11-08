"""步骤 1 的最小可运行脚本（见 ``02`` §7 步骤 1）。

两种跑法：

    # 1) 离线：不需要 Key、不联网，验证"图片 → 契约 A"这条链路是通的
    py -3.14 scripts/smoke_ai.py --offline

    # 2) 真实调用：需要项目根目录 .env 里的 AI_API_KEY
    py -3.14 scripts/smoke_ai.py path/to/meal.jpg

退出码：0 成功 / 2 缺 Key / 3 图片不存在 / 4 供应商或响应错误 / 5 契约校验失败
"""

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

sys.stdout.reconfigure(errors="replace")  # 避免个别终端区域设置把中文打成异常

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from app.ai import client as ai_client  # noqa: E402
from app.ai.image_analyzer import analyze_food  # noqa: E402
from app.utils.errors import AiProviderError, InvalidAiResponse  # noqa: E402

DEFAULT_IMAGES = [
    ROOT / "tests" / "fixtures" / "sample_meal.jpg",
    ROOT / "tests" / "fixtures" / "placeholder.jpg",
]
DEFAULT_IMAGE = next((p for p in DEFAULT_IMAGES if p.is_file()), DEFAULT_IMAGES[0])
MOCK_SUCCESS = ROOT / "tests" / "fixtures" / "mock_ai_result.json"
MOCK_PARTIAL = ROOT / "tests" / "fixtures" / "mock_ai_partial.json"


def _key_status(value: str) -> str:
    """只报告是否已配置，绝不打印 Key 片段（日志和截图都会外流）。"""
    if not value:
        return "(empty)"
    return f"configured (length {len(value)})"


def _print_config() -> None:
    print("-" * 62)
    print(f"python       : {sys.version.split()[0]}")
    print(f"cwd          : {Path.cwd()}")
    print(f"AI_BASE_URL  : {os.getenv('AI_BASE_URL') or ai_client.DEFAULT_BASE_URL}")
    print(f"AI_MODEL     : {os.getenv('AI_MODEL') or ai_client.DEFAULT_MODEL}")
    print(f"AI_TIMEOUT   : {os.getenv('AI_TIMEOUT_SECONDS') or ai_client.DEFAULT_TIMEOUT_SECONDS}s")
    print(f"AI_API_KEY   : {_key_status(os.getenv('AI_API_KEY', ''))}")
    print("-" * 62)


def _run_offline(kind: str) -> int:
    fixture = MOCK_PARTIAL if kind == "partial" else MOCK_SUCCESS
    raw = json.loads(fixture.read_text(encoding="utf-8"))
    print(f"[offline] 用 {fixture.name} 冒充模型返回，不联网、不读图")

    original = ai_client._call_sdk_once
    ai_client._call_sdk_once = lambda image_path, prompt: raw
    try:
        started = time.perf_counter()
        payload = analyze_food(str(DEFAULT_IMAGE))
        elapsed = (time.perf_counter() - started) * 1000
    finally:
        ai_client._call_sdk_once = original

    print(f"\n[offline] {elapsed:.1f} ms")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    assert payload["status"] == ("partial" if kind == "partial" else "success"), payload["status"]
    print(f"\nOK: status={payload['status']} foods={len(payload['foods'])}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Step 1 smoke test for app.ai")
    parser.add_argument("image", nargs="?", default=str(DEFAULT_IMAGE), help="餐食照片路径")
    parser.add_argument("--offline", action="store_true", help="不联网、不需要 Key")
    parser.add_argument("--mock", choices=["success", "partial"], default="success",
                        help="--offline 时用哪份 mock（默认 success）")
    parser.add_argument("--verbose", action="store_true", help="打印调试日志")
    args = parser.parse_args()

    import logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    _print_config()

    if args.offline:
        return _run_offline(args.mock)

    if not os.getenv("AI_API_KEY", "").strip():
        print("\n[x] 缺少 AI_API_KEY。")
        print(f"    打开 {ROOT / '.env'}，填入：AI_API_KEY=sk-...")
        print("    或先跑离线模式：py -3.14 scripts/smoke_ai.py --offline")
        return 2

    image = Path(args.image)
    if not image.is_file():
        print(f"\n[x] 图片不存在：{image}")
        print("    放一张真实餐食照片进去，或显式传路径：")
        print("    py -3.14 scripts/smoke_ai.py D:\\photos\\lunch.jpg")
        return 3

    print(f"image        : {image}  ({image.stat().st_size / 1024:.0f} KB)")
    started = time.perf_counter()
    try:
        payload = analyze_food(str(image))
    except AiProviderError as exc:
        print(f"\n[x] AI_PROVIDER_ERROR reason={(exc.details or {}).get('reason')}")
        print(f"    {exc.message}")
        return 4
    except InvalidAiResponse as exc:
        print(f"\n[x] INVALID_AI_RESPONSE reason={(exc.details or {}).get('reason')}")
        print(f"    {exc.message}")
        if args.verbose:
            traceback.print_exc()
        return 5
    elapsed = (time.perf_counter() - started) * 1000

    print(f"\n{elapsed:.0f} ms")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\nOK: status={payload['status']} foods={len(payload['foods'])} "
          f"warnings={len(payload['warnings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



