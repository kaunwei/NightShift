---
name: setup-unattended-workflow
description: "Non-destructive migration and setup skill to integrate the 24-hour unattended dual-terminal AI workflow into any project repository."
---

# Setup Unattended Dual-Terminal Workflow

Integrate the NightShift 24-hour unattended dual-terminal workflow into any target repository non-destructively without altering application logic or developer workflows.

## Non-Destructive Invariants

1. **Zero Production Mutation**: Never modify application source code, entrypoints, or existing build scripts (`main.*`, `Makefile`, `Dockerfile`).
2. **Append-Only Instructions**: Never overwrite existing project guidelines (`AGENTS.md`, `CLAUDE.md`, `README.md`). Append only.
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

### 2. Copy Core Assets
Deploy unattended harness assets into repository:
- `worker.sh` -> Repo root (`chmod +x worker.sh`).
- `.worker.env.example` -> Repo root.
- `.worker.env` -> Initialize from `.worker.env.example` (mandatory, co-located with `worker.sh`).
- `scripts/` -> `status.sh`, `watch_worker.sh`, `reorder_queue.sh`, `extract_skeleton.sh`, `probe_line.sh` (`chmod +x`).
- `.skills/universal-build-verify.md` -> Target project execution SOP.
- `tasks.txt`, `tasks.done`, `progress.log`, `.worker.notes.md` -> Initialize if missing.

### 3. Adapt `.skills/universal-build-verify.md`
Update the build and test commands in `.skills/universal-build-verify.md` to match the detected ecosystem.

### 4. Non-Destructive Rules Merge
Append the dual-terminal treaty to the end of `AGENTS.md` (or `CLAUDE.md` / `GEMINI.md`):
- Firewall: Terminal A (Planner) vs Terminal B (Worker).
- Worktree Isolation: Mode 1 (`WORKER_ISOLATION=1`, `.worker-tree`) vs Mode 2 (In-Place).
- Granularity Ladder: Level 1 (Macro), Level 2 (Meso), Level 3 (Micro) with blast radius caps.
- Strict Conventional Commit and double-funnel mechanical audit requirements.

### 5. Append-Only `.gitignore`
Append worker runtime artifacts to `.gitignore`:
```gitignore
# 24h Unattended Worker Artifacts
.worker.env
worker*.status
.worker*.log
.worker*.pid
PAUSE
.worker-tree/
.preview/
.reports/
tasks.txt.lock/
```

### 6. Verify Setup
1. Validate script syntax:
   ```bash
   bash -n worker.sh scripts/*.sh
   ```
2. Run sanity check:
   ```bash
   RUN_ONCE=1 ./worker.sh
   ```
3. Confirm to user: Workflow is ready to launch via `./worker.sh` in Terminal B with zero impact on existing codebase.
