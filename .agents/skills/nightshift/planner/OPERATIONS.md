# Planner operations

Read before slicing, dispatching, accepting, or recovering a queue. These rules supplement the main workflow.

## Slicing and dispatch

- Maintain `GLOSSARY.md` and `docs/adr/` through `domain-modeling`; use `grilling` for unresolved requirements. Tests exercise agreed public seams, never private helpers.
- Read the shared score before **each concurrent batch**; new workers start at 5. L1 leaves internals to the Worker. L2 specifies files, signatures, error boundaries, and deterministic verification. L3 specifies exact signature changes, fixtures, expected results, and red/green/verify logic. Deletion ceilings are in the Worker contract.
- Prefer prefactoring followed by independently demoable end-to-end slices. Once seams are verified, enqueue **all** discovered tickets in dependency order; after research, expand its report into the full implementation queue immediately in auto mode.
- Track A: `[CODE: REFACTOR]` uses at most 5 files and score at least 3, with assertion non-decrease and structural verification that deprecated symbols are absent. Track B: more than 5 files or score 1 uses `[CODE: EXPAND]`, `[CODE: MIGRATE]`, `[CODE: CONTRACT]`, each green-to-green.
- Multi-interface/refactor authorization requires all four: splitting would break intermediate builds/tests; a cohesive interface → implementation → test slice; a Level 3 blueprint below score 3; topology proved by a current `[DIAGNOSTIC]` or `[RESEARCH]` report.
- Every 10 completed tasks, run `code-review` over those tasks and `improve-codebase-architecture` over the last 20 commits' hotspots; enqueue the resulting `[CODE: REFACTOR]` ticket.

## Waiting and acceptance

- Delegate a Queue Sentinel to run `bash scripts/watch_worker.sh 3600 5 TASK-ID` for the task being watched, then read its task-scoped result and report completed/blocked status. The watcher returns success only after a fresh `[DONE]` ledger entry and a matching `[MECHANICAL_AUDIT] Status: PASS | Task: TASK-ID` record; stale PASS entries cannot complete a watch. Use the available subagent interface; the watcher itself does not call a model while waiting.
- Audit line 1 must show `[MECHANICAL_AUDIT] Status: PASS | Task: TASK-ID | Verify_Exit: 0 | Tests_Run: >=1 | Whitelist: PASS | Tree: CLEAN`.
- Audit PASS + Attempts 1 + Confidence HIGH is the fast track (target ≤5 seconds, no model review): integrate the isolated frontier with `git merge --ff-only feature/worker-frontier` in the authorized integration checkout.
- Audit failure, retries, confidence below HIGH, `[DEAD_END]`, or a critical seam requires `git show --stat <commit>` and `code-review`. Preempt remedial FIX/REFACTOR tickets to queue line 1 with `scripts/reorder_queue.sh`. Negative claims need isolated passing evidence.
- After acceptance, archive the issue report under `.reports/.archive/`. Keep score arithmetic and ghost attribution as defined in the main skill.

## Feedback, recovery, and preview

- `[NEED_GUIDANCE]`: read the question in `progress.log`, obtain human clarification, and requeue with `GUIDANCE:`. `[NEED_DECOMPOSITION]`: split into L2/L3 tickets. `[BLOCKED]` after three attempts: inspect `progress.log`/`.worker.log`, capture actionable quirks, and narrow scope rather than reissuing the same broad contract.
- Clean Pivot is the session recovery branch when fallout needs more than two patch tickets or `[SCOPE_BLOCKED]` occurs: restore `nightshift-session-base` and reissue one unified slice. The legacy operation is `git reset --hard nightshift-session-base`; use it only within explicitly authorized recovery scope, preserving unrelated work. Reject routes here; it is never a general retry shortcut.
- Isolation 1: human checkout on `main` conventionally uses port 3000; Worker uses `.worker-tree`, branch `feature/worker-frontier`, and `PORT`/`TEST_PORT` 3001. Isolation 0 runs in place. Every PASS publishes code, `bin/`, `dist/`, `build/`, and `.preview/version.json` for checkout-free testing.
- Human steering: Continue; Tweak via queue reorder; Safe Hold via `PAUSE`; Reject via Clean Pivot. When requested, update `ADDITIONAL_DIRS`, `AI_MODEL`, `AI_EFFORT`, `WORKER_ISOLATION`, or `TASK_TIMEOUT` in `.worker.env` and confirm briefly; model choice remains human-owned.
- Terminal A normally reads only reports, queue/progress, notes, glossary, docs, and skills. Source-edit/read exceptions are L3 intervention after three Worker failures, repeated diagnostic hallucination, or explicit user mandate. Prefer bounded Git metadata and `scripts/extract_skeleton.sh path#Lline` / `scripts/probe_line.sh path#Lline`; never unbounded history/diffs, push, clean, sudo, host package managers, or resets outside authorized Clean Pivot.
