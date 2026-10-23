#!/usr/bin/env bash
# ==============================================================================
# Worker Status & Project Progress Dashboard
# Non-blocking, instant read-only status viewer
# ==============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR" || exit 1
if [ -f "$SCRIPT_DIR/.worker.env" ]; then
  # shellcheck source=/dev/null
  source "$SCRIPT_DIR/.worker.env"
fi
STATUS_FILE="${STATUS_FILE:-worker.status}"
if [ "${WORKER_ID:-default}" != "default" ]; then
  STATUS_FILE="worker.${WORKER_ID}.status"
fi
PROGRESS_FILE="${PROGRESS_FILE:-progress.log}"
TASKS_FILE="${TASKS_FILE:-tasks.txt}"
TASKS_DONE_FILE="${TASKS_DONE_FILE:-tasks.done}"
PAUSE_FILE="${PAUSE_FILE:-PAUSE}"

echo "=============================================================================="
echo "              24h Unattended Worker Status Dashboard"
echo "=============================================================================="

# 1. Worker Daemon Status
if [ -f "$STATUS_FILE" ]; then
  "${PYTHON_BIN:-python3}" "$SCRIPT_DIR/scripts/worker_runtime.py" status-display "$STATUS_FILE" || \
    echo "Worker Status  : Invalid status file"
else
  echo "Worker Status  : No worker.status found"
fi

# Check Preview Drop-box
if [ -f ".preview/version.json" ]; then
  PREV_TASK=$(grep -o '"task_id":[[:space:]]*"[^"]*"' .preview/version.json 2>/dev/null | cut -d'"' -f4 || echo "")
  PREV_COMMIT=$(grep -o '"commit":[[:space:]]*"[^"]*"' .preview/version.json 2>/dev/null | cut -d'"' -f4 || echo "")
  PREV_TIME=$(grep -o '"updated_at":[[:space:]]*"[^"]*"' .preview/version.json 2>/dev/null | cut -d'"' -f4 || echo "")
  echo "Preview Ready  : $PREV_TASK ($PREV_COMMIT) updated at $PREV_TIME"
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
