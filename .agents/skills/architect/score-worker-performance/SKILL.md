---
name: score-worker-performance
description: "Score worker execution performance (1 to 5 stars) from progress.log audit traces and update docs/agents/granularity-profile.json automatically."
---

# Score Worker Performance

Audit worker execution trace from `progress.log` and update subsystem capability memory in `docs/agents/granularity-profile.json`.

## Scoring Rubric

| Score | Rating | Criteria | Granularity Action |
| :---: | :--- | :--- | :--- |
| ⭐⭐⭐⭐⭐ | **5 Stars** | Passed in 1 attempt (0 retries), clean diff, 0 warnings. | Maintain / Promote to Level 1. Worker is autonomous. |
| ⭐⭐⭐⭐ | **4 Stars** | Passed in 2 attempts (1 self-healed retry), green tests. | Maintain current Level (1 or 2). |
| ⭐⭐⭐ | **3 Stars** | Passed on 3rd attempt (2 retries needed). | Demote subsequent tasks in this module to Level 2. |
| ⭐⭐ | **2 Stars** | Raised `[NEED_GUIDANCE]` or `[NEED_DECOMPOSITION]`. | Demote to Level 2/3, provide guidance. |
| ⭐ | **1 Star** | Blocked after 3 retries, timed out, or crashed. | Demote to Level 3. Re-architect with user. |

## Process

1. **Read Top Entry in `progress.log`**: Inspect `Attempts`, `Attempt Trace`, `Duration`, and `Confidence`.
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
         "notes": "Handles arithmetic and boundary tests cleanly in 1 attempt"
       }
     }
   }
   ```
4. **Brief Human**: Report score and adjustment in 1 concise line.
