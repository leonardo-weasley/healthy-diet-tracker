#!/usr/bin/env bash
# 本地一键启动：安装依赖（首次）→ 建库 → 启动模拟 AI（按 .env）→ 启动应用
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON_BIN:-}"
if [ -z "$PYTHON" ]; then
  if [ -x .venv/bin/python ]; then PYTHON=".venv/bin/python"; else PYTHON="python3"; fi
fi

if ! "$PYTHON" -c "import flask, flask_sqlalchemy, pydantic, dotenv, PIL, openai" >/dev/null 2>&1; then
  echo "[start] installing dependencies into .venv (first run only) ..."
  "$PYTHON" -m venv .venv
  ./.venv/bin/python -m pip install --upgrade pip
  ./.venv/bin/python -m pip install -r requirements.txt
  PYTHON="./.venv/bin/python"
fi

echo "[start] open http://127.0.0.1:${APP_PORT:-5000}/ after the server is ready."
exec "$PYTHON" scripts/start_dev.py
