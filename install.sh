#!/usr/bin/env bash
# ==============================================================================
# NightShift Framework Installer & Porting Script
# Clean, non-destructive copy installer for Pure Skills-Driven Architecture.
# Usage: ./install.sh <target_repository_path>
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-}"

# Display banner
echo "=============================================================================="
echo "    NightShift: 24h Unattended Dual-Terminal AI Framework Installer"
echo "=============================================================================="

if [ -z "$TARGET_DIR" ]; then
  echo "Error: Target repository path is required."
  echo "Usage: $0 /path/to/target-project"
  exit 1
fi

TARGET_DIR="$(cd "$TARGET_DIR" 2>/dev/null && pwd || echo "$TARGET_DIR")"

if [ ! -d "$TARGET_DIR" ]; then
  echo "Error: Target directory does not exist: $TARGET_DIR"
  exit 1
fi

echo "Target Repository: $TARGET_DIR"
echo "Source Repository: $SCRIPT_DIR"
echo ""

# ------------------------------------------------------------------------------
# 1. Non-Destructive Copy of Core Assets
# ------------------------------------------------------------------------------
echo ">>> [1/5] Deploying core worker daemon & configuration..."
cp -f "$SCRIPT_DIR/worker.sh" "$TARGET_DIR/worker.sh"
chmod +x "$TARGET_DIR/worker.sh"

cp -f "$SCRIPT_DIR/.worker.env.example" "$TARGET_DIR/.worker.env.example"
if [ ! -f "$TARGET_DIR/.worker.env" ]; then
  cp "$SCRIPT_DIR/.worker.env.example" "$TARGET_DIR/.worker.env"
  echo "  ✓ Initialized .worker.env from example"
else
  echo "  • Preserved existing .worker.env (not overwritten)"
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
# Deploy top-level core skills: planner and explore
cp -R "$SCRIPT_DIR/.agents/skills/planner" "$TARGET_DIR/.agents/skills/"
echo "  ✓ Deployed .agents/skills/planner (Master Orchestrator)"
cp -R "$SCRIPT_DIR/.agents/skills/explore" "$TARGET_DIR/.agents/skills/"
echo "  ✓ Deployed .agents/skills/explore (Seam Explorer)"

# Deploy supporting skill categories if present
for category in architect worker engineering productivity misc; do
  if [ -d "$SCRIPT_DIR/.agents/skills/$category" ]; then
    mkdir -p "$TARGET_DIR/.agents/skills/$category"
    cp -R "$SCRIPT_DIR/.agents/skills/$category/"* "$TARGET_DIR/.agents/skills/$category/" 2>/dev/null || true
    echo "  ✓ Deployed .agents/skills/$category/"
  fi
done

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

# .worker.notes.md
if [ ! -f "$TARGET_DIR/.worker.notes.md" ]; then
  cat <<'EOF' > "$TARGET_DIR/.worker.notes.md"
# Worker Repository Notes & Compiler Quirks
# Shared across stateless worker runs. Updated by background worker via /manage-worker-notes.
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
fi

if [ -f "$SCRIPT_DIR/docs/agents/TRIAGE_LABELS.md" ]; then
  cp -f "$SCRIPT_DIR/docs/agents/TRIAGE_LABELS.md" "$TARGET_DIR/docs/agents/TRIAGE_LABELS.md"
  echo "  ✓ Copied docs/agents/TRIAGE_LABELS.md"
fi

# ------------------------------------------------------------------------------
# 5. Non-Destructive .gitignore Protection
# ------------------------------------------------------------------------------
echo ">>> [5/5] Ensuring .gitignore protection..."
GITIGNORE_FILE="$TARGET_DIR/.gitignore"
touch "$GITIGNORE_FILE"

REQUIRED_IGNORES=(
  ".worker.env"
  "worker*.status"
  ".worker*.log"
  ".worker*.pid"
  "PAUSE"
  ".worker-tree/"
  ".preview/"
  ".reports/"
  "tasks.txt.lock/"
  "tasks.done"
)

APPENDED_COUNT=0
for entry in "${REQUIRED_IGNORES[@]}"; do
  if ! grep -qxF "$entry" "$GITIGNORE_FILE" 2>/dev/null; then
    if [ $APPENDED_COUNT -eq 0 ]; then
      echo "" >> "$GITIGNORE_FILE"
      echo "# NightShift 24h Unattended Worker Artifacts" >> "$GITIGNORE_FILE"
    fi
    echo "$entry" >> "$GITIGNORE_FILE"
    APPENDED_COUNT=$(( APPENDED_COUNT + 1 ))
  fi
done

if [ $APPENDED_COUNT -gt 0 ]; then
  echo "  ✓ Appended $APPENDED_COUNT worker artifact entries to .gitignore"
else
  echo "  • .gitignore is already up to date"
fi

# ------------------------------------------------------------------------------
# Verification & Self-Test
# ------------------------------------------------------------------------------
echo ""
echo ">>> Verifying syntax of deployed scripts in target..."
bash -n "$TARGET_DIR/worker.sh" "$TARGET_DIR"/scripts/*.sh
echo "  ✓ All bash scripts pass syntax validation (Exit 0)"

echo ""
echo "=============================================================================="
echo "  Installation Complete! (Pure Skills-Driven Architecture)"
echo "=============================================================================="
echo "Quick Start in target repository:"
echo "  1. Terminal A (Planner) : Use /planner or natural language to decompose tasks"
echo "  2. Terminal B (Worker)  : Run './worker.sh' to start autonomous background loop"
echo "  3. Live Status          : Run './scripts/status.sh' to inspect live progress"
echo "=============================================================================="
