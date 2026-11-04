---
name: sentinel
description: Event-driven Queue Sentinel for background Worker supervision.
---

# Queue Sentinel

Select the Planner agent and exact conversation independently of the Worker
registration. Run one background watcher, then end the turn.

## Start

Codex Planner:

    WORKER_INACTIVE_REPEAT=1 bash nightshift/watch_worker.sh --agent codex --planner-id THREAD_ID 0 5

AgY Planner (existing print-mode CLI, explicit conversation):

    WORKER_INACTIVE_REPEAT=1 bash nightshift/watch_worker.sh --agent agy --planner-id CONVERSATION_ID 0 5

The relay dispatches actionable events using:
- Codex: `codex queue --thread ID --message EVENT --resume`.
- AgY: `agy --conversation ID -p EVENT`.

Use an authenticated local CLI and an exact target ID. AgY runs synchronously in
the relay; its conversation must be idle. Keep one watcher per Planner/queue pair
and stop its previous process before replacement. Agent routing never follows
Worker registration or falls back to another agent. Relay errors need recovery.
AgY argument routing is mock-tested; live continuation is unverified. Codex
blocked-event continuation was verified with an isolated fake Worker.

Legacy `watch_worker.sh 0 5` emits stdout only. Use it only with a separately
verified host integration; stdout alone does not start a Planner turn.
Positional arguments: timeout seconds, interval seconds, optional task ID.
Use queue-wide mode for batches; task ID is for single-ticket diagnosis.

## Events

Wake Planner only on:
- `[SENTINEL_COMPLETED]`: entire queue completed.
- Blocked, scope-blocked, paused-for-planner, no-response, worker-died, failed,
  or planner-review-required: inspect the report and follow planner Recover.
- `[SENTINEL_INACTIVE]`: relay the alert and keep waiting. Verify fresh evidence
  before treating inactivity as task failure.

Individual task completions and normal heartbeats do not enqueue Planner turns.
Keep supervision in the background rather than polling status in chat.
