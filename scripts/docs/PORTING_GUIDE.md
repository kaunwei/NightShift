# NightShift External Project Architecture Guide

External architecture isolates NightShift runtime state, task queues, and AST indices from the target repository. Target repositories retain zero NightShift runtime footprint; project-owned automation stays with product source.

## 1. Directory Structure

- Core: NightShift engine, adapters, and agent skills.
- Runner Workspace: One directory per project, containing its activator, configuration and temporary state. `projects/<project_name>/` is an example grouping; `<runner>/<project_name>/` is equally valid.
- Target Project: Product Git worktree containing source, tests, permanent documentation and project-owned automation.

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

### Ownership and project selection

Treat the selected project's runner as a directory. For example,
`NightShift_runner/slugbox/` contains `env.sh`, `config.json` and that project's
state. Preserve the user's chosen directory layout; the optional `projects/`
grouping above does not require another nesting level.

| Content | Maintained location |
| --- | --- |
| Shared engine, adapters and skills | NightShift core |
| Per-project `env.sh` activator and `config.json` | Selected project's runner directory |
| Queues, status, logs, temporary specs, tickets, handoffs, notes and indices | Same project's runner directory |
| Hot/cold test runners, framework evidence adapters, release/demo/build/serve scripts and export presets | Target project, using its existing script/configuration conventions |
| Generated regression reports, build/demo artifacts, import caches and local TLS keys | Selected project's runner directory, in appropriate temporary subdirectories |

Project selection means sourcing that directory's activator in the current
terminal:

```bash
cd /absolute/path/to/NightShift_runner/slugbox
source env.sh
ns-status
```

The runner's "launcher" is this `env.sh` activator. Keep `config.json` beside it
with `state: "."`. An instruction to keep launchers and temporary files in the
runner retains this per-project directory and its configuration. It does not ask
for an executable file named `slugbox`, a project-selection CLI or a new subshell.
Create such interfaces only when explicitly requested.

The runner needs no Git repository or Git protection. Keep project-specific
script implementations under the product's version control; the external config
invokes them from the product root. Temporary outputs go to the selected runner.
NightShift's product commit/scope audits still apply to the target worktree.

### Migration checks

Before moving files, read this guide completely and identify the core, product
and chosen per-project runner paths. Classify each moved file using the table.
Keep existing queues, references and generated artifacts intact during migration.

Before declaring the port complete, verify all of the following:

- Sourcing `env.sh` selects the intended product and exports absolute config,
  state and temporary-document paths in the current terminal.
- `env.sh` and `config.json` remain together in that project's runner directory;
  `state: "."` resolves there. Switching projects replaces every exported path.
- Hot/cold and artifact hooks invoke product-maintained scripts; their generated
  outputs stay in the selected runner.
- With an empty queue, `RUN_ONCE=1 ns-worker` exits cleanly and `ns-status` reads
  the same project's state. Existing work is not dispatched just to test setup.

## 2. Configuration: config.json

Place `config.json` beside the selected runner's `env.sh` (for example,
`projects/<project_name>/config.json` or `slugbox/config.json`):

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
Always source the selected project's file, for example
`source projects/<project_name>/env.sh` or `source slugbox/env.sh`.

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
