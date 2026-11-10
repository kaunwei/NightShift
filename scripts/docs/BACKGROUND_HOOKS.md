# Two-stage periodic hooks

Custom periodic hooks may register an optional second stage. Existing hooks,
one-shot hooks and built-in cold verification keep their existing behavior.
No skills changes are required.

```json
{
  "acceptance": {
    "hooks": [{
      "id": "periodic-analysis",
      "every": 3,
      "argv": ["python3", "tools/prepare.py"],
      "timeout": 60,
      "second_stage": {
        "argv": ["python3", "tools/analyze.py"],
        "timeout": 1800
      }
    }]
  }
}
```

Both stages use argv arrays without shell expansion. Use project-relative
script/input paths or the provided snapshot root, rather than absolute paths
pointing at the live product checkout. Invoke a shell explicitly
if required. Each timeout must be finite and positive; omitted timeouts use
the existing cold_timeout. second_stage is accepted only on custom periodic
hooks, and requires argv. An absent second_stage preserves the old hook.

## Scheduling

Two-stage hooks count accepted development commits only; research and no-change
accepts do not count. Ordinary periodic hooks retain their accepted-event count.
First stage runs synchronously, at a task boundary with the accepted revision
and clean-checkout guards. It must leave source, HEAD and nonignored files
unchanged. Prepare data in the provided artifact directory.

After first-stage success, runtime seals a copy of its artifacts and creates an
independent detached Git clone of the exact revision. It uses neither git
worktree nor shared object alternates/hardlinks. Second stage runs in that clone
while Worker continues in the product checkout. Submodules are not initialized;
unsupported inputs and links escaping their snapshot fail explicitly. Project
dependencies/engine installation remain the script's responsibility.

There is at most one background command per project. Busy hooks only accumulate
a saturated threshold count: no waiting run or extra first-stage invocation is
created. When the slot is free, the next task boundary prepares the latest
accepted revision. Eligible hooks rotate in configuration order. For every=3,
a run at commit 3 may still be busy at commit 9; if it completes at commit 10,
the next run uses commit 10, rather than creating runs for 6 and 9.

RUN_ONCE continues normal development and drains already eligible background
work when the queue becomes empty. Normal stop closes the owner pipe and waits
for cleanup. A separate supervisor also observes pipe EOF on daemon death and
kills the owned command process group, including ordinary descendant processes.
Timeouts retain full live logs with a bounded in-memory tail. This is process
ownership and final-state auditing, not an OS read-only sandbox.

## Script inputs and outputs

| Environment variable | Meaning |
| --- | --- |
| NIGHTSHIFT_HOOK_ID | Periodic registration ID |
| NIGHTSHIFT_HOOK_RUN_ID | Unique run identity |
| NIGHTSHIFT_HOOK_TASK | Development task supplying the revision |
| NIGHTSHIFT_HOOK_REVISION | Exact Git commit being analyzed |
| NIGHTSHIFT_HOOK_ARTIFACT_DIR | First stage writes here; second stage reads a sealed copy |
| NIGHTSHIFT_HOOK_REPORT_DIR | Persistent output directory for reports |
| NIGHTSHIFT_PROJECT_ROOT | Second-stage snapshot root |

Second stage does not inherit runtime project-selection variables that would
resolve back to the live checkout. It must not modify snapshot source, HEAD or
sealed artifacts. Tracked/nonignored source changes, changed artifact hashes,
nonzero exit, timeout and recognized zero-test results fail the run. Ignored
build products in the clone are allowed. Write exported reports to REPORT_DIR.

Each run retains result.json, input-manifest.json, first-stage evidence, script
reports and live logs under lifecycle/background-hooks/<run-id>. The manifest
records Git source tree identity plus artifact SHA-256/mode/link evidence.
Registration environment/credentials are not copied into supervisor requests
or ghost prompts. A successful run deletes clone, prepared data and sealed
inputs. Failure retains them for diagnosis.

Receipt freshness is observed at collection: same_revision, older_snapshot,
checkout_changed or unknown. hook-list recomputes freshness when requested.
Always compare revision and inputs again when consuming a report: successful
analysis of an older revision does not prove the current code passes.

## Failure and restart

Background completion is collected on the main thread at a task boundary.
Failure never edits the active development journal or scores the Worker. The
current task finishes first; a read-only diagnostic ghost then gets priority
over new dispatch. It uses the exact triggering registration with the existing
25-action/180-second diagnostic limits. Missing or changed registrations, unsafe
snapshot state and diagnostic failure fall back to the original raw report.
Ghost has a separate hook run identity, consumes no development closeout
allowance, and never commits, repairs or rotates models automatically.

The live session then holds dispatch for Planner repair. Inspect hook-list and
the run's result.json, put the repair ticket first, then acknowledge the failed
run using hook-cancel --run-id. This releases the in-memory hold. Failed hooks
restart their count; remaining ready background work waits for a new accepted
development commit, allowing the repair ticket to run first. Old snapshots are
not replayed with hook-retry.

All two-stage counters, readiness, fairness cursor, execution handles and failure
holds live in RAM, even if durable_hooks is enabled for legacy hooks. Restart
loads configuration with zero counts and no interrupted/retry state. Reports
and failed snapshots are evidence only and are never loaded as scheduling state.
Use normal stop before restarting; completed evidence is retained on disk.

Generic diagnostic outcomes use valid protocol terminal states. Main wrapper
command errors and malformed results remain single-attempt failures; they do
not cause extra ghost invocations or registration failover.
