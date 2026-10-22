# Autonomous AI Porting Guide
## How an AI Agent Migrates the 24h Unattended Dual-Terminal Framework to Another Project

If you are an AI assistant tasked with adopting, migrating, or deploying this 24-Hour Unattended Framework into a target repository, follow this deterministic, zero-breakage procedure.

---

## 1. Core Philosophy: Non-Destructive Invariance (零侵入原則)

When porting this framework into an existing project:
1. **NEVER modify or overwrite existing application code or entrypoints**:
   - Do NOT rewrite or inject code into their existing `main.py`, `index.ts`, `app.js`, `Dockerfile`, `Makefile`, etc.
   - Do NOT replace or alter their package management files (`package.json`, `Cargo.toml`, `requirements.txt`).
2. **NEVER modify or pollute existing project instructions or rules**:
   - The framework is 100% skills-driven (`.agents/skills/planner`, `.agents/skills/explore`, `.skills/universal-build-verify.md`). Existing `AGENTS.md`, `CLAUDE.md`, or `README.md` in the target repository remain completely untouched with **zero rules merging required**.
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

## 3. Migration Asset Checklist & Automatic Installer

The framework is packaged for zero-touch deployment via `install.sh`. Running:
```bash
./install.sh /path/to/target-project
```
deploys the complete Pure Skills-Driven architecture non-destructively:

| Asset Path | Permissions | Purpose |
| :--- | :---: | :--- |
| `install.sh` | `chmod +x` | Master copy installer (deploys scripts, skills, state files, and protects `.gitignore`). |
| `worker.sh` | `chmod +x` | Background daemon (supports isolation modes, zero-arg execution). |
| `.worker.env.example` | Read-only template | Config template with OS detection, model flags, and `WORKER_ISOLATION`. |
| `.worker.env` | Config file | Active config initialized from `.worker.env.example` in target root. |
| `scripts/` | `chmod +x` | Helper suite: `status.sh`, `watch_worker.sh`, `reorder_queue.sh`, `extract_skeleton.sh`, `probe_line.sh`. |
| `.skills/universal-build-verify.md` | Instruction | Worker build & test verification skill. |
| `.agents/skills/planner/` | Skill | Master engineering orchestrator (`/planner`). |
| `.agents/skills/explore/` | Skill | Two-tier seam explorer (`/explore`). |
| `.agents/skills/` (subdirs) | Skills | Supporting skills (`architect/`, `worker/`, `engineering/`, `productivity/`, `misc/`). |
| `.worker.notes.md` | Dynamic memory | Worker lessons learned, build quirks, and compiler flags. |
| `tasks.txt` | FIFO Queue | Task queue initialized with schema header. |
| `tasks.done` | Completed list | List of successfully executed tasks. |
| `progress.log` | Progress journal | Append-only execution log (strictly <= 15 lines per task). |
| `docs/agents/` | Metadata | Granularity profiles and triage labels. |
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
   - Swift: Check `Package.swift` -> Test: `swift test`

### Step 4.2: Execute Master Copy Installer (`install.sh`)
From the NightShift repository root, execute:
```bash
./install.sh /path/to/target-project
```
The installer automatically and non-destructively:
- Copies `worker.sh` and marks it executable (`chmod +x`).
- Copies `.worker.env.example` and initializes `.worker.env` if not already present.
- Deploys all `scripts/*.sh` tools with execution permissions.
- Copies the pure skills catalog (`.skills/universal-build-verify.md` and `.agents/skills/*`).
- Initializes runtime tracking files (`tasks.txt`, `.worker.notes.md`, `docs/agents/granularity-profile.json`) without overwriting existing files.
- Appends required worker runtime entries (`.worker.env`, `worker*.status`, `*.log`, `*.pid`, `PAUSE`, `.worker-tree/`, `.preview/`, `.reports/`, `tasks.txt.lock/`, `tasks.done`) to the target's `.gitignore`.
- Validates the bash syntax of all deployed scripts.

### Step 4.3: Adapt `.skills/universal-build-verify.md`
Inspect `<target-project>/.skills/universal-build-verify.md`.
Update **ONLY** Step 2.2 (Build) and Step 2.3 (Test) with the exact build and test commands discovered in Step 4.1.

### Step 4.4: Pure Skills Execution (Zero Rules Merging)
Because NightShift is a **Pure Skills-Driven Architecture**, there is **zero need to merge into, edit, or touch existing `AGENTS.md`, `CLAUDE.md`, or `GEMINI.md` files**.
- **Terminal A (Interactive Architect & Planner)**: Runs via the installed skills (`/planner`, `/explore`). Planner grooms requirements into atomic tracer-bullet tasks in `tasks.txt`.
- **Terminal B (Background Worker Daemon)**: Launched via `./worker.sh`. Stateless, headless worker sessions receive the prompt pointing directly to `.skills/universal-build-verify.md` and Matt Pocock's implementation skills.

### Step 4.5: Verification & Dry-Run Test
1. Run syntax validation in target repository:
   ```bash
   bash -n worker.sh scripts/*.sh
   ```
2. Test empty-queue dry run:
   ```bash
   RUN_ONCE=1 ./worker.sh
   ```
   Confirm that `.worker.env` is sourced, OS is auto-detected, and the script exits gracefully on empty queue (Exit 0).
3. Hand over cleanly to the user:
   - Terminal A: Plan and queue tasks using `/planner`.
   - Terminal B: Run `./worker.sh` to begin autonomous background loop.
   - Live Dashboard: Run `./scripts/status.sh` to monitor real-time worker progress and previews.
