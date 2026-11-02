---
name: sentinel
description: 0-Token Queue Sentinel for streaming background worker supervision.
---

# Queue Sentinel (0-Token Supervision)

Supervise background Worker tasks without consuming LLM context tokens or polling loops.

## Contract

1. **Zero-Token Streaming Wait**:
   Delegate active task monitoring to the deterministic shell watcher:

       WORKER_INACTIVE_REPEAT=1 bash nightshift/watch_worker.sh 0 5 TASK-ID

   Launch this via the host's background command execution. Terminal A (Planner) consumes 0 LLM tokens while the watcher runs.
2. **Reactive Wakeup**:
   Do NOT poll in a chat loop. End the agent turn and allow host notifications to wake Planner when:
   - `[SENTINEL_COMPLETED]`: Task completed and passed mechanical audit.
   - `[BLOCKED]` / `PAUSED_FOR_PLANNER`: Worker blocked or requested decomposition.
   - `[SENTINEL_INACTIVE]`: Worker heartbeat became stale.
3. **Inactivity Handling**:
   `[SENTINEL_INACTIVE]` is an observation, not a task failure. Relay an alert if needed and continue waiting.
   RUNNING/VERIFYING status resets the timer automatically.
4. **Completion Delivery**:
   A task is only done when verified by fresh mechanical audit evidence in `progress.log` and `tasks.done`.
