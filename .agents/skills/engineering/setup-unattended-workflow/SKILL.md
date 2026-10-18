---
name: setup-unattended-workflow
description: "Non-destructive migration and setup skill to integrate the 24-hour unattended dual-terminal AI workflow into any project repository."
---

# Setup Unattended Dual-Terminal Workflow

This skill teaches an AI agent how to safely, non-destructively adapt and integrate the 24-Hour Unattended Dual-Terminal AI Development Framework into the current project.

---

## Process

### 1. Explore Target Repository
Inspect the current workspace to understand its existing configuration:
- Detect project language and build system:
  - C/C++: `CMakeLists.txt`, `Makefile`, `ninja.build`
  - Python: `pyproject.toml`, `setup.py`, `requirements.txt`, `pytest.ini`
  - JavaScript/TypeScript: `package.json`, `tsconfig.json`
  - Rust: `Cargo.toml`
  - Go: `go.mod`
- Check existing agent rule files: `AGENTS.md`, `GEMINI.md`, `CLAUDE.md`.
- Check if `.gitignore` exists.

### 2. Copy Core Unattended Assets
Copy or initialize the following core assets:
- `worker.sh` -> placed at repo root (make executable with `chmod +x worker.sh`).
- `.worker.env.example` -> placed at repo root.
- `.worker.env` -> initialize from `.worker.env.example` in the **same directory as `worker.sh`** (mandatory).
- `scripts/watch_worker.sh` -> placed in `scripts/` (make executable with `chmod +x scripts/watch_worker.sh`).
- `.skills/universal-build-verify.md` -> placed in `.skills/universal-build-verify.md`.
- `.worker.notes.md` -> initialized with repository quirks and build hints.
- `tasks.txt` -> initialize empty queue template if not present.
- `tasks.done` -> initialize empty file if not present.
- `progress.log` -> initialize empty log template if not present.

### 3. Adapt `.skills/universal-build-verify.md` for Target Project
Customize the compilation and test commands inside `.skills/universal-build-verify.md` to match the detected build system:
- E.g., for Rust: `cargo build` and `cargo test`
- E.g., for Node/TS: `npm run build` and `npm test`
- E.g., for Python: `pytest` or `python -m unittest`
- E.g., for C/C++: `cmake --build build` and `ctest --test-dir build`

### 4. Safe Non-Destructive Rules Merge
Inspect `AGENTS.md` (or `GEMINI.md` / `CLAUDE.md`). **DO NOT overwrite existing project rules.**
Append the `## 24h Unattended Dual-Terminal Workflow` section to the end of the rule file, containing:
- Dual-terminal workflow & dual-track offloading summary.
- Single-directory sequential frontier strategy (preserves warm build caches and avoids multi-worktree disk bloat).
- Strict English inter-AI protocol.
- Atomic tracer-bullet task format schema.
- Safe Git Log rules (`git log -n 1 --stat`, strictly no `git diff` / raw logs in discussion context).
- Linear Git Rebase & Fast-Forward branch integration rules.

### 5. Update `.gitignore` (Append-Only)
Safely append the worker runtime artifacts to `.gitignore` without modifying existing entries:
```gitignore
# 24h Unattended Worker Artifacts
.worker.env
worker*.status
.worker*.log
.worker*.pid
PAUSE
.scratch/
tasks.txt.lock/
```

### 6. Verification
1. Run `bash -n worker.sh` syntax check.
2. Run `RUN_ONCE=1 ./worker.sh` to confirm `.worker.env` loading, OS detection, and graceful zero-queue exit.
3. Report to the human that the unattended dual-terminal workflow is successfully set up and ready to run via `./worker.sh` in Terminal B.
