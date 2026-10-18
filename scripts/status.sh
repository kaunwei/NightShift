#!/usr/bin/env bash
# ==============================================================================
# Worker Status & Project Progress Dashboard
# Non-blocking, instant read-only status viewer
# ==============================================================================

set -uo pipefail

STATUS_FILE="worker.status"
PROGRESS_FILE="progress.log"
TASKS_FILE="tasks.txt"
TASKS_DONE_FILE="tasks.done"

echo "=============================================================================="
echo "              24h Unattended Worker Status Dashboard"
echo "=============================================================================="

# 1. Worker Daemon Status
if [ -f "$STATUS_FILE" ]; then
  STATE=$(grep -o '"state":[[:space:]]*"[^"]*"' "$STATUS_FILE" 2>/dev/null | cut -d'"' -f4 || echo "UNKNOWN")
  TASK=$(grep -o '"current_task":[[:space:]]*"[^"]*"' "$STATUS_FILE" 2>/dev/null | cut -d'"' -f4 || echo "None")
  ELAPSED=$(grep -o '"elapsed_seconds":[[:space:]]*[0-9]*' "$STATUS_FILE" 2>/dev/null | grep -o '[0-9]*' || echo "0")
  BAR=$(grep -o '"bar":[[:space:]]*"[^"]*"' "$STATUS_FILE" 2>/dev/null | cut -d'"' -f4 || echo "[---]")
  PID=$(grep -o '"pid":[[:space:]]*[0-9]*' "$STATUS_FILE" 2>/dev/null | grep -o '[0-9]*' || echo "-")
  
  # Check if PID is actually alive
  if [ "$PID" != "-" ] && kill -0 "$PID" 2>/dev/null; then
    ALIVE_FLAG="[ALIVE (PID: $PID)]"
  else
    ALIVE_FLAG="[DEAD / INACTIVE]"
  fi

  echo "Worker State   : $STATE $ALIVE_FLAG"
  echo "Current Task   : ${TASK:-None} (${ELAPSED}s elapsed)"
  echo "Progress       : $BAR"
else
  echo "Worker Status  : No worker.status found"
fi

if [ -f "PAUSE" ]; then
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
