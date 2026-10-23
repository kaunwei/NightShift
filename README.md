# NightShift

NightShift is a queue-driven Planner/Worker toolkit for unattended development. A Planner skill turns a goal into bounded tickets and accepts the evidence; each Worker invocation handles one ticket through a configurable CLI. Explore supplies read-only codebase reports when the Planner needs evidence about ownership, callers, or public seams.

The intended workflow can run continuously, but the runtime does not start or supervise a Planner agent. An interactive agent must follow the Planner skill and keep dispatching work. See the [complete behavior specification](docs/NIGHTSHIFT_SPEC.md) and [source coverage index](docs/NIGHTSHIFT_SOURCE_COVERAGE.md) for the contracts, implementation limits, and audited source inventory.

## Components

- `worker.sh` loads `.worker.env`, checks Python, and starts `scripts/worker_runtime.py`.
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

The installer preserves an existing `.worker.env`, queue, history, and notes. To configure this repository directly, copy the example first:

```sh
cp .worker.env.example .worker.env
```

The example defaults to `AI_CLI=codex`, `AI_MODEL=gpt-6-luna`, and `AI_EFFORT=none`. Configure a different supported CLI/model in `.worker.env` as needed. Optional `AI_AGENTS_JSON` enables ordered provider failover after a failed CLI call reports a recognized quota or rate-limit error. The runtime does not query quotas in advance; when every registered agent is exhausted, it requeues the current ticket and stops.

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

The queue reorder helper accepts a complete replacement queue from a file or standard input; it has no `prepend` subcommand. By default, the worker uses an isolated `.worker-tree` and publishes build/source artifacts to `.preview/` after a successful mechanical audit. Set `WORKER_ISOLATION=0` for in-place execution. A runtime audit PASS is not Planner acceptance, and preview publication does not merge work into the main checkout.

## Regression tests

Tests use the standard library and fake CLI executables; they do not call a live model:

```sh
python3 -m unittest discover -s test -v
bash -n worker.sh install.sh scripts/*.sh
```

The installer deploys the suite under `test/nightshift_worker/` in target repositories. For porting details, see the [porting guide](docs/PORTING_GUIDE.md).
