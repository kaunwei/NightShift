# Hot/cold migration

Runtime commits and scores on the current branch. Planner schedules work and
explicitly restarts after failures. Setup is required; legacy VERIFY alone is
not evidence that a new TDD case ran. Generated lifecycle state lives under
`git rev-parse --git-path nightshift`; it is outside Git history and cleanup.

See [script-only runtime follow-ups](docs/RUNTIME_HARDENING.md) for retained
attempts, configurable readiness probes, POSIX live logs, optional evidence
capabilities, opt-in durable hooks and capacity inspection.

## Configure a project

Track `scripts/config.json` with the project's acceptance and agent commands:

```json
{
  "version": 1,
  "acceptance": {
    "hot": "python3 scripts/unittest_hot.py --start test",
    "cold": "python3 -m unittest discover -s test",
    "cold_every": 5,
    "hot_timeout": 300,
    "cold_timeout": 1800,
    "wiring": []
  },
  "agents": {
    "primary": {
      "default": true,
      "worker": {
        "step_base": {"L1": 60, "L2": 40, "L3": 20},
        "task_timeout_seconds": 1800,
        "research_step_budget": 100
      },
      "agent": {
        "adapter": "codex",
        "command": "codex",
        "args": [],
        "env": {},
        "config": {}
      }
    }
  }
}
```

Runtime reads persistent settings only from `scripts/config.json`. Each agent must define positive `worker.step_base` values for L1, L2, and L3. Restart the Worker after editing configuration.

Acceptance budgets are separate: hot discovery, hot execution and extra task
VERIFY share one `hot_timeout` deadline (default 300 seconds). Cold uses
`cold_timeout` (default 1800 seconds). Each phase field wins over an explicitly configured legacy `timeout`.
Without a phase field, an explicit legacy value remains that phase's fallback;
without either field, the phase default applies. Values must be finite positive
numbers, not booleans. These limits are separate from agent task timeouts.
A running Worker that loaded an older reader keeps its old semantics until a
user-controlled restart; adding fields does not hot-reload its Python modules.

Commands run from project root. `cold_every` is an optional compatibility
setting: it converts `cold` and `cold_timeout` to a periodic hook, counting
accepted development commits as before. Manual `[COLD]` tickets enter the same
hook ledger. Cold retains its per-revision pass record and silent success;
it does not change score or Git history. Counts and the per-session pass cache
start empty on every worker launch. The last cold result file is audit output,
not control input. Outputs must be ignored by Git. With `durable_hooks: true`,
counters and the per-revision pass cache persist in the dedicated hook ledger.

`wiring` lists exact configuration/registration files Ghost may edit to connect
existing tests. Include those files and tests in task TARGET. Ghost also may supply
the acceptance configuration. Keep executable test behavior in tests, separate
from wiring. Ghost leaves source, assertions and unrelated scripts unchanged.

## Post-acceptance hooks

A project can register periodic commands in its acceptance config:

```json
"hooks": [
  {"id":"package-demo","every":5,"argv":["python3","scripts/build_demo.py"],"timeout":420}
]
```

Configured `every` hooks count distinct accepted ticket events after
installation, including no-change results. Cold and hooks do not count. Legacy
`cold_every` has a different counting rule but uses the same scheduler,
executor, and failure handling. Use a stable hook ID. The
runtime serializes due hooks before the next ticket. The command runs in the
project root with `NIGHTSHIFT_HOOK_REVISION`, `NIGHTSHIFT_HOOK_TASK`,
`NIGHTSHIFT_HOOK_ID`, and `NIGHTSHIFT_HOOK_RUN_ID`. The last is an idempotency
key; scripts should use it for output names or external side-effect deduplication.
Commands must leave the Git revision and tracked/nonignored files unchanged.

Register a one-shot from a Planner shell before the ticket is accepted:

```sh
python3 "$NIGHTSHIFT_CORE/scripts/worker_runtime.py" hook-register --root . \
  --config "$NIGHTSHIFT_CONFIG_FILE" \
  --spec '{"id":"demo-42","after":"TASK-42","argv":["python3","scripts/build_demo.py"],"timeout":420}'
```

The CLI sends commands to the live worker through a private local pipe. It
does not register work when no worker is running. The worker owns one in-memory
scheduler; it does not poll or replay an acceptance hook ledger. Relaunching
`worker.sh` loads config and starts with no one-shots, counters, pending runs,
or retry state by default. Opting into `acceptance.durable_hooks` persists these
obligations and deduplication identities; interrupted effects require explicit
review and retry/cancel. Register session-only one-shots again after relaunching. A manually queued
`[COLD]` ticket remains part of the ordinary task queue.

Nonzero exits and timeouts use the cold-style failure report and pause dispatch;
accepted commits, reports and explicit pause controls are preserved. To retry a
failed hook in the same live worker, run `hook-retry --root . --config ... --run-id RUN_ID`,
then the Planner `restart` command to clear the failure pause without relaunching.
A relaunched session-only worker cannot retry a previous session's hook. Treat registered
argv as trusted project code; do not embed secrets in it.

## Hot failure triage and adapter deadlines

Workers run focused red/green checks; the runtime runs the permanent hot suite
and any extra VERIFY. Do not set VERIFY to the full cold command on new code
tickets. A selected-case-capable hot hook can report assertion failures for a
one-time rerun at the accepted base in a detached worktree. Set
`supports_case_selection: true` in its evidence only if it honors the exact
JSON IDs in `NIGHTSHIFT_ONLY_CASES`. A baseline failure creates a durable
repair record and stops dispatch. Ticket-only failures, baseline failures and
inconclusive diagnostics preserve the failed attempt without auto-requeueing
the original ticket. Fix the baseline or reslice before restarting.

`TASK_TIMEOUT` limits the shared adapter dispatch window (default 1800 seconds).
Per-agent limits are caps within that window. A productive execution timeout
goes to Planner instead of restarting from scratch on another agent. Status
reports distinguish runtime cancellation from a command returning exit 124.
Watcher elapsed time is the duration of the watch, not a ticket deadline.

### Custom Hot/Cold Runner Abstraction

By default, NightShift executes `hot` and `cold` commands via bash with `NIGHTSHIFT_PHASE` environment variables (`DefaultAcceptanceRunner`). A project can customize or completely override how hot and cold call functions work:

1. **Via `scripts/acceptance_runner.py`**:
   Create `scripts/acceptance_runner.py` in the project root, defining a custom `Runner` class (or function `get_runner(root, cfg)`) subclassing `acceptance.DefaultAcceptanceRunner` or `acceptance.AcceptanceRunner`:
   ```python
   import acceptance

   class CustomRunner(acceptance.DefaultAcceptanceRunner):
       def run_hot(self, args, result, run_verify):
           # Custom hot execution logic
           return super().run_hot(args, result, run_verify)

        def run_cold(self, root, run_verify):
            # Custom cold regression logic
            return super().run_cold(root, run_verify)

   def get_runner(root, cfg):
       return CustomRunner()
   ```

2. **Via `acceptance.runner` in `scripts/config.json`**:
   Specify a custom runner entry point: `"runner": "my_module:CustomRunner"`.

Keep generated queues/status/scores untracked. Installer ignores them; if an old
project tracks these files, untrack its generated state before starting Worker.
Upgrade preserves project configuration; it does not invent a hot gate for you.

## Worker handoff

Use persistent framework discovery. A task can declare additional `CASES: id,id`
and `VERIFY: command`; both join hot acceptance. New TDD cases must remain part
of normal hot without these task selectors on later tasks.

```json
{
  "outcome": "complete",
  "commit_message": "fix: handle empty input",
  "tdd_cases": [
    {"id": "test_input.InputTests.test_empty", "source": "test/test_input.py"}
  ]
}
```

Runtime reconciles declarations against permanent discovery: extra leading
`test.` prefixes and in-project absolute source paths normalize only to a unique
exact discovered case/source. It records original, canonical and dropped entries.
An unchanged case is removed from TDD declarations only when another valid new or
changed case remains; it still runs in the full regression suite.

Missing/empty declarations, unchanged-only or comment-only evidence, unknown or
ambiguous IDs, mismatched/outside sources, duplicates and unsupported fingerprints
fail. Failed, skipped, deselected or missing required cases always block acceptance.
Runtime commits only after the complete hot, VERIFY and scope audit pass.

## Framework adapter protocol

The hot command receives these environment variables:

| Variable | Meaning |
| --- | --- |
| NIGHTSHIFT_PHASE | discover or run |
| NIGHTSHIFT_RESULT | Unique JSON output path owned by this runtime invocation |
| NIGHTSHIFT_RUN | Nonce echoed by the output |
| NIGHTSHIFT_BASE | Task-start commit for test-content comparison |
| NIGHTSHIFT_TASK | Task ID; empty during permanent discovery |
| NIGHTSHIFT_REQUIRED | Required case IDs as JSON; empty during discovery |

Write this shape to NIGHTSHIFT_RESULT and exit zero only for success:

```json
{
  "run": "the received nonce",
  "cases": [{
    "id": "test_input.InputTests.test_empty",
    "source": "test/test_input.py",
    "fingerprint": "64 lowercase hex digits",
    "baseline_fingerprint": null,
    "status": "passed"
  }]
}
```

Discovery omits status. Fingerprints hash parsed test content (not comments,
docstrings or the whole test file); baseline_fingerprint is that same case's
fingerprint at NIGHTSHIFT_BASE, or null for a new case. Report stable IDs and
source associations. Execution reports actual case outcomes; absent, skipped,
failed or stale evidence fails. Every configured command must also exit zero.
Runtime invokes the adapter itself and requires fresh invocation identity.

The supplied unittest adapter supports top-level TestCase classes with methods
defined in the same file. It discovers real tests, compares method ASTs with Git
baseline and records actual unittest success. Import/discovery errors fail. A
framework with generated/inherited cases needs an adapter that can establish
equivalent source association; unsupported evidence fails explicitly. Source
change plus execution does not prove a test's assertions match the requirement.

For Swift/pytest/other frameworks, port discovery, source mapping and actual
result parsing to this contract. A bare `swift test`/pytest exit code is not a
replacement adapter. Run the new-case/persistent-discovery/skip/stale-evidence
fixtures before enabling a new integration. Framework-wide policy belongs here,
not in runtime heuristics.

## Failure and restart

1. Gate failure stops ordinary dispatch. Ghost gets actual output and may supply
   metadata, wire an existing test, rerun checks and write diagnosis. It has one
   bounded allowance per attempt; product/test repair goes to Planner.
2. Unresolved failure produces a report under the Git directory's
   `nightshift/reports` and notifies Planner. Ghost timeout still supplies available
   failure evidence. The dirty/staged scene remains available for inspection.
3. Planner inserts/reorders ordinary issue tasks through the queue scripts,
   revises instructions and explicitly runs:

       python3 scripts/worker_runtime.py restart --root .

4. Next Worker starts after `reset --hard HEAD` and `clean -fd`: tracked and
   nonignored uncommitted changes are discarded. Ignored files/reports survive.
   For external runners, restarting an existing failure pause records a one-shot
   cleanup authorization. The daemon consumes it under the workspace lock before
   checking for a clean worktree, including generated product files under `scripts/`.
   Runner state is preserved. A changed HEAD or cleanup failure pauses dispatch
   again; restarting without a failure pause does not authorize cleanup.
   A restore-verified attempt package is retained before destructive cleanup;
   failed patches are not automatically continued. Configured PAUSE and agent
   event gates remain separate controls. Cleanup failure keeps dispatch paused.

Cold failure uses the same diagnosis and restart flow, treated as a new issue;
earlier scores and commits remain. Successful development tasks use the existing
accept streak/score arithmetic automatically. Durable task/commit/event identities
make replay safe across interrupted commit, scoring and queue insertion.

## Check a migration

Use a disposable installed project. Add a real TDD case with Worker handoff,
observe hot/commit/score, then deliver another task and prove the first case still
runs without its old ticket. Set cold_every to two, observe a silent independent
cold, then fail cold and verify report/pause. Schedule an ordinary issue, restart
and confirm the next Worker sees clean tracked/nonignored files.

Repository verification: `python3 -m unittest discover -s test -p test_automatic_acceptance.py`.
These fixtures use real unittest hooks and disposable Git repositories, never a
model or cleanup of the live checkout.
