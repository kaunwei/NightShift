# Autonomous AI Porting Guide
## How an AI Agent Migrates the 24h Unattended Dual-Terminal Framework to Another Project

If you are an AI assistant tasked with adopting or migrating this 24-Hour Unattended Framework into a target repository, follow this deterministic, step-by-step procedure.

---

## 1. Architectural Overview & Matt Pocock Skills Synergy
This framework provides:
- **Terminal A (Interactive Architect)**: Human + AI plan architectures, groom specs (`to-spec`, `to-tickets`), write atomic tracer-bullet tasks to `tasks.txt`, and verify progress via `progress.log` (<=15 lines, zero context pollution).
- **Terminal B (Background Worker)**: `worker.sh` polls `tasks.txt`, runs `agy` with low-cost Flash models (`--mode accept-edits --print-timeout 1800s`), enforces `.skills/universal-build-verify.md`, builds, tests, and auto-commits.
- **Sequential Frontier on Warm Build Cache**: For enterprise codebases, runs tasks sequentially on a single warm working tree to avoid the massive disk, compile-cache, and port collisions of multi-worktree approaches.
- **Integration Branch Sandboxing**: Work on `feature/<batch-name>`, rebase onto `main`, fast-forward merge (`--ff-only`), and delete the feature branch.
- **Cross-Platform Compatibility**: Automatically detects and adapts to macOS (Darwin) and Linux (Ubuntu).

---

## 2. Porting Algorithm (Step-by-Step for Migration AI)

### Step 2.1: Inspect Target Project Stack
Analyze the target workspace:
1. **Language & Build System**:
   - C / C++: Check `CMakeLists.txt` -> Build: `cmake -B build -S . -G Ninja && cmake --build build`, Test: `ctest --test-dir build`
   - Python: Check `pyproject.toml` / `requirements.txt` -> Test: `pytest` or `python -m unittest`
   - Rust: Check `Cargo.toml` -> Build: `cargo build`, Test: `cargo test`
   - Node / TS: Check `package.json` -> Build: `npm run build`, Test: `npm test`
   - Go: Check `go.mod` -> Test: `go test ./...`
2. **Existing Rules**: Check for existing `AGENTS.md`, `GEMINI.md`, or `CLAUDE.md`.

### Step 2.2: Copy Core Assets
Ensure the following files are copied into the target project root:
- `worker.sh` (ensure `chmod +x worker.sh`)
- `.worker.env.example` (template with OS detection and model parameters)
- `.worker.env` (initialized by copying `.worker.env.example` in the same directory as `worker.sh`)
- `scripts/watch_worker.sh` (ensure `chmod +x scripts/watch_worker.sh`)
- `.skills/universal-build-verify.md` (placed at `.skills/universal-build-verify.md`)
- `.worker.notes.md` (initialized with repository build quirks)
- `tasks.txt` (empty or initialized with schema comment)
- `tasks.done` (empty file)
- `progress.log` (empty file with header)

### Step 2.3: Adapt `.skills/universal-build-verify.md`
In `.skills/universal-build-verify.md`, adjust `Step 2.2` and `Step 2.3` to match the target project's build and test commands discovered in Step 2.1.

### Step 2.4: Non-Destructive Merge into `AGENTS.md`
If target project has `AGENTS.md` (or `GEMINI.md` / `CLAUDE.md`), **DO NOT overwrite**. Append the standard block:

```markdown
## 24h Unattended Dual-Terminal Workflow

This repository supports the 24-Hour Unattended Dual-Terminal AI Development Framework.

### 1. Dual-Terminal Architecture & Dual-Track Offload
- **Terminal A (Interactive Architect)**: Discuss with human in Chinese/English, groom requirements into tracer-bullet tasks, write atomic tasks to `tasks.txt`, and inspect `progress.log` for rapid acceptance.
- **Terminal B (Background Worker)**: Runs `./worker.sh`. Stateless process per task, executes build, test, and auto-commits.
- **Track 1 Offload**: Exploratory code-reading is delegated to in-session Subagents (`invoke_subagent`).
- **Track 2 Offload**: Batch unattended execution is delegated to Terminal B.

### 2. Strict Inter-AI English Protocol
- All tasks in `tasks.txt`, summaries in `progress.log`, status in `worker.status`, and git commits MUST be in **strictly English**.

### 3. Atomic Task Format (tasks.txt)
Single-line format:
`TASK-XXX | LEVEL: 1 | TARGET: <files> | ACTION: <concrete logic> | VERIFY: <test command> | CONSTRAINTS: <bounds>`

### 4. Safe Git Log Rules for Acceptance AI
- Allowed: `git log -n 1 --stat`, `git show --stat <commit-hash>`, `git log --oneline -n 5`
- Prohibited: Bare `git log`, `git log -p`, full `git diff` (prevents context explosion).

### 5. Git Rebase & Integration Branch Strategy
Batch features run on an integration branch and merge linearly into `main`:
```bash
git checkout feature/<batch-name>
git rebase main
git checkout main
git merge --ff-only feature/<batch-name>
git branch -d feature/<batch-name>
```
```

### Step 2.5: Safe `.gitignore` Append
Append the following runtime artifacts to target `.gitignore` if not present:
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

### Step 2.6: Verification
1. Run `bash -n worker.sh` syntax check.
2. Run `RUN_ONCE=1 ./worker.sh` to verify mandatory `.worker.env` loading and empty-queue graceful exit.
3. Report completion to the user.
