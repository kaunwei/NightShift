# Engineering Specification: 24h Unattended Dual-Terminal Framework

This document specifies the technical architecture, protocols, data schemas, and lifecycle guarantees of the 24-Hour Unattended Dual-Terminal AI Development Framework.

---

## 0. Role Definition & Duty Boundary Firewall

The framework enforces a strict division of responsibilities:
- **Terminal A (Interactive Planner / Architect)**:
  - Default Reflex: Grooms requirements, models domain, decomposes into atomic contracts in `tasks.txt` (`[CODE]`, `[DIAGNOSTIC]`, `[RESEARCH]`), and yields control. NEVER modifies application code directly for routine tasks (`Sources/`, `src/`, `app/`, `lib/`, `tests/`) and avoids unbounded in-session debugging loops.
  - Sovereign Exceptions:
    1. *Anti-Rubber-Stamp Audit*: Mandated deep inspections on `Attempts > 1`, `Confidence < 1.0`, or critical architectural seams.
    2. *Level 3 Implementation Escalation*: Intervenes when a coding task was **already at Level 3 (Micro)** and Worker failed 3 retries, followed by a mandatory post-mortem allocation retro in `granularity-profile.json` and `.worker.notes.md`.
    3. *Diagnostic Evasion & Bogus Report Intervention*: Intervenes when Worker repeatedly produces vague/hallucinated reports or fails to isolate the issue after 2-3 retries without verifiable evidence. Planner directly isolates the root cause and logs quirks in `.worker.notes.md`.
    4. *Explicit User Mandate*: User explicitly asks Planner to modify code directly.
  - Active Skills: `/planner`, `/explore`, `/domain-modeling`, `/codebase-design`, `/tdd`, `/to-tickets`, `/code-review`, `/improve-codebase-architecture`, `/retro`.
- **Terminal B (Background Worker Daemon)**:
  - Headless execution engine. Reads `tasks.txt`, executes in `.worker-tree` (or root in Mode 2), runs build/tests, auto-commits with Conventional Commits, and stages `.preview/` snapshots.

---

## 1. System Topology & Dual-Terminal Architecture

The framework physically separates interactive architectural reasoning from unattended headless execution:

```
┌────────────────────────────────────────────────────────────────────────┐
│               Terminal A: Interactive Architect (In-Session)           │
│  • Discuss architecture & requirements with user in Chinese/English.   │
│  • Hot Preemption: Offload diagnostics to Worker with line 1 priority. │
│  • Decompose goals/bugs into single-line atomic English contracts.     │
│  • Writes tasks to tasks.txt and yields control immediately.           │
│  • Sentinel Subagent deployed for zero-token batch wakeup.             │
│  • Guides user with project-native preview commands for .preview/.     │
│  • Automatically merges feature/worker-frontier upon batch completion. │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (FIFO tasks.txt with atomic lock)
┌───────────────────────────────────▼────────────────────────────────────┐
│          Terminal B: Background Worker Daemon (worker.sh)              │
│  • Zero-argument background daemon (sources .worker.env).              │
│  • Evaluates WORKER_ISOLATION toggle (Mode 1: Worktree / Mode 2: Root) │
│  • Headless stateless CLI per task (Codex or agy, selected via env).   │
│  • Enforces universal-build-verify.md (100% test pass).                │
│  • Max 3 automated repair attempts -> clean rollback on block.         │
│  • Unified Conventional Commit & prepends <=15 lines to progress.log.  │
│  • Stages verified snapshot to .preview/ drop-box on task PASS.        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Workspace Isolation & Execution Modes

Configured via `WORKER_ISOLATION` in `.worker.env`:

### 2.1 Mode 1: Dual-Worktree Persistent Isolation (`WORKER_ISOLATION=1`, Default)
- **Topological Invariant**: Exactly **TWO** worktrees exist at any time:
  1. `Main Workspace` (`main` or active user branch): Human terminal, IDE, and test bench.
  2. `Worker Workspace` (`.worker-tree` on branch `feature/worker-frontier`): Daemon sandbox.
- **Persistence Guarantee**: `.worker-tree` is **never destroyed** between tasks. It remains warm across the entire 24h cycle to preserve build and compiler caches.
- **Untracked Config Mirroring**: `.worker-tree` automatically mirrors `.env` and `.worker.env` from the project root upon initialization.
- **Cache Symlinking**: Heavy dependency directories (`node_modules`, `.venv`) are symlinked from the main workspace to eliminate disk bloat and cold compile starts.
- **Conflict Prevention**:
  - Worker subshell runs with port offset (`PORT=3001`, `TEST_PORT=3001`).
  - Worker runs with isolated database paths (`DATABASE_URL=sqlite:///.worker-tree/test.db`).

### 2.2 Mode 2: Single-Tree In-Place Execution (`WORKER_ISOLATION=0`)
- **Use Case**: Hardware-locked repositories, fixed serial/COM devices, or environments restricted to a singleton port (e.g., port 22).
- **Behavior**: Worker operates directly in the project root on the active branch without creating `.worker-tree`.

---

## 3. Immutable Preview Drop-box Protocol (`.preview/`)

To enable painless early access without race conditions, compiler file locks (`ETXTBSY`), or mid-task syntax breaks:

1. **Trigger Condition**: Strictly upon **100% verification test pass** for an individual task.
2. **Atomic Publication**:
   - For script projects: `git archive feature/worker-frontier | tar -x -C .preview/`.
   - For compiled projects: Outputs in `build/bin`, `target/debug`, or `dist` are atomically staged into `.preview/`.
3. **Metadata Contract (`.preview/version.json`)**:
   ```json
   {
     "task_id": "TASK-005",
     "commit": "54cf031",
     "summary": "Add square_root method and unit tests",
     "updated_at": "2026-10-19T05:30:03Z"
   }
   ```
4. **Zero-Script Human Preview**:
   - Planner (Terminal A) inspects `.preview/version.json` and prompts the user with the exact native command:
     - Compiled: `./.preview/<binary>`
     - Interpreted: `python3 .preview/src/<entrypoint>.py`
   - Zero compilation required; zero git merge required.

---

## 4. Zero-Intervention Auto-Merge Protocol

When all tasks in `tasks.txt` are completed:
1. Sentinel Subagent detects zero remaining tasks and worker `IDLE` / `STOPPED` state via `scripts/watch_worker.sh`.
2. Sentinel triggers a proactive wakeup event in Terminal A.
3. Planner reads `head -n 15 progress.log` and verifies that all tasks passed.
4. If in Mode 1 (`WORKER_ISOLATION=1`):
   - Planner executes:
     ```bash
     git merge --ff-only feature/worker-frontier
     ```
   - Main workspace is cleanly updated to the latest verified frontier without manual human git commands.

---

## 5. Task Schema & Dynamic Granularity Ladder

### 5.1 Single-Line Tracer-Bullet Contract
```text
TASK-XXX | LEVEL: 1 | AFTER: <task_id> | TARGET: <file_paths> | ACTION: <concrete logic> | VERIFY: <test command> | CONSTRAINTS: <bounds>
```

### 5.2 Dynamic Granularity Levels (Implementation & Exploration)
- **Level 1 (Coarse / Macro)**:
  - *Implementation*: Defines public interface, verification test, and constraints. Worker has full autonomy on internal data structures and helpers.
  - *Exploration (`[DIAGNOSTIC]` / `[RESEARCH]`)*: Full-spectrum project-wide cross-interface trace (e.g. UI ➔ ViewModel ➔ Engine ➔ OS lifecycle).
- **Level 2 (Medium / Meso)**:
  - *Implementation*: Decomposes into distinct modules (e.g. data schema vs engine).
  - *Exploration*: Interface contract and state synchronization trace between interacting services.
- **Level 3 (Micro / Step)**:
  - *Implementation*: Precise function-level instructions used when worker requested guidance or previous attempts struggled.
  - *Exploration*: Function deep dive into specific timing calculations, drift, race conditions, or localized error branches.

### 5.3 Granularity Escalation Ladder & Level 3 Sovereign Intervention
1. **Escalation on Failure**: When a task blocks (`[BLOCKED]`):
   - Level 1 Blocked ➔ Demote to Level 2 (split into component slices).
   - Level 2 Blocked ➔ Demote to Level 3 (micro function-level instructions & exact tests).
2. **Level 3 Failure Threshold (Planner Sovereign Intervention)**:
   - When a task is **ALREADY at Level 3 (Micro)** and Worker still blocks/fails after 3 retries, this indicates deep architectural contradictions, environment quirks, or subtle bugs beyond the smaller model's scope.
   - **Planner Steps In**: Planner reads `.worker.log`, inspects target code directly, applies the surgical fix, runs verification tests, and commits.
3. **Post-Mortem Allocation Retro**:
   - Planner **MUST record why the allocation failed** in:
     - `docs/agents/granularity-profile.json` (subsystem score & notes)
     - `.worker.notes.md` (compiler traps / repo quirks discovered)
   - Permanently enhances future task allocation efficiency.

### 5.4 Hierarchical Progressive Exploration Protocol
For complex cross-module features and defects, Planner grooms and decides progressively from coarse to fine:
1. **Stage 1 (Macro Survey)**: Issue `LEVEL: 1 [RESEARCH]` / `[DIAGNOSTIC]` to map affected subsystems and lifecycle pipelines.
2. **Stage 2 (Meso Contract Trace)**: Issue `LEVEL: 2 [DIAGNOSTIC]` to examine inter-module communication protocols, event propagation, and contract breakages.
3. **Stage 3 (Micro Deep-Dive)**: Issue `LEVEL: 3 [DIAGNOSTIC]` to isolate internal calculations, race conditions, or timing drift.
4. **Stage 4 (Sound Architectural Decision)**: Armed with verified facts, Planner makes high-confidence decisions and allocates decoupled, single-seam `[CODE]` tickets.

---

## 6. Unified Conventional Commit Standard

Both Planner and Worker strictly format git commits as follows:

```bash
git commit -m "<type>(<scope>): <concise action description in English <= 60 chars> (<task_id>)" -m "<1-3 summary bullet points of changes>

Task: <task_id> (<granularity_level>)
Scope: <target_files>
Verification: <test command> (<measurable result, e.g. 8/8 passed, 100% OK>)
Attempts: <attempts_count> | Confidence: <confidence_score>"
```

- **Allowed types**: `feat`, `fix`, `refactor`, `test`, `perf`, `docs`.
- **Title Line Guardrail**: Raw task strings (`| LEVEL: ... | TARGET: ...`) are **strictly prohibited** in the commit title line.

---

## 7. Dynamic Queue Rescheduling & Hot Preemption

1. **Atomic File Locking**:
   - `worker_runtime.py` and `scripts/reorder_queue.sh` use POSIX directory locking (`mkdir tasks.txt.lock`) with automated retry backoff to ensure collision-free queue pops and insertions.
2. **Live Feedback Hotfix**:
   - If human spots an issue during early preview in `.preview/`, Planner inspects remaining tasks in `tasks.txt`, deduplicates redundant tasks, and injects `[HOTFIX]` tasks at line 1.
   - Worker picks up the hotfix immediately after finishing its current turn.

---

## 8. Two-Tier Anti-Rubber-Stamping Audit Protocol

To ensure acceptance integrity without token bloat:
1. **Tier 1 (Fast Screening)**: Read `head -n 15 progress.log` and `git log -n 1 --stat`. Low-token acceptance for routine tasks with 1 attempt and 1.0 confidence.
2. **Tier 2 (Mandatory Deep Audit)**:
   - Triggered whenever:
     - The task touches a critical architectural seam.
     - Worker reports `Attempts > 1`.
     - Worker reports `Confidence < 1.0`.
   - Action: Planner directly inspects git diffs, views modified line slices, or re-runs test suites locally to prevent simulated or hallucinated test passes.

