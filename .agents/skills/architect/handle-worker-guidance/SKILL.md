---
name: handle-worker-guidance
description: "Handle worker [NEED_GUIDANCE] and [NEED_DECOMPOSITION] requests cleanly without breaking queue automation."
---

# Handle Worker Guidance

Resolve worker questions, ambiguity reports, or decomposition proposals without breaking the 24h queue.

## Triggers
Activate when `progress.log` or `worker.status` indicates:
- `[NEED_GUIDANCE]`: Worker encountered an architectural contradiction or ambiguous specification.
- `[NEED_DECOMPOSITION]`: Worker rejected an oversized or multi-subsystem task.

## Workflow

### 1. Worker Requested Guidance (`[NEED_GUIDANCE]`)
1. Read `Question for Manager:` from `progress.log`.
2. Clarify decision with the human user: present trade-offs succinctly.
3. Prepend resolved task to `tasks.txt` with a `GUIDANCE:` field:
   ```text
   TASK-XXX | LEVEL: 2 | TARGET: <files> | ACTION: <logic> | GUIDANCE: <clarification> | VERIFY: <cmd> | CONSTRAINTS: <limits>
   ```

### 2. Worker Requested Decomposition (`[NEED_DECOMPOSITION]`)
1. Review proposed breakdown from `progress.log`.
2. Split original task into atomic `LEVEL: 2` or `LEVEL: 3` subtasks.
3. Prepend decomposed tasks to `tasks.txt`. Worker resumes automatically.

### 3. Worker Blocked (`[BLOCKED]` / 3 Failed Retries / Timeout)

Follow the Granularity Escalation Ladder:
- If task was **Level 1**: Demote to **Level 2** component slices. Re-queue in `tasks.txt`.
- If task was **Level 2**: Demote to **Level 3** micro-functions with exact signatures. Re-queue in `tasks.txt`.
- If task was **ALREADY at Level 3**:
  1. **Planner Sovereign Intervention**: Inspect `.worker.log` and target code directly.
  2. Apply surgical fix, verify tests, and commit.
  3. **Record Allocation Failure**: Log failure cause and compiler quirks in `docs/agents/granularity-profile.json` and `.worker.notes.md`.
