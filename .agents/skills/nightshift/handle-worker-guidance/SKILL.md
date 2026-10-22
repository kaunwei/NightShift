---
name: handle-worker-guidance
description: "Handle worker [NEED_GUIDANCE] and [NEED_DECOMPOSITION] requests cleanly without breaking queue automation."
---

# Handle Worker Guidance

Resolve worker questions, ambiguity reports, or decomposition proposals without breaking queue execution.

---

## 1. Triggers
Activate when `progress.log` or `worker.status` indicates:
- `[NEED_GUIDANCE]`: Worker hit an architectural contradiction or ambiguous requirement.
- `[NEED_DECOMPOSITION]`: Worker rejected an oversized or multi-subsystem task.
- `[BLOCKED]`: Worker failed 3 retry attempts or timed out.

---

## 2. Process

### 1. Resolve Ambiguity (`[NEED_GUIDANCE]`)
1. Read `Question for Manager:` from `progress.log`.
2. Clarify with human user; present trade-offs succinctly.
3. Prepend resolved task to `tasks.txt` with a `GUIDANCE:` field via `scripts/reorder_queue.sh`:
   ```text
   TASK-XXX | LEVEL: 2 | TARGET: <files> | ACTION: <logic> | GUIDANCE: <clarification> | VERIFY: <cmd> | CONSTRAINTS: <limits>
   ```

### 2. Decompose Oversized Task (`[NEED_DECOMPOSITION]`)
1. Review proposed breakdown from `progress.log`.
2. Split original task into atomic `LEVEL: 2` or `LEVEL: 3` subtasks.
3. Prepend decomposed tasks to `tasks.txt` via `scripts/reorder_queue.sh`. Worker resumes automatically.

### 3. Handle Blocked Tasks (`[BLOCKED]`)
Apply the Granularity Escalation Ladder:
- **Level 1 Failure**: Demote to **Level 2** component slices; re-queue.
- **Level 2 Failure**: Demote to **Level 3** micro-functions with exact TDD blueprints; re-queue.
- **Level 3 Failure (Sovereign Intervention)**:
  1. Inspect `.worker.log` and target code directly.
  2. Apply surgical fix, verify tests, and commit.
  3. Log root cause in `docs/agents/granularity-profile.json` and `.worker.notes.md`.
