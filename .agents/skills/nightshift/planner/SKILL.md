---
name: planner
description: "Plan and supervise NightShift work: discover seams, split tasks, dispatch workers, and accept results."
---

# Planner

Own the task graph and acceptance decision. Workers implement bounded tickets; the runtime enforces mechanical limits and records score outcomes. Never change a score to make work pass.

## Workflow

1. **Understand the domain and seams.** Read `GLOSSARY.md`, relevant ADRs, and repository notes. Use [`codebase-design`](../../engineering/codebase-design/SKILL.md) for interface decisions and [`grilling`](../../productivity/grilling/SKILL.md) for unresolved requirements. If callers or target paths are uncertain, follow [`explore`](../explore/SKILL.md) and base tickets on its current report.
2. **Slice the work.** For multi-ticket work, use [`to-spec`](../../engineering/to-spec/SKILL.md) and [`to-tickets`](../../engineering/to-tickets/SKILL.md); for a focused change, write a ticket directly. Each ticket needs explicit `TARGET:` paths, observable `VERIFY:` criteria, dependencies, and meaningful constraints. For broad or ambiguous work, show the complete dependency-ordered queue once for alignment; for known scope or explicit auto-run, dispatch the full queue without repeated approval. After research, expand its findings into the full implementation queue immediately in auto mode. Do not dictate command formatting or bundle actions to evade the budget.
3. **Set granularity before dispatch.** Read the shared score with `python3 scripts/worker_runtime.py score-read --state .worker-score.json`; it applies across all workers and providers:

   | Score | Level | Ticket shape |
   | --- | --- | --- |
   | 5 | 1 — macro | Largest bounded vertical slice; acceptance intent and target paths |
   | 3–4 | 2 — meso | One module/seam with explicit files and verification |
   | 1–2 | 3 — micro | One observable behavior with precise inputs, outputs, and test |

   Read the shared score before each concurrent batch. L1 leaves file choices to the Worker but bounds `TARGET:`; L2 names files, signatures, errors, and deterministic verification; L3 gives precise signatures, fixtures, expected results, and red/green steps. L3 deletes at most 40 lines, L2 150, and L1 is bounded by `TARGET:`. Use [`tdd`](../../engineering/tdd/SKILL.md) to define observable behavior. A low score means smaller tickets, not more score rules or Planner-written implementation.
4. **Dispatch in dependency order.** Queue format: `TASK-ID | LEVEL: 1-3 | [AFTER: TASK-ID] | TARGET: paths | ACTION: behavior | VERIFY: command | FORBIDDEN_SHORTCUTS: ... | CONSTRAINTS: ...`. Enqueue the full discovered graph, blockers first. Prefer a verified prefactor followed by independently demonstrable slices. Use `[CODE: REFACTOR]` only for at most 5 files at score 3+, with no assertion decrease and structural proof deprecated symbols are gone; larger or score-1 work uses green-to-green `[CODE: EXPAND]`, `[CODE: MIGRATE]`, or `[CODE: CONTRACT]` tickets. Multi-interface refactors need inseparable intermediate builds, one cohesive interface/implementation/test slice, a Level-3 blueprint below score 3, and topology evidence from a current diagnostic or research report. After every 10 completed tasks, queue a review of those tasks and an architecture review of the last 20 commits' hotspots.
5. **Review evidence and accept.** Read the task record and runtime mechanical audit. Confirm the requested behavior, verification evidence, target scope, and any report pointers. Use [`code-review`](../../engineering/code-review/SKILL.md) when the change warrants an independent review. Record one compact score result with an evidence pointer; the runtime changes stars, never the Planner.

## Acceptance and score

- Record `accept`, `reject`, or `no_fault` with `python3 scripts/worker_runtime.py score-record --state .worker-score.json --task-id TASK-ID --result RESULT --evidence FILE#Lx`. `no_fault` is for environment/scope failures, not unsuccessful implementation.
- Five consecutive eligible accepts raise the shared score by one (cap 5). A reject resets the accept window; `no_fault` is excluded. The script alone performs this arithmetic. The human alone chooses models and may manually edit the score.
- Runtime timeout and exhausted action budget are hard failures. On the second and third hard failure for the same task ID, the runtime lowers the score by one each time; further failures do not lower it again. A successful audited task clears that task's failure count. Do not disguise an unchanged retry with a new ID; split only when scope or granularity changes.
- `[NEED_DECOMPOSITION]` after action-budget exhaustion returns the failed task to Planner: inspect its snapshot under `.scratch/failed_tasks/`, narrow or split its scope, and send revised tickets through `tasks.txt`. Preserve the original ID for unchanged retries. Keep the daemon running; `PAUSE` holds claims until explicitly released. Empty queues and failed tasks are waiting states, not instructions to exit or restart the daemon. Use `RUN_ONCE=1` only for explicit finite tests.

- A worker may request `[NEED_GUIDANCE]`, `[NEED_DECOMPOSITION]`, or report `[BLOCKED]`. Clarify, split, or narrow the ticket; do not raise its score. Record only reusable repository quirks in `.worker.notes.md`.
- A `[CLOSEOUT_REQUIRED]` handoff may run once, against the original task. It can verify and perform allowed Git finalization, but cannot implement. Any remaining implementation means the original task failed; a ghost closeout is not a task and does not affect score cadence.
- An agent failover event pauses replacement dispatch after the failed attempt is stopped and its baseline restored. Review the watcher handoff and acknowledge or revise the affected queued work before allowing the replacement registration to start.
- For queue changes, use `scripts/reorder_queue.sh`; honor `PAUSE`. Delegate a Queue Sentinel to run `bash scripts/watch_worker.sh 3600 5 TASK-ID`, then read the task-scoped result and task record. Review the audit fields: PASS, verification exit 0, at least one test, whitelist PASS, and clean tree. Fast-track an audited first-attempt `HIGH` result; investigate failures, retries, low confidence, critical seams, or `[DEAD_END]` with focused diff review and [`code-review`](../../engineering/code-review/SKILL.md). A negative claim needs passing isolated evidence.
- A watched task is complete only with a fresh `[DONE]` ledger entry and a matching task-scoped `[MECHANICAL_AUDIT] Status: PASS`; an empty queue or old PASS is not evidence. The audit must report `Verify_Exit: 0`, `Tests_Run: >=1`, `Whitelist: PASS`, and `Tree: CLEAN`. Integrate a first-attempt HIGH result with fast-forward only in the authorized integration checkout; review failed, retried, low-confidence, dead-end, or critical-seam work before integration. Archive accepted issue reports under `.reports/.archive/`.

## Reports and safeguards

- Follow `explore` for report freshness and research-only scope. Treat `.reports/<slug>/SUMMARY.md` as current only while its referenced source paths remain unchanged; never rely on archived reports.
- Keep queue tickets, progress records, and commit messages in English. Keep investigations bounded: use `git show --stat`, `git log --oneline -n 20`, and focused source pointers instead of unbounded history or diffs.
- Honor `PAUSE`, declared targets, user-approved scope, and runtime audit. `[NEED_GUIDANCE]` requires human clarification before requeueing with `GUIDANCE:`; `[NEED_DECOMPOSITION]` becomes smaller L2/L3 tickets. After three blocked attempts, inspect task logs, capture reusable quirks, and narrow the ticket. Use Clean Pivot only when fallout exceeds two patch tickets or `[SCOPE_BLOCKED]` occurs, and only when that recovery is explicitly authorized; preserve unrelated work.
- Worker tasks run in the project directory. Treat existing `.worker-tree`, branches, and `.preview` as legacy data during upgrades: inspect them for unfinished work before manually migrating; the installer leaves them intact. Preserve unrelated and pre-existing project changes during recovery. Human steering is Continue, queue tweak, `PAUSE` (holds future claims), or reject/replan.
- In Terminal A, inspect reports, logs, queue, glossary, ADRs, docs, skills, and bounded Git metadata. Read source only for L3 intervention after three Worker failures, repeated diagnostic hallucination, or explicit user mandate; prefer `scripts/extract_skeleton.sh path#Lline` and `scripts/probe_line.sh path#Lline` over broad reads. Never use unbounded history/diffs, push, clean, sudo, host package managers, or unauthorized resets.
