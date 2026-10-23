# NightShift: 24-Hour Unattended AI Development Framework

A plug-and-play, dual-terminal AI development framework combining **Matt Pocock's engineering skills** with an **unattended background worker daemon (`worker.sh`)** for 24-hour autonomous code generation, live `.preview/` testing, and double-funnel verification.

---

## Architecture Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│               Terminal A: Interactive Planner (/planner, /explore)     │
│  • Domain & Seam Modeling: /domain-modeling, /codebase-design, /explore│
│  • Tracer-Bullet Slicing (to-tickets): End-to-end vertical slices      │
│    independently demoable in .preview/.                                │
│  • Full-Horizon Dispatch: Enqueues 100% of discovered tasks at once    │
│    (First-Time Alignment or Full-Auto Mode).                           │
│  • 10-Task Cadence: Auto-runs /code-review & /improve-codebase-arch    │
│    every 10 tasks and injects a [CODE: REFACTOR] ticket.               │
│  • Double-Funnel Acceptance:                                           │
│    - Green Light (Attempts=1, HIGH): <=5s 0-token FF-merge into main.  │
│    - Yellow Light: Auto-triggers /code-review.                         │
│    - [BLOCKED] (3 failed retries): Auto-triggers /retro & escalation.  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (FIFO tasks.txt with POSIX lock)
┌───────────────────────────────────▼────────────────────────────────────┐
│          Terminal B: Background Worker Daemon (./worker.sh)            │
│  • Zero-argument daemon (auto-sources .worker.env & .worker.notes.md). │
│  • Mode 1 (WORKER_ISOLATION=1): Persistent .worker-tree sandbox on     │
│    branch feature/worker-frontier; stages PASS builds to .preview/.    │
│  • Mode 2 (WORKER_ISOLATION=0): Direct in-place single-tree execution. │
│  • Executes via /implement (skipping per-task /code-review), /tdd,     │
│    /codebase-design, /diagnosing-bugs, and /research.                  │
│  • Mechanical Audits: [CODE], [DIAGNOSTIC], [RESEARCH], Proof of       │
│    Negative for [DEAD_END], Assertion Non-Decrease, Blast Radius.      │
│  • Max 3 attempts -> auto Conventional Commit & <=15-line progress.log.│
└────────────────────────────────────────────────────────────────────────┘
```

---

## Key Features

1. **Clean Command Surface + Upstream Skill Integrity**:
   - Exposes only **`/planner`** and **`/explore`** for NightShift orchestration, keeping Terminal A's `/` autocomplete clean.
   - Preserves Matt Pocock's upstream skills (`.agents/skills/engineering/`, `productivity/`, `misc/`) 100% intact for frictionless `git pull` updates, binding them via direct file pointers.
2. **Tracer-Bullet Slicing (`to-tickets`) & On-the-Fly Live Preview (`.preview/`)**:
   - Tasks are sliced vertically end-to-end so every completed ticket stages a runnable snapshot and `.preview/version.json` into `.preview/`.
   - Test new features live (e.g. `./.preview/bin/app`) on `main` (`PORT=3000`) while Worker continues building subsequent tasks in `.worker-tree` (`PORT=3001`).
3. **Full-Horizon Batch Dispatch & Full-Auto Mode**:
   - Once `/explore` verifies seams, Planner dispatches the entire discovered task queue in one shot (never drip-feeding 2–3 tasks at a time).
   - Protected by live queue preemption (`scripts/reorder_queue.sh`), safe pause (`touch PAUSE`), and instant Git rollback (`git reset --hard nightshift-session-base`).
4. **Double-Funnel Acceptance & Token Protection**:
   - **Worker**: Runs fast unit/integration tests without spawning per-task `/code-review` sub-agents.
   - **Green Light (`Attempts: 1 | Confidence: HIGH`)**: Zero review tokens; immediate `git merge --ff-only feature/worker-frontier`.
   - **Yellow Light (`Attempts > 1`, low confidence, or critical seam)**: Automatically runs `/code-review`.
   - **`[BLOCKED]` (3 failed retries)**: Automatically runs `/retro` on the failure trace to upgrade checks/standards and `.worker.notes.md`.
5. **10-Task Architecture Deepening Cadence**:
   - Every 10 tasks (`TASK-010`, `TASK-020`, ...), Planner automatically runs `/code-review` and `/improve-codebase-architecture` over recent commit hotspots (`git log --oneline -n 20`) and queues a `[CODE: REFACTOR]` ticket.
6. **Dual-Worktree Persistent Isolation (`WORKER_ISOLATION=1`, Default)**:
   - Eliminates IDE file flickering and compiler/linker locks (`ETXTBSY`) while symlinking heavy dependency caches (`node_modules`, `.venv`).
   - Includes `WORKER_ISOLATION=0` fallback for hardware-locked or fixed-port projects.

---

## File Structure

- **`install.sh` / `update.sh`**: Unified non-destructive installer and updater (deploys scripts/skills, preserves user state, and prevents duplicate `.gitignore` entries).
- **`worker.sh` + `worker_runtime.py`**: Bash-compatible daemon entry point plus Python 3 queue, task-field, JSON status, and Codex argument operations. Git audit, CLI execution, isolation, and preview remain in Bash during the staged migration.
- **`.worker.env.example`**: Configuration template (model selection, effort level, timeout, `WORKER_ISOLATION`, `ADDITIONAL_DIRS`).

The active low-cost test configuration is `AI_CLI=codex`, `AI_MODEL=gpt-6-luna`, and `AI_EFFORT=none`. The retained `test/` suite uses a fake Codex executable, so routine regression tests consume no model tokens:

```sh
python3 -m unittest discover -s test -v
bash -n worker.sh install.sh scripts/*.sh
```
- **`.skills/universal-build-verify.md`**: Worker execution SOP and hard guardrails (Terminal B).
- **`.agents/skills/nightshift/`**: NightShift orchestrator skills (`planner/SKILL.md` and `explore/SKILL.md`).
- **`.agents/skills/{engineering,productivity,misc,in-progress}/`**: Matt Pocock's upstream skills catalog (unmodified).
- **`.worker.notes.md`**: Shared compiler flags and toolchain quirks across stateless worker runs (`< 30 lines`).
- **`tasks.txt`**: FIFO task queue (single-line English tracer-bullet contracts).
- **`progress.log`**: Prepend-only verification journal (`<= 15 lines` per task, stamped with `[MECHANICAL_AUDIT]` at line 1).
- **`scripts/`**:
  - **`status.sh`**: Real-time dashboard of worker state, queue progress, and `.preview/` version.
  - **`watch_worker.sh`**: Zero-token blocking waiter for Sentinel Subagents.
  - **`reorder_queue.sh`**: Atomic queue reordering and hot preemption (`line 1` injection).
  - **`extract_skeleton.sh`**: AST signature skeleton extractor for low-token exploration.
  - **`probe_line.sh`**: File- and line-scoped code inspector.
- **`docs/`**:
  - **`SPEC.md`**: Technical specification of the dual-terminal architecture and audit gates.
  - **`PORTING_GUIDE.md`**: Step-by-step guide for installing or updating NightShift in external repositories.
  - **`agents/`**: Module granularity ratings (`granularity-profile.json`) and triage metadata.

---

## Quick Start Guide

### 1. Initialize Configuration
```bash
cp .worker.env.example .worker.env
```

### 2. Launch Terminal B (Background Worker)
Open a separate terminal or tmux pane:
```bash
./worker.sh
# Or run once until queue is empty:
RUN_ONCE=1 ./worker.sh
```

### 3. Plan & Dispatch in Terminal A
1. Run `/planner` (or `/explore` for seam discovery) in your interactive AI session.
2. Approve the proposed full queue (or reply `auto` for uninterrupted Full-Auto dispatch into `tasks.txt`).
3. Worker executes tasks in `.worker-tree`, stages passing builds to `.preview/`, and Sentinel wakes Planner to fast-forward merge into `main`.

### 4. Live Status & Queue Control
```bash
./scripts/status.sh                                # Live dashboard & .preview/ info
./scripts/reorder_queue.sh prepend "TASK-099 ..."  # Hot-preempt urgent task to line 1
touch PAUSE                                        # Pause worker after current task
rm PAUSE                                           # Resume worker
```

---

## Porting & Updating in Other Projects

NightShift uses a **Pure Skills-Driven Architecture**—it never modifies your project's `AGENTS.md`, `CLAUDE.md`, or `README.md`.

```bash
./install.sh /path/to/target-project
# Or update an existing deployment:
./update.sh /path/to/target-project
```

The installer automatically detects fresh install vs. update, syncs `worker.sh`, `scripts/`, `.skills/`, and `.agents/skills/`, preserves your active `.worker.env`, `tasks.txt`, and `.worker.notes.md`, and keeps `.gitignore` clean without duplicate entries. See [docs/PORTING_GUIDE.md](docs/PORTING_GUIDE.md) for details.
