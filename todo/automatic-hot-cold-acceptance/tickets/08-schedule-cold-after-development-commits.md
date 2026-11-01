# 08: Insert cold after N successful development commits and recover cadence on restart

**What to build:** The user configures a task interval and the script inserts exactly one due cold task, avoiding duplicate or already-passing work across queue changes and restarts.

**Blocked by:** 07: Execute an independent cold FIFO task with silent success and diagnosed failure

**Status:** complete

## Acceptance criteria

- [x] Add a validated positive cold interval setting and document how projects configure or leave periodic cold unconfigured; do not invent a hidden default cadence.
- [x] Advance cadence only after a successful development-task commit. Research, no-change work, failed tasks, Ghost substeps and cold tasks do not count.
- [x] At the configured threshold, use the existing atomic scheduling insertion/claim mechanism to enqueue one internal cold task as early as the pending FIFO allows.
- [x] Persist counted task/commit identities and pending/due state in ignored runtime data. Replaying a completion or restarting near insertion cannot advance twice or enqueue duplicates.
- [x] Coalesce an already pending or executing cold request instead of creating another for the same due interval.
- [x] At execution compare actual HEAD with the last successfully cold-tested commit; an identical already-passing revision skips test execution without notification, commit or score change.
- [x] Update last-passing revision only on a complete successful cold outcome, never after a failure. Mark covered cadence intervals so success/skip cannot create an endless immediate insertion loop.
- [x] If HEAD advanced between insertion and execution, test execution-time HEAD and record which counted interval(s) it covers; do not falsely label a different revision as tested.
- [x] Cold failure leaves dispatch paused and preserves sufficient scheduling state for Planner to replan/restart without dropping the failed issue or looping an unacknowledged task.

## Verification

Use N=2 and a deterministic command counter: two accepted development commits insert one cold; failures/research do not count. Cover restart before/after insertion, duplicate completion, pending coalescing, identical-hash skip, newer execution HEAD and post-failure Planner restart.

## Out of scope

No background cold process, concurrent test worktree or historical score correction.

