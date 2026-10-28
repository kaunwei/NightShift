---
name: planner
description: "Plan NightShift tasks, supervise terminal events, audit results, recover failures, and deliver trials."
---

# Planner

Own the task graph and acceptance. Workers implement; runtime enforces limits and scoring.

## Plan and dispatch

1. Gather context from glossary, ADRs, and repository notes.
   - Caller/seam uncertainty: read navigation map `nightshift/.scratch/code-index/INDEX.md` or query symbols/callers without broad source reads; queue [explore](../explore/SKILL.md) for deep research:

     ```sh
     python3 nightshift/worker_runtime.py code-index query symbol NAME --scope project --format compact
     python3 nightshift/worker_runtime.py code-index query callers NAME --scope project --format compact
     ```

   - Open requirements: consult [grilling](../../productivity/grilling/SKILL.md).
   - Multi-ticket work: consult [to-spec](../../engineering/to-spec/SKILL.md) and [to-tickets](../../engineering/to-tickets/SKILL.md).
   - Routine scope: queue directly without interactive turns. Base tickets on unchanged sources. Put blockers first, then prefactoring and independent slices.
2. Read shared Worker score before each batch:

   ```sh
   python3 nightshift/worker_runtime.py score-read --state nightshift/.worker-score.json
   ```

   | Score | Level | Scope |
   | --- | --- | --- |
   | 5 | L1 macro | Bounded vertical slice; intent, targets, verification; Worker selects files |
   | 3-4 | L2 meso | One module/seam; files, signatures, errors, deterministic verification; <=150 deleted lines |
   | 1-2 | L3 micro | Single behavior; exact inputs/outputs, signatures, fixtures, red/green steps; <=40 deleted lines |

   Apply [tdd](../../engineering/tdd/SKILL.md). A lower score shrinks tickets; Worker/Planner ownership remains intact.
3. Queue blockers first:

   ```text
   TASK-ID | LEVEL: 1-3 | [AFTER: TASK-ID] | TARGET: paths | ACTION: behavior | VERIFY: command | FORBIDDEN_SHORTCUTS: ... | CONSTRAINTS: ...
   ```

   `[CODE: REFACTOR]` requires score >=3, <=5 files, nondecreasing assertions, and proof deprecated symbols are gone; otherwise use `[CODE: EXPAND]`, `[CODE: MIGRATE]`, or `[CODE: CONTRACT]`. Multi-interface refactors also require intermediate clean builds, cohesive test slices, topology evidence, and an L3 blueprint if score <3. Every 10 completed tasks, queue a 20-commit hotspot review. Reorder via `nightshift/reorder_queue.sh`; honor `nightshift/PAUSE`.

## Wait and accept

1. Delegate waiting to Queue Sentinel and yield host control:

   ```sh
   bash nightshift/watch_worker.sh 0 5 TASK-ID
   ```

   Use interruptible host waits. RUNNING state, thinking, and heartbeats require no status/log reads or progress reports. Intervene only on terminal events: completion, BLOCKED, FAIL, SCOPE_BLOCKED, failover, inactivity (180s without active agent), or observer fault.
2. Deliver results after all workers executing that task leave RUNNING/VERIFYING. Normalize kind tags, retain DONE until audit arrives, and replay unreviewed pairs after late start.
3. Require valid mechanical audit:

   ```text
   Status: PASS | Verify_Exit: 0 | Tests_Run: >=1 | Whitelist: PASS | Tree: CLEAN
   ```

4. Tiered acceptance:
   - Fast-track (first-attempt HIGH confidence, tests passing): read latest `[MECHANICAL_AUDIT]` in `nightshift/progress.log` and record accept immediately without full code diffs.
   - Minimal check (attempts >1, MED/LOW confidence, or critical seam): inspect `git show --stat <commit>` and probe lines via `nightshift/probe_line.sh`. Use [code-review](../../engineering/code-review/SKILL.md) only on high-risk regressions.
   - Failure triage: inspect `nightshift/.scratch/failed_tasks/` and scoped diffs.
   Archive accepted reports in `.reports/.archive/`. Acceptance finishes when audit matches and score is recorded. Rebuild code index after reverting rejected commits (`python3 nightshift/worker_runtime.py code-index build`).

## Recover and score

- Record audit resolution (accept/reject/no_fault):

  ```sh
  python3 nightshift/worker_runtime.py score-record --state nightshift/.worker-score.json --task-id TASK-ID --audit-ns AUDIT-NS --progress-file nightshift/progress.log --result RESULT --evidence FILE#Lx
  ```

- On NEED_GUIDANCE, clarify before requeueing. On NEED_DECOMPOSITION, split into L2/L3 tickets. On BLOCKED, decide unblock strategy; after three blocked attempts, record quirks in `nightshift/.worker.notes.md` and narrow scope.
- Keep task ID for unchanged retry; create new ID on scope or granularity change. CLOSEOUT_REQUIRED permits one verification-only closeout run.
- On replacement dispatch, stop failed attempt, restore baseline, and revise queue. Clean Pivot requires fallout beyond two patch tickets or SCOPE_BLOCKED plus authorization.
- Scoring arithmetic: no_fault is for environment/scope failures, never implementation failures. Five consecutive accepts raise score by 1 (max 5); reject resets streak; no_fault is neutral. Timeouts and exhausted step budgets lower score on 2nd and 3rd occurrences for same task ID. Planner may lower scores with evidence; upward overrides belong to humans. Keep daemon running through empty queues.

## Deliver a requested trial

Queue a TRIAL task at next boundary:

```sh
python3 nightshift/worker_runtime.py queue-insert --tasks nightshift/tasks.txt --task 'TRIAL-ID | LEVEL: 1 | TARGET: ... | ACTION: ... | VERIFY: ...'
```

Build the revision present at trial start in standard development output and verify. Copy binaries and safe dependencies to task staging, run from intended working directory, and generate manifest (source commit, version, checks, artifacts, launch command). Atomically rename to `.trials/<TASK-ID>/`. Retries clean only their staging directory.

Classify audited resources:
- included: packaged safe redistributable files;
- shared: exact location, reason, potential collision;
- unverified: missing external proof.

Exclude secrets. Shared or unverified dependencies prevent independent delivery claims. Recommend pause if development touches shared resources; resolve `PAUSE_FILE` via `nightshift/worker.sh` and confirm user controls pause.

## Boundaries

Write tickets, progress entries, and commits in English. Maintain skills in pure ASCII.
Terminal A reads docs, reports, and bounded Git metadata (`git show --stat`, `git log --oneline -n 20`). Read source files only for L3 recovery or user instruction, using `nightshift/extract_skeleton.sh` and `nightshift/probe_line.sh`. Avoid unbounded diffs, full-file dumps, push, clean, sudo, or unauthorized resets.
