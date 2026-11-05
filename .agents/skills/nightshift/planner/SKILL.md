---
name: planner
description: Plan NightShift tasks, supervise failures, replan the FIFO and deliver trials.
---

# Planner

Own task scope, scheduling and explicit restart. Worker implements; runtime accepts,
commits and scores on the same current branch. Successful tasks need no manual review.

## Environment

Activate the project environment before operating:

    source /path/to/runner/<project>/env.sh

This sets working directory to project root, exports `$NIGHTSHIFT_CORE`, `$NIGHTSHIFT_STATE_DIR`,
`$TASKS_FILE`, `$TASKS_DONE_FILE`, `$PROGRESS_FILE`, `$STATUS_FILE`, and helpers (`ns-status`, `ns-watch`).
If running un-sourced, discover paths via:

    python3 "$NIGHTSHIFT_CORE/scripts/worker_runtime.py" project-info --config PATH/config.json [--project NAME]

## Dispatch

1. Read glossary, ADRs and notes. Read navigation map at `$NIGHTSHIFT_STATE_DIR/code-index/INDEX.md`
   or run script-directed function/symbol queries without broad source reads; queue
   [explore](../explore/SKILL.md) for deep research:

       python3 "$NIGHTSHIFT_CORE/scripts/worker_runtime.py" code-index query symbol NAME --scope project --format compact
       python3 "$NIGHTSHIFT_CORE/scripts/worker_runtime.py" code-index query callers NAME --scope project --format compact

   Open requirements use [grilling](../../productivity/grilling/SKILL.md); multi-ticket work
   uses to-spec/to-tickets. Routine tasks queue directly.
2. Read the selected registration's score:

       python3 "$NIGHTSHIFT_CORE/scripts/worker_runtime.py" score-read --state "$NIGHTSHIFT_STATE_DIR/.worker-agent-scores" --agent-id NAME

   Score 5: L1 vertical slice. Score 3-4: L2 one module/seam. Score 1-2: L3 exact
   behavior, inputs/outputs and red/green steps. Shrink scope as score falls.
3. Queue blockers first. Include product, tests and permanent hot wiring in TARGET:

       TASK-ID [CODE: FIX] | LEVEL: 2 | TARGET: src,test | ACTION: behavior | CASES: stable.case.id | VERIFY: command

   Reorder through `"$NIGHTSHIFT_CORE/scripts/reorder_queue.sh"`. Insert prioritized issue tasks with:

       python3 "$NIGHTSHIFT_CORE/scripts/worker_runtime.py" queue-insert --tasks "$TASKS_FILE" --task 'TASK-ISSUE | LEVEL: 2 | TARGET: src,test | ACTION: fix issue | VERIFY: command'

   Use green intermediate phases for interface migrations. Every ten completed
   development tasks, queue a bounded hotspot review of the last twenty commits.

## Supervise

Delegate queue monitoring to Queue Sentinel and end the turn. Never poll status or chat loops.

    WORKER_INACTIVE_REPEAT=1 bash "$NIGHTSHIFT_CORE/scripts/watch_worker.sh" 0 5

(In sourced shell: `ns-watch 0 5`).

Worker owns execution and drains tasks autonomously. Wake Planner only on:
- `[SENTINEL_COMPLETED]`: Entire queue drained (`IDLE`).
- `[BLOCKED]` / `PAUSED_FOR_PLANNER`: Unrecoverable failure or needs decomposition.
- `[SENTINEL_INACTIVE]`: Stale heartbeat; send a user-facing inactivity reminder using send_message from the same watcher process, ignoring observer fault.

Normal task completions and heartbeats require zero Planner intervention. Stale timeout is not task failure-require fresh evidence before acting.

## Recover

On verification failure, the runtime automatically pauses dispatch and records a diagnostic
report under `$NIGHTSHIFT_STATE_DIR/reports/` (and logs `[BLOCKED]` in `$PROGRESS_FILE`). Execution remains
paused until Planner reviews the report, replans the FIFO queue, and explicitly resumes.

1. Read the failure report under `$NIGHTSHIFT_STATE_DIR/reports/`. Inspect dirty files before
   restart if needed.
2. Read scores, revise prompts and use scheduling scripts to put ordinary issue
   tasks as early in FIFO as possible:

       python3 "$NIGHTSHIFT_CORE/scripts/worker_runtime.py" queue-insert --tasks "$TASKS_FILE" --task 'TASK-ISSUE | LEVEL: 2 | TARGET: src,test | ACTION: fix issue | VERIFY: command'

   Delegate fixes except lowest-level work. A changed scope uses a new task ID.
   Repairs use the ordinary hot gate.
3. Explicitly resume after replanning:

       python3 "$NIGHTSHIFT_CORE/scripts/worker_runtime.py" restart --root . --config "$NIGHTSHIFT_CONFIG_FILE"

   Honor configured PAUSE and agent-event gates separately. Queue edits alone do
   not resume; dispatch remains paused until `restart`. Next Worker discards
   tracked/nonignored uncommitted work; ignored files and reports survive.
   Failed patches are not stashed or continued.

Five accepted tasks raise score by one (max five); failure resets the streak.
Existing timeout/budget penalties remain. Read
`$NIGHTSHIFT_CORE/scripts/acceptance.md` for hook setup,
TDD evidence, cadence and restart state.

## Trials

Queue a TRIAL at the next boundary. Build the starting revision in normal development
output; copy safe artifacts to staging, verify launch from the intended directory,
write a manifest (commit, version, checks, artifacts, command), then atomically rename
to .trials/TASK-ID. Retry clears only its staging directory. Classify dependencies
as included/shared/unverified; shared or unverified inputs prevent independent
claims. Exclude secrets. Recommend pause when development touches shared resources.

## Boundaries

Write tickets/commits in English and skills in ASCII. Terminal A reads reports and bounded
Git metadata (`git show --stat`, `git log --oneline -n 20`). Read source files only for
L3 recovery or user instruction, using code-index queries.
Runtime owns clean, commit and score writes. Keep daemon alive through empty queues;
Planner owns restart.
