# NightShift External Project Architecture Guide

Set up one shared core and one runner per product Git repository. Keep engine
files, queues and generated state outside the product. Product-owned automation,
source, permanent tests and documentation remain version controlled in the product.

The former embedded installer/updater is retired. This guide is the canonical
porting reference; the root PORTING_GUIDE.md points here.

## Layout and ownership

```text
NightShift-core/
  scripts/                   # Engine, adapters, parser and runtime references
  .agents/skills/            # Shared role/engineering skills
  .skills/                   # Worker execution contract
runner-workspace/
  my-app/
    config.json              # Product path, state, acceptance and agents
    env.sh                   # Source in the current terminal
    run_worker.sh            # Copy of the core launcher template
    tasks.txt                # FIFO
    tasks.done               # Outcome history
    progress.log             # Audit history
    worker.status            # Worker status
    .worker-agent-scores/     # Persistent per-registration capability history
    spec/ todo/ handoff/ notes/
    .scratch/                # Attempt retention and disposable artifacts
    code-index/              # AST navigation files
    lifecycle/
      preflight.json         # Readiness evidence
      reports/               # Task failure reports
      verify/                # Live command logs and metadata
      background-hooks/      # Hook reports, manifests and retained failures
product-repository/
  source, tests, docs, project-owned scripts
```

Generated directories appear when needed. Preserve the user's chosen runner
layout: `runner/my-app/` and `runner/projects/my-app/` are both valid. The runner
needs no Git repository. `state: "."` resolves relative to its config.json.

| Material | Destination |
| --- | --- |
| Engine, adapter implementations and shared skills | Core |
| Config, activator, standalone wrapper and all runtime state | Selected runner |
| Temporary specs, tickets, handoffs and notes | Runner exports listed below |
| Framework evidence runners, build/release/demo scripts and export presets | Product's existing script conventions |
| Generated reports, build/demo outputs, caches and local credentials | Appropriate runner subdirectories |
| Permanent requirements, ADRs, user docs, source and tests | Product Git history |

## Prepare the core and runner

Prerequisites are Python 3, Bash and Git, plus the chosen model CLI. Process and
hook supervision currently use POSIX facilities. Prepare the parser in the core:

```bash
export NIGHTSHIFT_CORE=/absolute/path/to/NightShift
bash "$NIGHTSHIFT_CORE/scripts/tools/setup.sh"
```

Setup verifies actual C, C++ and Python parsing. Product compilers, engines,
framework discovery and build dependencies are project-owned prerequisites.

Create the runner and copy the existing standalone wrapper:

```bash
mkdir -p /absolute/path/to/runner/my-app
cp "$NIGHTSHIFT_CORE/scripts/templates/run_worker.sh" /absolute/path/to/runner/my-app/run_worker.sh
chmod +x /absolute/path/to/runner/my-app/run_worker.sh
```

Place config.json and env.sh beside it. The wrapper discovers the core using
NIGHTSHIFT_CORE and sources the same activator. Set the core default in env.sh or
export NIGHTSHIFT_CORE before activation; it must point to the local checkout.
For migration, stop owned execution at a safe boundary and preserve queues,
references, old reports and user-owned `.worker-tree`/`.preview` data explicitly.
Sourcing an activator does not move existing files or rewrite queued paths.

## Project configuration

Example runner config.json for a Python unittest project:

```json
{
  "version": 1,
  "projects": {
    "my-app": {"path": "/absolute/path/to/product", "state": "."}
  },
  "acceptance": {
    "version": 1,
    "hot": "python3 '/absolute/path/to/NightShift/scripts/unittest_hot.py' --start tests",
    "cold": "python3 -m unittest discover -s tests",
    "hot_timeout": 300,
    "cold_timeout": 1800,
    "cold_every": 5
  },
  "agents": {
    "primary": {
      "default": true,
      "worker": {
        "task_timeout_seconds": 1800,
        "research_step_budget": 100,
        "step_base": {"L1": 60, "L2": 40, "L3": 20},
        "preparation_steps": 40
      },
      "agent": {"adapter": "codex", "command": "codex"}
    }
  }
}
```

Replace both absolute paths and select the intended adapter/model in the agent
profile. The supplied hot command implements persistent discovery/execution
receipts. A bare pytest/unittest command can be cold or ticket VERIFY; using it
as hot requires a [framework evidence adapter](../acceptance.md#framework-adapter-protocol).
Validate permanent discovery and actual execution before dispatching code work.

Commands run from the product root. Acceptance budgets are separate from Worker
execution timeouts. Code actions use max(level base, preparation floor) plus the
planned file estimate times per-file steps. With the example and default five
steps per file, one-file L1/L2/L3 budgets are 65/45/45. Research has its own budget.
An optional registration preflight probe checks the effective sandbox/tooling
before claim; see [readiness](RUNTIME_HARDENING.md#readiness-before-queue-claim).

For multi-project configs, select a project explicitly with --project. An activated
terminal exports NIGHTSHIFT_PROJECT_NAME; commands below pass it to the CLI.
Restart the daemon after editing configuration. Existing agents retain inherited
environment until restarted.

## Activate the selected runner

Save the [activator template](#activator-template) below as runner env.sh. Source
it in the current Bash/Zsh terminal:

```bash
source /absolute/path/to/runner/my-app/env.sh
ns-help
ns-status
ns-queue
```

Activation changes to the product, exports absolute config/state paths and shows
one `(ns:my-app)` prefix in interactive terminals. Re-sourcing replaces the context.
`deactivate-ns` restores the previous prompt/directory and clears the runner
exports. Custom prompt managers should retain the project prefix when rebuilding
PS1. Running `bash env.sh` affects only its child shell.

The activator creates these temporary-document destinations in the runner:

| Export | Purpose |
| --- | --- |
| NIGHTSHIFT_SPEC_DIR | Temporary specifications/design drafts |
| NIGHTSHIFT_TODO_DIR | Tickets, plans and unassigned work |
| NIGHTSHIFT_HANDOFF_DIR | Handoffs and session summaries |
| NIGHTSHIFT_NOTES_DIR | Investigation notes and diagnostic reports |
| NIGHTSHIFT_SCRATCH_DIR | Disposable development artifacts |

Use these absolute paths in queued references. Environment variables do not
redirect arbitrary relative writes. Permanent product docs stay with product
source, and secrets stay out of ticket prose/reports. Switching runners replaces
every exported document/state path.

## Check setup without dispatching work

Use a fresh runner with an empty queue; preserve an existing nonempty queue.
Inspect selected paths and exercise the launcher without model work:

```bash
python3 "$NIGHTSHIFT_CORE/scripts/worker_runtime.py" project-info \
  --root "$NIGHTSHIFT_PROJECT_ROOT" --config "$NIGHTSHIFT_CONFIG_FILE" \
  --project "$NIGHTSHIFT_PROJECT_NAME"
# Only when tasks.txt is empty:
RUN_ONCE=1 ns-worker
ns-status
```

Done means project-info names the intended product/runner, the empty session exits
cleanly, status reads that runner, the product has no new runtime files, and
activation/deactivation restore the terminal context. This smoke check does not
certify the model sandbox or hot framework; validate those project prerequisites
separately before queueing implementation.

## Tickets and capability

A code ticket declares its acceptance unit, LEVEL, TARGET, action and verification:

```text
TASK-042 [CODE: FIX] | LEVEL: 3 | TARGET: src/parser.py,tests/test_parser.py | FILES: 2 | ACTION: Reject empty input and add a permanent regression case | VERIFY: python3 -m unittest discover -s tests -p test_parser.py
```

Worker returns structured evidence; runtime owns verification, commits and score
updates. Default code handoff requires new/meaningfully changed permanent tests,
full hot and scope audits. Explicit REFACTOR/EXISTING can pin unchanged cases;
VERIFY-only executes actual commands without product edits, commit or score credit.
Use the [ticket contract](TICKET_ACCEPTANCE.md) for those mode requirements.

| Registration score | Allowed LEVEL |
| --- | --- |
| 5 | L1, L2, L3 |
| 3-4 | L2, L3 |
| 1-2 | L3 |

LEVEL need not equal the recommendation. A lower number represents broader work;
claim, routing, failover and direct task execution enforce the capability ceiling.
Invalid contracts leave the FIFO under CONTRACT_BLOCKED. TARGET/deletion audits
still apply. Planner reads registration scores directly when sizing complete
acceptance units; no extra capacity-review step is required.

## Operations and recovery

| Helper | Behavior |
| --- | --- |
| ns-worker / ns-run | Start the selected standalone wrapper |
| ns-help | List helpers |
| ns-status / ns-queue | Inspect selected state / FIFO |
| ns-watch 0 5 TASK-ID | Wait for audited task completion or a genuine fault |
| ns-pause / ns-resume | Set/clear the manual pause flag at a task boundary |
| deactivate-ns | Restore the prior terminal context |

Persistent mode waits for future tickets; the wrapper retries worker exits.
RUN_ONCE=1 executes one daemon session without wrapper retry, preserving its exit
code. It may process multiple tickets and can finish at an empty queue, a dispatch
gate or after draining scheduled foreground hooks. Eligible background work is
drained before normal exit. It does not mean exactly one ticket.

For an ordinary task failure, Planner inspects lifecycle/reports, revises the
FIFO into bounded repair work, then releases the diagnosed failure pause:

```bash
python3 "$NIGHTSHIFT_CORE/scripts/worker_runtime.py" restart \
  --root "$NIGHTSHIFT_PROJECT_ROOT" --config "$NIGHTSHIFT_CONFIG_FILE" \
  --project "$NIGHTSHIFT_PROJECT_NAME"
```

This keeps the live session and starts subsequent work clean; it does not resume
an interrupted verification. ns-resume only clears the manual PAUSE file.
Capability-change events have their own acknowledgement gate. Read the event and
use the runtime agent-event-ack command with its event/state arguments before
resuming affected dispatch. See [recovery details](../acceptance.md#failure-and-restart).

## Optional hooks

Ordinary configured hooks count accepted ticket events, including no-change;
cold_every counts accepted development commits. They execute synchronously before
the next ticket. A live hook-register one-shot targets an exact future task ID.
Default one-shots/counters are session-only; durable_hooks optionally persists
legacy hook obligations, whose interrupted effects need explicit review.

A custom periodic hook may register a second stage:

```json
{
  "id": "periodic-analysis",
  "every": 3,
  "argv": ["python3", "tools/prepare.py"],
  "timeout": 60,
  "second_stage": {
    "argv": ["python3", "tools/analyze.py"],
    "timeout": 1800
  }
}
```

Add this object to acceptance.hooks only after its product-owned scripts exist.
First stage writes NIGHTSHIFT_HOOK_ARTIFACT_DIR; runtime seals a copy for second
stage. Both can export reports to NIGHTSHIFT_HOOK_REPORT_DIR. The second stage
uses a fixed-revision independent clone, with no git worktree; use snapshot-relative
paths and the supplied root/artifact variables.

Dual-stage hooks count development commits only. One background command runs per
project; busy thresholds coalesce and use the latest accepted revision when free.
Reports identify revision/input hashes and freshness; older success does not
validate current code. Failures wait for the active ticket, get a diagnostic
using the triggering registration when available, then hold new claims for
Planner repair. Missing registrations or unsafe snapshots fall back to raw evidence.
Ghost does not edit/commit, rotate models or score the Worker. Acknowledge after
putting repair work first:

```bash
python3 "$NIGHTSHIFT_CORE/scripts/worker_runtime.py" hook-list \
  --root "$NIGHTSHIFT_PROJECT_ROOT" --config "$NIGHTSHIFT_CONFIG_FILE" \
  --project "$NIGHTSHIFT_PROJECT_NAME"
python3 "$NIGHTSHIFT_CORE/scripts/worker_runtime.py" hook-cancel \
  --root "$NIGHTSHIFT_PROJECT_ROOT" --config "$NIGHTSHIFT_CONFIG_FILE" \
  --project "$NIGHTSHIFT_PROJECT_NAME" --run-id RUN_ID
```

Second-stage counters, handles and failure holds always live in RAM, even with
durable legacy hooks. Stop cleans owned background commands; relaunch starts at
zero without replay. Reports and failed snapshots remain evidence on disk.
Success deletes temporary clones/inputs. Full variables and limits are in
[Background Hooks](BACKGROUND_HOOKS.md); ordinary hook retry/cancel semantics are
in [post-acceptance hooks](../acceptance.md#post-acceptance-hooks).

## Activator template

Copy this Bash/Zsh template into the selected runner's env.sh and set the core
path. Keep run_worker.sh beside it, copied from the
[standalone template](../templates/run_worker.sh). It preserves the existing
activation, temporary-document, helper and deactivation behavior.

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
  unset WORKER_AGENT_EVENTS_FILE WORKER_AGENT_EVENTS_CURSOR_FILE WORKER_AGENT_EVENTS_ACK_FILE
  unset AGENT_DISPATCH_GATE_FILE
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
