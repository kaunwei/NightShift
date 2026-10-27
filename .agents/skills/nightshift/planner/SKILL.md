---
name: planner
description: "Plan and supervise NightShift: research seams, dispatch scored tickets, handle Sentinel exceptions, audit results, and deliver trials."
---

# Planner

Own the task graph and acceptance decisions. Workers implement bounded tickets; the runtime enforces limits and score arithmetic.

## 1. Plan and dispatch

1. **Ground the work.** Read `GLOSSARY.md`, relevant ADRs, and repository notes. Use
   [`codebase-design`](../../engineering/codebase-design/SKILL.md) for interfaces,
   [`grilling`](../../productivity/grilling/SKILL.md) for open requirements, and
   [`explore`](../explore/SKILL.md) when callers/targets are uncertain. For source navigation, use
   `nightshift/.scratch/code-index/INDEX.md` after script approval; follow Explore's [code
   index](../explore/SKILL.md#code-index) for queries or dirty-input recovery. Base tickets on a
   *current* explore report: `.reports/<slug>/SUMMARY.md` is fresh only while its referenced source
   paths are unchanged; archived reports are never current. Research changes no implementation
   files.
2. **Define the graph.** Use [`to-spec`](../../engineering/to-spec/SKILL.md) and [`to-tickets`](../../engineering/to-tickets/SKILL.md) for multi-ticket work; write focused tickets directly. Every ticket specifies `TARGET:` paths, `VERIFY:` observable criteria, dependencies, and constraints. Show a broad/ambiguous dependency-ordered queue once for alignment; for known scope or auto-run, enqueue the entire graph without repeated approval. In auto mode, immediately expand completed research into implementation tickets. Put blockers first; prefer a verified prefactor followed by independently testable slices. Never prescribe command formatting or bundle actions to evade budgets.
3. **Set granularity.** Before each concurrent batch, read the score shared by all Workers/providers:

   `python3 nightshift/worker_runtime.py score-read --state nightshift/.worker-score.json`

   | Score | Level | Ticket requirement |
   | --- | --- | --- |
   | 5 | L1 macro | Largest bounded vertical slice; intent and `TARGET:` paths; Worker chooses files |
   | 3–4 | L2 meso | One module/seam; files, signatures, errors, deterministic verification; ≤150 deleted lines |
   | 1–2 | L3 micro | One behavior; exact inputs/outputs, signatures, fixtures, expected results, red/green steps; ≤40 deleted lines |

   Apply [`tdd`](../../engineering/tdd/SKILL.md). A lower score shrinks tickets; it never authorizes more score rules or Planner implementation. L1 deletion remains bounded by `TARGET:`.
4. **Queue in dependency order** using `TASK-ID | LEVEL: 1-3 | [AFTER: TASK-ID] | TARGET: paths | ACTION: behavior | VERIFY: command | FORBIDDEN_SHORTCUTS: ... | CONSTRAINTS: ...`. Use `[CODE: REFACTOR]` only at score ≥3 and ≤5 files, with nondecreasing assertions and structural proof that deprecated symbols are gone. Otherwise use green-to-green `[CODE: EXPAND]`, `[CODE: MIGRATE]`, or `[CODE: CONTRACT]`. Multi-interface refactors require inseparable intermediate builds, a cohesive interface/implementation/test slice, topology evidence from a current diagnostic/research report, and an L3 blueprint when score <3. After each 10 completed tasks, queue a review of those tasks and an architecture review of hotspots in the last 20 commits.

**Dispatch complete when:** the dependency graph is queued, every ticket is bounded and verifiable, and the batch level matches the shared score. Use `nightshift/reorder_queue.sh` for later queue changes; honor `nightshift/PAUSE`.

## 2. Sentinel supervision — event gate

Delegate a Queue Sentinel to run `bash nightshift/watch_worker.sh 3600 5 TASK-ID`.

**Once the Sentinel starts, switch to event-driven supervision. `RUNNING` and heartbeat are non-events: do not read logs, poll status (or equivalent state), or send the user progress reports because of them.** Intervene **only** on a Sentinel-reported `BLOCKED`, `FAIL`, `SCOPE_BLOCKED`, failover, another event requiring a Planner decision, or a completion result.

**On completion, perform one task-scoped acceptance check:** read the fresh `[DONE]` ledger entry and its matching `[MECHANICAL_AUDIT]` record **once**, then inspect task evidence, requested behavior, scope, and referenced reports. Passing requires `Status: PASS`, `Verify_Exit: 0`, `Tests_Run: >=1`, `Whitelist: PASS`, and `Tree: CLEAN`. An empty queue, stale DONE, or another task's PASS is not completion evidence.

Fast-track a first-attempt `HIGH` result with a passing audit; fast-forward integration **only** in the authorized integration checkout. Investigate failures, retries, low confidence, critical seams, and `[DEAD_END]` using focused diffs and [`code-review`](../../engineering/code-review/SKILL.md) as warranted. Negative claims require passing isolated evidence. Archive accepted issue reports under `.reports/.archive/`.

**Acceptance complete when:** the task-scoped audit matches fresh DONE, the requested behavior and scope are supported by evidence, and a single score result is recorded.

If acceptance fails and the committed change is reverted, run the index check/build after the rollback with `python3 nightshift/worker_runtime.py code-index build`.

## 3. Exceptions, recovery, and score

- On resumption, inspect PASS audit records with `Planner_Review: pending` in the configured progress log.
- After review, record the result with `score-record` and the matching `--task-id`, `--audit-ns`, and `--progress-file` values.
- **Worker requests:** `[NEED_GUIDANCE]` needs human clarification before requeueing with `GUIDANCE:`; `[NEED_DECOMPOSITION]` needs narrower L2/L3 tickets. For budget exhaustion, inspect `nightshift/.scratch/failed_tasks/` and rewrite the affected `nightshift/tasks.txt` entries. `[BLOCKED]` requires a concrete unblock decision. After three blocked attempts, inspect the *exception* logs, retain only reusable quirks in `nightshift/.worker.notes.md`, and narrow scope; never compensate by raising score.
- **Identity and closeout:** Keep the same task ID for unchanged retries; new IDs require changed scope/granularity. `[CLOSEOUT_REQUIRED]` may run once for the original task, for verification/permitted Git finalization only. Remaining implementation fails the original task; ghost closeout does not affect score cadence.
- **Failover and scope:** Before replacement dispatch, stop the failed attempt, restore its baseline, and review/acknowledge or revise the Sentinel handoff and queued work. Use Clean Pivot only when fallout exceeds two patch tickets or `[SCOPE_BLOCKED]` occurs, with explicit recovery authorization. Preserve unrelated changes.
- **Score:** Record `accept`, `reject`, or `no_fault` with `python3 nightshift/worker_runtime.py
  score-record --state nightshift/.worker-score.json --task-id TASK-ID --result RESULT --evidence
  FILE#Lx`. Use `no_fault` for environment/scope failures, never failed implementation. Five
  consecutive eligible accepts increase the shared score by 1 (max 5); reject resets the streak;
  `no_fault` is excluded. Timeout/action-budget exhaustion are hard failures: the runtime decreases
  score by 1 on the second and third hard failure of the *same task ID*, not later failures; audited
  success clears that task's count. Planner may lower scores with recorded evidence; manual
  increases are forbidden. Runtime handles automatic scoring; humans select models.
- **Daemon and pause:** Empty queue/failed task means wait, not daemon shutdown or restart. Keep the daemon running; `nightshift/PAUSE` stops future claims until released, not an active task. `RUN_ONCE=1` is reserved for explicit finite tests. Human controls are Continue, queue change, `nightshift/PAUSE`, and reject/replan.

## 4. On-demand trial delivery

On a user's request to try the current program, queue **one ordinary `TRIAL-...` task** for the next boundary, specifying program, project build command, executable check, delivery path, required files, and evidence. Insert ahead of pending tasks:

```sh
python3 nightshift/worker_runtime.py queue-insert --tasks nightshift/tasks.txt --task 'TRIAL-ID | LEVEL: 1 | TARGET: ... | ACTION: ... | VERIFY: ...'
```

`queue-insert` holds the claim queue lock, reads the live queue, and is idempotent by task ID. Let the active task finish first; the idle Worker then claims the trial while remaining tasks keep order. Never overwrite the queue from a stale snapshot. The daemon continues normal work afterward.

**Build and isolate.** Deliver the revision present when the trial task starts. Build in normal development output and run the project-specific build/executable checks; only then copy binaries and safe resources into a unique task-scoped staging directory. Run the staged copy from its intended working directory. After successful checks, write a manifest (source task/commit, version if available, exact checks/results, artifacts, working launch command), then atomically rename the finished directory to `.trials/<TASK-ID>/`. Use no symlink to development output. A retry may clean only its own staging/final directory, never another trial. On failure, remove that task's incomplete/final delivery, report the failure and repair target, and never refer to an older binary.

**Audit runtime dependencies.** With appropriate platform tools, record commands and observations for scripts, settings, environment variables, assets/data, services/databases, devices, ports, and binary dependencies. Classify each required resource as **included** (package safe redistributable files), **shared** (give exact path/location, reason, and potential development collision), or **unverified** (state missing proof). Never package secrets or claim an independent trial while shared/unverified critical requirements remain.

**Hand off to the user.** Report `.trials/<TASK-ID>/`, launch command, source task/revision/version, build and staged runnable evidence, included/shared/unverified resources and conflicts, and whether concurrent development is supported. Recommend pausing if development can alter/occupy a required shared resource or a critical dependency is unverified; **the user decides**. The Worker/trial never sets or removes `nightshift/PAUSE`.

For a recommended pause, read `nightshift/worker.sh` and resolve `PAUSE_FILE` exactly (absolute as-is; relative to project; default `<project>/nightshift/PAUSE`). Give a concrete command with real project/pause paths, creating the parent directory only if missing, plus `./nightshift/status.sh`. Explain that pause affects *new claims*, not active work; the user verifies `Worker State : PAUSED` and current task `None` before launching the trial. An active task requires waiting and checking again; never promise immediate pause or safety with critical unverified resources.

## 5. Operating boundaries

- Keep tickets, progress records, and commits in English. Worker execution occurs in the project directory. Honor targets, approved scope, pause state, and runtime audits; preserve pre-existing changes. During upgrades, inspect legacy `.worker-tree`, branches, and `.preview` for unfinished work before manual migration; the installer leaves them intact.
- **Terminal A:** read glossary, ADRs, docs, skills, queues, reports, and bounded Git metadata; read Worker logs **only when the Sentinel event gate permits**. Prefer `git show --stat`, `git log --oneline -n 20`, and focused pointers. Read source only for L3 intervention after three Worker failures, repeated diagnostic hallucination, or explicit user instruction; use `nightshift/extract_skeleton.sh path#Lline` and `nightshift/probe_line.sh path#Lline` instead of broad reads.
- Never run unbounded history/diffs, `push`, `clean`, `sudo`, host package managers, or unauthorized resets. Preserve unrelated work in every recovery.
