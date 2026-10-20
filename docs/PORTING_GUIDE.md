# Autonomous AI Porting Guide
## How an AI Agent Migrates the 24h Unattended Dual-Terminal Framework to Another Project

If you are an AI assistant tasked with adopting, migrating, or deploying this 24-Hour Unattended Framework into a target repository, follow this deterministic, zero-breakage procedure.

---

## 1. Core Philosophy: Non-Destructive Invariance (零侵入原則)

When porting this framework into an existing project:
1. **NEVER modify or overwrite existing application code or entrypoints**:
   - Do NOT rewrite or inject code into their existing `main.py`, `index.ts`, `app.js`, `Dockerfile`, `Makefile`, etc.
   - Do NOT replace or alter their package management files (`package.json`, `Cargo.toml`, `requirements.txt`).
2. **NEVER overwrite existing project instructions or rules**:
   - If the project already has `AGENTS.md`, `CLAUDE.md`, or `README.md`, **DO NOT overwrite**. Use **append-only** integration.
3. **Preserve Native Developer Ergonomics**:
   - The framework lives alongside the project as a decoupled harness (`worker.sh`, `.skills/`, `.worker.env`, `tasks.txt`).
   - Human developers and CI/CD pipelines continue using their native commands (`npm start`, `cargo test`, `pytest`, `docker compose up`) without any disruption.

---

## 2. Fast Update & Rapid Deployment for Collaborators (團隊快速同步與部署機制)

A common bottleneck in software teams is that every time code is updated, collaborators or deployment servers suffer from 10–20 minute rebuilds and broken configurations. When porting this framework, the AI must ensure the target project follows these three acceleration treaties:

### 2.1 Smart Delta Sync (差異跳過法則)
- **Problem**: Collaborators habitually re-run full package installations (`npm install`, `pip install`, `cargo build`) on every `git pull`, even though 90% of commits only modify application logic.
- **Guidance for Porting AI**: Document in the target project's `README.md` or contributor section that collaborators can check if manifests changed before installing:
  ```bash
  # Check if package manifests changed in the latest pull
  git diff HEAD@{1} -- package-lock.json pnpm-lock.yaml requirements.txt poetry.lock Cargo.lock go.sum
  # If output is empty -> Skip installation entirely! 0 seconds lost.
  ```

### 2.2 Config Drift Doctor (設定檔漂移防護)
- Maintain `.worker.env.example` (and the project's native `.env.example`).
- If any new configuration keys are added during feature development, they MUST be documented with defaults in the `.example` templates.
- Collaborators can compare their local `.worker.env` against `.worker.env.example` in seconds without encountering silent runtime crashes.

### 2.3 Warm Build Cache Deployment (熱工作目錄快取)
- For CI/CD or staging deployments, avoid cold `rm -rf` cloning from scratch.
- Use persistent working directories with `git fetch && git checkout -f <tag>` to preserve warm compiler caches (`target/`, `.next/cache/`, `node_modules/`, `.venv/`).

---

## 3. Migration Asset Checklist

The following framework files must be copied into the target repository root:

| Asset Path | Permissions | Purpose |
| :--- | :---: | :--- |
| `worker.sh` | `chmod +x` | Background daemon (supports isolation modes, zero-arg execution). |
| `.worker.env.example` | Read-only template | Config template with OS detection, model flags, and `WORKER_ISOLATION`. |
| `.worker.env` | Config file | Active config initialized from `.worker.env.example` in the **same directory as `worker.sh`**. |
| `scripts/status.sh` | `chmod +x` | Real-time visual dashboard of worker state, queue, and preview status. |
| `scripts/watch_worker.sh` | `chmod +x` | Sentinel subagent waiter script for non-blocking Terminal A wakeup. |
| `scripts/reorder_queue.sh` | `chmod +x` | Atomic POSIX-locked task queue reordering & hot preemption tool. |
| `.skills/universal-build-verify.md` | Instruction | Worker build & test verification skill. |
| `.worker.notes.md` | Dynamic memory | Worker lessons learned, build quirks, and compiler flags. |
| `tasks.txt` | FIFO Queue | Task queue initialized with schema header. |
| `tasks.done` | Completed list | List of successfully executed tasks. |
| `progress.log` | Progress journal | Append-only execution log (strictly <= 15 lines per task). |
| `.worker-tree/` | Ignored directory | Persistent worker sandbox (auto-created if `WORKER_ISOLATION=1`). |
| `.preview/` | Ignored directory | Immutable early-access drop-box (auto-staged on task PASS). |

---

## 4. Deterministic Porting Algorithm (Step-by-Step for Migration AI)

### Step 4.1: Inspect Target Project Stack
Analyze the target workspace without modifying anything:
1. **Language & Build System**:
   - C / C++: Check `CMakeLists.txt` -> Build: `cmake -B build -S . -G Ninja && cmake --build build`, Test: `ctest --test-dir build`
   - Python: Check `pyproject.toml` / `requirements.txt` -> Test: `pytest` or `python -m unittest`
   - Rust: Check `Cargo.toml` -> Build: `cargo build`, Test: `cargo test`
   - Node / TS: Check `package.json` -> Build: `npm run build`, Test: `npm test`
   - Go: Check `go.mod` -> Test: `go test ./...`
2. **Existing Rules**: Check for existing `AGENTS.md`, `GEMINI.md`, or `CLAUDE.md`.

### Step 4.2: Copy Assets & Initialize Config
1. Copy all assets from the Migration Asset Checklist (Section 3).
2. Set execute permissions:
   ```bash
   chmod +x worker.sh scripts/status.sh scripts/watch_worker.sh scripts/reorder_queue.sh
   ```
3. Initialize `.worker.env` from `.worker.env.example`:
   ```bash
   cp .worker.env.example .worker.env
   ```
   *(Ensure `WORKER_ISOLATION=1` is set by default, or `0` for hardware-locked environments).*

### Step 4.3: Adapt `.skills/universal-build-verify.md`
Inspect `.skills/universal-build-verify.md`. Update **ONLY** Step 2.2 (Build) and Step 2.3 (Test) with the exact build and test commands discovered in Step 4.1.

### Step 4.4: Non-Destructive Merge into Agent Rules
If the target repository already has `AGENTS.md`, `GEMINI.md`, or `CLAUDE.md`, **DO NOT overwrite**.
Append the following section to the end of their file:

```markdown
## 24h Unattended Dual-Terminal Workflow

This repository supports the 24-Hour Unattended Dual-Terminal AI Development Framework.

### 0. Role Definition & Duty Boundary Firewall (雙角色極簡職責防線)
- **Terminal A (Interactive Architect & Planner)**:
  - High-level system architecture, domain modeling, requirement grooming, and task decomposition.
  - **Default Reflex**: Discuss -> Decompose into atomic contracts in `tasks.txt` (`LEVEL: 1|2|3`, archetypes: `[CODE]`, `[DIAGNOSTIC]`, `[RESEARCH]`) -> Stop calling tools and yield control to Terminal B! Do NOT modify business code directly (`Sources/`, `src/`, `app/`, `lib/`, `tests/`) and do NOT run in-session diagnostic/debug loops.
  - **Sovereign Exceptions**:
    1. *Anti-Rubber-Stamp Audit*: Mandated deep inspection on `Attempts > 1`, `Confidence < 1.0`, or critical seams.
    2. *Level 3 Implementation Escalation*: Intervene when a task was **already at Level 3 (Micro)** and Worker failed 3 retries, followed by a post-mortem allocation retro in `granularity-profile.json` and `.worker.notes.md`.
    3. *Diagnostic Evasion & Bogus Report Intervention*: Intervene when Worker repeatedly produces vague/hallucinated reports or fails to isolate the issue after 2-3 retries without verifiable evidence. Planner directly isolates the root cause and logs quirks in `.worker.notes.md`.
    4. *Explicit User Mandate*: User explicitly requests Planner to write or fix code directly.
  - **Active Skills**: `/domain-modeling`, `/to-tickets`, `/calibrate-task-granularity`, `/watch-worker-queue`, `/code-review`.
- **Terminal B (Background Worker Daemon)**:
  - Headless unattended implementation, compilation, test execution, and atomic commits.
  - Operates in `.worker-tree` (if `WORKER_ISOLATION=1`) or in-place (`WORKER_ISOLATION=0`). Follows `.skills/universal-build-verify.md`, max 3 retries, commits, and prepends <=15 lines to `progress.log`. Never changes architecture, never enters chat loops.

### 1. Dual-Terminal Architecture & Dual-Track Offload
- **Terminal A (Interactive Architect)**: Discuss requirements with human, groom specs into atomic tracer-bullet tasks, write to `tasks.txt`, and inspect `progress.log` for rapid acceptance.
- **Terminal B (Background Worker)**: Runs `./worker.sh`. Stateless process per task, executes build, test, and auto-commits.
- **Hot Preemption for Exploration**: Exploratory and diagnostic tasks have top priority and jump to line 1 of `tasks.txt` so Worker delivers verified facts quickly without bloating Terminal A's context. When Worker reaches the critical threshold (struggles or produces bogus reports), Planner steps in and inspects directly.
- **Sentinel Waiter Subagent**: Subagents in Terminal A are restricted to non-blocking queue monitoring (`scripts/watch_worker.sh`).

### 2. Dual-Worktree Isolation vs In-Place Execution Modes
- **Mode 1: Dual-Worktree Isolation (`WORKER_ISOLATION=1`, Default)**:
  - Maintains exactly TWO persistent worktrees (`main` and `.worker-tree`).
  - Worker executes in `.worker-tree` on branch `feature/worker-frontier`.
  - Immutable Drop-box (`.preview/`): stages verified snapshots on task PASS. Human previews early without compiling or merging.
  - Auto-Merge on Completion: When tasks finish, Sentinel wakes Planner, who conducts acceptance and automatically runs `git merge --ff-only feature/worker-frontier` into `main` with zero manual human git intervention.
- **Mode 2: Single-Tree In-Place (`WORKER_ISOLATION=0`)**:
  - Used for fixed ports (e.g. port 22) or hardware-locked resources. Runs directly in project root.

### 3. Strict Inter-AI English Protocol
- All tasks in `tasks.txt`, summaries in `progress.log`, status in `worker.status`, and git commits MUST be in **strictly English**.

### 4. Dynamic Granularity Ladder (tasks.txt)
Single-line tracer-bullet format:
`TASK-XXX | LEVEL: 1 | TARGET: <files> | ACTION: <concrete logic> | VERIFY: <test command> | CONSTRAINTS: <bounds>`
- **Level 1 (Coarse)**: Public interface & test contract; worker decides internal implementation.
- **Level 2 (Medium)**: Component/slice breakdown.
- **Level 3 (Micro)**: Function-level surgical instructions.
- **Escalation Ladder**: Level 1 Blocked -> Demote to Level 2 -> Demote to Level 3. If Level 3 still fails after 3 retries -> Planner sovereign intervention & retro.

### 5. Safe Git Log Rules for Acceptance AI
- Allowed: `git log -n 1 --stat`, `git show --stat <commit-hash>`, `git log --oneline -n 5`
- Prohibited: Bare `git log`, `git log -p`, full `git diff` (prevents context explosion).
```

### Step 4.5: Safe `.gitignore` Append
Append the following runtime artifacts to the target `.gitignore` without disturbing existing entries:
```gitignore
# 24h Unattended Worker Artifacts
.worker.env
worker*.status
.worker*.log
.worker*.pid
PAUSE
.scratch/
tasks.txt.lock/
.worker-tree/
.preview/
```

### Step 4.6: Verification & Handover
1. Run syntax checks:
   ```bash
   bash -n worker.sh
   bash -n scripts/status.sh
   bash -n scripts/watch_worker.sh
   bash -n scripts/reorder_queue.sh
   ```
2. Test dry-run:
   ```bash
   RUN_ONCE=1 ./worker.sh
   ```
   Confirm that `.worker.env` is sourced, OS is auto-detected, and the script exits gracefully on empty queue.
3. Hand over cleanly to the user:
   - Provide zero-argument launch instruction: `./worker.sh` in Terminal B.
   - Inform them how to check progress via `./scripts/status.sh` or `head -n 15 progress.log`.
   - Point out that native project commands (`npm test`, `pytest`, etc.) remain 100% untouched.
