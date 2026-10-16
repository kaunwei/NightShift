# 24-Hour Unattended AI Development Framework

A plug-and-play, dual-terminal decoupled AI development framework designed for 24-hour unattended autonomous code generation, verification, and linear integration.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                 Terminal A: Interactive Architect           │
│  • Human + High-IQ AI (Gemini 3.7 / Claude Sonnet).         │
│  • Discuss requirements, groom domain models.               │
│  • Decompose goals into single-line atomic English tasks.   │
│  • Inspects progress.log (<=10 lines) for zero pollution.   │
└──────────────────────────────┬──────────────────────────────┘
                               │ (FIFO tasks.txt)
┌──────────────────────────────▼──────────────────────────────┐
│                 Terminal B: Unattended Background Worker    │
│  • worker.sh daemon polls tasks.txt continuously.           │
│  • Invokes cheap Flash models via agy CLI.                  │
│  • Enforces .skills/universal-build-verify.md SOP.          │
│  • Executes builds (C++/Python), unit tests, GUI smoke tests.│
│  • Max 3 repair attempts -> auto rollback on failure.       │
│  • Auto Git Commit & prepends summary to progress.log.      │
└─────────────────────────────────────────────────────────────┘
```

---

## File Structure

- **`worker.sh`**: Background daemon loop with PID lock, watchdog timer (600s), rate-limit backoff, and clean rollback.
- **`.skills/universal-build-verify.md`**: Universal SOP for background workers (security guardrails, C++/Python/GUI verification, 3-retry limit, auto-commit).
- **`AGENTS.md` / `GEMINI.md`**: Master rules, atomic task schema, safe git log rules, and linear rebase guidelines.
- **`docs/PORTING_GUIDE.md`**: Autonomous porting manual for external AIs to migrate this framework to any repository without human copy-pasting.
- **`tasks.txt`**: FIFO task queue (single-line atomic English contracts).
- **`tasks.done`**: Completed task history log.
- **`progress.log`**: Latest verification reports (newest prepended at top).
- **`worker.status`**: Real-time worker heartbeat JSON.

---

## Quick Start Guide

### Terminal A (Architect / Human Discussion):
1. Discuss features with the AI in Terminal A.
2. Direct the AI to generate atomic tasks into `tasks.txt`.
3. Check `progress.log` to review completed deliverables.

### Terminal B (Background Worker):
Start the unattended worker:
```bash
./worker.sh
```

To run with a specific model or timeout:
```bash
AI_MODEL=gemini-3.8-flash-low TASK_TIMEOUT=900 ./worker.sh
```

### Emergency Pause:
To safely pause the worker after the current task finishes:
```bash
touch PAUSE
```
To resume:
```bash
rm PAUSE
```

---

## Porting to Other Projects

To port this framework to another project, point your AI assistant to [docs/PORTING_GUIDE.md](file:///home/kw/workspace/auto_script/docs/PORTING_GUIDE.md). The AI will autonomously inspect your target repository, merge rules non-destructively into your `AGENTS.md`, and drop in the worker components.
