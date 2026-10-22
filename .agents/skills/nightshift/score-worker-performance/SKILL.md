---
name: score-worker-performance
description: "Score worker execution performance (1 to 5 stars) from progress.log audit traces and update docs/agents/granularity-profile.json automatically."
---

# Score Worker Performance

Audit worker execution traces from `progress.log` and calibrate module capability ratings in `docs/agents/granularity-profile.json`.

---

## 1. Scoring Rubric

| Score | Rating | Criteria | Granularity Action |
| :---: | :--- | :--- | :--- |
| ⭐⭐⭐⭐⭐ | **5 Stars** | Passed in 1 attempt (0 retries), clean diff, 0 warnings. | Maintain / Promote to Level 1. Worker is autonomous. |
| ⭐⭐⭐⭐ | **4 Stars** | Passed in 2 attempts (1 self-healed retry), green tests. | Maintain current Level (1 or 2). |
| ⭐⭐⭐ | **3 Stars** | Passed on 3rd attempt (2 retries needed). | Demote subsequent tasks in this module to Level 2. |
| ⭐⭐ | **2 Stars** | Raised `[NEED_GUIDANCE]` or `[NEED_DECOMPOSITION]`. | Demote to Level 2/3, provide guidance. |
| ⭐ | **1 Star** | Blocked after 3 retries, timed out, crashed, or caught by anti-cheating guard. | Demote to Level 3. Re-architect with user. |

> [!NOTE]
> **No-Fault Exemption (`[SCOPE_BLOCKED]`)**: When Worker halts honestly upon discovering compiler errors in downstream files outside declared `TARGET:`, this is boundary compliance, NOT a failure. Do NOT deduct stars in `granularity-profile.json`.

---

## 2. Process

1. **Inspect `progress.log`**: Read top entry for `Attempts`, `Attempt Trace`, `Duration`, and `Confidence`.
2. **Match Score**: Apply rubric.
3. **Update `docs/agents/granularity-profile.json`**:
   ```json
   {
     "modules": {
       "src/calc": {
         "recommended_level": "Level 1 (Coarse)",
         "last_score": 5,
         "success_rate": "100%",
         "total_tasks": 1,
         "notes": "Handles boundary tests cleanly in 1 attempt"
       }
     }
   }
   ```
4. **Brief Human**: Report score and adjustment in 1 concise line.
