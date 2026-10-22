---
name: record-attempt-trace
description: "Guidelines for background worker to record transparent, honest execution attempts, retry traces, and confidence scores into progress.log."
---

# Record Attempt Trace

Truthfully record execution steps, retry attempts, and confidence scores into `progress.log`.

---

## 1. Core Standards
1. **Zero Concealment**: Record intermediate failures honestly in `Attempt Trace`. Never hide mistakes.
2. **Strict Limit**: Entries MUST be `<= 15 lines`. High-signal bullet points only; zero discursive prose.
3. **Pointers Over Prose**: Use exact file/line pointers (`src/module.py#L12-L30`).
4. **Confidence Metrics**:
   - `HIGH`: Tests passed 100%, 0 warnings, standard conventions.
   - `MEDIUM`: Tests passed, but required 1-2 retries to align fixtures/linkers.
   - `LOW`: Tests passed, but code feels brittle or edge cases remain unverified.
5. **No Guessing**: For contradictory specs or ambiguous interfaces, emit `[NEED_DECOMPOSITION]` or `[NEED_GUIDANCE]` immediately.
6. **Mechanical Verification Alignment**: Daemon mechanically audits tests and stamps `[MECHANICAL_AUDIT]` above this entry. Falsifying `Confidence` or `Attempts` triggers immediate cheating rejection.

---

## 2. Log Entry Template (<= 15 lines)

```text
================================================================================
[SUCCESS | BLOCKED] TASK-XXX: <Task Title>
Time: <Timestamp> | Duration: <Xs> | Attempts: <N>/3 | Confidence: <HIGH|MED|LOW>
Task Granularity: <Level 1|Level 2|Level 3>
Changes: <Files / Report path>
Verification: Build <PASS|FAIL>, Tests <PASS|FAIL> (<N> passed)
Attempt Trace:
  • Att 1: <PASS or failure reason with exact error summary>
  • Att 2/3: <Fix applied and result>
Notes: <Optional observations>
================================================================================
```
