# NightShift

NightShift is a queue-driven Planner/Worker toolkit for unattended development. A Planner skill turns a goal into bounded tickets and accepts the evidence; each Worker invocation handles one ticket through a configurable CLI. Explore supplies read-only codebase reports when the Planner needs evidence about ownership, callers, or public seams.

The intended workflow can run continuously, but the runtime does not start or supervise a Planner agent. An interactive agent must follow the Planner skill and keep dispatching work. See the [complete behavior specification](docs/NIGHTSHIFT_SPEC.md) and [source coverage index](docs/NIGHTSHIFT_SOURCE_COVERAGE.md) for the contracts, implementation limits, and audited source inventory.

## Components

- `worker.sh` owns worker runtime defaults, checks Python, and starts `scripts/worker_runtime.py`.
- `.agents/skills/nightshift/planner/` defines ticket planning, dispatch, acceptance, and recovery.
- `.agents/skills/nightshift/explore/` defines read-only seam research and report handoff.
- `.skills/universal-build-verify.md` defines Worker execution, verification, and closeout expectations.
- `scripts/` contains the runtime, status and queue controls, report helpers, and source inspection helpers.
- `tasks.txt` is the FIFO queue. The runtime claims one ticket at a time and executes it sequentially. Dependency ordering and dispatch choices belong to the Planner; the runtime does not schedule a dependency graph or run a Planner.
- `progress.log`, `tasks.done`, `worker.status`, `.worker.log`, and `.worker-score.json` record runtime outcomes, current state, diagnostics, and shared reliability feedback.
- `docs/` contains the full behavior spec, source-to-spec coverage, deployment guide, and agent metadata; `docs/adr/` is reserved for architectural decisions.

## Setup

Install into another existing repository:

```sh
./install.sh /path/to/target-project
```

Update a deployment with the same installer interface:

```sh
./update.sh /path/to/target-project
```

The installer also deploys `update.sh` into the target project so future updates can be started there.

Worker-wide runtime settings are configured at the top of `worker.sh`. Agent registrations live in the single `scripts/adapters/agents.json` object, keyed by agent name. Each entry separates `worker.task_timeout_seconds` from the `agent` launch settings (`adapter`, the real executable `command`, optional `args` and `env`, and provider-specific `config`). The `default` flag orders preferred registrations first; multiple defaults are allowed. The selected adapter script is launched internally by Python, so `agent.command` names the real agent executable such as `codex` or `agy`, not Python. The installer preserves an existing agent registry. Failover follows registration order after quota exhaustion or a confirmed timeout. A capability change creates a Planner gate, so the replacement waits until the Planner acknowledges or revises the affected work. If every registration is quota-exhausted, the task remains queued until quota state is reset.

## Run and inspect

Start the persistent worker:

```sh
./worker.sh
```

Run until the queue is empty:

```sh
RUN_ONCE=1 ./worker.sh
```

Useful controls:

```sh
./scripts/status.sh
./scripts/reorder_queue.sh prepared-queue.txt  # replace queue from a prepared file
touch PAUSE                         # pause before the next ticket
rm PAUSE                            # resume
```

The queue reorder helper accepts a complete replacement queue from a file or standard input; it has no `prepend` subcommand. Worker tasks execute directly in the project directory. Trial deliveries go under `.trials/<TASK-ID>/` after their staged copy passes the runnable check; previous deliveries remain separate from development build outputs. Upgrades preserve old `.worker-tree`, branches, and `.preview` contents so you can inspect or migrate unfinished work manually. A runtime audit PASS is not Planner acceptance.

## Regression tests

Tests use the standard library and fake CLI executables; they do not call a live model:

```sh
python3 -m unittest discover -s test -v
bash -n worker.sh install.sh scripts/*.sh
```

The installer deploys the suite under `test/nightshift_worker/` in target repositories. For porting details, see the [porting guide](docs/PORTING_GUIDE.md).
