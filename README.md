# NightShift

NightShift runs a FIFO of bounded development tickets through named Worker
registrations. Runtime verifies evidence, audits scope, commits accepted work and
updates registration scores. Planner handles decomposition and recovery; Explore
provides read-only codebase reports. The runtime does not launch a Planner agent.

## Workspace layout

| Location | Owns |
| --- | --- |
| Core checkout | `scripts/` runtime, adapters, parser tools, `.agents/skills/` and `.skills/` |
| Per-project runner | `config.json`, `env.sh`, `run_worker.sh`, queues, logs, scores, reports and indices |
| Product Git repository | Source, permanent tests/docs and project-maintained build/test/demo scripts |

The runner is outside the product. Worker edits and commits the selected product;
engine files and generated runtime state stay in the core/runner. Trial artifacts
may be explicitly delivered under the product's `.trials/<TASK-ID>/`.

For first setup or migration, follow the [Porting Guide](scripts/docs/PORTING_GUIDE.md).
It includes the configuration, activator template and an empty-queue smoke check.
The embedded `install.sh` / `remove.sh` workflow is retired.

## Run and inspect

Activate an already configured runner in the current Bash/Zsh terminal:

```bash
source /absolute/path/to/runner/my-app/env.sh
ns-status
ns-queue
ns-worker
```

Activation selects the product directory, absolute runner paths and a single
`(ns:<project>)` prompt prefix. `deactivate-ns` restores the previous terminal
context. `ns-help` lists the supplied helpers.

`ns-worker` runs persistently and waits for future tickets. The standalone wrapper
retries child-worker exits. To run one daemon session, preserving its exit code without wrapper retry:

```bash
RUN_ONCE=1 ns-worker
```

A session can process multiple tickets. Stop boundaries include an empty queue,
Planner gates and draining scheduled foreground hooks; eligible background work
is drained before normal exit. RUN_ONCE is not a one-ticket limit. Configuration
changes take effect after restart.

| Control | Use |
| --- | --- |
| `ns-pause` / `ns-resume` | Set/clear the manual pause flag at a ticket boundary |
| `ns-watch 0 5 TASK-ID` | Wait for task-scoped completion/failure; zero means unlimited waiting |
| `ns-status` / `ns-queue` | Inspect the selected runner |
| Runtime `restart` | Release a diagnosed task-failure pause after Planner revises the FIFO |
| Runtime `hook-list` / `hook-cancel` | Inspect live hooks / acknowledge a failed background run |

Manual resume, task-failure recovery and capability-event acknowledgement are
separate controls. See [operations and recovery](scripts/docs/PORTING_GUIDE.md#operations-and-recovery).
Queue reordering replaces the FIFO from a file or stdin; it has no prepend subcommand.

## Tickets and acceptance

Code normally supplies new or meaningfully changed permanent tests. Runtime runs
full hot, ticket VERIFY and scope audits before committing. A plain test command
is not a framework evidence adapter: the hot runner must implement the
[hot protocol](scripts/acceptance.md#framework-adapter-protocol).

LEVEL communicates scope/precision and imposes a one-way capability ceiling:

| Registration score | Allowed ticket LEVEL |
| --- | --- |
| 5 | L1, L2, L3 |
| 3-4 | L2, L3 |
| 1-2 | L3 |

L1 is broader work; L3 is more explicit and bounded. Higher-capability Workers can
still take L3. Invalid/oversized contracts remain queued under CONTRACT_BLOCKED.
`FILES` estimates planned work without recursively counting directory contents.
Explicit REFACTOR/EXISTING and VERIFY-only modes are described in the
[ticket contract](scripts/docs/TICKET_ACCEPTANCE.md).

Each registration has its own score under runner `.worker-agent-scores/`.
Automatic feedback lowers score after every two attributable failures across
task IDs and raises it after five effective development accepts. Research,
verification-only and unproven/environment failures are neutral. Scores remain
within 1..5; Planner reads the executing registration's score when sizing work.

## Background hooks

A custom periodic hook can add optional `second_stage.argv` and `timeout`.
Preparation runs synchronously; analysis runs on a fixed commit in an independent
clone, with sealed first-stage artifacts. No git worktree is created.

Only one background command runs per project. Busy triggers retain a saturated
commit count, then use the latest accepted revision when the slot becomes free.
Failures wait for the current ticket, get a diagnostic ghost, then hold new
claims for Planner repair without scoring the Worker. Background scheduling and
failure holds are RAM-only and reset on restart; reports and failed snapshots
remain evidence. Successful historical analysis does not prove newer code passes.

For configuration, script variables and recovery, read
[Background Hooks](scripts/docs/BACKGROUND_HOOKS.md). Ordinary hooks without a
second stage retain their existing synchronous behavior.

## Verification and references

Prepare the core's parser environment, then run the model-free regression suite:

```bash
bash scripts/tools/setup.sh
python3 -m unittest discover -s test -v
for script in scripts/*.sh scripts/templates/*.sh; do bash -n "$script"; done
```

Tests use disposable repositories and fake model CLIs. Retired installer cases
were removed; standalone runtime, trial and clone checks execute using portable
fixtures. See [test setup](test/README.md) for parser/process prerequisites.

- [Porting Guide](scripts/docs/PORTING_GUIDE.md): setup, ownership, activation and recovery.
- [Runtime hardening](scripts/docs/RUNTIME_HARDENING.md): preflight probes, retained attempts and live logs.
- [Behavior specification](scripts/docs/NIGHTSHIFT_SPEC.md) and [source coverage](scripts/docs/NIGHTSHIFT_SOURCE_COVERAGE.md): contracts and audited implementation limits.
