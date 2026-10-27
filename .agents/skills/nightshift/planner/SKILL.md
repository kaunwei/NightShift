---
name: planner
description: "Plan NightShift tasks, supervise terminal events, audit results, recover failures, and deliver trials."
---

# Planner

Own the task graph and acceptance. Workers implement; runtime enforces limits and scoring.

## Plan and dispatch

1. Read the glossary, relevant ADRs and repository notes. Use [codebase-design](../../engineering/codebase-design/SKILL.md) for interfaces, [grilling](../../productivity/grilling/SKILL.md) for open requirements, and [explore](../explore/SKILL.md) for uncertain callers/targets. Base tickets on current research: referenced sources must be unchanged; archived reports are not current. Research leaves implementation untouched. Follow Explore's [code index](../explore/SKILL.md#code-index) for navigation, approval and dirty-input recovery.
2. Use [to-spec](../../engineering/to-spec/SKILL.md) and [to-tickets](../../engineering/to-tickets/SKILL.md) for multi-ticket work; write focused tickets directly. Specify targets, observable verification, dependencies and constraints. Align a broad/ambiguous queue once; enqueue known/auto-run scope without repeated approval. In auto mode, turn completed research into implementation tickets immediately. Put blockers first, then verified prefactoring and independent testable slices.
3. Before each concurrent batch, read the shared Worker/provider score:

   ```sh
   python3 nightshift/worker_runtime.py score-read --state nightshift/.worker-score.json
   ```

   | Score | Level | Required scope |
   | --- | --- | --- |
   | 5 | L1 macro | Largest bounded vertical slice; intent and targets; Worker selects files |
   | 3-4 | L2 meso | One module/seam; files, signatures, errors, deterministic verification; <=150 deleted lines |
   | 1-2 | L3 micro | One behavior; exact inputs/outputs, signatures, fixtures, expected results, red/green steps; <=40 deleted lines |

   Apply [tdd](../../engineering/tdd/SKILL.md). L1 deletions stay within targets. Lower scores narrow work, not score policy or the Worker/Planner ownership split. Keep actions independently reviewable; never prescribe formatting or bundle commands to evade budgets.
4. Queue blockers first:

   ```text
   TASK-ID | LEVEL: 1-3 | [AFTER: TASK-ID] | TARGET: paths | ACTION: behavior | VERIFY: command | FORBIDDEN_SHORTCUTS: ... | CONSTRAINTS: ...
   ```

   `[CODE: REFACTOR]` requires score >=3, <=5 files, nondecreasing assertions and proof deprecated symbols are gone. Otherwise use green-to-green `[CODE: EXPAND]`, `[CODE: MIGRATE]` or `[CODE: CONTRACT]` phases. Multi-interface refactors also require inseparable intermediate builds, a cohesive interface/implementation/test slice, current topology evidence and an L3 blueprint if score <3. Every 10 completed tasks, queue their review and an architecture review of hotspots in the last 20 commits.

Dispatch is complete when the bounded, verifiable graph is queued at the score's level. Reschedule with `nightshift/reorder_queue.sh`; honor `nightshift/PAUSE`.

## Wait and accept

Delegate a Queue Sentinel:

```sh
bash nightshift/watch_worker.sh 0 5 TASK-ID
```

Use a long notification-interruptible host wait. Expiry only renews waiting; local program checks do not invoke a model. Runtime owns execution deadlines. RUNNING, thinking and heartbeats require no Planner status/log reads or progress reports.

Deliver results after all workers executing that task leave RUNNING/VERIFYING; unrelated tasks may continue. Normalize kind tags separately from task identity, retain DONE until its audit arrives, and replay unreviewed pairs after observer restart/late start. Acknowledge after acceptance. If an observer exits without a result, resume its durable subscription; observer exit, timeout or stale status alone does not establish Worker failure.

Intervene on task completion, BLOCKED, FAIL, SCOPE_BLOCKED, failover or another decision event. A user status request or irrecoverable observer error also permits inspection.

On completion, read fresh task-scoped DONE and its matching MECHANICAL_AUDIT once, then inspect behavior, scope, evidence and reports. Require all:

```text
Status: PASS | Verify_Exit: 0 | Tests_Run: >=1 | Whitelist: PASS | Tree: CLEAN
```

Queue emptiness, stale DONE or another task's PASS proves nothing. Fast-track first-attempt HIGH results with passing audits; fast-forward only the authorized integration checkout. Investigate failures, retries, low confidence, critical seams and DEAD_END with focused diffs and [code-review](../../engineering/code-review/SKILL.md). Negative claims need isolated passing evidence. Archive accepted issue reports in `.reports/.archive/`.

Acceptance is complete when fresh DONE/audit match, evidence supports the requested scope/behavior, and one score result is recorded. After reverting a rejected commit, rebuild the [code index](../explore/SKILL.md#code-index).

## Recover and score

- On resume, review PASS audits marked `Planner_Review: pending`. Record accept/reject/no_fault with matching task ID, audit timestamp and progress file:

  ```sh
  python3 nightshift/worker_runtime.py score-record --state nightshift/.worker-score.json --task-id TASK-ID --audit-ns AUDIT-NS --progress-file nightshift/progress.log --result RESULT --evidence FILE#Lx
  ```

- NEED_GUIDANCE requires human clarification before requeueing with GUIDANCE. NEED_DECOMPOSITION requires narrower L2/L3 work. For exhausted budgets, inspect `nightshift/.scratch/failed_tasks/` and rewrite affected queue entries. BLOCKED requires a concrete unblock decision. After three blocked attempts, inspect exception logs, keep reusable quirks in `nightshift/.worker.notes.md` and narrow scope.
- Keep task IDs for unchanged retries; change IDs only with scope/granularity. CLOSEOUT_REQUIRED permits one verification/permitted-Git closeout of the original task. Remaining implementation fails that task; ghost closeout does not change score cadence.
- Before replacement dispatch, stop the failed attempt, restore its baseline, and acknowledge/revise the Sentinel handoff and queue. Clean Pivot requires fallout beyond two patch tickets or SCOPE_BLOCKED, plus explicit recovery authorization. Preserve unrelated work.
- Use no_fault for environment/scope failures, never implementation failures. Five consecutive eligible accepts raise the shared score by 1, up to 5; reject resets the streak; no_fault is excluded. Runtime counts timeout/action-budget exhaustion as hard failures, lowering score on the second and third occurrence for the same task ID, not later ones. Audited success clears that task's count. Planner may lower scores with evidence; manual increases are forbidden. Runtime owns arithmetic; humans choose models.
- Keep the daemon running through empty queues/failures. PAUSE stops future claims, not active work. Reserve RUN_ONCE=1 for explicit finite tests. Human controls: Continue, queue changes, PAUSE and reject/replan.

## Deliver a requested trial

Queue one ordinary TRIAL task at the next boundary, with program, project build command, executable check, delivery path, required files and evidence:

```sh
python3 nightshift/worker_runtime.py queue-insert --tasks nightshift/tasks.txt --task 'TRIAL-ID | LEVEL: 1 | TARGET: ... | ACTION: ... | VERIFY: ...'
```

The locked, task-ID-idempotent insertion preserves pending order. Let active work finish; normal daemon work continues afterward. Never replace a live queue from a stale snapshot.

Build the revision present at trial start in normal development output and verify it. Then copy binaries/safe resources to unique task staging, run that copy from its intended working directory, and write a manifest: source task/commit, version if available, exact checks/results, artifacts and working launch command. Atomically rename to `.trials/<TASK-ID>/`. Delivery must not symlink to development output. Retries may clean only their own staging/final directory. Failure removes that task's incomplete/final delivery and reports the repair target; never offer an older binary.

Audit runtime scripts, settings, environment, assets/data, services/databases, devices, ports and binary dependencies with platform tools and recorded observations. Classify resources:

- included: safe redistributable files packaged with the trial;
- shared: exact location, reason and possible development collision;
- unverified: missing proof.

Exclude secrets. Shared/unverified critical dependencies prevent an independent-delivery claim. Handoff includes delivery path/launch command, source task/revision/version, build/staged-run evidence, resource classifications/conflicts and concurrent-development support.

Recommend pause when development can alter/occupy shared resources or critical dependencies remain unverified; the user decides. Worker/trial never changes PAUSE. Read `nightshift/worker.sh` to resolve PAUSE_FILE: absolute as-is, relative to project, default `<project>/nightshift/PAUSE`. Give concrete commands using real paths, create the parent only if missing, and include `./nightshift/status.sh`. Explain pause affects new claims only; user verifies PAUSED with current task None before launch. Wait/recheck active work; promise neither immediate pause nor safety with critical unverified dependencies.

## Boundaries

Write tickets, progress and commits in English; write skills in ASCII. Workers execute in the project directory; honor targets, scope, pause and audits. Preserve existing changes. Before manual upgrade migration, inspect legacy `.worker-tree`, branches and `.preview` for unfinished work; installer preserves them.

Terminal A reads docs/skills, queues/reports and bounded Git metadata. Worker logs require the event gate above. Prefer `git show --stat`, `git log --oneline -n 20` and focused pointers. Source reads require L3 intervention after three Worker failures, repeated diagnostic hallucination or explicit user instruction; use `nightshift/extract_skeleton.sh path#Lline` and `nightshift/probe_line.sh path#Lline` rather than broad reads.

Never run unbounded history/diffs, push, clean, sudo, host package managers or unauthorized resets. Preserve unrelated work during recovery.
