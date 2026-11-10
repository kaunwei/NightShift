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
      env.sh               # Source: prompt, cd, helper commands and deactivation
      run_worker.sh        # Standalone worker launcher (core template)
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

- Sourcing `env.sh` changes to the intended product and exports absolute config,
  state and temporary-document paths in the current terminal; an interactive
  prompt shows `(ns:<project_name>)`, and `ns-help` / `ns-run` are available.
- Re-sourcing keeps one indicator. `deactivate-ns` restores the previous prompt
  and directory and clears the selected project's exported paths.
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

Activation changes the current directory to the target product and shows
`(ns:<project_name>)` in an interactive Bash/Zsh prompt. Re-sourcing replaces the
context without stacking prompt prefixes. `ns-help` lists available commands;
`ns-run` aliases `ns-worker`. `deactivate-ns` restores the prior prompt/directory
and clears the selected project's state and temporary-document exports.

For standalone execution, copy
[`scripts/templates/run_worker.sh`](scripts/templates/run_worker.sh) beside
`env.sh` and `config.json`, make it executable and run `./run_worker.sh`. It loads
the same activator. `RUN_ONCE=1 ./run_worker.sh` honors single-run mode.

Set the template's core path to the local NightShift checkout (or export
`NIGHTSHIFT_CORE` before sourcing it). Use `source env.sh` in Bash/Zsh; executing
`bash env.sh` only changes the child process and cannot activate the parent shell.
Custom prompt managers must retain the `(ns:<project_name>)` prefix when rebuilding
the prompt. Project-specific helpers such as `ns-hot`, `ns-cold` and `ns-demo` can
call scripts in the target repository.

| Command | Behavior |
| --- | --- |
| `ns-run` / `ns-worker` | Start the selected runner's `run_worker.sh` |
| `ns-help` | List available helpers after activation |
| `ns-status` / `ns-queue` | Inspect the selected project's status / queue |
| `ns-watch [--help]` | Watch task completion or worker events |
| `ns-pause` / `ns-resume` | Set / clear the manual pause file; failure recovery remains separate |
| `deactivate-ns` | Restore the prior prompt and directory; clear project context |

The standalone wrapper retries worker exits in persistent mode. `RUN_ONCE=1`
executes one worker invocation and preserves its exit code without retrying.

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

# Re-activation replaces the old context and keeps one prompt indicator.
_NS_ACTIVATION_DIR="$_ENV_DIR"
_NS_ACTIVATION_CORE="${NIGHTSHIFT_CORE:-}"
if [ "${_NS_ENV_ACTIVE:-0}" = 1 ]; then deactivate-ns; fi
_ENV_DIR="$_NS_ACTIVATION_DIR"
NIGHTSHIFT_CORE="$_NS_ACTIVATION_CORE"
unset _NS_ACTIVATION_DIR _NS_ACTIVATION_CORE
_NS_SAVED_PWD="$PWD"
_NS_SAVED_PS1_SET="${PS1+x}"
_NS_SAVED_PS1="${PS1-}"
_NS_SAVED_GODOT_SET="${GODOT_BIN+x}"
_NS_SAVED_GODOT="${GODOT_BIN-}"
_NS_SAVED_BYTECODE_SET="${PYTHONDONTWRITEBYTECODE+x}"
_NS_SAVED_BYTECODE="${PYTHONDONTWRITEBYTECODE-}"
_NS_SAVED_ROOT_SET="${PROJECT_ROOT+x}"
_NS_SAVED_ROOT="${PROJECT_ROOT-}"

export NIGHTSHIFT_CORE="${NIGHTSHIFT_CORE:-/absolute/path/to/NightShift}"
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
touch "$TASKS_FILE" "$TASKS_DONE_FILE" "$PROGRESS_FILE" || return 1

# Resolve the target and state using the same reader as the worker.
_NS_PROJECT_CONTEXT="$(python3 "$NIGHTSHIFT_CORE/scripts/project_config.py" \
  --config "$NIGHTSHIFT_CONFIG_FILE" --root "$PWD")" || return 1
eval "$_NS_PROJECT_CONTEXT"
unset _NS_PROJECT_CONTEXT
export PAUSE_FILE="$NIGHTSHIFT_STATE_DIR/PAUSE"
ns-worker() { bash "$NIGHTSHIFT_STATE_DIR/run_worker.sh" "$@"; }
ns-run() { ns-worker "$@"; }
ns-status() { bash "$NIGHTSHIFT_CORE/scripts/status.sh" --config "$NIGHTSHIFT_CONFIG_FILE" "$@"; }
ns-watch() { bash "$NIGHTSHIFT_CORE/scripts/watch_worker.sh" --config "$NIGHTSHIFT_CONFIG_FILE" "$@"; }
ns-queue() { cat "$TASKS_FILE"; }
ns-pause() { touch "$PAUSE_FILE"; }
ns-resume() { command rm -f -- "$PAUSE_FILE"; }
ns-help() {
  printf '%s\n' \
    'ns-run / ns-worker     Start the selected project worker' \
    'ns-status              Show worker and queue status' \
    'ns-watch [--help]      Watch worker completion/events' \
    'ns-queue               Show the task queue' \
    'ns-pause / ns-resume    Set/clear the manual pause flag' \
    'deactivate-ns          Restore the previous prompt and directory'
}
deactivate-ns() {
  if [ "${_NS_ENV_ACTIVE:-0}" != 1 ]; then return 0; fi
  if [ "$_NS_SAVED_PS1_SET" = x ]; then PS1="$_NS_SAVED_PS1"; else unset PS1; fi
  if [ "$_NS_SAVED_GODOT_SET" = x ]; then export GODOT_BIN="$_NS_SAVED_GODOT"; else unset GODOT_BIN; fi
  if [ "$_NS_SAVED_BYTECODE_SET" = x ]; then export PYTHONDONTWRITEBYTECODE="$_NS_SAVED_BYTECODE"; else unset PYTHONDONTWRITEBYTECODE; fi
  if [ "$_NS_SAVED_ROOT_SET" = x ]; then export PROJECT_ROOT="$_NS_SAVED_ROOT"; else unset PROJECT_ROOT; fi
  if [ -d "$_NS_SAVED_PWD" ]; then cd "$_NS_SAVED_PWD" || return 1; fi
  unset NIGHTSHIFT_CORE NIGHTSHIFT_CONFIG_FILE NIGHTSHIFT_STATE_DIR NIGHTSHIFT_PROJECT_ROOT NIGHTSHIFT_PROJECT_NAME
  unset NIGHTSHIFT_SPEC_DIR NIGHTSHIFT_TODO_DIR NIGHTSHIFT_HANDOFF_DIR NIGHTSHIFT_NOTES_DIR NIGHTSHIFT_SCRATCH_DIR
  unset TASKS_FILE TASKS_DONE_FILE PROGRESS_FILE STATUS_FILE PAUSE_FILE
  unset _NS_ENV_ACTIVE _NS_SAVED_PWD _NS_SAVED_PS1_SET _NS_SAVED_PS1
  unset _NS_SAVED_GODOT_SET _NS_SAVED_GODOT _NS_SAVED_BYTECODE_SET _NS_SAVED_BYTECODE
  unset _NS_SAVED_ROOT_SET _NS_SAVED_ROOT _ENV_DIR
  unset -f ns-worker ns-run ns-status ns-watch ns-queue ns-pause ns-resume ns-help ns-hot ns-cold ns-demo deactivate-ns
}
_NS_ENV_ACTIVE=1
case "$-" in
  *i*) PS1="(ns:$NIGHTSHIFT_PROJECT_NAME) ${PS1-}" ;;
esac
cd "$NIGHTSHIFT_PROJECT_ROOT" || return 1

printf 'NightShift activated: (ns:%s)\n  Target: %s\n  State:  %s\n' \
  "$NIGHTSHIFT_PROJECT_NAME" "$NIGHTSHIFT_PROJECT_ROOT" "$NIGHTSHIFT_STATE_DIR"
ns-help
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
