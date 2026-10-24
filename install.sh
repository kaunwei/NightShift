#!/usr/bin/env bash
# ==============================================================================
# NightShift Framework Installer & Updater
# Clean, non-destructive installer and updater for Pure Skills-Driven Architecture.
# Usage: ./install.sh <target_repository_path>
#    or: ./update.sh <target_repository_path>
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
TARGET_DIR="${1:-}"

# Display banner
echo "=============================================================================="
echo "    NightShift: 24h Unattended Dual-Terminal AI Framework"
echo "=============================================================================="

if [ -z "$TARGET_DIR" ]; then
  echo "Error: Target repository path is required."
  echo "Usage: $0 /path/to/target-project"
  echo "  (Use '.' if you are running this from within the target repository)"
  exit 1
fi

if [ "$#" -ne 1 ]; then
  echo "Error: Exactly one target repository path is required."
  echo "Usage: $0 /path/to/target-project"
  exit 1
fi

if ! TARGET_DIR="$(cd -P -- "$TARGET_DIR" 2>/dev/null && pwd -P)"; then
  echo "Error: Target directory does not exist: $TARGET_DIR"
  exit 1
fi

if [ ! -d "$TARGET_DIR" ]; then
  echo "Error: Target directory does not exist: $TARGET_DIR"
  exit 1
fi

if [ "$TARGET_DIR" = "$SCRIPT_DIR" ]; then
  echo "Notice: Target directory is the NightShift framework source itself ($SCRIPT_DIR)."
  echo "Cannot install/update NightShift into its own source directory."
  exit 0
fi

# Detect whether this is a fresh install or an update
IS_UPDATE=0
if [ -f "$TARGET_DIR/worker.sh" ] || [ -d "$TARGET_DIR/.agents/skills/nightshift" ] || [ -d "$TARGET_DIR/.agents/skills/planner" ]; then
  IS_UPDATE=1
  echo "Target Repository : $TARGET_DIR"
  echo "Operation Mode    : UPDATE (Existing installation detected)"
else
  echo "Target Repository : $TARGET_DIR"
  echo "Operation Mode    : FRESH INSTALL"
fi
echo "Source Repository : $SCRIPT_DIR"
echo ""

# ------------------------------------------------------------------------------
# 1. Non-Destructive Copy of Core Assets
# ------------------------------------------------------------------------------
echo ">>> [1/5] Deploying core worker daemon & configuration..."
cp -f "$SCRIPT_DIR/worker.sh" "$TARGET_DIR/worker.sh"
mkdir -p "$TARGET_DIR/scripts"
cp -f "$SCRIPT_DIR/scripts/worker_runtime.py" "$TARGET_DIR/scripts/worker_runtime.py"
echo "  ✓ Deployed scripts/worker_runtime.py"
mkdir -p "$TARGET_DIR/scripts/adapters"
for adapter in codex.py agy.py generic.py; do
  cp -f "$SCRIPT_DIR/scripts/adapters/$adapter" "$TARGET_DIR/scripts/adapters/$adapter"
  chmod +x "$TARGET_DIR/scripts/adapters/$adapter"
done
mkdir -p "$TARGET_DIR/docs"
cp -f "$SCRIPT_DIR/docs/PORTING_GUIDE.md" "$TARGET_DIR/docs/PORTING_GUIDE.md"
mkdir -p "$TARGET_DIR/test/nightshift_worker"
cp -f "$SCRIPT_DIR/test/test_worker_runtime.py" "$TARGET_DIR/test/nightshift_worker/test_worker_runtime.py"
cp -f "$SCRIPT_DIR/test/README.md" "$TARGET_DIR/test/nightshift_worker/README.md"
touch "$TARGET_DIR/test/nightshift_worker/__init__.py"
chmod +x "$TARGET_DIR/worker.sh"
if [ "$IS_UPDATE" -eq 1 ]; then
  echo "  ✓ Updated worker.sh"
else
  echo "  ✓ Installed worker.sh"
fi

mkdir -p "$TARGET_DIR/agents"
if [ ! -f "$TARGET_DIR/agents/agents.json" ]; then
  cp "$SCRIPT_DIR/agents/agents.json" "$TARGET_DIR/agents/agents.json"
  echo "  ✓ Initialized agents/agents.json"
else
  echo "  • Preserved existing agents/agents.json (not overwritten)"
fi
if [ -f "$TARGET_DIR/.worker.env.example" ]; then
  rm -f "$TARGET_DIR/.worker.env.example"
  echo "  ✓ Removed deprecated .worker.env.example"
fi

# ------------------------------------------------------------------------------
# 2. Deploy Helper Scripts
# ------------------------------------------------------------------------------
echo ">>> [2/5] Deploying helper scripts..."
mkdir -p "$TARGET_DIR/scripts"
for script in extract_skeleton.sh probe_line.sh reorder_queue.sh status.sh watch_worker.sh; do
  if [ -f "$SCRIPT_DIR/scripts/$script" ]; then
    cp -f "$SCRIPT_DIR/scripts/$script" "$TARGET_DIR/scripts/$script"
    chmod +x "$TARGET_DIR/scripts/$script"
    echo "  ✓ Deployed scripts/$script"
  fi
done

# ------------------------------------------------------------------------------
# 3. Deploy Skills Catalog (Pure Skills-Driven Architecture)
# ------------------------------------------------------------------------------
echo ">>> [3/5] Deploying skills catalog (Zero Context Pollution)..."
mkdir -p "$TARGET_DIR/.skills"
cp -f "$SCRIPT_DIR/.skills/universal-build-verify.md" "$TARGET_DIR/.skills/universal-build-verify.md"
echo "  ✓ Deployed .skills/universal-build-verify.md"

mkdir -p "$TARGET_DIR/.agents/skills"
if [ -f "$SCRIPT_DIR/.agents/skills.json" ]; then
  if [ ! -e "$TARGET_DIR/.agents/skills.json" ]; then
    cp "$SCRIPT_DIR/.agents/skills.json" "$TARGET_DIR/.agents/skills.json"
  else
    echo "  • Preserved existing .agents/skills.json"
  fi
fi

# Clean up legacy paths if updating from older layout
rm -rf "$TARGET_DIR/.agents/skills/architect" 2>/dev/null || true
rm -rf "$TARGET_DIR/.agents/skills/worker" 2>/dev/null || true
rm -rf "$TARGET_DIR/.agents/skills/planner" 2>/dev/null || true
rm -rf "$TARGET_DIR/.agents/skills/explore" 2>/dev/null || true
rm -rf "$TARGET_DIR/.agents/skills/productivity/configure-unattended-worker" 2>/dev/null || true
rm -rf "$TARGET_DIR/.agents/skills/engineering/setup-unattended-workflow" 2>/dev/null || true
for legacy_ns in watch-worker-queue score-worker-performance handle-worker-guidance manage-worker-notes record-attempt-trace configure-unattended-worker setup-unattended-workflow; do
  rm -rf "$TARGET_DIR/.agents/skills/nightshift/$legacy_ns" 2>/dev/null || true
done

# Deploy skill categories
for category in nightshift engineering productivity misc in-progress; do
  if [ -d "$SCRIPT_DIR/.agents/skills/$category" ]; then
    mkdir -p "$TARGET_DIR/.agents/skills/$category"
    cp -R "$SCRIPT_DIR/.agents/skills/$category/." "$TARGET_DIR/.agents/skills/$category/"
    echo "  ✓ Deployed .agents/skills/$category/"
  fi
done

# Remove retired Planner sidecar after its guidance has moved into the skill.
rm -f "$TARGET_DIR/.agents/skills/nightshift/planner/OPERATIONS.md"

# ------------------------------------------------------------------------------
# 4. Initialize State Files (Non-Destructive)
# ------------------------------------------------------------------------------
echo ">>> [4/5] Initializing runtime tracking files..."

# tasks.txt
if [ ! -f "$TARGET_DIR/tasks.txt" ]; then
  cat <<'EOF' > "$TARGET_DIR/tasks.txt"
# Task Queue (FIFO) - Format: TASK-XXX | LEVEL: 1-3 | [AFTER: <id>] | TARGET: <paths> | ACTION: <logic> | VERIFY: <test_cmd> | FORBIDDEN_SHORTCUTS: <hacks> | CONSTRAINTS: <limits>
EOF
  echo "  ✓ Initialized tasks.txt with schema header"
else
  echo "  • Preserved existing tasks.txt"
fi

# tasks.done
if [ ! -f "$TARGET_DIR/tasks.done" ]; then
  touch "$TARGET_DIR/tasks.done"
  echo "  ✓ Initialized tasks.done"
else
  echo "  • Preserved existing tasks.done"
fi

# progress.log
if [ ! -f "$TARGET_DIR/progress.log" ]; then
  touch "$TARGET_DIR/progress.log"
  echo "  ✓ Initialized progress.log"
else
  echo "  • Preserved existing progress.log"
fi

# .worker.notes.md
if [ ! -f "$TARGET_DIR/.worker.notes.md" ]; then
  cat <<'EOF' > "$TARGET_DIR/.worker.notes.md"
# Worker Repository Notes & Compiler Quirks
# Shared across stateless worker runs. Updated by background worker per .skills/universal-build-verify.md.
EOF
  echo "  ✓ Initialized .worker.notes.md"
else
  echo "  • Preserved existing .worker.notes.md"
fi

# docs/agents metadata
mkdir -p "$TARGET_DIR/docs/agents"
if [ ! -f "$TARGET_DIR/docs/agents/granularity-profile.json" ]; then
  cat <<'EOF' > "$TARGET_DIR/docs/agents/granularity-profile.json"
{
  "modules": {}
}
EOF
  echo "  ✓ Initialized docs/agents/granularity-profile.json"
else
  echo "  • Preserved existing docs/agents/granularity-profile.json"
fi

# ------------------------------------------------------------------------------
# 5. Non-Destructive .gitignore Protection (Zero Duplication)
# ------------------------------------------------------------------------------
echo ">>> [5/5] Ensuring .gitignore protection..."
GITIGNORE_FILE="$TARGET_DIR/.gitignore"
touch "$GITIGNORE_FILE"

REQUIRED_IGNORES=(
  ".worker.env"
  "worker*.status"
  ".worker*.log"
  ".worker*.pid"
  ".worker-agent-state*.json"
  ".worker-score*.json"
  ".worker-score*.json.lock/"
  ".worker-agent-scores/"
  ".worker-agent-events.jsonl"
  ".worker-agent-events.jsonl.lock/"
  ".worker-agent-events*.json*"
  ".worker-dispatch-gate.json"
  ".worker-dispatch-gate.json.lock/"
  "PAUSE"
  ".scratch/"
  ".reports"
  "tasks.txt.lock/"
  ".worker-tree/"
  ".preview/"
  ".trials/"
  "tasks.done"
  "tasks.done.*"
)

HEADER="# NightShift 24h Unattended Worker Artifacts"

# Ensure existing .gitignore ends with a newline if non-empty
if [ -s "$GITIGNORE_FILE" ]; then
  LAST_CHAR=$(tail -c 1 "$GITIGNORE_FILE" 2>/dev/null || true)
  if [ -n "$LAST_CHAR" ] && [ "$LAST_CHAR" != $'\n' ]; then
    echo "" >> "$GITIGNORE_FILE"
  fi
fi

# Find which required entries are actually missing
MISSING_ENTRIES=()
for entry in "${REQUIRED_IGNORES[@]}"; do
  if ! grep -qxF "$entry" "$GITIGNORE_FILE" 2>/dev/null; then
    MISSING_ENTRIES+=("$entry")
  fi
done

if [ ${#MISSING_ENTRIES[@]} -gt 0 ]; then
  # Only add header if it is not already in .gitignore
  if ! grep -qxF "$HEADER" "$GITIGNORE_FILE" 2>/dev/null; then
    if [ -s "$GITIGNORE_FILE" ]; then
      echo "" >> "$GITIGNORE_FILE"
    fi
    echo "$HEADER" >> "$GITIGNORE_FILE"
  fi

  for entry in "${MISSING_ENTRIES[@]}"; do
    echo "$entry" >> "$GITIGNORE_FILE"
  done
  echo "  ✓ Appended ${#MISSING_ENTRIES[@]} missing worker artifact entries to .gitignore (no duplicates)"
else
  echo "  • .gitignore is already up to date (no changes needed)"
fi

# ------------------------------------------------------------------------------
# Verification & Self-Test
# ------------------------------------------------------------------------------
echo ""
echo ">>> Verifying syntax of deployed scripts in target..."
bash -n "$TARGET_DIR/worker.sh" "$TARGET_DIR"/scripts/*.sh
"${PYTHON_BIN:-python3}" -c 'import ast, pathlib, sys; ast.parse(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))' "$TARGET_DIR/scripts/worker_runtime.py"
echo "  ✓ Bash and Python worker files pass syntax validation (Exit 0)"

echo ""
echo "=============================================================================="
if [ "$IS_UPDATE" -eq 1 ]; then
  echo "  Update Complete! (All scripts & skills updated; configs & state preserved)"
else
  echo "  Installation Complete! (Pure Skills-Driven Architecture)"
fi
echo "=============================================================================="
echo "Quick Start in target repository:"
echo "  1. Terminal A (Planner) : Use /planner or natural language to decompose tasks"
echo "  2. Terminal B (Worker)  : Run './worker.sh' to start autonomous background loop"
echo "  3. Live Status          : Run './scripts/status.sh' to inspect live progress"
echo "=============================================================================="
