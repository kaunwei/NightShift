---
name: sentinel
description: 0-Token Queue Sentinel for streaming background worker supervision.
---

# Queue Sentinel (0-Token Supervision)

Supervise background Worker tasks without consuming LLM context tokens or polling loops.

## Contract

1. **Zero-Token Streaming Wait (Queue-Level)**:
   Delegate active queue monitoring to the deterministic shell watcher WITHOUT specifying a single task ID:

       WORKER_INACTIVE_REPEAT=1 bash nightshift/watch_worker.sh 0 5

   Launch this via the host's background command execution. Terminal A (Planner) consumes 0 LLM tokens while the watcher runs.
2. **Autonomous Batch Progression (No Routine Wakeups)**:
   Worker automatically takes tasks sequentially from FIFO (`tasks.txt`). Individual task completions (`[DONE]` / `[MECHANICAL_AUDIT] PASS`) do NOT wake up Planner. Planner must NOT be interrupted for routine milestone checks while the queue is progressing normally.
3. **Reactive Wakeup Triggers**:
   Do NOT poll in a chat loop. End the agent turn and allow host notifications to wake Planner ONLY when intervention is required:
   - `[SENTINEL_COMPLETED]`: Entire task queue is empty (`IDLE` / `STOPPED` with all remaining tasks finished).
   - `[BLOCKED]` / `PAUSED_FOR_PLANNER` / `[SCOPE_BLOCKED]`: Worker encountered an unrecoverable failure or needs decomposition.
   - `[SENTINEL_INACTIVE]`: Worker heartbeat became stale and inactive across consecutive periods.
4. **Single-Task Debugging Exception**:
   Only pass a specific `TASK-ID` (`watch_worker.sh 0 5 TASK-ID`) during interactive manual single-ticket diagnosis or testing, never during unattended 24h queue drain.
5. **Inactivity Handling**:
   `[SENTINEL_INACTIVE]` is an observation, not a task failure. Relay an alert if needed and continue waiting.
   RUNNING/VERIFYING status resets the timer automatically.
