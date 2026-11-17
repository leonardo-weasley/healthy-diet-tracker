"""本地一键启动：建库 → 导入食物 →（必要时）启动模拟 AI → 启动 Web 应用。

用法::

    python scripts/start_dev.py

它会读取项目根目录的 ``.env``：

* 数据库为空时自动建表并导入 ``app/nutrition/food_database.json``（幂等）；
* 当 ``AI_BASE_URL`` 指向本机 5100 端口时，自动启动 ``mock_ai_provider.py``；
* Ctrl+C 退出时一并关闭模拟 AI 子进程。
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")


def _run(script: str) -> None:
    subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, check=True)


def _healthy(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _uses_local_mock() -> bool:
    base = os.getenv("AI_BASE_URL", "")
    return base.startswith("http://127.0.0.1:5100") or base.startswith("http://localhost:5100")


def main() -> int:
    print("[start] preparing database ...", flush=True)
    _run("scripts/init_db.py")
    _run("scripts/seed_foods.py")

    mock: subprocess.Popen | None = None
    if _uses_local_mock() and not _healthy("http://127.0.0.1:5100/health"):
        print("[start] launching mock AI provider on http://127.0.0.1:5100 ...", flush=True)
        mock = subprocess.Popen(
            [sys.executable, str(ROOT / "scripts" / "mock_ai_provider.py")],
            cwd=ROOT,
        )
        for _ in range(40):
            if _healthy("http://127.0.0.1:5100/health"):
                break
            if mock.poll() is not None:
                print("[start] mock AI provider exited unexpectedly.", flush=True)
                return mock.returncode or 1
            time.sleep(0.25)
        else:
            print("[start] mock AI provider did not become healthy in time.", flush=True)
            mock.terminate()
            return 1
    elif _uses_local_mock():
        print("[start] mock AI provider already running.", flush=True)

    print("[start] starting web app ...", flush=True)
    try:
        return subprocess.call([sys.executable, str(ROOT / "run.py")], cwd=ROOT)
    except KeyboardInterrupt:
        return 0
    finally:
        if mock is not None and mock.poll() is None:
            mock.terminate()
            try:
                mock.wait(timeout=5)
            except subprocess.TimeoutExpired:
                mock.kill()


if __name__ == "__main__":
    raise SystemExit(main())
