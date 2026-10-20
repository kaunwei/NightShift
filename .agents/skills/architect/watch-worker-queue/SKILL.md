---
name: watch-worker-queue
description: "Deploy a lightweight Sentinel Subagent to monitor the Terminal B worker daemon and trigger proactive wakeup when all tasks are complete."
---

# Watch Worker Queue

Deploy a lightweight Sentinel Subagent to monitor background execution and trigger proactive wakeup upon completion.

## When to Use
- After writing batch tasks to `tasks.txt`.
- When unattended event-driven notification is required.
- **NEVER use `sleep` or polling loops in chat.**

## Protocol

```
[Planner] Writes tasks to tasks.txt -> Deploys Queue Sentinel -> Yields control immediately.
   │
[Sentinel Subagent]
   • Runs: `bash scripts/watch_worker.sh 3600` (zero LLM token consumption while waiting).
   • On script exit: reads `head -n 15 progress.log` and notifies Planner.
   │
[Event Wakeup] -> Planner awakes and delivers acceptance report to Human.
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

## Acceptance & Merge Protocol

When Sentinel wakes Planner:
1. **Verify**: Planner reads `head -n 15 progress.log` and validates test status.
2. **Auto-Merge (`WORKER_ISOLATION=1`)**: Run `git merge --ff-only feature/worker-frontier` into `main`. Zero manual human git commands needed.
3. **In-Place Mode (`WORKER_ISOLATION=0`)**: Commits already on `main`. Deliver final status report.
