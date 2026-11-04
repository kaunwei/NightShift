---
name: sentinel
description: Relay Worker events to the selected Planner.
---

# Queue Sentinel

Choose the Planner agent and exact conversation ID, independently of Worker.
Run one background watcher per queue, then end the turn:

    bash nightshift/watch_worker.sh --agent codex --planner-id THREAD_ID 0 5
    bash nightshift/watch_worker.sh --agent agy --planner-id CONVERSATION_ID 0 5

Codex uses `queue --thread ID --message EVENT --resume`.
AgY uses `--conversation ID -p EVENT`; keep that conversation idle.
Both require an authenticated CLI. Stop the old watcher before replacement.
Legacy positional mode emits stdout only and needs a verified host relay.
Use `--help` for arguments. Batch runs omit task ID.

Handle only:
- Queue completed: deliver results.
- Blocked, failed, paused, dead, no response, or review required: planner Recover.
- Inactive: relay the alert and keep waiting; verify before declaring failure.

Normal progress requires no Planner turn. Relay errors require recovery.
Codex blocked-event wakeup is verified; AgY routing is mock-tested only.
