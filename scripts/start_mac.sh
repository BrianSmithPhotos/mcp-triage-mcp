#!/usr/bin/env bash
# Starts planner-mcp (Docker), the backend (uv/FastAPI), and the frontend (Next.js).
# Logs and PIDs go to .run/, which is gitignored. Use scripts/stop.sh to tear down.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"
mkdir -p "$RUN_DIR"

cd "$ROOT_DIR"
echo "Starting planner-mcp via docker compose..."
docker compose up -d

echo "Starting backend on :8001..."
(cd "$ROOT_DIR/backend" && uv run uvicorn src.main:app --reload --port 8001) \
  > "$RUN_DIR/backend.log" 2>&1 &
echo $! > "$RUN_DIR/backend.pid"

echo "Starting frontend on :3000..."
(cd "$ROOT_DIR/web" && npm run dev) \
  > "$RUN_DIR/web.log" 2>&1 &
echo $! > "$RUN_DIR/web.pid"

echo
echo "Backend:  http://localhost:8001  (log: .run/backend.log)"
echo "Frontend: http://localhost:3000  (log: .run/web.log)"
echo "planner-mcp: http://localhost:8000  (docker compose logs -f planner-mcp)"
echo
echo "Run scripts/stop.sh to stop everything."
