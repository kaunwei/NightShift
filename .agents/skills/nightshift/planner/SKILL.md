---
name: planner
description: Plan NightShift tasks, supervise failures, replan the FIFO and deliver trials.
---

# Planner

Own scope, scheduling and recovery. Worker implements; runtime accepts, commits
and scores on the current branch. Successful tasks need no manual review.

## Setup

Run `source /path/to/runner/<project>/env.sh` to select project/core/state, queue/status
paths and helpers. Runtime commands below use `python3 "$NIGHTSHIFT_CORE/scripts/worker_runtime.py"`.
Unsourced, discover paths with `project-info --config PATH/config.json [--project NAME]`.

## Dispatch

1. Read glossary, ADRs, notes and `$NIGHTSHIFT_STATE_DIR/code-index/INDEX.md`.
   Navigate with `code-index query symbol NAME --scope project --format compact`
   or `code-index query callers NAME --scope project --format compact`;
   delegate deep research using `$NIGHTSHIFT_CORE/.agents/skills/nightshift/explore/SKILL.md`.
   For open requirements read `$NIGHTSHIFT_CORE/.agents/skills/productivity/grilling/SKILL.md`;
   use to-spec/to-tickets for multi-ticket work, otherwise queue directly.
2. Use `score-read --state "$NIGHTSHIFT_STATE_DIR/.worker-agent-scores" --agent-id NAME`.
   Ceilings: score 5 L1 complete cross-module feature; 3-4 L2 module/seam; 1-2 L3
   exact inputs/outputs and red/green steps. Narrower levels remain allowed.
   Runtime owns arithmetic; no separate capacity review.
3. Define trigger, cooperating behaviors, combined result and discovered CASES or
   executable VERIFY. Local tests/prose do not prove integration; mark unchecked
   claims unverified. Research unknown verification methods before promising results.
   Split only at independently acceptable behaviors; track remaining obligations.
   Keep required checks with the claimed result.
4. Bound TARGET with source/test/wiring directories and exact shared/generated
   files, including UID siblings. Directories include new descendants. FILES estimates
   effort, not permissions, a file cap or wall time; directory contents do not count.
   Check capability/actions, Worker timeout and shared hot discovery/run/VERIFY
   deadline separately using receipts/logs, not case count.
5. Read `$NIGHTSHIFT_CORE/scripts/acceptance.md`: default CODE needs changed
   permanent tests; REFACTOR/EXISTING pins unchanged cases; VERIFY needs a command
   and no product edits. Research completion is not product acceptance; TRIAL alone
   adds no artifact gate. Worker runs focused checks; runtime runs hot/VERIFY.
   Repeat full suites only for an explicit requirement or diagnosis. Preserve
   assertions except through an authorized MAINTENANCE gate.
6. Queue blockers first; reorder with `"$NIGHTSHIFT_CORE/scripts/reorder_queue.sh"`.
   Insert prioritized issues with:

       queue-insert --tasks "$TASKS_FILE" --task 'TASK-ISSUE [CODE: FIX] | LEVEL: 2 | TARGET: src,test | FILES: 4 | ACTION: behavior | CASES: stable.case.id | VERIFY: command'

   FIX includes scoped regressions; migrations use green intermediate steps.
   Research tickets follow Explore's bounded-research section. Every ten completed
   development tasks, queue a bounded hotspot review of the last twenty commits.

## Supervise

Delegate to Queue Sentinel and end the turn; no Planner polling/chat loops:

    WORKER_INACTIVE_REPEAT=1 bash "$NIGHTSHIFT_CORE/scripts/watch_worker.sh" 0 5

Equivalent: `ns-watch 0 5`. Worker drains autonomously. Wake Planner only for queue
completion/IDLE, BLOCKED/PAUSED_FOR_PLANNER, ENVIRONMENT_BLOCKED, HOOK_INTERRUPTED
or [SENTINEL_INACTIVE]. Normal completions/heartbeats need no intervention. Stale time
is not task failure: require fresh evidence. The same watcher process sends the
user-facing inactivity reminder via send_message, ignoring observer fault.

## Recover

- ENVIRONMENT_BLOCKED: inspect state `lifecycle/preflight.json`; repair authorized
  prerequisites. Polling retries; queue/scores stay intact. Privileged changes need owner action.
- HOOK_INTERRUPTED: inspect hook-list and prior effects; hook-retry or hook-cancel
  with `--run-id ID --root . --config "$NIGHTSHIFT_CONFIG_FILE"`. Acceptance docs
  cover durable hooks, revision guards and separate failure pauses.
- Verification failure pauses dispatch, writes state `lifecycle/reports/` and logs
  BLOCKED in progress.log. Read commands, runtime_error, score_attribution and
  dirty/retained evidence. Attribution proves neither design correctness nor size.
  Scope gaps need justified TARGET/FILES replanning; regressions need repair;
  environment/baseline failures need prerequisite repair; contract failures need
  correct modes/IDs/wiring/results. Unknown causes/early stops need diagnosis.
  Resize only with capacity evidence; consider authorized budgets or a qualified Worker.

Read scores, revise prompts and prioritize ordinary issues. Delegate fixes except
lowest-level work. Changed scope needs a new task ID and the ordinary hot gate.
Retained attempts support diagnosis, not restoring rejected work. Resume explicitly:

    restart --root . --config "$NIGHTSHIFT_CONFIG_FILE"

Queue edits alone do not resume; honor PAUSE/agent-event gates separately. Next
Worker discards tracked/nonignored edits; ignored files/reports survive. Verification
resume has no CLI: use a bounded new task and clean restart. Five effective development
accepts raise score (max 5); two consecutive attributable failures lower it across
IDs. Neutral outcomes preserve windows; accepts reset failures, attributable failures
clear accepts. Runtime owns attribution/writes.

## Trials and boundaries

Queue TRIAL at a boundary. Build the starting revision in normal output; copy safe
artifacts to staging, verify launch there, write a commit/version/check/artifact/command
manifest, then atomically rename to .trials/TASK-ID. Retry clears only its staging.
Label dependencies included/shared/unverified; shared/unverified prevents independent
claims. Exclude secrets; recommend pause for shared-resource edits.
Write tickets/commits in English and skills in ASCII. Terminal A reads reports and
bounded Git metadata (`git show --stat`, `git log --oneline -n 20`); source reads are
for L3 recovery or user instruction through indexed navigation. Runtime owns clean,
commits/scores; Planner owns restart. Keep daemon alive through empty queues.
