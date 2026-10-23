#!/usr/bin/env bash
# Compatibility launcher for the Python NightShift worker runtime.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.worker.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "[FATAL ERROR] Missing required configuration file: $ENV_FILE" >&2
  echo "Initialize it from .worker.env.example before starting the worker." >&2
  exit 1
fi

# shellcheck source=/dev/null
source "$ENV_FILE"

PYTHON_BIN="${PYTHON_BIN:-python3}"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[FATAL ERROR] Python runtime not found: $PYTHON_BIN" >&2
  exit 1
fi
if [ ! -f "$SCRIPT_DIR/scripts/worker_runtime.py" ]; then
  echo "[FATAL ERROR] Missing scripts/worker_runtime.py" >&2
  exit 1
fi

# Export only documented worker settings. Do not implicitly expose unrelated
# values sourced from .worker.env to model subprocesses.
export WORKER_ID="${WORKER_ID:-default}" OS_TYPE="${OS_TYPE:-auto}"
export TASKS_FILE="${TASKS_FILE:-tasks.txt}" TASKS_DONE_FILE="${TASKS_DONE_FILE:-tasks.done}"
export PROGRESS_FILE="${PROGRESS_FILE:-progress.log}" PAUSE_FILE="${PAUSE_FILE:-PAUSE}"
export STATUS_FILE="${STATUS_FILE:-worker.status}" LOG_FILE="${LOG_FILE:-.worker.log}"
export AI_CLI="${AI_CLI:-codex}" AI_MODEL="${AI_MODEL:-}" AI_EFFORT="${AI_EFFORT:-}"
export AGY_MODE="${AGY_MODE:-accept-edits}" CODEX_SANDBOX="${CODEX_SANDBOX:-workspace-write}"
export CODEX_APPROVAL_MODE="${CODEX_APPROVAL_MODE:-auto}" CODEX_EPHEMERAL="${CODEX_EPHEMERAL:-1}"
export TASK_TIMEOUT="${TASK_TIMEOUT:-1800}" STEP_BASE="${STEP_BASE:-12}"
export STEP_PER_FILE="${STEP_PER_FILE:-5}" POLL_INTERVAL="${POLL_INTERVAL:-5}"
export USE_SANDBOX="${USE_SANDBOX:-0}" RUN_ONCE="${RUN_ONCE:-0}"
export ADDITIONAL_DIRS="${ADDITIONAL_DIRS:-}" WORKER_ISOLATION="${WORKER_ISOLATION:-1}"
export WORKER_PORT="${WORKER_PORT:-3001}"

exec "$PYTHON_BIN" "$SCRIPT_DIR/scripts/worker_runtime.py" daemon --root "$SCRIPT_DIR"
