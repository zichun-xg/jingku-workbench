#!/usr/bin/env zsh
# 一键启动镜库：后端 8765 + 前端 5173
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [ ! -d .venv ]; then
  echo "正在创建 Python 虚拟环境…"
  python3 -m venv .venv
fi

echo "正在安装后端依赖…"
.venv/bin/pip install -q -r backend/requirements.txt

if [ ! -d frontend/node_modules ]; then
  echo "正在安装前端依赖…"
  (cd frontend && npm install)
fi

echo "启动后端 http://127.0.0.1:8765"
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8765 --reload &
BACK_PID=$!
trap "kill $BACK_PID 2>/dev/null" EXIT INT TERM

echo "启动前端，浏览器打开 http://127.0.0.1:5173"
cd frontend
npm run dev
