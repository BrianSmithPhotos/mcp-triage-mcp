#!/usr/bin/env bash
# Stops the backend, frontend, and planner-mcp container started by scripts/start.sh.
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"

stop_pid_file() {
  local name="$1"
  local pid_file="$RUN_DIR/$name.pid"
  if [ -f "$pid_file" ]; then
    local pid
    pid="$(cat "$pid_file")"
    if kill -0 "$pid" 2>/dev/null; then
      echo "Stopping $name (pid $pid and its children)..."
      # Kill the entire process group so child processes (e.g. uvicorn spawned by
      # uv run, next-server spawned by next dev) don't linger after the parent dies.
      pkill -TERM -P "$pid" 2>/dev/null || true
      kill "$pid" 2>/dev/null || true
    else
      echo "$name not running (stale pid file)"
    fi
    rm -f "$pid_file"
  else
    echo "$name not running (no pid file)"
  fi
}

stop_pid_file backend
stop_pid_file web

cd "$ROOT_DIR"
echo "Stopping planner-mcp via docker compose..."
docker compose down
