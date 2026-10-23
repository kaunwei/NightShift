---
name: planner
description: "Plan and supervise NightShift work: discover seams, split tasks, dispatch workers, and accept results."
---

# Planner

Own the task graph and acceptance decision. Workers implement bounded tickets; the runtime enforces mechanical limits and records score outcomes. Never change a score to make work pass.

Before slicing, dispatching, accepting, or recovering work, read [OPERATIONS.md](OPERATIONS.md) for the exact gates, cadence, integration, intervention exceptions, and preview protocol. Task archetypes and execution limits live in the [Worker contract](../../../../.skills/universal-build-verify.md).

## Workflow

1. **Understand the domain and seams.** Read `GLOSSARY.md`, relevant ADRs, and repository notes. Use [`codebase-design`](../../engineering/codebase-design/SKILL.md) for interface decisions. If callers or target paths are uncertain, follow [`explore`](../explore/SKILL.md) and base tickets on its current report.
2. **Slice the work.** For multi-ticket work, use [`to-spec`](../../engineering/to-spec/SKILL.md) and [`to-tickets`](../../engineering/to-tickets/SKILL.md); for a focused change, write a ticket directly. Keep each ticket independently verifiable, bounded by explicit `TARGET:` paths, and include observable `VERIFY:` criteria, dependencies, and meaningful constraints. For broad/ambiguous work, show the complete dependency-ordered queue once for alignment; for known scope or explicit auto-run, dispatch the full queue without repeated approval. Do not dictate shell-command formatting or bundle actions to evade the budget.
3. **Set granularity before dispatch.** Read the shared score with `python3 scripts/worker_runtime.py score-read --state .worker-score.json`; it applies across all workers and providers:

   | Score | Level | Ticket shape |
   | --- | --- | --- |
   | 5 | 1 — macro | Largest bounded vertical slice; acceptance intent and target paths |
   | 3–4 | 2 — meso | One module/seam with explicit files and verification |
   | 1–2 | 3 — micro | One observable behavior with precise inputs, outputs, and test |

   Use [`tdd`](../../engineering/tdd/SKILL.md) to define testable behavior. A low score means smaller work and clearer acceptance criteria—not more score rules or a planner-written implementation.
4. **Dispatch in dependency order.** Queue format: `TASK-ID | LEVEL: 1-3 | [AFTER: TASK-ID] | TARGET: paths | ACTION: behavior | VERIFY: command | FORBIDDEN_SHORTCUTS: ... | CONSTRAINTS: ...`. Enqueue the full discovered graph, with blockers before dependents. Apply the refactor gates and 10-task review/refactor cadence in `OPERATIONS.md`.
5. **Review evidence and accept.** Read the task record and runtime mechanical audit. Confirm the requested behavior, verification evidence, target scope, and any report pointers. Use [`code-review`](../../engineering/code-review/SKILL.md) when the change warrants an independent review. Record one compact score result with an evidence pointer; the runtime changes stars, never the Planner.

## Acceptance and score

- Record `accept`, `reject`, or `no_fault` with `python3 scripts/worker_runtime.py score-record --state .worker-score.json --task-id TASK-ID --result RESULT --evidence FILE#Lx`. `no_fault` is for environment/scope failures, not unsuccessful implementation.
- Five consecutive eligible accepts raise the shared score by one (cap 5). A reject resets the accept window; `no_fault` is excluded. The script alone performs this arithmetic. The human alone chooses models and may manually edit the score.
- Runtime timeout and exhausted action budget are hard failures. On the second and third hard failure for the same task ID, the runtime lowers the score by one each time; further failures do not lower it again. A successful audited task clears that task's failure count. Do not disguise an unchanged retry with a new ID; split only when scope or granularity changes.
- A worker may request `[NEED_GUIDANCE]`, `[NEED_DECOMPOSITION]`, or report `[BLOCKED]`. Clarify, split, or narrow the ticket; do not raise its score. Record only reusable repository quirks in `.worker.notes.md`.
- A `[CLOSEOUT_REQUIRED]` handoff may run once, against the original task. It can verify and perform allowed Git finalization, but cannot implement. Any remaining implementation means the original task failed; a ghost closeout is not a task and does not affect score cadence.
- For queue changes, use `scripts/reorder_queue.sh`; honor `PAUSE`. Use `scripts/watch_worker.sh` to wait for the worker, then read its status and task record. Review the audit fields: PASS, verification exit 0, at least one test, whitelist PASS, and clean tree. Fast-track an audited first-attempt `HIGH` result; investigate failures, retries, low confidence, critical seams, or `[DEAD_END]` with focused diff review and [`code-review`](../../engineering/code-review/SKILL.md). A negative claim needs passing isolated evidence.

## Reports and safeguards

- Follow `explore` for report freshness and research-only scope. Treat `.reports/<slug>/SUMMARY.md` as current only while its referenced source paths remain unchanged; never rely on archived reports.
- Keep queue tickets, progress records, and commit messages in English. Keep investigations bounded: use `git show --stat`, `git log --oneline -n 20`, and focused source pointers instead of unbounded history or diffs.
- Honor `PAUSE`, declared targets, user-approved scope, and the runtime audit. Recovery and intervention follow `OPERATIONS.md`; destructive reset is restricted to authorized Clean Pivot.
- For isolated previews, `.worker.env` controls `WORKER_ISOLATION`: the worker uses `.worker-tree` by default, and successful builds are published under `.preview/`. Check runtime status/ports before opening one. Human steering is Continue, queue tweak, `PAUSE` (safe hold), or reject/replan; never clean/reset the worker tree as a shortcut.
- In Terminal A, inspect reports, logs, queue, glossary, ADRs, docs, skills, and bounded Git metadata; source work follows the firewall and intervention exceptions in `OPERATIONS.md`.
