#!/usr/bin/env bash
# ==============================================================================
# Project Runner (Run Latest Verified / Live Working Tree State)
# Safe, non-intrusive execution while background worker.sh is running
# ==============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

STATUS_FILE="worker.status"

# Check worker activity without interfering
if [ -f "$STATUS_FILE" ]; then
  STATE=$(grep -o '"state":[[:space:]]*"[^"]*"' "$STATUS_FILE" 2>/dev/null | cut -d'"' -f4 || echo "IDLE")
  TASK=$(grep -o '"current_task":[[:space:]]*"[^"]*"' "$STATUS_FILE" 2>/dev/null | cut -d'"' -f4 || echo "")
  
  if [ "$STATE" = "RUNNING" ] && [ -n "$TASK" ] && [ "$TASK" != "null" ]; then
    echo -e "\033[1;33m[NOTICE]\033[0m Background Worker is actively processing: $TASK"
    echo -e "         Executing project with current cumulative working tree..."
    echo ""
  fi
fi

# Run the requested command or default project runner
if [ $# -eq 0 ]; then
  # Default action: run the project entrypoint
  echo -e "\033[1;32m[RUN]\033[0m Executing: python3 src/calc.py"
  python3 src/calc.py
elif [ "$1" = "test" ] || [ "$1" = "tests" ]; then
  echo -e "\033[1;32m[TEST]\033[0m Running test suite: python3 -m unittest discover tests"
  python3 -m unittest discover tests
else
  # Pass-through custom command
  echo -e "\033[1;32m[EXEC]\033[0m Executing: $@"
  "$@"
fi
