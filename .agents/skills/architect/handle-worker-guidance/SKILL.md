---
name: handle-worker-guidance
description: "Handle worker [NEED_GUIDANCE] and [NEED_DECOMPOSITION] requests cleanly without breaking queue automation."
---

# Handle Worker Guidance Skill (Architect AI)

This skill teaches the Interactive Architect AI (Terminal A) how to process worker questions, ambiguity reports, or decomposition proposals without disrupting the automated pipeline.

---

## When to Use
Activate this skill when `progress.log` or `worker.status` indicates:
- `[NEED_GUIDANCE]`: Worker found an architectural ambiguity or conflicting specification.
- `[NEED_DECOMPOSITION]`: Worker evaluated a Level 1 task and determined it spans too many subsystems.

---

## Handling Workflow

### Case 1: Worker requested Guidance (`[NEED_GUIDANCE]`)
1. Read the exact question under `Question for Manager:` in `progress.log`.
2. Consult the human user in Traditional Chinese (繁體中文):
   > "Worker 在執行 TASK-XXX 時暫停求助，詢問：[問題摘要]。建議我們選擇 [選項A / 選項B]，您同意嗎？"
3. Upon human decision, formulate the clarification.
4. Prepend the updated task back to `tasks.txt` with a `GUIDANCE:` field:
   ```text
   TASK-XXX | LEVEL: 2 | TARGET: <files> | ACTION: <action> | GUIDANCE: <Resolution to the question> | VERIFY: <cmd> | CONSTRAINTS: <limits>
   ```

### Case 2: Worker requested Decomposition (`[NEED_DECOMPOSITION]`)
1. Read the worker's proposed subtask breakdown from `progress.log`.
2. Review the breakdown with the human user.
3. Replace the original oversized task in `tasks.txt` with the decomposed subtasks (tagged `LEVEL: 2` or `LEVEL: 3`).
4. Worker will automatically pop the first subtask within 5 seconds.

---

### Case 3: Worker Blocked (`[BLOCKED]` / 3 Retries Failed / Timeout)

When a task fails or blocks, Planner must NOT impulsively jump in to write code. Instead, Planner follows the **Granularity Escalation Ladder**:

```
[Worker Blocked]
       │
       ▼
Task at Level 1? ──► Demote to Level 2 (Split into module slices) ──► Re-queue in tasks.txt
       │ (No)
       ▼
Task at Level 2? ──► Demote to Level 3 (Exact function signatures & steps) ──► Re-queue in tasks.txt
       │ (No)
       ▼
Task ALREADY at Level 3 (Micro)?
       │ (YES)
       ▼
【Planner Sovereign Intervention Triggered】
 1. Planner investigates error logs (.worker.log) and code directly.
 2. Planner applies surgical fix, runs test suite, and commits.
 3. Post-Mortem Retro: Planner records WHY the allocation failed in:
    • `docs/agents/granularity-profile.json` (subsystem rating & notes)
    • `.worker.notes.md` (compiler/repo quirks discovered)
    ➔ Permanently enhances future task allocation efficiency!
```

1. **Step 1: Check Current Granularity Level**:
   - If task was **Level 1 (Coarse)**: Scope was likely too broad. Demote and split into discrete **Level 2 (Medium)** tasks. Re-queue in `tasks.txt`.
   - If task was **Level 2 (Medium)**: Component logic was ambiguous. Demote to **Level 3 (Micro)** with exact function-level instructions and explicit `VERIFY:` tests. Re-queue in `tasks.txt`.

2. **Step 2: Level 3 Threshold ➔ Planner Sovereign Intervention (親自介入門檻)**:
   - If the task was **ALREADY at Level 3 (Micro)** and Worker STILL failed after 3 retries:
     - The problem is no longer task sizing—it is a deep architectural contradiction, compiler quirk, or edge-case bug exceeding the smaller model's context capacity.
     - **Planner Steps In**: Planner reads `.worker.log`, directly inspects the target files, applies the surgical fix, runs verification tests, and commits.

3. **Step 3: Post-Mortem Allocation Retro (復盤與分配能力校準)**:
   - After Planner resolves the Level 3 blocker, Planner **MUST record why the allocation failed**:
     - Update `docs/agents/granularity-profile.json` (set score to 1-2 stars, document specific failure mode).
     - Update `.worker.notes.md` (record the non-obvious build flag, API quirk, or compiler behavior discovered).
   - This calibration loop ensures Planner's future task decomposition becomes progressively sharper and more efficient.

