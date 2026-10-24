#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SMOKE_ROOT="$ROOT/test/.install-add-task-smoke"

if [ "$SMOKE_ROOT" = "$ROOT" ] || [ -z "$ROOT" ]; then
  echo "Refusing unsafe smoke-test path: $SMOKE_ROOT" >&2
  exit 2
fi

rm -rf -- "$SMOKE_ROOT"
mkdir -p "$SMOKE_ROOT/src" "$SMOKE_ROOT/tests" "$SMOKE_ROOT/scripts"

cleanup() {
  rm -rf -- "$SMOKE_ROOT/.git"
}
trap cleanup EXIT

cat > "$SMOKE_ROOT/README.md" <<'EOF'
# Install and add-task smoke project

This disposable project checks the NightShift updater and queued Worker flow.
EOF

cat > "$SMOKE_ROOT/src/calc.py" <<'EOF'
def add(left, right):
    return left + right
EOF

cat > "$SMOKE_ROOT/tests/test_calc.py" <<'EOF'
from src.calc import add


def test_add():
    assert add(2, 3) == 5
EOF

printf 'smoke.log\n' > "$SMOKE_ROOT/.gitignore"

"$ROOT/update.sh" "$SMOKE_ROOT"

cat > "$SMOKE_ROOT/scripts/smoke-agent" <<'PY'
#!/usr/bin/env python3
"""Deterministic fake agent for the installed Worker smoke test."""
import json
import os
from pathlib import Path
import sys

task_id = os.environ["NIGHTSHIFT_TASK_ID"]
result_path = Path(os.environ["NIGHTSHIFT_RESULT_FILE"])
if task_id == "TASK-SMOKE-CODE":
    source = Path("src/calc.py")
    source.write_text(source.read_text(encoding="utf-8") +
                      "\n\ndef multiply(left, right):\n    return left * right\n",
                      encoding="utf-8")
    payload = {
        "outcome": "complete",
        "changed": True,
        "verification_evidence": "Added multiply and passed its declared check.",
        "commit_message": "feat: smoke-test code task",
    }
elif task_id == "TASK-SMOKE-EXPLORE":
    report = Path(".reports/smoke/SUMMARY.md")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "## Topology\n\n"
        "`src/calc.py#L1` exports the small arithmetic seam used by the smoke test.\n\n"
        "## Coupling bottlenecks\n\n"
        "The module has no runtime dependencies; its test imports the public function.\n\n"
        "## Expand–Migrate–Contract\n\n"
        "Expand with the new operation, migrate its caller, then contract only after use is verified.\n",
        encoding="utf-8",
    )
    payload = {
        "outcome": "complete",
        "changed": True,
        "verification_evidence": "Produced the declared Explore report with a source pointer.",
        "commit_message": "docs: smoke-test explore task",
    }
else:
    print(f"Unexpected smoke task: {task_id}", file=sys.stderr)
    raise SystemExit(2)

result_path.write_text(json.dumps(payload), encoding="utf-8")
PY
chmod +x "$SMOKE_ROOT/scripts/smoke-agent"

python3 - "$SMOKE_ROOT/scripts/adapters/agents.json" <<'PY'
import json
from pathlib import Path
import sys

Path(sys.argv[1]).write_text(json.dumps({"smoke": {
    "default": True,
    "worker": {"task_timeout_seconds": 120},
    "agent": {"adapter": "generic", "command": "./scripts/smoke-agent",
              "args": [], "env": {}, "config": {"model": "smoke"}},
}}, indent=2) + "\n", encoding="utf-8")
PY

git -C "$SMOKE_ROOT" init -q
git -C "$SMOKE_ROOT" config user.name "NightShift Smoke"
git -C "$SMOKE_ROOT" config user.email "nightshift-smoke@example.invalid"
git -C "$SMOKE_ROOT" add -A
git -C "$SMOKE_ROOT" commit -qm "test: initialize disposable smoke project"

EXPLORE_TASK="TASK-SMOKE-EXPLORE | LEVEL: 1 | TARGET: .reports/smoke/SUMMARY.md | ACTION: [RESEARCH] Explore the calc module seam and write a concise report | VERIFY: REPORT_ONLY | FORBIDDEN_SHORTCUTS: none | CONSTRAINTS: read-only product scope"
CODE_TASK="TASK-SMOKE-CODE | LEVEL: 1 | TARGET: src/calc.py | ACTION: [CODE: FIX] Add a multiply function | VERIFY: python3 -c 'from src.calc import multiply; assert multiply(6, 7) == 42; print(\"1 test passed\")' | FORBIDDEN_SHORTCUTS: none | CONSTRAINTS: keep the change in src/calc.py"

python3 "$SMOKE_ROOT/scripts/worker_runtime.py" queue-insert \
  --tasks "$SMOKE_ROOT/tasks.txt" --task "$EXPLORE_TASK"
python3 "$SMOKE_ROOT/scripts/worker_runtime.py" queue-insert \
  --tasks "$SMOKE_ROOT/tasks.txt" --task "$CODE_TASK"

RUN_ONCE=1 POLL_INTERVAL=0.05 TASK_TIMEOUT=120 \
  bash "$SMOKE_ROOT/worker.sh" | tee "$SMOKE_ROOT/smoke.log"

grep -q '\[DONE\].*TASK-SMOKE-CODE' "$SMOKE_ROOT/tasks.done"
grep -q '\[DONE\].*TASK-SMOKE-EXPLORE' "$SMOKE_ROOT/tasks.done"
grep -q 'Status: PASS | Task: TASK-SMOKE-CODE' "$SMOKE_ROOT/progress.log"
grep -q 'Status: PASS | Task: TASK-SMOKE-EXPLORE' "$SMOKE_ROOT/progress.log"
grep -q 'REPORT_META: Task=TASK-SMOKE-EXPLORE' \
  "$SMOKE_ROOT/.reports/smoke/SUMMARY.md"
grep -q 'src/calc.py#L1' "$SMOKE_ROOT/.reports/smoke/SUMMARY.md"
grep -q '^feat: smoke-test code task$' <(git -C "$SMOKE_ROOT" log -1 --format=%s)

if [ "$(python3 -c "import json; print(json.load(open('$SMOKE_ROOT/worker.status'))['state'])")" != "STOPPED" ]; then
  echo "Worker did not stop cleanly; see $SMOKE_ROOT/smoke.log" >&2
  exit 1
fi
if [ -e "$SMOKE_ROOT/.worker.pid" ]; then
  echo "Worker PID file was not cleaned up" >&2
  exit 1
fi

echo "PASS: update, queue insertion, code task, Explore task, audits, and code commit verified."
echo "The disposable project stays under $SMOKE_ROOT; its temporary .git directory will be removed."
