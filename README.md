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
│  • Level 1~3 granularity aligned with Matt Pocock's TDD blueprints.    │
│  • Inspects progress.log (<=15 lines) for zero token pollution.        │
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
│  • Decoupled Mechanical Audits: [CODE], [RESEARCH], [DIAGNOSTIC].      │
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
   - Prevents network port collisions (`PORT=3001`) and test database contamination.
2. **Decoupled Multi-Archetype Mechanical Audits**:
   - `[CODE]`: Deterministic test suite pass, Anti-Idle (`Tests_Run >= 1`), target whitelist, blast radius limits, assertion non-decrease.
   - `[RESEARCH]`: Artifact integrity check, Clean Tree (zero uncommitted/modified product code), pointer validity probe.
   - `[DIAGNOSTIC]`: Product code lock, clean build, repro failure strictly on test assertion.
3. **Immutable Early-Access Drop-box (`.preview/`)**:
   - As soon as a task passes verification, Worker stages an immutable snapshot/binary with `version.json`.
   - Human can test intermediate builds immediately without compilation and without branch switching.
4. **Single-Tree In-Place Mode (`WORKER_ISOLATION=0`)**:
   - Zero-overhead fallback for projects locked to fixed ports or singleton hardware resources.
5. **Atomic Hot Preemption & Dynamic Rescheduling**:
   - Planner dynamically injects urgent `[CODE]` or `[DIAGNOSTIC]` tasks to line 1 of `tasks.txt` via atomic locks (`scripts/reorder_queue.sh`).
6. **Zero-Token Sentinel Auto-Merge**:
   - When queue empties, Sentinel Subagent (`scripts/watch_worker.sh`) wakes Planner without chat polling loops.
   - Planner performs acceptance and automatically runs `git merge --ff-only feature/worker-frontier` into `main`.

---

## File Structure

- **`install.sh` / `update.sh`**: One-command non-destructive copy installer and updater to deploy or upgrade NightShift in any target project.
- **`worker.sh`**: Core background daemon supporting isolation modes, POSIX queue locking, and mechanical audit funnels.
- **`.worker.env.example`**: Configuration template with model parameters, OS detection, and isolation toggle.
- **`.skills/universal-build-verify.md`**: Universal SOP for background workers (security guardrails, Matt implementation skills, TDD, auto-commit).
- **`.agents/skills/nightshift/`**: Unified NightShift workflow skills suite (`planner`, `explore`, `watch-worker-queue`, `score-worker-performance`, `handle-worker-guidance`, `manage-worker-notes`, `record-attempt-trace`, `configure-unattended-worker`, `setup-unattended-workflow`).
- **`.worker.notes.md`**: Shared repository quirks and compiler flags cheat sheet across stateless runs.
- **`tasks.txt`**: FIFO task queue (single-line atomic English contracts).
- **`progress.log`**: Latest verification reports (newest prepended at top, <=15 lines per task).
- **`scripts/`**:
  - **`status.sh`**: Real-time non-blocking visual dashboard of worker state, queue, and preview status.
  - **`watch_worker.sh`**: Zero-token blocking waiter for Sentinel Subagents.
  - **`reorder_queue.sh`**: Atomic queue reordering and hot preemption tool.
  - **`extract_skeleton.sh`**: Signature skeleton and context slice extractor for dossier reports.
  - **`probe_line.sh`**: Precise line-level code auditor.
- **`docs/`**:
  - **`SPEC.md`**: Architectural specification of the dual-terminal and isolation protocols.
  - **`PORTING_GUIDE.md`**: Autonomous AI porting guide for adopting this framework into other projects.
  - **`agents/`**: Domain models, triage labels, and granularity profiles.

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

NightShift uses a **Pure Skills-Driven Architecture** with zero rules merging (`AGENTS.md` is never touched or required).
To port NightShift into any target repository in seconds (or update an existing installation):

```bash
./install.sh /path/to/target-project
# or to update an existing deployment:
./update.sh /path/to/target-project
```

The script automatically detects fresh install vs update, updates framework scripts and skills, safely preserves existing configs/tasks/notes, and ensures `.gitignore` has zero duplicate entries.
Then adapt the build and test commands in `<target-project>/.skills/universal-build-verify.md`.
For comprehensive details, see [docs/PORTING_GUIDE.md](docs/PORTING_GUIDE.md).
