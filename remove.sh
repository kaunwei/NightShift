#!/usr/bin/env bash
# Remove NightShift-owned runtime, state, and legacy install files from a project.
set -euo pipefail
SCRIPT_DIR="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
if [ -d "$SCRIPT_DIR/nightshift" ]; then
  SOURCE_ROOT="$SCRIPT_DIR"
else
  SOURCE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd -P)"
fi
if [ "$#" -ne 1 ] || [ -z "${1:-}" ]; then
  echo "Usage: $0 <target_repository_path>" >&2
  exit 2
fi
if ! TARGET_DIR="$(cd -P -- "$1" 2>/dev/null && pwd -P)"; then
  echo "Error: target directory does not exist: $1" >&2
  exit 2
fi
if [ "$TARGET_DIR" = "$SOURCE_ROOT" ]; then
  echo "Refusing to remove the NightShift source repository." >&2
  exit 2
fi
if [ ! -d "$TARGET_DIR/nightshift" ] && [ ! -f "$TARGET_DIR/worker.sh" ] \
  && [ ! -d "$TARGET_DIR/.agents/skills/nightshift" ]; then
  echo "No NightShift installation markers found in $TARGET_DIR" >&2
  exit 1
fi

# Keep the consumer-owned index scope while removing the installed tool and state.
SCOPE_CONFIG=""
if [ -f "$TARGET_DIR/nightshift/code-index.toml" ]; then
  SCOPE_CONFIG="$(mktemp "${TMPDIR:-/tmp}/nightshift-code-index.XXXXXX")"
  cp "$TARGET_DIR/nightshift/code-index.toml" "$SCOPE_CONFIG"
elif [ -f "$TARGET_DIR/.nightshift/code-index.toml" ]; then
  SCOPE_CONFIG="$(mktemp "${TMPDIR:-/tmp}/nightshift-code-index.XXXXXX")"
  cp "$TARGET_DIR/.nightshift/code-index.toml" "$SCOPE_CONFIG"
fi

rm -rf "$TARGET_DIR/nightshift"
if [ -n "$SCOPE_CONFIG" ]; then
  mkdir -p "$TARGET_DIR/nightshift"
  cp "$SCOPE_CONFIG" "$TARGET_DIR/nightshift/code-index.toml"
  rm -f "$SCOPE_CONFIG"
fi
# Remove legacy code locations owned by earlier NightShift installs.
rm -f "$TARGET_DIR/worker.sh" "$TARGET_DIR/update.sh" "$TARGET_DIR/.worker.env.example" \
  "$TARGET_DIR/tasks.txt" "$TARGET_DIR/tasks.done" "$TARGET_DIR/progress.log" \
  "$TARGET_DIR/worker.status" "$TARGET_DIR/.worker.log" "$TARGET_DIR/.worker.pid" \
  "$TARGET_DIR/.worker.notes.md" "$TARGET_DIR/.worker-score.json" "$TARGET_DIR/.worker-dispatch-gate.json" \
  "$TARGET_DIR/.worker-agent-events.jsonl" "$TARGET_DIR/.worker-agent-events.cursor.json" \
  "$TARGET_DIR/.worker-agent-events.acks.jsonl" "$TARGET_DIR/.worker-agent-state.default.json" \
  "$TARGET_DIR/.worker-ghost-state.default.json" "$TARGET_DIR/PAUSE" \
  "$TARGET_DIR/tasks.txt.lock" "$TARGET_DIR/.worker-score.json.lock" \
  "$TARGET_DIR/.worker-dispatch-gate.json.lock" "$TARGET_DIR/.worker-agent-events.jsonl.lock"
rm -f "$TARGET_DIR"/worker.*.status "$TARGET_DIR"/.worker.*.log "$TARGET_DIR"/.worker.*.pid \
  "$TARGET_DIR"/.worker-agent-state.*.json "$TARGET_DIR"/.worker-ghost-state.*.json
rm -rf "$TARGET_DIR/.worker-agent-scores" "$TARGET_DIR/.worker-ghosts"
# Legacy Worker snapshots were written to the root-level scratch directory.
rm -rf "$TARGET_DIR/.scratch"
rm -f "$TARGET_DIR/.worker.env.example" \
  "$TARGET_DIR/scripts/worker_runtime.py" "$TARGET_DIR/scripts/adapters/agents.json" \
  "$TARGET_DIR/scripts/adapters/agy.py" "$TARGET_DIR/scripts/adapters/codex.py" \
  "$TARGET_DIR/scripts/adapters/generic.py" "$TARGET_DIR/scripts/extract_skeleton.sh" \
  "$TARGET_DIR/scripts/probe_line.sh" "$TARGET_DIR/scripts/reorder_queue.sh" \
  "$TARGET_DIR/scripts/status.sh" "$TARGET_DIR/scripts/watch_worker.sh"
rm -rf "$TARGET_DIR/tools/nightshift-code-index" "$TARGET_DIR/test/nightshift_worker"
rmdir "$TARGET_DIR/scripts/adapters" 2>/dev/null || true
# Retain all unrelated skills/docs/scripts in the consuming project.
rm -rf "$TARGET_DIR/.agents/skills/nightshift"
rm -f "$TARGET_DIR/.skills/universal-build-verify.md"
for doc in PORTING_GUIDE.md DETERMINISTIC_EXPLORE_STRATEGY.md DETERMINISTIC_EXPLORE_RESULTS.md NIGHTSHIFT_SPEC.md NIGHTSHIFT_SOURCE_COVERAGE.md LOCAL_TDD.md; do
  if [ -f "$TARGET_DIR/docs/$doc" ] && [ -f "$SOURCE_ROOT/nightshift/docs/$doc" ] \
    && cmp -s "$TARGET_DIR/docs/$doc" "$SOURCE_ROOT/nightshift/docs/$doc"; then
    rm -f "$TARGET_DIR/docs/$doc"
  fi
done
if [ -f "$TARGET_DIR/docs/PORTING_GUIDE.md" ] \
  && grep -q '^# Install NightShift in another repository' "$TARGET_DIR/docs/PORTING_GUIDE.md"; then
  rm -f "$TARGET_DIR/docs/PORTING_GUIDE.md"
fi
rmdir "$TARGET_DIR/.agents/skills" "$TARGET_DIR/.skills" "$TARGET_DIR/.agents" 2>/dev/null || true
rmdir "$TARGET_DIR/.nightshift" 2>/dev/null || true
printf 'Removed NightShift-owned files from %s; retained project code, docs, skills, and the code-index scope config.\n' "$TARGET_DIR"
