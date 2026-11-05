# NightShift

NightShift is a queue-driven Planner/Worker toolkit for unattended development. A Planner skill turns a goal into bounded tickets and accepts the evidence; each Worker invocation handles one ticket through a configurable CLI. Explore supplies read-only codebase reports when the Planner needs evidence about ownership, callers, or public seams.

The intended workflow can run continuously, but the runtime does not start or supervise a Planner agent. An interactive agent must follow the Planner skill and keep dispatching work. See the [complete behavior specification](scripts/docs/NIGHTSHIFT_SPEC.md) and [source coverage index](scripts/docs/NIGHTSHIFT_SOURCE_COVERAGE.md) for the contracts, implementation limits, and audited source inventory.

## Components

- `scripts/` owns the runtime engine, adapters, helper scripts, parser tool, configuration, queue, logs, and state. `scripts/worker.sh` starts the worker.
- `.agents/skills/nightshift/planner/` defines ticket planning, dispatch, acceptance, and recovery.
- `.agents/skills/nightshift/explore/` defines read-only seam research and report handoff.
- `.skills/universal-build-verify.md` defines Worker execution, verification, and closeout expectations.
- `scripts/.scratch/code-index/INDEX.md` is the bounded agent navigation map; `scripts/tools/` owns the reusable Tree-sitter index CLI and parser registry. The consuming project owns the source selection and `tool`/`project` scope labels in `scripts/config.json`.
- `scripts/tasks.txt` is the FIFO queue. The runtime claims one ticket at a time and executes it sequentially. Dependency ordering and dispatch choices belong to the Planner; the runtime does not schedule a dependency graph or run a Planner.
- `scripts/progress.log`, `scripts/tasks.done`, `scripts/worker.status`, `scripts/.worker.log`, and `scripts/.worker-score.json` record runtime outcomes, current state, diagnostics, and shared reliability feedback. Attempt snapshots and failed-task recovery files live under `scripts/.scratch/`. Worker checks their sizes without reading logs and queues one internal review when attempts or failures reach 100 MiB, or failure archives reach 20 directories. The Worker reviews deletion evidence and overwrites `scripts/.scratch/review/last-review.json` (at most 1 KiB); Planner has no additional reading step.
- Source-only `scripts/docs/` contains the behavior spec, source-to-spec coverage, deployment guide, and NightShift operating guides. Root `docs/` remains available for project documentation and agent metadata.

## External Workspace Architecture (Zero Footprint)

NightShift supports a Three-Tier external architecture where **target project repositories contain zero NightShift files**:

1. **NightShift Core**: Reusable runtime engine and skill registry (`/opt/NightShift` or cloned path).
2. **Runner Workspace**: State and queue directory per project (e.g. `~/nightshift-workspace/projects/<project>/`).
3. **Target Project**: The consumer codebase (clean Git working tree, zero pollution).

For detailed setup, see the [Porting Guide](PORTING_GUIDE.md).

### Environment Activation (`env.sh`)

Similar to Python virtual environments (`source venv/bin/activate`), each project workspace in the runner provides an `env.sh` script to fix the Planner and developer terminal context without modifying the target repository:

```sh
# Activate project context:
source /path/to/runner/projects/my-app/env.sh
```

When activated:
- Automatically switches directory (`cd`) to the target project code root.
- Exports all standard NightShift variables (`$TASKS_FILE`, `$NIGHTSHIFT_STATE_DIR`, `$PROGRESS_FILE`, `$STATUS_FILE`).
- Updates terminal prompt indicator to `(ns:my-app)`.
- Injects quick command helpers:
  - `ns-status`: Display real-time worker status & queue progress dashboard.
  - `ns-worker`: Run the project worker daemon (`run_worker.sh`).
  - `ns-watch`: Stream live worker events and audit triggers.
  - `ns-pause` / `ns-resume`: Safely pause before claiming the next task, or resume.
  - `deactivate-ns`: Deactivate project context and restore shell environment.

## Run and inspect

Start the project worker daemon:

```sh
# Via runner workspace project script:
./projects/my-app/run_worker.sh

# Or when env.sh is activated:
ns-worker
```

Run until the queue is empty:

```sh
RUN_ONCE=1 ./projects/my-app/run_worker.sh
```

Useful controls:

```sh
# Status dashboard
./projects/my-app/status.sh   # or `ns-status` in activated shell

# Pause before next ticket
touch /path/to/my-app/PAUSE   # or `ns-pause`

# Resume
rm -f /path/to/my-app/PAUSE   # or `ns-resume`
```

The queue reorder helper accepts a complete replacement queue from a file or standard input; it has no `prepend` subcommand. Worker tasks execute directly in the project directory. Trial deliveries go under `.trials/<TASK-ID>/` after their staged copy passes the runnable check; previous deliveries remain separate from development build outputs. Upgrades preserve old `.worker-tree`, branches, and `.preview` contents so you can inspect or migrate unfinished work manually. Runtime hot acceptance commits and scores automatically. Planner handles failed tasks and explicitly restarts; see [hot/cold migration](scripts/acceptance.md).

## Regression tests

Tests use the standard library and fake CLI executables; they do not call a live model:

```sh
python3 -m unittest discover -s test -v
bash -n scripts/*.sh
```

For porting details, see the [porting guide](PORTING_GUIDE.md).

## Completion waiting and parser readiness

Use `bash scripts/watch_worker.sh 0 5 TASK-ID` to wait for a task. The default is unlimited notification waiting; local file checks do not call a model. Task-kind tags such as RESEARCH are normalized for exact matching. DONE remains pending until the corresponding audit arrives, and an unreviewed completed result can be replayed after a late watcher start. Completion is withheld while a worker is still RUNNING/VERIFYING on that task. Planner wakes for terminal results or genuine faults, not fixed 60-second/five-minute checks.

Install/update creates and validates the private code-index environment by parsing C, C++ and Python. Generated-runtime exclusions are also persisted in local Git info/exclude so rollback of an uncommitted .gitignore cannot expose the parser venv to cleanup. A missing environment error includes the repair command. Installer success establishes parser readiness; building an index still requires clean indexed source/settings inputs and never commits unrelated user changes.
