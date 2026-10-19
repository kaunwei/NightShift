# NightShift: 24-Hour Unattended AI Development Framework

A plug-and-play, dual-terminal decoupled AI development framework designed for 24-hour unattended autonomous code generation, verification, and linear integration.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│               Terminal A: Interactive Architect (In-Session)           │
│  • Human + High-IQ AI (Gemini / Claude).                               │
│  • Discuss requirements, groom domain models & tracer-bullet tasks.    │
│  • Decompose goals into single-line atomic English contracts.          │
│  • Inspects progress.log (<=15 lines) for zero token pollution.        │
│  • [Early-Access] Guides Human with native preview commands (.preview/)│
│  • [Acceptance] Auto-merges verified frontier into main upon wake-up.  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (FIFO tasks.txt)
┌───────────────────────────────────▼────────────────────────────────────┐
│          Terminal B: Background Worker Daemon (worker.sh)              │
│  • Pure zero-argument execution (auto-sources .worker.env).            │
│  • Mode 1 (WORKER_ISOLATION=1): Persistent .worker-tree sandbox.       │
│    Stages verified snapshots to .preview/ drop-box on task PASS.       │
│  • Mode 2 (WORKER_ISOLATION=0): Direct in-place single-tree execution. │
│  • Headless stateless CLI per task (agy --mode accept-edits).          │
│  • Enforces .skills/universal-build-verify.md (TDD + Smoke tests).     │
│  • Max 3 repair attempts -> auto rollback on failure.                  │
│  • Auto Conventional Commit & prepends <=15 lines to progress.log.     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

1. **Dual-Worktree Persistent Isolation (`WORKER_ISOLATION=1`, Default)**:
   - Exactly **TWO** persistent worktrees exist (`main` and `.worker-tree`).
   - The worker executes inside `.worker-tree` on branch `feature/worker-frontier`.
   - Human's workspace remains 100% stable; IDE files never flicker; compiler/linker locks (`ETXTBSY`) are eliminated.
   - Automatically mirrors untracked configs (`.env`, `.worker.env`) and symlinks heavy dependencies (`node_modules`, `.venv`) with zero disk bloat.
   - Protects against network port collisions (`PORT=3001`) and test database contamination.
2. **Immutable Early-Access Drop-box (`.preview/`)**:
   - As soon as a task passes verification (e.g. 3 of 10 tasks), Worker stages an immutable snapshot/binary with `version.json`.
   - Human can try out the latest build immediately without compiling and without modifying git branches.
3. **Single-Tree In-Place Mode (`WORKER_ISOLATION=0`)**:
   - Zero-overhead fallback for projects locked to fixed ports (e.g. port 22) or singleton hardware resources.
4. **Live Human-in-the-Loop Feedback & Dynamic Rescheduling**:
   - Human tests intermediate milestones in `.preview/` while Worker continues executing.
   - Planner dynamically injects `[HOTFIX]` tasks to line 1 of `tasks.txt` via atomic directory locks (`scripts/reorder_queue.sh`).
5. **Zero-Intervention Auto-Merge**:
   - When all tasks complete, Sentinel Subagent wakes Planner.
   - Planner performs final acceptance and automatically runs `git merge --ff-only feature/worker-frontier` into `main`. No manual human git commands needed.

---

## File Structure

- **`worker.sh`**: Core background daemon supporting isolation modes, POSIX queue locking, and timeout watchdogs.
- **`.worker.env`**: Mandatory active environment configuration (co-located with `worker.sh`).
- **`.worker.env.example`**: Configuration template with model parameters, OS detection, and isolation toggle.
- **`.skills/universal-build-verify.md`**: Universal SOP for background workers (security guardrails, TDD, auto-commit).
- **`AGENTS.md` / `GEMINI.md`**: Master agent rules, Conventional Commit standards, and dynamic granularity ladders.
- **`docs/SPEC.md`**: Detailed architectural specification of the dual-terminal and isolation protocols.
- **`docs/PORTING_GUIDE.md`**: Autonomous AI porting guide for adopting this framework into other projects.
- **`scripts/status.sh`**: Real-time non-blocking visual dashboard of worker state, queue, and preview status.
- **`scripts/watch_worker.sh`**: Zero-token blocking waiter for Sentinel Subagents.
- **`scripts/reorder_queue.sh`**: Atomic queue reordering and hot preemption tool.
- **`tasks.txt`**: FIFO task queue (single-line atomic English contracts).
- **`tasks.done`**: Completed task history log.
- **`progress.log`**: Latest verification reports (newest prepended at top, <=15 lines per task).
- **`worker.status`**: Real-time worker heartbeat JSON.

---

## Quick Start Guide

### 1. Initialize Configuration
```bash
cp .worker.env.example .worker.env
```

### 2. Launch Terminal B (Background Worker)
Open a separate terminal window or tmux session and run:
```bash
./worker.sh
```
*(Runs as a perpetual daemon. To run once until the queue is empty, set `RUN_ONCE=1 ./worker.sh`)*

### 3. Terminal A (Interactive Architect & Planning)
1. Discuss features with the AI in Terminal A.
2. Planner writes atomic tasks into `tasks.txt`.
3. Background Worker picks up tasks, verifies them, and commits automatically.

### 4. Check Status & Early-Access Preview
Inspect live progress without disturbing the worker:
```bash
./scripts/status.sh
```
When intermediate milestones pass, Planner will provide the exact native command to preview the `.preview/` drop-box:
```bash
# Example: run the verified preview binary/script directly (0 compilation, 0 merge)
./.preview/<app>            # for compiled binaries
python3 .preview/src/<app>  # for script applications
```

### 5. Emergency Pause / Resume
To pause the worker safely after its current task finishes:
```bash
touch PAUSE
```
To resume execution:
```bash
rm PAUSE
```

---

## Porting to Other Projects

To port this framework to another project, point your AI assistant to [docs/PORTING_GUIDE.md](docs/PORTING_GUIDE.md). The AI will autonomously inspect your repository, adhere to non-destructive invariants, and set up the worker harness without breaking existing workflows.
