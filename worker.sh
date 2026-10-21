#!/usr/bin/env bash
# ==============================================================================
# 24-Hour Unattended Background Worker Daemon
# Dual-Terminal AI Development Framework
# ==============================================================================

set -uo pipefail

# ------------------------------------------------------------------------------
# 1. Mandatory Environment Configuration (.worker.env)
# ------------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.worker.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "=============================================================================="
  echo "[FATAL ERROR] Missing required configuration file: $ENV_FILE"
  echo ""
  echo "The .worker.env configuration is mandatory and MUST reside in the same"
  echo "directory as worker.sh."
  echo ""
  echo "Please initialize your configuration by copying the example template:"
  echo "  cp \"$SCRIPT_DIR/.worker.env.example\" \"$ENV_FILE\""
  echo "=============================================================================="
  exit 1
fi

# shellcheck source=/dev/null
source "$ENV_FILE"

# ------------------------------------------------------------------------------
# 2. Operating System Detection & Switching (macOS / Ubuntu / Linux)
# ------------------------------------------------------------------------------
TARGET_OS="${OS_TYPE:-auto}"
DETECTED_OS="unknown"
case "$(uname -s)" in
  Darwin*) DETECTED_OS="mac" ;;
  Linux*)
    if [ -f /etc/os-release ] && grep -qi ubuntu /etc/os-release; then
      DETECTED_OS="ubuntu"
    else
      DETECTED_OS="linux"
    fi
    ;;
  *) DETECTED_OS="unknown" ;;
esac

if [ "$TARGET_OS" = "auto" ] || [ -z "$TARGET_OS" ]; then
  ACTIVE_OS="$DETECTED_OS"
else
  ACTIVE_OS="$TARGET_OS"
fi

case "$ACTIVE_OS" in
  mac|darwin)
    NUM_CPUS=$(sysctl -n hw.ncpu 2>/dev/null || echo 4)
    PLATFORM_NAME="macOS (Darwin)"
    TIMEOUT_BIN=""
    if command -v gtimeout >/dev/null 2>&1; then
      TIMEOUT_BIN="gtimeout"
    elif command -v timeout >/dev/null 2>&1; then
      TIMEOUT_BIN="timeout"
    fi
    ;;
  ubuntu)
    NUM_CPUS=$(nproc 2>/dev/null || echo 4)
    PLATFORM_NAME="Linux (Ubuntu)"
    TIMEOUT_BIN=""
    if command -v timeout >/dev/null 2>&1; then
      TIMEOUT_BIN="timeout"
    fi
    ;;
  *)
    NUM_CPUS=$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)
    PLATFORM_NAME="Linux ($ACTIVE_OS)"
    TIMEOUT_BIN=""
    if command -v timeout >/dev/null 2>&1; then
      TIMEOUT_BIN="timeout"
    fi
    ;;
esac

# ------------------------------------------------------------------------------
# 3. Parameters, Paths & Multi-Worker Identity
# ------------------------------------------------------------------------------
WORKER_ID="${WORKER_ID:-default}"

resolve_path() {
  local p="$1"
  if [[ "$p" = /* ]]; then
    echo "$p"
  else
    echo "$SCRIPT_DIR/$p"
  fi
}

TASKS_FILE="$(resolve_path "${TASKS_FILE:-tasks.txt}")"
TASKS_DONE_FILE="$(resolve_path "${TASKS_DONE_FILE:-tasks.done}")"
PROGRESS_FILE="$(resolve_path "${PROGRESS_FILE:-progress.log}")"
PAUSE_FILE="$(resolve_path "${PAUSE_FILE:-PAUSE}")"

if [ "$WORKER_ID" = "default" ]; then
  STATUS_FILE="$(resolve_path "${STATUS_FILE:-worker.status}")"
  LOG_FILE="$(resolve_path "${LOG_FILE:-.worker.log}")"
  PID_FILE="$(resolve_path "${PID_FILE:-.worker.pid}")"
else
  STATUS_FILE="$(resolve_path "worker.${WORKER_ID}.status")"
  LOG_FILE="$(resolve_path ".worker.${WORKER_ID}.log")"
  PID_FILE="$(resolve_path ".worker.${WORKER_ID}.pid")"
fi

AI_CLI="${AI_CLI:-agy}"
AI_MODEL="${AI_MODEL:-gemini-3.8-flash-low}"
AI_EFFORT="${AI_EFFORT:-low}"
AGY_MODE="${AGY_MODE:-accept-edits}"
TASK_TIMEOUT="${TASK_TIMEOUT:-1800}"
POLL_INTERVAL="${POLL_INTERVAL:-5}"
USE_SANDBOX="${USE_SANDBOX:-0}"
RUN_ONCE="${RUN_ONCE:-0}"
ADDITIONAL_DIRS="${ADDITIONAL_DIRS:-}"
WORKER_ISOLATION="${WORKER_ISOLATION:-1}"
WORKER_PORT="${WORKER_PORT:-3001}"
PREVIEW_DIR="$SCRIPT_DIR/.preview"

if [ "$WORKER_ISOLATION" = "1" ] || [ "$WORKER_ISOLATION" = "true" ]; then
  WORK_DIR="$SCRIPT_DIR/.worker-tree"
  ISOLATION_FLAG="true"
else
  WORK_DIR="$SCRIPT_DIR"
  ISOLATION_FLAG="false"
fi

# Force non-interactive, unpaged batch environment
export CI=1
export PAGER=cat
export NO_COLOR=1
export DEBIAN_FRONTEND=noninteractive
export TERM=dumb

# ------------------------------------------------------------------------------
# Workspace Isolation & Preview Staging Helpers
# ------------------------------------------------------------------------------
ensure_worker_tree() {
  if [ "$WORKER_ISOLATION" != "1" ] && [ "$WORKER_ISOLATION" != "true" ]; then
    return 0
  fi

  local target_dir="$SCRIPT_DIR/.worker-tree"
  local branch_name="feature/worker-frontier"

  if [ ! -d "$target_dir" ] || [ ! -f "$target_dir/.git" ]; then
    echo "[WORKER] Initializing persistent worker worktree at $target_dir (Branch: $branch_name)..."
    if ! git show-ref --verify --quiet "refs/heads/$branch_name"; then
      git branch "$branch_name" HEAD 2>/dev/null || true
    fi
    git worktree add -B "$branch_name" "$target_dir" "$branch_name" 2>/dev/null || true
  fi

  # Fast-forward worker-frontier if main is ahead and worker tree is clean
  if git merge-base --is-ancestor "$branch_name" HEAD 2>/dev/null; then
    git -C "$target_dir" merge --ff-only HEAD 2>/dev/null || true
  fi

  # Mirror untracked environment configs
  [ -f "$SCRIPT_DIR/.env" ] && cp "$SCRIPT_DIR/.env" "$target_dir/.env" 2>/dev/null || true
  [ -f "$SCRIPT_DIR/.worker.env" ] && cp "$SCRIPT_DIR/.worker.env" "$target_dir/.worker.env" 2>/dev/null || true

  # Mirror heavy dependency caches
  [ -d "$SCRIPT_DIR/node_modules" ] && [ ! -e "$target_dir/node_modules" ] && ln -sf "$SCRIPT_DIR/node_modules" "$target_dir/node_modules" 2>/dev/null || true
  [ -d "$SCRIPT_DIR/.venv" ] && [ ! -e "$target_dir/.venv" ] && ln -sf "$SCRIPT_DIR/.venv" "$target_dir/.venv" 2>/dev/null || true

  # Share untracked ephemeral reports directory
  mkdir -p "$SCRIPT_DIR/.reports/.archive"
  [ ! -e "$target_dir/.reports" ] && ln -sf "$SCRIPT_DIR/.reports" "$target_dir/.reports" 2>/dev/null || true
}

publish_preview_artifact() {
  local task_id="$1"
  local task_title="$2"
  mkdir -p "$PREVIEW_DIR"

  # Clean git archive of feature/worker-frontier into .preview/
  if command -v tar >/dev/null 2>&1; then
    ( cd "$SCRIPT_DIR" && git archive feature/worker-frontier 2>/dev/null | tar -x -C "$PREVIEW_DIR" 2>/dev/null || true )
  fi

  # Copy compiled binary directories if present
  for bin_dir in build/bin target/debug bin dist; do
    if [ -d "$WORK_DIR/$bin_dir" ]; then
      mkdir -p "$PREVIEW_DIR/$bin_dir"
      cp -R "$WORK_DIR/$bin_dir/"* "$PREVIEW_DIR/$bin_dir/" 2>/dev/null || true
    fi
  done

  # Record version metadata
  local commit_hash
  commit_hash=$(git -C "$WORK_DIR" rev-parse --short HEAD 2>/dev/null || echo "unknown")
  cat <<JSON > "$PREVIEW_DIR/version.json"
{
  "task_id": "$task_id",
  "commit": "$commit_hash",
  "summary": "$task_title",
  "updated_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
}
JSON
  echo "[WORKER] Staged immutable preview drop-box at .preview/ (Commit: $commit_hash)"
}

# ------------------------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------------------------
render_progress_bar() {
  local cur="$1"
  local total="$2"
  local width="${3:-30}"
  if [ "$total" -le 0 ]; then
    echo "[------------------------------] 0% (0/0)"
    return
  fi
  local pct=$(( cur * 100 / total ))
  local filled=$(( cur * width / total ))
  local empty=$(( width - filled ))
  local bar=""
  for ((i=0; i<filled; i++)); do bar+="#"; done
  for ((i=0; i<empty; i++)); do bar+="-"; done
  echo "[$bar] ${pct}% (${cur}/${total})"
}

run_with_timeout() {
  local timeout_sec="$1"
  shift
  if [ -n "$TIMEOUT_BIN" ] && command -v "$TIMEOUT_BIN" >/dev/null 2>&1; then
    "$TIMEOUT_BIN" "$timeout_sec" "$@"
  elif command -v timeout >/dev/null 2>&1; then
    timeout "$timeout_sec" "$@"
  elif command -v gtimeout >/dev/null 2>&1; then
    gtimeout "$timeout_sec" "$@"
  else
    # Fallback for systems without timeout/gtimeout
    "$@" &
    local child_pid=$!
    (
      sleep "$timeout_sec"
      if kill -0 "$child_pid" 2>/dev/null; then
        kill -TERM "$child_pid" 2>/dev/null || true
        sleep 2
        kill -KILL "$child_pid" 2>/dev/null || true
      fi
    ) </dev/null >/dev/null 2>&1 &
    local watchdog_pid=$!
    wait "$child_pid"
    local exit_code=$?
    pkill -P "$watchdog_pid" 2>/dev/null || true
    kill -9 "$watchdog_pid" 2>/dev/null || true
    wait "$watchdog_pid" 2>/dev/null || true
    if [ $exit_code -eq 137 ] || [ $exit_code -eq 143 ]; then
      return 124
    fi
    return "$exit_code"
  fi
}

update_status() {
  local state="$1"
  local current_task="${2:-}"
  local elapsed="${3:-0}"
  local current_idx="${4:-0}"
  local total_tasks="${5:-0}"
  local remaining="${6:-0}"
  local percent="${7:-0%}"
  local bar="${8:-}"
  local now
  now=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

  if [ -z "$bar" ]; then
    bar=$(render_progress_bar "$current_idx" "$total_tasks" 30)
  fi

  cat <<EOF > "$STATUS_FILE"
{
  "worker_id": "$WORKER_ID",
  "os": "$ACTIVE_OS",
  "platform": "$PLATFORM_NAME",
  "isolation": $ISOLATION_FLAG,
  "work_dir": "$WORK_DIR",
  "state": "$state",
  "current_task": $(if [ -n "$current_task" ]; then echo "\"$current_task\""; else echo "null"; fi),
  "elapsed_seconds": $elapsed,
  "progress": {
    "current_index": $current_idx,
    "total_tasks": $total_tasks,
    "remaining": $remaining,
    "percentage": "$percent",
    "bar": "$bar"
  },
  "pid": $$,
  "model": "$AI_MODEL",
  "cli": "$AI_CLI",
  "timeout_seconds": $TASK_TIMEOUT,
  "last_heartbeat": "$now"
}
EOF
}

# ------------------------------------------------------------------------------
# Process Lock & Signal Handlers
# ------------------------------------------------------------------------------
if [ -f "$PID_FILE" ]; then
  OLD_PID=$(cat "$PID_FILE" 2>/dev/null || echo "")
  if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "ERROR: Worker daemon already running with PID $OLD_PID."
    exit 1
  fi
fi
echo "$$" > "$PID_FILE"

cleanup() {
  echo ""
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] Shutting down worker daemon..."
  rm -f "$PID_FILE"
  update_status "STOPPED" "" "0" "0" "0" "0" "0%" "[------------------------------] 0%"
  exit 0
}

trap cleanup SIGINT SIGTERM EXIT

prepend_progress_log() {
  local entry="$1"
  local temp_file
  temp_file=$(mktemp)
  echo "$entry" > "$temp_file"
  if [ -f "$PROGRESS_FILE" ]; then
    cat "$PROGRESS_FILE" >> "$temp_file"
  fi
  mv "$temp_file" "$PROGRESS_FILE"
}

isolate_and_rollback_dirty_tree() {
  local task_id="$1"
  local backup_dir="$SCRIPT_DIR/.scratch/failed_tasks/${task_id}_$(date +%Y%m%d_%H%M%S)"
  mkdir -p "$backup_dir"
  
  echo "[WORKER] Isolating failed changes to $backup_dir and resetting clean git tree..."
  git -C "$WORK_DIR" diff > "$backup_dir/changes.diff" 2>/dev/null || true
  git -C "$WORK_DIR" status --porcelain > "$backup_dir/status.txt" 2>/dev/null || true
  
  # Safe reset to head
  git -C "$WORK_DIR" restore . 2>/dev/null || true
  git -C "$WORK_DIR" clean -df 2>/dev/null || true
}

validate_post_flight() {
  local task_id="$1"
  local task_target="$2"
  local task_constraints="$3"
  local task_title="$4"
  local task_level="${5:-1}"
  local task_base_sha="${6:-HEAD~1}"

  # 1. Check clean working tree (Ghost files & uncommitted tests check)
  local dirty_files untracked_files
  dirty_files=$(git -C "$WORK_DIR" status --porcelain 2>/dev/null | grep -vE "(progress\.log|tasks\.txt|tasks\.done|worker\..*\.status|\.preview)" || true)
  untracked_files=$(git -C "$WORK_DIR" ls-files --others --exclude-standard 2>/dev/null | grep -vE "(progress\.log|tasks\.txt|tasks\.done|worker\..*\.status|\.preview|\.worker\..*)" || true)
  if [ -n "$dirty_files" ] || [ -n "$untracked_files" ]; then
    echo "[WORKER_GUARD] ❌ Dirty tree / untracked files detected after task:"
    echo "$dirty_files"
    echo "$untracked_files"
    GUARD_ERROR="Dirty working tree or untracked ghost files detected after task."
    return 1
  fi

  local committed_files
  committed_files=$(git -C "$WORK_DIR" diff --name-only "$task_base_sha" HEAD 2>/dev/null || git -C "$WORK_DIR" diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null || true)

  # 2. [Anti-Cheating Mech 1] Diagnostic Product-Code Lock
  # Modifying product code in [DIAGNOSTIC] is strictly forbidden.
  if echo "$task_title $task_constraints" | grep -iqE "\[DIAGNOSTIC\]"; then
    local committed_prod_files
    committed_prod_files=$(echo "$committed_files" | grep -iE '^(Sources|src|app|lib)/' || true)
    if [ -n "$committed_prod_files" ]; then
      echo "[WORKER_GUARD] ❌ Diagnostic Violation! Product code modified during [DIAGNOSTIC] task:"
      echo "$committed_prod_files"
      GUARD_ERROR="Diagnostic Violation: Modifying production code in [DIAGNOSTIC] is strictly forbidden. Only tests and .reports/ allowed."
      return 4
    fi
  fi

  # 3. [Anti-Cheating Mech 2 & Refactor Gate] Test Immutability & Assertion Non-Decrease
  if ! echo "$task_title $task_constraints" | grep -iqE "\[DIAGNOSTIC\]|\[RESEARCH\]"; then
    local committed_test_files
    committed_test_files=$(echo "$committed_files" | grep -iE '(^tests/|^Tests/|Test\.[a-z]+$|_test\.[a-z]+$)' || true)
    if [ -n "$committed_test_files" ]; then
      # If [CODE: FIX] or tests not in TARGET:
      if echo "$task_title" | grep -iqE "\[CODE:[[:space:]]*FIX\]" || ! echo "$task_target" | grep -iqE "(tests/|Tests/|test)"; then
        if ! echo "$task_constraints" | grep -iqE "test refactor approved"; then
          echo "[WORKER_GUARD] ❌ Test Immutability Violation! Test files modified during fix without explicit TARGET authorization:"
          echo "$committed_test_files"
          GUARD_ERROR="Test Immutability Violation: Modified test files without authorization in TARGET ($committed_test_files)."
          return 5
        fi
      fi

      # When test edits are authorized (e.g. [CODE: REFACTOR]): Assertion Non-Decrease Gate
      local deleted_asserts added_asserts
      deleted_asserts=$(git -C "$WORK_DIR" diff "$task_base_sha" HEAD -- $committed_test_files 2>/dev/null | grep -E '^\-[[:space:]]*(XCTAssert|#expect|assert|expect\(|self\.assert)' | grep -v -- '^\-\-\-' | wc -l | tr -dc '0-9')
      added_asserts=$(git -C "$WORK_DIR" diff "$task_base_sha" HEAD -- $committed_test_files 2>/dev/null | grep -E '^\+[[:space:]]*(XCTAssert|#expect|assert|expect\(|self\.assert)' | grep -v -- '^\+\+\+' | wc -l | tr -dc '0-9')
      [ -z "$deleted_asserts" ] && deleted_asserts=0
      [ -z "$added_asserts" ] && added_asserts=0

      if [ "$deleted_asserts" -gt "$added_asserts" ]; then
        echo "[WORKER_GUARD] ❌ Assertion Non-Decrease Violation! Deleted assertions ($deleted_asserts) > Added assertions ($added_asserts)."
        echo "[WORKER_GUARD] Weakening or deleting assertions during refactoring is strictly forbidden."
        GUARD_ERROR="Assertion Non-Decrease Violation: Deleted $deleted_asserts assertions while adding only $added_asserts."
        return 7
      fi
    fi
  fi

  # 4. [Blast Radius Gate] Limit line deletions dynamically by Level
  local deleted_lines
  deleted_lines=$(git -C "$WORK_DIR" diff --numstat "$task_base_sha" HEAD 2>/dev/null | awk '{sum += $2} END {print sum+0}')
  [ -z "$deleted_lines" ] && deleted_lines=0

  if ! echo "$task_constraints" | grep -iqE "large deletion approved|unrestricted"; then
    if [ "$task_level" -eq 3 ] && [ "$deleted_lines" -gt 40 ]; then
      echo "[WORKER_GUARD] ❌ Blast Radius Violation! Level 3 (Micro) deleted $deleted_lines lines (Max: 40)."
      GUARD_ERROR="Blast Radius Violation: Level 3 tasks cannot delete >40 lines (Deleted: $deleted_lines). Split task or calibrate to Level 2."
      return 8
    elif [ "$task_level" -eq 2 ] && [ "$deleted_lines" -gt 150 ]; then
      echo "[WORKER_GUARD] ❌ Blast Radius Violation! Level 2 (Standard) deleted $deleted_lines lines (Max: 150)."
      GUARD_ERROR="Blast Radius Violation: Level 2 tasks cannot delete >150 lines (Deleted: $deleted_lines). Split task or calibrate to Level 1."
      return 8
    fi
  fi

  # 5. Check target whitelist
  if [ -n "$task_target" ]; then
    # Unrestricted bypass only if explicitly stated
    if echo "$task_constraints" | grep -iqE "unrestricted"; then
      return 0
    fi
    # Diagnostics/research bypass whitelist if they only touched tests/reports (already guarded above)
    if echo "$task_title $task_constraints" | grep -iqE "\[DIAGNOSTIC\]|\[RESEARCH\]"; then
      return 0
    fi

    if [ -n "$committed_files" ]; then
      local target_tokens
      target_tokens=$(echo "$task_target" | tr ',' '\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | tr '[:upper:]' '[:lower:]')

      while IFS= read -r f; do
        [ -z "$f" ] && continue
        case "$f" in
          progress.log|tasks.txt|tasks.done|worker.status|.gitignore|.worker.notes.md|.reports/*|docs/reports/*)
            continue
            ;;
        esac

        local f_lower
        f_lower=$(echo "$f" | tr '[:upper:]' '[:lower:]')
        local matched=0

        while IFS= read -r t; do
          [ -z "$t" ] && continue
          t_clean="${t%/}"
          if [ "$f_lower" = "$t_clean" ] || [[ "$f_lower" == "$t_clean/"* ]]; then
            matched=1
            break
          fi
        done <<< "$target_tokens"

        if [ $matched -eq 0 ]; then
          # Check if multi-interface refactor is approved in constraints
          if echo "$task_constraints" | grep -iqE "multi-interface"; then
            matched=1
          fi
        fi

        if [ $matched -eq 0 ]; then
          echo "[WORKER_GUARD] ❌ Target Whitelist Violation! File '$f' is not declared in TARGET ($task_target)."
          echo "[WORKER_GUARD] Undeclared cross-subsystem edits are forbidden. Declare target or emit [SCOPE_BLOCKED] / [NEED_DECOMPOSITION]."
          GUARD_ERROR="Target Whitelist Violation: Modified unannounced file '$f' outside declared scope."
          return 2
        fi
      done <<< "$committed_files"
    fi
  fi

  return 0
}

# ------------------------------------------------------------------------------
# Startup Initialization
# ------------------------------------------------------------------------------
touch "$TASKS_FILE" "$TASKS_DONE_FILE" "$PROGRESS_FILE"
mkdir -p "$SCRIPT_DIR/.reports/.archive"
ensure_worker_tree

# Clean Pivot Checkpoint (Mechanism 4)
if git -C "$WORK_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C "$WORK_DIR" tag -f nightshift-session-base HEAD 2>/dev/null || true
  git tag -f nightshift-session-base HEAD 2>/dev/null || true
  echo "[WORKER] Checkpoint tagged: nightshift-session-base at $(git -C "$WORK_DIR" rev-parse --short HEAD 2>/dev/null)"
fi

echo "=============================================================================="
echo " 24-Hour Unattended AI Worker Daemon Started"
echo " Worker ID: $WORKER_ID | OS: $PLATFORM_NAME (CPUs: $NUM_CPUS)"
echo " PID: $$ | CLI: $AI_CLI | Model: $AI_MODEL | Mode: $AGY_MODE"
echo " WorkDir: $WORK_DIR | Isolation: $ISOLATION_FLAG"
echo " Tasks: $TASKS_FILE | Status: $STATUS_FILE"
echo " Progress: $PROGRESS_FILE | Log: $LOG_FILE"
echo "=============================================================================="

update_status "IDLE" "" "0" "0" "0" "0" "0%" "[------------------------------] 0%"

WAS_BUSY=0
IDLE_STATUS_SHOWN=0

# ------------------------------------------------------------------------------
# Main Polling Loop
# ------------------------------------------------------------------------------
while true; do
  # Check for physical pause switch
  if [ -f "$PAUSE_FILE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [PAUSED] Found $PAUSE_FILE. Sleeping..."
    update_status "PAUSED" "Paused via $PAUSE_FILE file" "0" "0" "0" "0" "0%" "[PAUSED]"
    sleep "$POLL_INTERVAL"
    continue
  fi

  # Peek at the first non-empty, non-comment line in tasks.txt
  RAW_TASK=$(grep -v '^[[:space:]]*#' "$TASKS_FILE" 2>/dev/null | grep -v '^[[:space:]]*$' | head -n 1 || true)

  DONE_COUNT=$(grep -v '^[[:space:]]*#' "$TASKS_DONE_FILE" 2>/dev/null | grep -v '^[[:space:]]*$' | wc -l | tr -dc '0-9')
  [ -z "$DONE_COUNT" ] && DONE_COUNT=0
  REMAINING_COUNT=$(grep -v '^[[:space:]]*#' "$TASKS_FILE" 2>/dev/null | grep -v '^[[:space:]]*$' | wc -l | tr -dc '0-9')
  [ -z "$REMAINING_COUNT" ] && REMAINING_COUNT=0
  TOTAL_COUNT=$(( DONE_COUNT + REMAINING_COUNT ))

  if [ -z "$RAW_TASK" ]; then
    BAR=$(render_progress_bar "$DONE_COUNT" "$TOTAL_COUNT" 30)
    update_status "IDLE" "" "0" "$DONE_COUNT" "$TOTAL_COUNT" "0" "100%" "$BAR"

    if [ $WAS_BUSY -eq 1 ]; then
      echo ""
      echo "=============================================================================="
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🎉 [ALL TASKS COMPLETED] $BAR"
      echo "[IDLE] Queue is empty (Total completed: $DONE_COUNT tasks)."
      echo "=============================================================================="
      WAS_BUSY=0
      IDLE_STATUS_SHOWN=1
      if [ "$RUN_ONCE" = "1" ] || [ "$RUN_ONCE" = "true" ]; then
        echo "[WORKER] Exiting because RUN_ONCE is enabled."
        exit 0
      fi
    elif [ $IDLE_STATUS_SHOWN -eq 0 ]; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] [IDLE] Queue is empty (Total completed: $DONE_COUNT tasks). Waiting for tasks in $TASKS_FILE..."
      IDLE_STATUS_SHOWN=1
      if [ "$RUN_ONCE" = "1" ] || [ "$RUN_ONCE" = "true" ]; then
        echo "[WORKER] Queue is empty and RUN_ONCE is enabled. Exiting."
        exit 0
      fi
    fi

    sleep "$POLL_INTERVAL"
    continue
  fi

  WAS_BUSY=1
  IDLE_STATUS_SHOWN=0

  CURRENT_IDX=$(( DONE_COUNT + 1 ))
  PERCENT_START=$(( (DONE_COUNT * 100) / TOTAL_COUNT ))
  BAR_START=$(render_progress_bar "$DONE_COUNT" "$TOTAL_COUNT" 30)

  # Pop the task line atomically from tasks.txt with directory-lock protection
  LOCK_DIR="${TASKS_FILE}.lock"
  LOCK_MAX_RETRIES=50
  LOCK_RETRY=0
  while ! mkdir "$LOCK_DIR" 2>/dev/null; do
    sleep 0.1
    LOCK_RETRY=$(( LOCK_RETRY + 1 ))
    if [ $LOCK_RETRY -ge $LOCK_MAX_RETRIES ]; then
      rmdir "$LOCK_DIR" 2>/dev/null || true
    fi
  done

  TEMP_TASKS=$(mktemp)
  awk -v task="$RAW_TASK" '
    !found && $0 == task { found=1; next }
    { print }
  ' "$TASKS_FILE" > "$TEMP_TASKS"
  mv "$TEMP_TASKS" "$TASKS_FILE"
  rmdir "$LOCK_DIR" 2>/dev/null || true

  TASK_TITLE="$RAW_TASK"
  TASK_ID=$(echo "$RAW_TASK" | awk -F'|' '{print $1}' | tr -d ' ' || echo "TASK-UNKNOWN")
  TASK_LEVEL=$(echo "$RAW_TASK" | grep -o 'LEVEL:[[:space:]]*[0-9]' | awk '{print $2}' || echo "1")
  TASK_TARGET=$(echo "$RAW_TASK" | sed -n 's/.*TARGET:[[:space:]]*\([^|]*\).*/\1/p' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' || echo "")
  TASK_VERIFY=$(echo "$RAW_TASK" | sed -n 's/.*VERIFY:[[:space:]]*\([^|]*\).*/\1/p' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' || echo "")
  TASK_FORBIDDEN=$(echo "$RAW_TASK" | sed -n 's/.*FORBIDDEN_SHORTCUTS:[[:space:]]*\([^|]*\).*/\1/p' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' || echo "")
  TASK_CONSTRAINTS=$(echo "$RAW_TASK" | sed -n 's/.*CONSTRAINTS:[[:space:]]*\([^|]*\).*/\1/p' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' || echo "")
  TASK_BASE_SHA=$(git -C "$WORK_DIR" rev-parse HEAD 2>/dev/null || echo "HEAD~1")
  START_TIME=$(date +%s)
  
  echo ""
  echo "=============================================================================="
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] >>> [Task $CURRENT_IDX of $TOTAL_COUNT (In Progress) | Completed: $DONE_COUNT/$TOTAL_COUNT ($PERCENT_START%)]"
  echo ">>> Progress: $BAR_START"
  echo ">>> Task: $TASK_TITLE"
  echo "=============================================================================="

  update_status "RUNNING" "$TASK_TITLE" "0" "$CURRENT_IDX" "$TOTAL_COUNT" "$((REMAINING_COUNT - 1))" "${PERCENT_START}%" "$BAR_START"

  # Construct Prompt for the CLI Process
  PROMPT_PAYLOAD=$(cat <<PROMPT_EOF
You are the unattended Background Worker AI executing an atomic task.
Read and strictly follow the mandatory SOP in .skills/universal-build-verify.md and guidelines in AGENTS.md.

TASK TO IMPLEMENT:
$TASK_TITLE

MANDATORY EXECUTION RULES:
1. REAL-TIME STEP LOGGING: Before running any command or editing any file, print an explicit line (e.g. "[EXEC] Modifying <file>...", "[EXEC] Running command: <command>", "[EXEC] Running test: <command>") so the operator can see what you are doing in real time.
2. TARGET SCOPE & CONSTRAINTS:
   - Modify ONLY declared files/directories (${TASK_TARGET:-target files}).
   - Cohesive multi-object / multi-interface changes are allowed when declared in TARGET.
   - [CODE: FIX]: Tests/ are strictly read-only. Modify only product files declared in TARGET.
   - [CODE: REFACTOR]: Tests/ and Mocks/ can be declared in TARGET.
     * ASSERTION NON-DECREASE GATE: You may update test method calls, but the total count of test assertions must NEVER decrease! Deleting or weakening assertions is strictly forbidden (Cheating).
   - [SCOPE_BLOCKED] ESCAPE HATCH: If compiler errors occur in downstream files outside declared TARGET, DO NOT touch them! Stop immediately and emit "[SCOPE_BLOCKED] (Need Target: <File>#L<Line>)" in your output. This will NOT deduct credit.
   - BLAST RADIUS LIMITS: Level 3 tasks max deletion <= 40 lines; Level 2 tasks max deletion <= 150 lines; Level 1 tasks unlimited (TARGET-bounded).
   - [RESEARCH] / [DIAGNOSTIC]: SUMMARY.md MUST include Interface Skeletons and 10-line context slices (use scripts/extract_skeleton.sh <file>#L<line>). Compiler probes permitted via dry-run signature tweak, build, and immediate 'git restore .'.
   - All tests and modified files MUST be staged and committed cleanly. Working tree must be 100% clean after commit.
3. FORBIDDEN SHORTCUTS (SYMPTOM MASKING BAN):
   ${TASK_FORBIDDEN:-"Never use thread sleeps/asyncAfter to mask race conditions, never swallow errors with try?/empty catch, never alter non-optional properties to optional just to dodge initializers, and never weaken assertions."}
   VIOLATION OF THESE PROHIBITIONS = IMMEDIATE REJECTION & ROLLBACK.
4. NO SUDO: Under NO circumstances run sudo, apt, or global system commands.
5. BUILD & VERIFY (ANTI-CHEATING GATES):
   - For [CODE] tasks: Verification must 100% PASS. Test Immutability Lock: Modifying or weakening assertions in existing repro tests is strictly forbidden (Cheating). Modify product code in TARGET only.
   - For [DIAGNOSTIC] tasks: False Red-Light Prevention: Repro test must compile cleanly (Build PASS / 0 syntax errors) and fail strictly on assertion (Test FAIL). Compilation errors or missing symbols are INVALID repros. Modifying production code (Sources/, src/, etc.) is strictly forbidden.
   - Scientific [DEAD_END]: Declaring [DEAD_END] requires Proof of Negative (passing isolated unit test or runtime log proving suspect module is innocent while global symptom persists). Unsubstantiated claims are rejected as task failure.
   - Run the appropriate build and test commands (e.g. ${TASK_VERIFY:-build and test}).
6. RETRY LIMIT: Max 3 repair attempts. If unable to pass after 3 fixes, stop immediately and record [BLOCKED].
7. UNIFIED CONVENTIONAL COMMIT (STRICT STYLE):
   On 100% verification pass, stage modified files and commit using this clean two-part Conventional Commit format:

   git commit -m "<type>(<scope>): <concise action description in English <= 60 chars> ($TASK_ID)" -m "<1-3 summary bullet points of concrete changes>

Task: $TASK_ID (Level ${TASK_LEVEL:-1})
Scope: ${TASK_TARGET:-<modified files>}
Verification: ${TASK_VERIFY:-<test command>} (100% PASS)
Attempts: <attempts_count> | Confidence: <1.0 or confidence score>"

   * Allowed <type>: feat, fix, refactor, test, docs, perf.
   * <scope>: module or component name (e.g. calc, auth, api, ui).
   * STRICT PROHIBITION: Do NOT put raw task strings (e.g. "TASK-XXX | LEVEL: ... | TARGET: ...") into the commit title! The title line must be clean and elegant for 'git log --oneline'.
8. TOP PREPEND PROGRESS: Write a structured <=10 lines report at the VERY TOP of $PROGRESS_FILE.
PROMPT_EOF
)

  # Execute CLI with Timeout Guard
  CMD_OUTPUT_TMP=$(mktemp)
  EXIT_CODE=0

  if [ "$AI_CLI" = "agy" ]; then
    EXTRA_CLI_ARGS=()
    if [ "$USE_SANDBOX" = "1" ] || [ "$USE_SANDBOX" = "true" ]; then
      EXTRA_CLI_ARGS+=("--sandbox")
    fi
    if [ -n "$AGY_MODE" ]; then
      EXTRA_CLI_ARGS+=("--mode" "$AGY_MODE")
    fi
    EXTRA_CLI_ARGS+=("--print-timeout" "${TASK_TIMEOUT}s")
    if [ -n "$ADDITIONAL_DIRS" ]; then
      IFS=',' read -ra DIRS <<< "$ADDITIONAL_DIRS"
      for d in "${DIRS[@]}"; do
        d_trimmed=$(echo "$d" | xargs)
        if [ -n "$d_trimmed" ] && [ -d "$d_trimmed" ]; then
          EXTRA_CLI_ARGS+=("--add-dir" "$d_trimmed")
        fi
      done
    fi

    # Pass --effort only if AI_MODEL does not already include an effort suffix
    if [ -n "$AI_EFFORT" ]; then
      case "$AI_MODEL" in
        *-low|*-medium|*-high|*-xhigh|*-max)
          ;;
        *)
          EXTRA_CLI_ARGS+=("--effort" "$AI_EFFORT")
          ;;
      esac
    fi

    echo "[WORKER] Launching $AI_CLI (Model: $AI_MODEL, Mode: ${AGY_MODE:-default}, WorkDir: $WORK_DIR)..."
    (
      cd "$WORK_DIR" && \
      export PORT="$WORKER_PORT" && \
      export TEST_PORT="$WORKER_PORT" && \
      run_with_timeout "$TASK_TIMEOUT" agy -p "$PROMPT_PAYLOAD" \
        --dangerously-skip-permissions \
        --model "$AI_MODEL" \
        "${EXTRA_CLI_ARGS[@]}"
    ) 2>&1 | tee "$CMD_OUTPUT_TMP"
    EXIT_CODE="${PIPESTATUS[0]}"
  else
    echo "[WORKER] Launching $AI_CLI (WorkDir: $WORK_DIR)..."
    (
      cd "$WORK_DIR" && \
      export PORT="$WORKER_PORT" && \
      export TEST_PORT="$WORKER_PORT" && \
      run_with_timeout "$TASK_TIMEOUT" "$AI_CLI" "$PROMPT_PAYLOAD"
    ) 2>&1 | tee "$CMD_OUTPUT_TMP"
    EXIT_CODE="${PIPESTATUS[0]}"
  fi

  # Detect native print-timeout message in CLI output
  if [ $EXIT_CODE -eq 0 ] && grep -q "print timeout after" "$CMD_OUTPUT_TMP" 2>/dev/null; then
    EXIT_CODE=124
  fi

  END_TIME=$(date +%s)
  DURATION=$(( END_TIME - START_TIME ))

  # Append run output to .worker.log for auditing
  echo "=== [$(date '+%Y-%m-%d %H:%M:%S')] Task: $TASK_TITLE (Duration: ${DURATION}s, Exit: $EXIT_CODE) ===" >> "$LOG_FILE"
  cat "$CMD_OUTPUT_TMP" >> "$LOG_FILE"
  echo "" >> "$LOG_FILE"

  if [ $EXIT_CODE -eq 124 ]; then
    # Timeout occurred
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [TIMEOUT] Task exceeded ${TASK_TIMEOUT}s limit!"
    isolate_and_rollback_dirty_tree "$TASK_ID"
    
    BLOCKED_SUMMARY=$(cat <<BLOCK_EOF
================================================================================
[BLOCKED] $TASK_ID: Timeout Exceeded (${TASK_TIMEOUT}s)
Time: $(date '+%Y-%m-%d %H:%M:%S') | Status: TIMEOUT
Failure Reason: Task execution timed out after ${TASK_TIMEOUT} seconds.
Action Needed for Human: Task may be too complex. Split into smaller atomic tasks.
================================================================================
BLOCK_EOF
)
    prepend_progress_log "$BLOCKED_SUMMARY"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [FAILED] $TASK_TITLE [TIMEOUT]" >> "$TASKS_DONE_FILE"
    update_status "BLOCKED" "$TASK_TITLE (TIMEOUT)" "$DURATION" "$CURRENT_IDX" "$TOTAL_COUNT" "$((REMAINING_COUNT - 1))" "${PERCENT_START}%" "$BAR_START"

  elif grep -q '\[SCOPE_BLOCKED\]' "$CMD_OUTPUT_TMP" 2>/dev/null; then
    # Worker honestly reported downstream scope blocked
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🚧 [SCOPE BLOCKED] Worker honestly stopped at unannounced downstream boundaries."
    isolate_and_rollback_dirty_tree "$TASK_ID"
    
    BLOCKED_SUMMARY=$(cat <<BLOCK_EOF
================================================================================
[SCOPE_BLOCKED] $TASK_ID: Downstream Scope Boundary Reached
Time: $(date '+%Y-%m-%d %H:%M:%S') | Status: SCOPE_BLOCKED
Details: Compiler errors detected in files outside TARGET whitelist.
Worker honestly stopped without violating boundaries. (No credit deduction).
Action Needed for Human: Expand TARGET in tasks.txt or adopt Expand-Migrate-Contract.
================================================================================
BLOCK_EOF
)
    prepend_progress_log "$BLOCKED_SUMMARY"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [SCOPE_BLOCKED] $TASK_TITLE" >> "$TASKS_DONE_FILE"
    update_status "SCOPE_BLOCKED" "$TASK_TITLE" "$DURATION" "$CURRENT_IDX" "$TOTAL_COUNT" "$((REMAINING_COUNT - 1))" "${PERCENT_START}%" "$BAR_START"

  elif grep -q '\[NEED_GUIDANCE\]\|\[NEED_DECOMPOSITION\]' "$CMD_OUTPUT_TMP" 2>/dev/null; then
    # Worker honestly requested guidance or decomposition
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✋ [AWAITING GUIDANCE] Worker honestly requested manager guidance."
    isolate_and_rollback_dirty_tree "$TASK_ID"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [GUIDANCE_REQUESTED] $TASK_TITLE" >> "$TASKS_DONE_FILE"
    update_status "AWAITING_GUIDANCE" "$TASK_TITLE" "$DURATION" "$CURRENT_IDX" "$TOTAL_COUNT" "$((REMAINING_COUNT - 1))" "${PERCENT_START}%" "$BAR_START"

  elif [ $EXIT_CODE -ne 0 ]; then
    # Execution failed
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] CLI exited with code $EXIT_CODE"
    isolate_and_rollback_dirty_tree "$TASK_ID"
    
    BLOCKED_SUMMARY=$(cat <<BLOCK_EOF
================================================================================
[BLOCKED] $TASK_ID: Execution Failed (Exit Code: $EXIT_CODE)
Time: $(date '+%Y-%m-%d %H:%M:%S') | Status: FAILED
Failure Reason: Worker CLI returned non-zero exit status $EXIT_CODE.
Action Needed for Human: Inspect .worker.log for error details.
================================================================================
BLOCK_EOF
)
    prepend_progress_log "$BLOCKED_SUMMARY"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [FAILED] $TASK_TITLE [EXIT_$EXIT_CODE]" >> "$TASKS_DONE_FILE"
    update_status "BLOCKED" "$TASK_TITLE (ERROR $EXIT_CODE)" "$DURATION" "$CURRENT_IDX" "$TOTAL_COUNT" "$((REMAINING_COUNT - 1))" "${PERCENT_START}%" "$BAR_START"

  else
    # Run Post-Flight Guard Validation
    GUARD_ERROR=""
    validate_post_flight "$TASK_ID" "$TASK_TARGET" "$TASK_CONSTRAINTS" "$TASK_TITLE" "$TASK_LEVEL" "$TASK_BASE_SHA"
    GUARD_STATUS=$?

    MECH_VERIFY_EXIT=0
    VERIFY_LOG_TMP=$(mktemp)
    if [ $GUARD_STATUS -eq 0 ]; then
      # Run Mechanical Verification Audit (Mechanism 5)
      if echo "$TASK_TITLE $TASK_CONSTRAINTS" | grep -iqE "\[DIAGNOSTIC\]"; then
        echo "[WORKER_GUARD] 🔍 Executing Mechanical Audit ([DIAGNOSTIC]): ${TASK_VERIFY:-None}"
        if [ -n "$TASK_VERIFY" ]; then
          (
            cd "$WORK_DIR" && \
            export PORT="$WORKER_PORT" && \
            export TEST_PORT="$WORKER_PORT" && \
            run_with_timeout 180 bash -c "$TASK_VERIFY"
          ) > "$VERIFY_LOG_TMP" 2>&1 || true
          # In [DIAGNOSTIC]: Ensure it did not fail from compilation error
          if grep -iqE "error: cannot find|syntax error|compilation failed|build failed|undefined symbol" "$VERIFY_LOG_TMP" 2>/dev/null; then
            GUARD_STATUS=4
            GUARD_ERROR="False Red-Light Detected: Repro failed on compilation/syntax error instead of test assertion."
          fi
        fi
      elif echo "$TASK_TITLE $TASK_CONSTRAINTS" | grep -iqE "\[RESEARCH\]"; then
        echo "[WORKER_GUARD] 🔍 Executing Mechanical Audit ([RESEARCH])..."

        # 1. Gate 2: Clean Tree / Git Zero-Modification Gate
        # Ensure working tree has no uncommitted changes to product code or test files
        local research_dirty
        research_dirty=$(git -C "$WORK_DIR" status --porcelain 2>/dev/null | grep -vE "(progress\.log|tasks\.txt|tasks\.done|worker\..*\.status|\.preview|\.worker\..*|\.reports/)" || true)
        if [ -n "$research_dirty" ]; then
          GUARD_STATUS=12
          GUARD_ERROR="Research Zero-Touch Violation: Uncommitted/modified files detected after research ($research_dirty)."
        fi

        # 2. Gate 1: Artifact Integrity Gate
        # Look for SUMMARY.md in .reports/ or report path in TARGET
        if [ $GUARD_STATUS -eq 0 ]; then
          local report_path=""
          if [ -n "$TASK_TARGET" ] && [ -f "$WORK_DIR/$TASK_TARGET" ]; then
            report_path="$WORK_DIR/$TASK_TARGET"
          else
            report_path=$(find "$WORK_DIR/.reports" -name "SUMMARY.md" 2>/dev/null | head -n 1 || true)
            if [ -z "$report_path" ]; then
              report_path=$(find "$WORK_DIR/docs/research" -name "*.md" 2>/dev/null | head -n 1 || true)
            fi
          fi

          if [ -z "$report_path" ] || [ ! -s "$report_path" ]; then
            GUARD_STATUS=11
            GUARD_ERROR="Research Artifact Missing: No non-empty SUMMARY.md found in .reports/ or declared TARGET."
          else
            # Check for core markdown structure (at least one heading)
            if ! grep -qE '^#+[[:space:]]+' "$report_path" 2>/dev/null; then
              GUARD_STATUS=11
              GUARD_ERROR="Research Artifact Invalid: Report '$report_path' lacks standard markdown headings."
            else
              echo "[WORKER_GUARD] ✅ Artifact verified: $report_path ($(wc -c < "$report_path" | tr -dc '0-9') bytes)"

              # 3. Gate 4: Pointer Validity Probe
              # Extract pointers like <File>#L<Line> from report and verify target file and line count
              local sampled_ptrs
              sampled_ptrs=$(grep -oE '[a-zA-Z0-9_./-]+\.[a-zA-Z0-9]+#L[0-9]+' "$report_path" 2>/dev/null | head -n 5 || true)
              if [ -n "$sampled_ptrs" ]; then
                while IFS= read -r ptr; do
                  [ -z "$ptr" ] && continue
                  local p_file="${ptr%#L*}"
                  local p_line="${ptr##*#L}"
                  if [ -f "$WORK_DIR/$p_file" ]; then
                    local total_lines
                    total_lines=$(wc -l < "$WORK_DIR/$p_file" | tr -dc '0-9')
                    if [ "$p_line" -gt "$total_lines" ]; then
                      GUARD_STATUS=13
                      GUARD_ERROR="Pointer Validity Violation: Line $p_line in pointer '$ptr' exceeds total file lines ($total_lines)."
                      break
                    fi
                    echo "[WORKER_GUARD] 🔍 Verified pointer target: $p_file#L$p_line (Total lines: $total_lines)"
                  fi
                done <<< "$sampled_ptrs"
              fi
            fi
          fi
        fi

        # 4. Optional Custom VERIFY (only if explicitly specified and not REPORT_ONLY / none)
        if [ $GUARD_STATUS -eq 0 ] && [ -n "$TASK_VERIFY" ]; then
          if ! echo "$TASK_VERIFY" | grep -iqE "^(REPORT_ONLY|none)$"; then
            echo "[WORKER_GUARD] 🔍 Executing Custom Research VERIFY: $TASK_VERIFY"
            (
              cd "$WORK_DIR" && \
              export PORT="$WORKER_PORT" && \
              export TEST_PORT="$WORKER_PORT" && \
              run_with_timeout 180 bash -c "$TASK_VERIFY"
            ) > "$VERIFY_LOG_TMP" 2>&1
            MECH_VERIFY_EXIT=$?
            if [ $MECH_VERIFY_EXIT -ne 0 ]; then
              GUARD_STATUS=6
              GUARD_ERROR="Mechanical Verification Failed: '$TASK_VERIFY' returned exit code $MECH_VERIFY_EXIT (Expected 0)."
            fi
          fi
        fi
      else
        echo "[WORKER_GUARD] 🔍 Executing Mechanical Audit ([CODE]): ${TASK_VERIFY:-None}"
        if [ -n "$TASK_VERIFY" ]; then
          (
            cd "$WORK_DIR" && \
            export PORT="$WORKER_PORT" && \
            export TEST_PORT="$WORKER_PORT" && \
            run_with_timeout 180 bash -c "$TASK_VERIFY"
          ) > "$VERIFY_LOG_TMP" 2>&1
          MECH_VERIFY_EXIT=$?
          if [ $MECH_VERIFY_EXIT -ne 0 ]; then
            GUARD_STATUS=6
            GUARD_ERROR="Mechanical Verification Failed: '$TASK_VERIFY' returned exit code $MECH_VERIFY_EXIT (Expected 0)."
          else
            # Anti-Idle Check: Ensure tests executed >= 1 (prevent typo in test filter)
            if grep -iqE "(0 tests passed|0 passed|ran 0 tests|0 suites passed|No matching tests)" "$VERIFY_LOG_TMP" 2>/dev/null; then
              GUARD_STATUS=9
              GUARD_ERROR="Empty Test Run Detected (Anti-Idle): VERIFY ran 0 tests. Possible test filter typo."
            else
              # Module Regression Check: Ensure whole package/module tests still pass
              if [ -f "$WORK_DIR/Package.swift" ]; then
                echo "[WORKER_GUARD] 🔍 Executing Regression Check (swift test)..."
                (
                  cd "$WORK_DIR" && \
                  export PORT="$WORKER_PORT" && \
                  export TEST_PORT="$WORKER_PORT" && \
                  run_with_timeout 180 swift test
                ) >/dev/null 2>&1
                if [ $? -ne 0 ]; then
                  GUARD_STATUS=10
                  GUARD_ERROR="Regression Check Failed: Whole-suite regression tests failed."
                fi
              fi
            fi
          fi
        fi
      fi
    fi
    rm -f "$VERIFY_LOG_TMP"

    if [ $GUARD_STATUS -ne 0 ]; then
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🛑 [GUARD REJECTION] Post-flight validation failed: $GUARD_ERROR"
      isolate_and_rollback_dirty_tree "$TASK_ID"
      BLOCKED_SUMMARY=$(cat <<BLOCK_EOF
[MECHANICAL_AUDIT] Status: FAIL | Verify_Exit: $MECH_VERIFY_EXIT | Whitelist: $GUARD_STATUS | Tree: DIRTY
================================================================================
[BLOCKED] $TASK_ID: Guard Validation Failed
Time: $(date '+%Y-%m-%d %H:%M:%S') | Status: GUARD_VIOLATION
Failure Reason: $GUARD_ERROR
Action Needed for Human: Inspect error and check target whitelist, forbidden shortcuts, or test assertions.
================================================================================
BLOCK_EOF
)
      prepend_progress_log "$BLOCKED_SUMMARY"
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] [FAILED] $TASK_TITLE [GUARD_VIOLATION]" >> "$TASKS_DONE_FILE"
      update_status "BLOCKED" "$TASK_TITLE (GUARD VIOLATION)" "$DURATION" "$CURRENT_IDX" "$TOTAL_COUNT" "$((REMAINING_COUNT - 1))" "${PERCENT_START}%" "$BAR_START"
    else
      # Extract actual attempts count from output or progress.log
      DETECTED_ATTEMPTS=$(grep -oE 'Attempts:[[:space:]]*[0-9]+' "$CMD_OUTPUT_TMP" 2>/dev/null | head -n 1 | awk '{print $2}' || true)
      [ -z "$DETECTED_ATTEMPTS" ] && DETECTED_ATTEMPTS=$(grep -oE 'Attempts:[[:space:]]*[0-9]+' "$PROGRESS_FILE" 2>/dev/null | head -n 1 | awk '{print $2}' || true)
      [ -z "$DETECTED_ATTEMPTS" ] && DETECTED_ATTEMPTS="1"

      DIFF_STAT=$(git -C "$WORK_DIR" diff --stat "$TASK_BASE_SHA" HEAD 2>/dev/null | tail -n 1 | xargs || echo "0 files changed")

      # Prepend machine audit stamp to progress.log (Mechanism 5)
      prepend_progress_log "[MECHANICAL_AUDIT] Status: PASS | Verify_Exit: 0 | Tests_Run: >=1 | Whitelist: PASS | Tree: CLEAN | Diff: $DIFF_STAT | Attempts: $DETECTED_ATTEMPTS"

      # Success
      if [ "$WORKER_ISOLATION" = "1" ] || [ "$WORKER_ISOLATION" = "true" ]; then
        publish_preview_artifact "$TASK_ID" "$TASK_TITLE"
      fi
      NEW_DONE_COUNT=$(( DONE_COUNT + 1 ))
      FINAL_BAR=$(render_progress_bar "$NEW_DONE_COUNT" "$TOTAL_COUNT" 30)
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] [SUCCESS] Task completed in ${DURATION}s | $FINAL_BAR"
      echo "[$(date '+%Y-%m-%d %H:%M:%S')] [DONE] $TASK_TITLE (Duration: ${DURATION}s)" >> "$TASKS_DONE_FILE"
      update_status "IDLE" "" "0" "$NEW_DONE_COUNT" "$TOTAL_COUNT" "$((REMAINING_COUNT - 1))" "$(( (NEW_DONE_COUNT * 100) / TOTAL_COUNT ))%" "$FINAL_BAR"
    fi
  fi

  rm -f "$CMD_OUTPUT_TMP"
  sleep "$POLL_INTERVAL"
done
