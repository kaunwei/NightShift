#!/usr/bin/env bash
# ==============================================================================
# Worker Status & Project Progress Dashboard
# Non-blocking, instant read-only status viewer
# ==============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "$(basename "$SCRIPT_DIR")" = "scripts" ]; then
  NIGHTSHIFT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
  PROJECT_ROOT="$NIGHTSHIFT_DIR"
  RUNTIME_PATH="$SCRIPT_DIR/worker_runtime.py"
else
  NIGHTSHIFT_DIR="$SCRIPT_DIR"
  PROJECT_ROOT="$(cd "$NIGHTSHIFT_DIR/.." && pwd)"
  RUNTIME_PATH="$NIGHTSHIFT_DIR/worker_runtime.py"
fi
CONFIG_FILE=""
PROJECT_SELECTION=""
while [ $# -gt 0 ]; do
  case "$1" in
    --config)
      [ -n "${2:-}" ] || { echo "--config requires a path" >&2; exit 2; }
      CONFIG_FILE="$2"
      shift 2
      ;;
    --project)
      [ -n "${2:-}" ] || { echo "--project requires a name" >&2; exit 2; }
      PROJECT_SELECTION="$2"
      shift 2
      ;;
    *)
      break
      ;;
  esac
done
if [ -z "$CONFIG_FILE" ]; then
  if [ -f "$NIGHTSHIFT_DIR/config.json" ]; then
    CONFIG_FILE="$NIGHTSHIFT_DIR/config.json"
  elif [ -n "${NIGHTSHIFT_CONFIG_FILE:-}" ]; then
    CONFIG_FILE="$NIGHTSHIFT_CONFIG_FILE"
  fi
fi
if [ -z "$PROJECT_SELECTION" ] && [ -n "${NIGHTSHIFT_PROJECT_NAME:-}" ]; then
  PROJECT_SELECTION="$NIGHTSHIFT_PROJECT_NAME"
fi
if [ -f "$CONFIG_FILE" ]; then
  PROJECT_CONTEXT=$("${PYTHON_BIN:-python3}" "$NIGHTSHIFT_DIR/project_config.py" --config "$CONFIG_FILE" --root "$PROJECT_ROOT" ${PROJECT_SELECTION:+--project "$PROJECT_SELECTION"}) || exit $?
  eval "$PROJECT_CONTEXT"
elif [ -n "$PROJECT_SELECTION" ]; then
  echo "Missing NightShift config: $CONFIG_FILE" >&2
  exit 2
fi
cd "$PROJECT_ROOT" || exit 1
STATUS_FILE="${STATUS_FILE:-$NIGHTSHIFT_DIR/worker.status}"
if [ "${WORKER_ID:-default}" != "default" ]; then
  STATUS_FILE="$(dirname "$STATUS_FILE")/worker.${WORKER_ID}.status"
fi
PROGRESS_FILE="${PROGRESS_FILE:-$NIGHTSHIFT_DIR/progress.log}"
TASKS_FILE="${TASKS_FILE:-$NIGHTSHIFT_DIR/tasks.txt}"
TASKS_DONE_FILE="${TASKS_DONE_FILE:-$NIGHTSHIFT_DIR/tasks.done}"
PAUSE_FILE="${PAUSE_FILE:-$NIGHTSHIFT_DIR/PAUSE}"

echo "=============================================================================="
echo "              24h Unattended Worker Status Dashboard"
echo "=============================================================================="

# 1. Worker Daemon Status
if [ -f "$STATUS_FILE" ]; then
  "${PYTHON_BIN:-python3}" "$RUNTIME_PATH" status-display "$STATUS_FILE" || \
    echo "Worker Status  : Invalid status file"
else
  echo "Worker Status  : No $NIGHTSHIFT_DIR/worker.status found"
fi

if [ -f "$PAUSE_FILE" ]; then
  echo "Pause Flag     : [PAUSED] (PAUSE file detected - worker will hold after current task)"
fi

echo "------------------------------------------------------------------------------"
# 2. Queue Summary
DONE_COUNT=0
[ -f "$TASKS_DONE_FILE" ] && DONE_COUNT=$(grep -v '^[[:space:]]*#' "$TASKS_DONE_FILE" 2>/dev/null | grep -v '^[[:space:]]*$' | wc -l | tr -dc '0-9')
REMAINING_COUNT=0
[ -f "$TASKS_FILE" ] && REMAINING_COUNT=$(grep -v '^[[:space:]]*#' "$TASKS_FILE" 2>/dev/null | grep -v '^[[:space:]]*$' | wc -l | tr -dc '0-9')

echo "Tasks Summary  : Completed: ${DONE_COUNT:-0} | Remaining in Queue: ${REMAINING_COUNT:-0}"

echo "------------------------------------------------------------------------------"
# 3. Latest Verified Git Commit
echo "Latest Verified Commit (HEAD):"
git log -n 1 --oneline || echo "No git commits found."

echo "------------------------------------------------------------------------------"
# 4. Recent Completed Tasks
echo "Recent Progress (progress.log top entries):"
if [ -f "$PROGRESS_FILE" ]; then
  head -n 12 "$PROGRESS_FILE" | grep -v '^[[:space:]]*#' | grep -v '^[[:space:]]*$' | head -n 8 || echo "No recent entries."
else
  echo "No progress.log found."
fi
echo "=============================================================================="
