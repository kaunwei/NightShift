# NightShift External Project Architecture Guide

External architecture isolates NightShift runtime state, task queues, and AST indices from the target repository. Target repositories retain zero NightShift footprint.

## 1. Directory Structure

- Core: NightShift engine, adapters, and agent skills.
- Runner Workspace: Project state directory under `projects/<project_name>/`.
- Target Project: Clean git worktree containing only product source and tests.

```text
runner-workspace/
  projects/
    <project_name>/
      config.json          # Project configuration (path, state, acceptance, agents)
      env.sh               # Environment activation script
      tasks.txt            # Worker FIFO queue
      tasks.done           # Completed task log
      progress.log         # Audit and progress history
      worker.status        # Real-time daemon status
      spec/                # Temporary specifications and design drafts
      todo/                # Tickets, plans, and unassigned work
      handoff/             # Agent handoffs and session summaries
      notes/               # Investigation notes and temporary reports
      .scratch/            # Disposable development artifacts
      code-index/          # AST navigation index (INDEX.md, index.json)
      reports/             # Failure diagnostic reports
```

## 2. Configuration: config.json

Place `config.json` in `projects/<project_name>/config.json`:

```json
{
  "version": 1,
  "projects": {
    "<project_name>": {
      "path": "/absolute/path/to/target/project",
      "state": "."
    }
  },
  "acceptance": {
    "hot": "pytest -q tests/test_fast.py",
    "cold": "pytest",
    "hot_timeout": 300,
    "cold_timeout": 1800,
    "cold_every": 5
  },
  "agents": {
    "primary": {
      "default": true,
      "worker": {
        "task_timeout_seconds": 1800,
        "step_base": {"L1": 22, "L2": 22, "L3": 22}
      },
      "agent": {
        "adapter": "codex",
        "command": "codex"
      }
    }
  }
}
```

## 3. Environment Anchor: env.sh

`env.sh` anchors agent and terminal sessions to the project runner state.
Always source it: `source projects/<project_name>/env.sh`.

Template for `projects/<project_name>/env.sh`:

```bash
# NightShift Project Environment Activator (Bash / Zsh)
# Usage: source env.sh

if [ -n "${ZSH_VERSION:-}" ]; then
  _ENV_DIR="$(cd "$(dirname "${(%):-%N}")" && pwd)"
elif [ -n "${BASH_SOURCE[0]:-}" ]; then
  _ENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
else
  _ENV_DIR="$(pwd)"
fi

export NIGHTSHIFT_CORE="${NIGHTSHIFT_CORE:-/Volumes/Vault500G/workspace/NightShift}"
export NIGHTSHIFT_CONFIG_FILE="$_ENV_DIR/config.json"
export NIGHTSHIFT_STATE_DIR="$_ENV_DIR"

# Temporary development documents belong to this runner, not the product tree.
export NIGHTSHIFT_SPEC_DIR="$NIGHTSHIFT_STATE_DIR/spec"
export NIGHTSHIFT_TODO_DIR="$NIGHTSHIFT_STATE_DIR/todo"
export NIGHTSHIFT_HANDOFF_DIR="$NIGHTSHIFT_STATE_DIR/handoff"
export NIGHTSHIFT_NOTES_DIR="$NIGHTSHIFT_STATE_DIR/notes"
export NIGHTSHIFT_SCRATCH_DIR="$NIGHTSHIFT_STATE_DIR/.scratch"
mkdir -p "$NIGHTSHIFT_SPEC_DIR" "$NIGHTSHIFT_TODO_DIR" "$NIGHTSHIFT_HANDOFF_DIR" \
  "$NIGHTSHIFT_NOTES_DIR" "$NIGHTSHIFT_SCRATCH_DIR" || return 1
export TASKS_FILE="$_ENV_DIR/tasks.txt"
export TASKS_DONE_FILE="$_ENV_DIR/tasks.done"
export PROGRESS_FILE="$_ENV_DIR/progress.log"
export STATUS_FILE="$_ENV_DIR/worker.status"

ns-worker() { bash "$NIGHTSHIFT_CORE/scripts/worker.sh" --config "$NIGHTSHIFT_CONFIG_FILE" "$@"; }
ns-status() { bash "$NIGHTSHIFT_CORE/scripts/status.sh" --config "$NIGHTSHIFT_CONFIG_FILE" "$@"; }
ns-queue()  { cat "$TASKS_FILE"; }

echo "NightShift environment loaded: $(basename "$_ENV_DIR")"
echo "  Target: $(grep -o '"path":[[:space:]]*"[^"]*"' "$NIGHTSHIFT_CONFIG_FILE" | cut -d'"' -f4)"
echo "  State:  $_ENV_DIR"
```

## 4. Operational Rules for Agents

1. Zero Footprint:
   Never write runtime logs, status, or task queues into the target repository.
2. Temporary Specs and Tickets:
   Use the exported absolute paths for development documents:
   - `$NIGHTSHIFT_SPEC_DIR`: temporary specifications and design drafts.
   - `$NIGHTSHIFT_TODO_DIR`: tickets, execution plans, and unassigned work.
   - `$NIGHTSHIFT_HANDOFF_DIR`: handoffs, session summaries, and continuation instructions.
   - `$NIGHTSHIFT_NOTES_DIR`: research notes, diagnostic writeups, and temporary reports.
   - `$NIGHTSHIFT_SCRATCH_DIR`: disposable artifacts and experiments.

   These directories are created when `env.sh` is sourced. Paths are derived from
   the selected runner every time; switching projects must not reuse another
   runner's document paths. Skills do not need editing: agents should use these
   environment paths when choosing output destinations, and tickets should cite
   absolute runner document paths rather than project-relative `todo/` or `spec/`.
   Environment variables provide destinations; they do not redirect arbitrary
   relative filesystem writes automatically.

   Keep permanent product requirements, ADRs, user guides, source, and tests in
   the target repository when they are intended for version control. Do not put
   secrets in temporary documents. Existing files and queued references are not
   migrated by sourcing the environment; migrate them explicitly at a safe boundary.
   Already-running agents retain their inherited environment until restarted.

   If the activator provides `deactivate-ns`, unset `NIGHTSHIFT_SPEC_DIR`,
   `NIGHTSHIFT_TODO_DIR`, `NIGHTSHIFT_HANDOFF_DIR`, `NIGHTSHIFT_NOTES_DIR`, and
   `NIGHTSHIFT_SCRATCH_DIR` there as well.
3. Queue Format:
   Enqueued tasks in `tasks.txt` must follow:
   `TASK-ID | LEVEL: 1-3 | TARGET: <paths> | ACTION: <instruction> | VERIFY: <test_command>`
4. Execution:
   Run `ns-worker` (persistent daemon) or `RUN_ONCE=1 ns-worker` (single task run).


## Optional acceptance hooks

Keep artifact and project-specific logic in the project. NightShift runs
configured `acceptance.hooks` every N accepted tickets, or a live-session
`hook-register` one-shot after an exact ticket ID. Relaunching the worker resets
hook registrations, counters and pending runs. See
[scheduler configuration and recovery](scripts/acceptance.md#post-acceptance-hooks).
