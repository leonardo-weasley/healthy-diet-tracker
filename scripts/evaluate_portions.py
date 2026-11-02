"""照片回归跑批（对应 02 §7 步骤 6，选做但强烈建议每周跑一次）。

用法：

    py -3.14 scripts/evaluate_portions.py                 # 清单里每张图跑 1 次
    py -3.14 scripts/evaluate_portions.py --repeat 2      # 每张跑 2 次，看稳定性
    py -3.14 scripts/evaluate_portions.py --markdown docs/PORTION_EVAL.md

规则：
- 清单来自 tests/fixtures/photos.json；清单外的图片也会被自动纳进来（note 记为 -），
  你往目录里丢图不用改代码。
- 只读，不改任何文件；除非显式给 --markdown，否则只打印。
- 需要 .env 里的 AI_API_KEY，会真实调用（每张图约 $0.001）。
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
MANIFEST = FIXTURES / "photos.json"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}

sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(errors="replace")

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from app.ai.image_analyzer import analyze_food  # noqa: E402
from app.ai.prompts import FOOD_NAME_HINTS  # noqa: E402
from app.utils.errors import AiProviderError, InvalidAiResponse  # noqa: E402

WHITELIST = {h.strip() for h in FOOD_NAME_HINTS.replace("\n", " ").split(",") if h.strip()}


def load_photos() -> list[dict]:
    """清单 + 目录扫描合并；清单管的只是 note。"""
    on_disk = sorted(p for p in FIXTURES.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)

    notes: dict[str, dict] = {}
    if MANIFEST.is_file():
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        notes = {row["file"]: row for row in data.get("photos", [])}

    photos = []
    for path in on_disk:
        meta = notes.get(path.name, {})
        photos.append({
            "path": path,
            "dish": meta.get("dish", "-"),
            "note": meta.get("note", "-"),
        })

    missing = [name for name in notes if not (FIXTURES / name).is_file()]
    for name in missing:
        print(f"[warn] 清单里有、磁盘上没有：{name}")
    return photos


def run_one(path: Path) -> dict:
    started = time.perf_counter()
    try:
        payload = analyze_food(str(path))
        return {
            "ok": True,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "payload": payload,
        }
    except (AiProviderError, InvalidAiResponse) as exc:
        return {
            "ok": False,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "error_code": exc.code,
            "reason": (exc.details or {}).get("reason"),
            "message": exc.message,
        }


def summarize(rows: list[dict]) -> dict:
    hits = 0
    total = 0
    for row in rows:
        if not row["ok"]:
            continue
        for food in row["payload"]["foods"]:
            total += 1
            if food["food_name"] in WHITELIST:
                hits += 1
    return {"items": total, "matched": hits}


def fmt_item(food: dict) -> str:
    name = food["food_name"] or "null"
    weight = food["estimated_weight_g"]
    weight_s = f"{weight:.0f}g" if weight is not None else "?"
    return f"{food['display_name']}/{name} {weight_s}"


def main() -> int:
    parser = argparse.ArgumentParser(description="AI photo regression runner")
    parser.add_argument("--repeat", type=int, default=1, help="每张图跑几次（默认 1）")
    parser.add_argument("--markdown", type=Path, help="把结果写成 markdown 表格")
    anchor = parser.add_mutually_exclusive_group()
    anchor.add_argument("--only", help="只跑文件名包含该字串的图")
    anchor.add_argument("--skip-placeholder", action="store_true", help="跳过负样本")
    args = parser.parse_args()

    if not os.getenv("AI_API_KEY", "").strip():
        print("[x] 缺少 AI_API_KEY（%s）" % (ROOT / ".env"))
        return 2

    photos = load_photos()
    if args.only:
        photos = [p for p in photos if args.only in p["path"].name]
    if args.skip_placeholder:
        photos = [p for p in photos if p["path"].name != "placeholder.jpg"]
    if not photos:
        print("[x] 没有可跑的照片")
        return 3

    rows = []
    for photo in photos:
        print(f"\n>>> {photo['path'].name}  ({photo['dish']})")
        runs = []
        for i in range(max(1, args.repeat)):
            result = run_one(photo["path"])
            runs.append(result)
            if not result["ok"]:
                print(f"    [{i + 1}] {result['error_code']} reason={result['reason']}")
                continue
            payload = result["payload"]
            items = " | ".join(fmt_item(f) for f in payload["foods"]) or "-"
            print(f"    [{i + 1}] {result['elapsed_ms']}ms {payload['status']} "
                  f"({len(payload['foods'])} 项) {items}")
        rows.append({**photo, "runs": runs})

    stats = summarize([r for row in rows for r in row["runs"]])
    print("\n" + "-" * 70)
    print(f"照片 {len(rows)} 张，调用 {sum(len(r['runs']) for r in rows)} 次；"
          f"识别出 {stats['items']} 项，其中命中白名单 {stats['matched']} 项")
    if stats["items"]:
        print(f"命中率 {stats['matched'] / stats['items']:.0%}")

    if args.markdown:
        write_markdown(args.markdown, rows, stats)
        print(f"\n已写入 {args.markdown}")
    return 0


def _signature(run: dict) -> tuple:
    """去掉自由文本后的可比较签名：food_name + 重量。"""
    return tuple(
        (f["food_name"], f["estimated_weight_g"]) for f in run["payload"]["foods"]
    )


def write_markdown(target: Path, rows: list[dict], stats: dict) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# 识别与份量回归表",
        "",
        "> 由 `scripts/evaluate_portions.py` 生成，模型 `deepseek-flash`，温度 0，思考模式关闭。",
        f"> 生成时间：{time.strftime('%Y-%m-%d %H:%M')}",
        "",
        "| 照片 | 菜品 | 状态 | 复现性 | 耗时 | 识别结果（名称 / food_name 重量） |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        first = row["runs"][0]
        status = first["payload"]["status"] if first["ok"] else first["error_code"]
        elapsed = f"{first['elapsed_ms']} ms"
        if first["ok"]:
            items = "<br>".join(fmt_item(f) for f in first["payload"]["foods"]) or "-"
        else:
            items = f"`{first['error_code']}` reason={first['reason']}"
        stable = "-"
        sigs = {_signature(r) for r in row["runs"] if r["ok"]}
        if len(row["runs"]) > 1 and sigs:
            stable = "稳定" if len(sigs) == 1 else "波动"
        lines.append(
            f"| {row['path'].name} | {row['dish']} | {status} | {stable} | {elapsed} | {items} |"
        )

    lines += ["", "## 汇总", "",
              f"- 照片：{len(rows)} 张，调用 {sum(len(r['runs']) for r in rows)} 次",
              f"- 识别项：{stats['items']} 项，命中白名单 {stats['matched']} 项", ""]
    lines += ["## 已知失败类型", "",
              "- 白名单外菜品（如肥肠、红烧肉做法差异）→ `food_name` 为 null，需人工补",
              "- 多菜品拼盘容易漏项或把配菜当主菜",
              "- 份量估计偏保守，汤/汁类几乎无法估重", ""]
    target.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())


