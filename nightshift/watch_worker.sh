#!/usr/bin/env bash
# Wait for a specific worker task to finish and pass its mechanical audit.

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
cd "$PROJECT_ROOT" || exit 1

TASKS_FILE="${TASKS_FILE:-$NIGHTSHIFT_DIR/tasks.txt}"
TASKS_DONE_FILE="${TASKS_DONE_FILE:-$NIGHTSHIFT_DIR/tasks.done}"
STATUS_FILE="${STATUS_FILE:-$NIGHTSHIFT_DIR/worker.status}"
PROGRESS_FILE="${PROGRESS_FILE:-$NIGHTSHIFT_DIR/progress.log}"
if [ "${WORKER_ID:-default}" != "default" ]; then
  STATUS_FILE="$NIGHTSHIFT_DIR/worker.${WORKER_ID}.status"
fi
MAX_WAIT_SECONDS="${1:-3600}"
POLL_INTERVAL="${2:-5}"
EXPECTED_TASK_ID="${3:-${WATCH_TASK_ID:-}}"
AGENT_EVENTS_FILE="${WORKER_AGENT_EVENTS_FILE:-$NIGHTSHIFT_DIR/.worker-agent-events.jsonl}"
AGENT_EVENTS_CURSOR_FILE="${WORKER_AGENT_EVENTS_CURSOR_FILE:-$NIGHTSHIFT_DIR/.worker-agent-events.cursor.json}"
AGENT_EVENTS_ACK_FILE="${WORKER_AGENT_EVENTS_ACK_FILE:-$NIGHTSHIFT_DIR/.worker-agent-events.acks.jsonl}"
AGENT_DISPATCH_GATE_FILE="${AGENT_DISPATCH_GATE_FILE:-$NIGHTSHIFT_DIR/.worker-dispatch-gate.json}"

START_TIME=$(date +%s)
LAST_DONE_BYTES=0
BASELINE_AUDITS=$(mktemp "${TMPDIR:-/tmp}/nightshift-audit-baseline.XXXXXX") || exit 1
trap 'rm -f "$BASELINE_AUDITS"' EXIT
if [ -f "$PROGRESS_FILE" ]; then
  grep -E '^\[MECHANICAL_AUDIT\] Status: PASS \| Task: TASK-' "$PROGRESS_FILE" > "$BASELINE_AUDITS" || true
fi
if [ -f "$TASKS_DONE_FILE" ]; then
  LAST_DONE_BYTES=$(wc -c < "$TASKS_DONE_FILE" | tr -d '[:space:]')
fi
TRACKED_TASKS=""
AUDITED_DONE_TASKS=""

track_task() {
  local task_id="$1"
  [ -n "$task_id" ] || return 0
  case " $TRACKED_TASKS " in
    *" $task_id "*) ;;
    *) TRACKED_TASKS="${TRACKED_TASKS}${TRACKED_TASKS:+ }$task_id" ;;
  esac
}

contains_task() {
  local task_id="$1" list="$2"
  case " $list " in *" $task_id "*) return 0 ;; *) return 1 ;; esac
}

task_ids_from_file() {
  local file="$1"
  [ -f "$file" ] || return 0
  sed -nE 's/^[[:space:]]*(TASK-[[:alnum:]_.-]+).*/\1/p' "$file"
}

track_task "$EXPECTED_TASK_ID"
echo "[SENTINEL] Watching background worker (Timeout: ${MAX_WAIT_SECONDS}s, Interval: ${POLL_INTERVAL}s${EXPECTED_TASK_ID:+, Task: ${EXPECTED_TASK_ID}})..."

while true; do
  if [ -f "$RUNTIME_PATH" ]; then
    python3 "$RUNTIME_PATH" agent-events-watch \
      --events "$AGENT_EVENTS_FILE" --cursor "$AGENT_EVENTS_CURSOR_FILE" \
      --acknowledgements "$AGENT_EVENTS_ACK_FILE" --gate "$AGENT_DISPATCH_GATE_FILE" \
      --handoff "$PROGRESS_FILE" >/dev/null || echo "[SENTINEL_WARNING] Agent event watcher failed; dispatch remains gated." >&2
  fi
  NOW=$(date +%s)
  ELAPSED=$(( NOW - START_TIME ))

  if [ "$ELAPSED" -ge "$MAX_WAIT_SECONDS" ]; then
    echo "[SENTINEL_TIMEOUT] Exceeded ${MAX_WAIT_SECONDS}s waiting for task completion."
    exit 2
  fi

  while IFS= read -r task_id; do track_task "$task_id"; done < <(task_ids_from_file "$TASKS_FILE")

  STATE="UNKNOWN"
  CURRENT_TASK=""
  WORKER_PID=""
  if [ -f "$STATUS_FILE" ]; then
    STATE=$(grep -o '"state":[[:space:]]*"[^"]*"' "$STATUS_FILE" 2>/dev/null | cut -d'"' -f4 || true)
    CURRENT_TASK=$(grep -o '"current_task":[[:space:]]*"[^"]*"' "$STATUS_FILE" 2>/dev/null | grep -Eo 'TASK-[[:alnum:]_.-]+' | head -n 1 || true)
    WORKER_PID=$(grep -o '"pid":[[:space:]]*[0-9]*' "$STATUS_FILE" 2>/dev/null | awk '{print $2}' || true)
    [ -z "$STATE" ] && STATE="UNKNOWN"
  fi
  track_task "$CURRENT_TASK"

  NEW_DONE=""
  if [ -f "$TASKS_DONE_FILE" ]; then
    CURRENT_DONE_BYTES=$(wc -c < "$TASKS_DONE_FILE" | tr -d '[:space:]')
    if [ "$CURRENT_DONE_BYTES" -lt "$LAST_DONE_BYTES" ]; then
      # The ledger was rotated. Treat its current contents as new evidence.
      LAST_DONE_BYTES=0
    fi
    if [ "$CURRENT_DONE_BYTES" -gt "$LAST_DONE_BYTES" ]; then
      NEW_DONE=$(tail -c +$((LAST_DONE_BYTES + 1)) "$TASKS_DONE_FILE" 2>/dev/null || true)
      LAST_DONE_BYTES="$CURRENT_DONE_BYTES"
    fi
  fi

  NEW_DONE_IDS=$(printf '%s\n' "$NEW_DONE" | grep -Eo '\[DONE\][[:space:]]+TASK-[[:alnum:]_.-]+' | awk '{print $2}' || true)
  NEW_FAILED_IDS=$(printf '%s\n' "$NEW_DONE" | grep -Eo '\[(FAILED|SCOPE_BLOCKED|GUIDANCE_REQUESTED)\][[:space:]]+TASK-[[:alnum:]_.-]+' | awk '{print $2}' || true)
  while IFS= read -r task_id; do track_task "$task_id"; done <<< "$NEW_DONE_IDS"
  while IFS= read -r task_id; do track_task "$task_id"; done <<< "$NEW_FAILED_IDS"

  for task_id in $TRACKED_TASKS; do
    if contains_task "$task_id" "$NEW_FAILED_IDS"; then
      echo "[SENTINEL_FAILED] Task $task_id received a failure result after ${ELAPSED}s."
      exit 1
    fi
    if contains_task "$task_id" "$NEW_DONE_IDS"; then
      MATCHING_AUDITS=$(grep -E "^\\[MECHANICAL_AUDIT\\] Status: PASS \\| Task: ${task_id} \\|" "$PROGRESS_FILE" 2>/dev/null || true)
      FRESH_AUDIT=0
      while IFS= read -r audit_line; do
        [ -n "$audit_line" ] || continue
        if ! grep -Fqx -- "$audit_line" "$BASELINE_AUDITS"; then
          FRESH_AUDIT=1
          break
        fi
      done <<< "$MATCHING_AUDITS"
      if [ "$FRESH_AUDIT" -eq 1 ]; then
        case " $AUDITED_DONE_TASKS " in
          *" $task_id "*) ;;
          *) AUDITED_DONE_TASKS="${AUDITED_DONE_TASKS}${AUDITED_DONE_TASKS:+ }$task_id" ;;
        esac
        if [ -n "$EXPECTED_TASK_ID" ] && [ "$task_id" = "$EXPECTED_TASK_ID" ]; then
          echo "[SENTINEL_COMPLETED] Task $task_id completed with a task-scoped mechanical audit PASS in ${ELAPSED}s."
          exit 0
        fi
      fi
    fi
  done

  REMAINING_TASKS=$(grep -v '^[[:space:]]*#' "$TASKS_FILE" 2>/dev/null | grep -v '^[[:space:]]*$' | wc -l | tr -d '[:space:]')
  if [ -z "$EXPECTED_TASK_ID" ] && [ "$REMAINING_TASKS" -eq 0 ] && { [ "$STATE" = "IDLE" ] || [ "$STATE" = "STOPPED" ]; }; then
    if [ -n "$AUDITED_DONE_TASKS" ]; then
      echo "[SENTINEL_COMPLETED] Task $AUDITED_DONE_TASKS completed with a task-scoped mechanical audit PASS in ${ELAPSED}s."
      exit 0
    fi
  fi

  if [ "$STATE" = "SCOPE_BLOCKED" ]; then
    echo "[SENTINEL_SCOPE_BLOCKED] Worker encountered unannounced downstream scope after ${ELAPSED}s. (No-fault escalation)."
    exit 3
  fi
  if [ "$STATE" = "BLOCKED" ] || [ "$STATE" = "AWAITING_GUIDANCE" ]; then
    echo "[SENTINEL_BLOCKED] Worker entered state: $STATE after ${ELAPSED}s."
    exit 1
  fi
  if [ "$STATE" = "AGENT_NO_RESPONSE" ]; then
    echo "[SENTINEL_AGENT_NO_RESPONSE] Worker entered state: $STATE after ${ELAPSED}s."
    exit 1
  fi
  if [ "$STATE" = "PAUSED_FOR_PLANNER" ]; then
    echo "[SENTINEL_PAUSED_FOR_PLANNER] Worker entered state: $STATE after ${ELAPSED}s."
    exit 1
  fi

  if [ -n "$WORKER_PID" ] && [ "$STATE" = "RUNNING" ]; then
    if ! kill -0 "$WORKER_PID" 2>/dev/null; then
      echo "[SENTINEL_WORKER_DIED] Worker process $WORKER_PID terminated unexpectedly."
      exit 1
    fi
  fi

  sleep "$POLL_INTERVAL"
done
