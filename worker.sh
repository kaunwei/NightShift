#!/usr/bin/env bash
# Compatibility launcher for the Python NightShift worker runtime.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Worker runtime settings live in this launcher. Agent-specific settings live
# in scripts/adapters/agents.json and are passed through the common adapter protocol.
PYTHON_BIN="${PYTHON_BIN:-python3}"
WORKER_ID="${WORKER_ID:-default}"
OS_TYPE="${OS_TYPE:-auto}"
TASKS_FILE="${TASKS_FILE:-tasks.txt}"
TASKS_DONE_FILE="${TASKS_DONE_FILE:-tasks.done}"
PROGRESS_FILE="${PROGRESS_FILE:-progress.log}"
PAUSE_FILE="${PAUSE_FILE:-PAUSE}"
WORKER_SCORE_FILE="${WORKER_SCORE_FILE:-.worker-score.json}"
WORKER_AGENT_SCORES_DIR="${WORKER_AGENT_SCORES_DIR:-.worker-agent-scores}"
WORKER_AGENT_EVENTS_FILE="${WORKER_AGENT_EVENTS_FILE:-.worker-agent-events.jsonl}"
AI_AGENT_STATE_FILE="${AI_AGENT_STATE_FILE:-}"
WORKER_GHOST_STATE_FILE="${WORKER_GHOST_STATE_FILE:-}"
WORKER_GHOST_ARTIFACT_DIR="${WORKER_GHOST_ARTIFACT_DIR:-.worker-ghosts}"
AGENT_DISPATCH_GATE_FILE="${AGENT_DISPATCH_GATE_FILE:-.worker-dispatch-gate.json}"
STATUS_FILE="${STATUS_FILE:-worker.status}"
LOG_FILE="${LOG_FILE:-.worker.log}"
TASK_TIMEOUT="${TASK_TIMEOUT:-1800}"
STEP_BASE="${STEP_BASE:-12}"
STEP_PER_FILE="${STEP_PER_FILE:-5}"
POLL_INTERVAL="${POLL_INTERVAL:-5}"
RUN_ONCE="${RUN_ONCE:-0}"
WORKER_PORT="${WORKER_PORT:-3000}"
AGENT_CONFIG_FILE="${AGENT_CONFIG_FILE:-$SCRIPT_DIR/scripts/adapters/agents.json}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[FATAL ERROR] Python runtime not found: $PYTHON_BIN" >&2
  exit 1
fi
if [ ! -f "$SCRIPT_DIR/scripts/worker_runtime.py" ]; then
  echo "[FATAL ERROR] Missing scripts/worker_runtime.py" >&2
  exit 1
fi

# Export only documented worker settings to the runtime.
export AGENT_CONFIG_FILE
export WORKER_ID OS_TYPE TASKS_FILE TASKS_DONE_FILE PROGRESS_FILE PAUSE_FILE
export WORKER_SCORE_FILE WORKER_AGENT_SCORES_DIR WORKER_AGENT_EVENTS_FILE
export AI_AGENT_STATE_FILE WORKER_GHOST_STATE_FILE WORKER_GHOST_ARTIFACT_DIR
export AGENT_DISPATCH_GATE_FILE STATUS_FILE LOG_FILE TASK_TIMEOUT STEP_BASE STEP_PER_FILE
export POLL_INTERVAL RUN_ONCE WORKER_PORT

exec "$PYTHON_BIN" "$SCRIPT_DIR/scripts/worker_runtime.py" daemon --root "$SCRIPT_DIR"
