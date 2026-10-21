---
name: watch-worker-queue
description: "Deploy a lightweight Sentinel Subagent to monitor the Terminal B worker daemon and trigger proactive wakeup when all tasks are complete."
---

# Watch Worker Queue

Deploy a lightweight Sentinel Subagent to monitor background worker execution and wake Planner upon completion without chat polling loops.

## Protocol

```
[Planner] Enqueue tasks -> Deploy Queue Sentinel -> Yield control immediately.
   │
[Sentinel Subagent]
   • Runs: `bash scripts/watch_worker.sh 3600` (zero token consumption while waiting).
   • On script exit: reads `head -n 15 progress.log` and notifies Planner.
   │
[Event Wakeup] -> Planner awakes and executes final acceptance.
```

## Invocation Payload

```json
{
  "Subagents": [
    {
      "TypeName": "self",
      "Role": "Queue Sentinel",
      "Prompt": "Run `bash scripts/watch_worker.sh 3600`. When it exits, read `head -n 15 progress.log` and report whether tasks completed successfully or if any task is blocked."
    }
  ]
}
```

## Acceptance & Merge

When Sentinel wakes Planner:
1. **Verify**: Check `head -n 15 progress.log` for passing `[MECHANICAL_AUDIT]`.
2. **Auto-Merge (`WORKER_ISOLATION=1`)**: Run `git merge --ff-only feature/worker-frontier` into `main`. Zero manual git operations needed.
3. **In-Place Mode (`WORKER_ISOLATION=0`)**: Commits already on `main`; present final summary to human.
