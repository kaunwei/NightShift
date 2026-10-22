---
name: configure-unattended-worker
description: "Configure background worker environment (.worker.env, reference directories, model selection, sandbox) automatically based on human conversation."
---

# Configure Unattended Worker

Autonomously update worker parameters in `.worker.env` during Terminal A conversations without manual human shell editing.

---

## 1. Triggers
Activate when the user requests:
- External reference repository (e.g. `/path/to/repo`).
- Model switch (e.g. Claude 3.7, Gemini 3.8 Flash/Pro).
- Sandbox, timeout, or execution mode changes.

---

## 2. Autonomous Actions

### 1. External Reference Repositories
1. Update `ADDITIONAL_DIRS` in `.worker.env` (co-located with `worker.sh`):
   ```bash
   ADDITIONAL_DIRS="/absolute/path/to/external/repo"
   ```
2. When referencing external code in `tasks.txt`, specify the path in `ACTION:`:
   ```text
   TASK-XXX | TARGET: src/calc.py | ACTION: Port logic from /path/to/external/repo/src/calc.py | VERIFY: pytest tests/ | CONSTRAINTS: Only edit local target
   ```

### 2. Worker Parameters (`.worker.env`)
Update settings in `.worker.env`:
```bash
OS_TYPE="auto"                # "auto" | "mac" | "ubuntu" | "linux"
WORKER_ID="default"           # Parallel worker namespace: "worker-1", "worker-2", etc.
AI_MODEL="gemini-3.8-flash-low"
AI_EFFORT="low"
AGY_MODE="accept-edits"
USE_SANDBOX="0"
TASK_TIMEOUT="1800"
RUN_ONCE="0"
WORKER_ISOLATION="1"          # "1" (.worker-tree) | "0" (in-place)
```

### 3. User Confirmation
Brief human in one concise line:
> "已自動更新 `.worker.env` 參數，啟動 `./worker.sh` 即可自動套用。"
