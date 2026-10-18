# Architecture Review: Dual-Terminal Workflow vs. Matt Pocock Skills & Large-Project Scalability

## Executive Summary
This document reviews the architectural alignment between our **24-Hour Unattended Dual-Terminal Framework** and **Matt Pocock's Skills Ecosystem** (`ask-matt`, `implement-spec`, `chief-of-staff`, `to-tickets`, `tdd`, `retro`). It analyzes the real-world overhead of Git Worktrees on large codebases, evaluates the trade-offs of parallelization, and establishes the definitive operating protocol for porting this workflow to any enterprise repository.

---

## 1. Large-Project Reality Check: Worktree Overhead vs. Sequential Frontier

When scaling background AI workers, parallelization via Git Worktrees (`git worktree add`) is often the first intuitive idea. However, on large-scale enterprise projects (100k+ lines, large dependency trees, compiled artifacts), **blind worktree parallelization creates severe overhead**:

| Dimension | Git Worktree Parallel Swarm | Single-Directory Sequential Frontier (Recommended) |
| :--- | :--- | :--- |
| **Disk Overhead** | **Severe (Nx duplication)**. 4 workers = 4 full checkout trees + 4 duplicated dependency directories (`node_modules`, `.venv`, `target/`). | **Zero**. Operates on the existing working directory. |
| **Build & Cache Cold Starts** | **Severe**. Each worktree lacks warm compilation caches (`ccache`, CMake build dirs, Cargo caches), triggering repeated full builds. | **Near Instant (Warm Incremental Builds)**. Shares compilation artifacts across sequential tasks. |
| **Shared Resource Contention** | **High Collision Risk**. Test suites contending for fixed ports (e.g., 3000, 8080), Docker containers, or local database ports (Postgres 5432). | **Zero Contention**. Only one test suite runs at any given moment. |
| **Git Merge & Conflict Burden** | **High**. Reconciling concurrent branch merges into the integration branch often requires manual human conflict resolution. | **Zero Merge Conflict**. Changes build linearly and atomically on the integration branch. |
| **AI Context Hygiene** | Requires coordinating multiple disparate AI processes. | **Pristine**. Single worker resets context per task (`agy -p` per task), strictly avoiding context pollution. |

### Architectural Conclusion:
> [!IMPORTANT]
> For **95% of large and medium codebases**, the **Single-Directory Sequential Frontier** is vastly superior in speed, resource consumption, and reliability compared to multi-worktree execution. Git Worktrees should remain an **optional, advanced mode** reserved only for microservices or repositories with completely decoupled directories.

---

## 2. Deep Philosophical Alignment: Dual-Terminal Framework & Matt Pocock Skills

Is our 24-hour Dual-Terminal Framework aligned with Matt Pocock's core design philosophy? **Yes, they share identical core values:**

### 2.1 Context Hygiene & Smart Zone Preservation
- **Matt Pocock's Rule**: Keep planning in one unbroken window until `/to-tickets`, then `/clear` context between ticket implementations. The model must always operate within its **Smart Zone** (~150k tokens) where reasoning is sharp.
- **Dual-Terminal Realization**:
  - **Terminal A (Interactive Architect)**: Maintains strategic focus with the human, decomposing goals into atomic single-line English tasks without cluttering its context with build logs or file contents.
  - **Terminal B (Worker Daemon)**: Headless, stateless process (`worker.sh`) executing `agy -p` per task. Each task starts with fresh, clean context and terminates upon completion, achieving 100% context hygiene automatically.

### 2.2 Context Pointers over Text Duplication
- **Matt Pocock's Rule**: *"Communication to and from subagents should be sparse. Communicate primarily through context pointers: research notes, previous commits, and specs. Don't duplicate information already available via pointers."*
- **Dual-Terminal Realization**:
  - `tasks.txt` uses compact, pointer-rich single lines (`TARGET: src/calc.py | ACTION: ... | VERIFY: ...`).
  - `progress.log` is capped at `<= 15 lines` of verified facts and commit hashes, preventing context explosions.

### 2.3 Single-Seam Autonomy & Test-Driven Development (TDD)
- **Matt Pocock's Rule**: Implementations are driven by `/tdd` (Red-Green-Refactor) locked down by regression tests.
- **Dual-Terminal Realization**: Worker executes `.skills/universal-build-verify.md` with 100% test pass enforcement, atomic commit, and max 3-attempt automated self-healing.

### 2.4 Continuous Environment Improvement (`/retro`)
- **Matt Pocock's Rule**: After a build, `/retro` modifies the **environment**, not the code: checks, linters, steering files, and coding standards so the next build starts in a better environment ("Pit of Success").
- **Dual-Terminal Realization**: Worker maintains `.worker.notes.md` (recording build quirks and flags) and updates `granularity-profile.json`.

---

## 3. Key Concepts Adopted from Matt Pocock into Our Framework

To further sharpen our workflow, the following high-value concepts from Matt Pocock's skills are officially integrated into our treaties:

### 3.1 Tracer-Bullet Slicing (`to-tickets`)
Tasks written by Terminal A into `tasks.txt` MUST be **vertical tracer bullets** (piercing end-to-end functionality from interface to implementation and test), rather than broad horizontal technical layers (e.g., never "write all schemas", then "write all APIs").

### 3.2 Task Graph & Frontier (`implement-spec`)
While `tasks.txt` is read sequentially, tasks can declare dependencies:
```text
TASK-004 | AFTER: TASK-003 | TARGET: src/calc.py | ACTION: ... | VERIFY: ...
```
This ensures downstream tasks are never executed out of order, and allows the Architect to express a true **Task Graph DAG**.

### 3.3 Integration Branch Sandboxing (`implement-spec`)
- Batch feature tasks are NEVER committed directly to `main`.
- Terminal A creates an integration branch (`git checkout -b feature/<batch-name>`).
- Terminal B commits atomic tracer-bullet commits onto this feature branch.
- Upon batch completion, Terminal A runs `/code-review` across the feature branch diff, and linearly fast-forward merges (`git merge --ff-only`) into `main`.

### 3.4 Pre-flight Exploration Subagent (Track 1 Offload)
Before queueing complex tasks, Terminal A offloads exploratory file-reading to an in-session Subagent (`invoke_subagent`). The subagent writes scratch notes, allowing Terminal B's worker to focus purely on implementation with zero exploration overhead.

---

## 4. Live Human-in-the-Loop Feedback & Dynamic Queue Rescheduling

### 4.1 The Live Feedback Scenario
Consider a batch of 10 tasks queued in `tasks.txt`:
1. **Incremental Cumulative Landing**:
   - As Worker finishes Task 1, 2, and 3, each commit is committed to the local working branch with full verification (`100% test pass`).
   - The codebase in the working tree is live, working, and up to date.
2. **Concurrent Human Testing in Terminal A**:
   - While Worker continues executing Task 4 in Terminal B, the Human or Planner in Terminal A can execute unit tests, launch the dev server, or smoke test the live functionality produced by Tasks 1–3.
3. **Mid-Flight Feedback & Triage**:
   - Suppose Human discovers an edge-case bug in Task 2 (e.g. division by zero in percentage calculation).
   - Human immediately provides feedback to Terminal A: *"Found a zero-division edge case in percentage"*.
4. **Planner Queue Scanning & Deduplication**:
   - Planner inspects the remaining unpopped queue (`tasks.txt`, containing Tasks 5–10).
   - Planner checks if any of Tasks 5–10 overlap, conflict, or duplicate with this bug fix. If Task 8 was originally planning to touch the same function, Planner modifies or merges it.
5. **Hot Preemption & Atomic Insertion**:
   - Planner formats an urgent tracer-bullet task:
     ```text
     TASK-003B | LEVEL: 1 | TARGET: src/calc.py, tests/test_calc.py | ACTION: Fix zero-divisor edge case in percentage | VERIFY: python3 -m unittest discover tests | CONSTRAINTS: 100% test pass
     ```
   - Planner invokes `scripts/reorder_queue.sh` (which acquires `tasks.txt.lock`) and injects `TASK-003B` at the very top of `tasks.txt` ahead of Task 5.
6. **Seamless Zero-Conflict Pick-up**:
   - When Task 4 finishes its turn, Worker opens `tasks.txt` and immediately claims `TASK-003B`.
   - The bug is fixed and committed before Task 5 even begins!

### 4.2 Why This Completely Obsoletes Worktree Duplication
- **In Multi-Worktree Parallelism**:
  - Tasks 1, 2, 3, 4, 5... are split across 5 different worktrees on divergent branches.
  - Human cannot test the cumulative result of 1+2+3 because they haven't been integrated yet.
  - A bug discovered in Task 2 means Tasks 4 and 5 were built on faulty assumptions, creating a nightmare of three-way merge conflicts and re-work across all worktrees.
- **In Single-Working-Tree Dynamic Rescheduling**:
  - The working directory maintains a single, pristine linear history on the integration branch.
  - Zero disk duplication, zero cold compiler restarts, zero test port collisions.
  - Human feedback is immediate, and the queue is completely malleable in real time.

---

## 5. Skills Ecosystem Matrix

| Skill | Role in Framework | Operating Terminal | Interaction Pattern |
| :--- | :--- | :--- | :--- |
| **`chief-of-staff`** | Strategic DRI & Long-Running Orchestrator | Terminal A (Architect) | Coordinates roadmaps, sets schedules, aligns pit-of-success environment. |
| **`wayfinder`** | High-level foggy idea mapping | Terminal A (Architect) | Charts decision tickets on complex initiatives. |
| **`grill-with-docs`** | Requirements sharpening | Terminal A (Architect) | Interviews human, updates `GLOSSARY.md` and ADRs. |
| **`to-spec` / `to-tickets`** | Decomposition into tracer bullets | Terminal A (Architect) | Emits structured single-line tasks into `tasks.txt`. |
| **`universal-build-verify`** | Automated TDD & Smoke Testing | Terminal B (Worker) | Enforces 100% test pass before git commit. |
| **`code-review`** | Two-axis review (Standards + Spec) | Terminal A (Architect) | Final acceptance check on integration branch before merge. |
| **`retro`** | Environment & steering evolution | Terminal A & B | Updates `.worker.notes.md`, linter configs, coding standards. |
| **`watch-worker-queue`** | Zero-token completion sentinel | In-Session Subagent | Wakes Terminal A when queue is empty or guidance is needed. |
