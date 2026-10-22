---
name: setup-unattended-workflow
description: "Non-destructive migration and setup skill to integrate the 24-hour unattended dual-terminal AI workflow into any project repository."
---

# Setup Unattended Dual-Terminal Workflow

Integrate the NightShift 24-hour unattended dual-terminal workflow into any target repository non-destructively without altering application logic or developer workflows.

## Non-Destructive Invariants

1. **Zero Production Mutation**: Never modify application source code, entrypoints, or existing build scripts (`main.*`, `Makefile`, `Dockerfile`).
2. **Zero Context Pollution**: Never modify or pollute existing project instruction files (`AGENTS.md`, `CLAUDE.md`, `README.md`). The framework is 100% skills-driven.
3. **Decoupled Harness**: Operates as an external sidecar harness. Native developer commands remain completely unaffected.

## Process

### 1. Inspect Workspace
Identify project ecosystem to determine build/test commands:
- **Rust**: `Cargo.toml` (`cargo build` / `cargo test`)
- **Python**: `pyproject.toml`, `setup.py`, `pytest.ini` (`pytest` or `python -m unittest`)
- **Node/TS**: `package.json` (`npm run build` / `npm test` or `pnpm`/`yarn`)
- **C/C++**: `CMakeLists.txt`, `Makefile` (`cmake --build build` / `ctest`)
- **Go**: `go.mod` (`go build ./...` / `go test ./...`)
- **Swift**: `Package.swift` (`swift build` / `swift test`)

### 2. Run Master Copy Installer (`install.sh`)
Execute `./install.sh <target_project_path>`. The installer handles:
- Copying `worker.sh` and helper scripts (`scripts/`).
- Initializing `.worker.env` (from `.worker.env.example`) co-located with `worker.sh`.
- Deploying the complete skills catalog (`.skills/universal-build-verify.md` and `.agents/skills/*`).
- Initializing non-destructive state files (`tasks.txt`, `.worker.notes.md`, `docs/agents/granularity-profile.json`).
- Automatically protecting `.gitignore` with worker runtime entries.

### 3. Adapt `.skills/universal-build-verify.md`
Update the build and test commands in `<target>/.skills/universal-build-verify.md` to match the detected ecosystem.

### 4. Pure Skills Execution (Zero Rules Merging)
NightShift relies purely on skills (`/planner`, `/explore`, and `.skills/universal-build-verify.md`).
There is **no need to merge or edit `AGENTS.md` or `CLAUDE.md`**.
- **Terminal A (Interactive Architect & Planner)**: Invokes `/planner` and `/explore` to groom specs into single-line atomic contracts in `tasks.txt`.
- **Terminal B (Background Worker Daemon)**: Runs `./worker.sh` headlessly, reading `.skills/universal-build-verify.md` and Matt's implementation suite per task.

### 5. Verify Setup
1. Validate script syntax:
   ```bash
   bash -n worker.sh scripts/*.sh
   ```
2. Run sanity check:
   ```bash
   RUN_ONCE=1 ./worker.sh
   ```
3. Confirm to user: Workflow is ready to launch via `./worker.sh` in Terminal B with zero impact on existing codebase.
