# Parallel Worker Architecture & Skills Review

## Executive Summary
This document reviews the integration between our current 24-Hour Unattended AI Development Workflow and the skills ecosystem (Matt Pocock skills + Architect/Worker custom skills). It analyzes architectural bottlenecks in the current single-worker FIFO setup, identifies friction points across skills, and defines the blueprint for **Parallel Worktree Worker Swarms**.

---

## 1. Current Workflow Bottlenecks & Friction Points

### 1.1 Single Working Tree Collision (Fatal in Multi-Process)
- **Problem**: In the current single-worker setup, `worker.sh` runs directly in the root repository. If a worker fails, its cleanup function invokes:
  ```bash
  git restore .
  git clean -df
  ```
  If multiple workers run concurrently in the same working tree, Worker A's failure rollback will wipe out uncommitted changes currently being written by Worker B.
- **Git Lock Contention**: Running parallel `git add` and `git commit` inside a single working directory triggers `.git/index.lock` collisions.
- **Solution**: **Git Worktree Isolation**. Each parallel worker must operate in its own physical worktree (e.g. `.worktrees/worker-1`, `.worktrees/worker-2`) linked to independent feature branches (`feature/worker-1`, `feature/worker-2`).

### 1.2 Head-of-Line Blocking in Single FIFO Queue (`tasks.txt`)
- **Problem**: When a long-running, multi-attempt task (Level 2 or 3) is at the front of `tasks.txt`, subsequent small, independent tasks are blocked even when computing resources and AI rate limits are available.
- **Race Condition on Task Popping**: Multiple workers reading `tasks.txt` concurrently without atomic locking would claim the identical task.
- **Solution**:
  1. **Atomic Directory Lock**: Implemented in `worker.sh` using POSIX atomic `mkdir "$TASKS_FILE.lock"`.
  2. **Seam-Tagged Tasks**: Tasks specify their target architectural seam (`SEAM: <subsystem>`), allowing workers to safely parallelize across orthogonal subsystems.

### 1.3 Progress Log Contention (`progress.log`)
- **Problem**: The protocol dictates prepending `<= 15 lines` at the very top of `progress.log`. Concurrent writes cause partial writes or interleaved corrupted records.
- **Solution**: Workers append to individual log shards (e.g. `.worker.worker-1.log`) and acquire the queue lock when prepending to the shared `progress.log`, or Sentinel aggregates completed tasks.

---

## 2. Skills Conflict & Alignment Review

| Skill | Current State | Friction / Conflict | Recommended Enhancement |
| :--- | :--- | :--- | :--- |
| **`calibrate-task-granularity`** | Sizes tasks into Level 1 (Coarse), 2 (Medium), 3 (Micro) based on history. | Evaluates tasks in isolation; does not evaluate cross-task file or seam overlap. | Add **Seam Independence Check**: Only assign parallel execution to tasks touching disjoint file trees. Overlapping seams must remain serialized. |
| **`chief-of-staff`** *(Newly Added)* | Single-session DRI coordinating subagents and schedules. | Designed originally for interactive subagents, not headless background daemons. | Reposition Chief-of-Staff as the **Parallel Swarm Orchestrator**: Planner uses it to decompose batch roadmaps into independent worktree tasks. |
| **`codebase-design`** | Defines deep modules and narrow interfaces. | None. Highly synergistic. | Deep module seams provide the exact boundary required for conflict-free parallel workers. |
| **`tdd`** | Red-green-refactor cycle on single seams. | Test suite execution might contend on fixed resources (ports, test DBs). | Worker test runners should use ephemeral resources (e.g. dynamic ports, in-memory SQLite, isolated temp dirs). |
| **`diagnosing-bugs`** | Diagnosis loop requiring tight feedback commands. | Unattended workers may retry unguided on environmental flakes. | Retain strict 3-retry limit with immediate `[NEED_GUIDANCE]` escalation. |
| **`watch-worker-queue`** | Sentinel monitors single `worker.status`. | Blind to multi-worker states (`worker.worker-1.status`, etc.). | Upgrade Sentinel to aggregate status across all active `worker.*.status` files. |
| **`configure-unattended-worker`** | Writes single `.worker.env`. | Did not distinguish macOS vs Linux differences or multi-worker IDs. | **Resolved**: Updated with mandatory `.worker.env` check, `OS_TYPE` detection/override, and `WORKER_ID`. |

---

## 3. Parallel Worker Architecture Blueprint (Git Worktree Swarm)

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Terminal A: Interactive Architect                    │
│   • Uses /chief-of-staff & /calibrate-task-granularity                 │
│   • Slices goals into Orthogonal Seams (Seam A, Seam B, Seam C)        │
│   • Writes atomic tasks to tasks.txt                                   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Atomic Locking FIFO Queue)
             ┌──────────────────────┴──────────────────────┐
             ▼                                             ▼
┌───────────────────────────────┐             ┌───────────────────────────────┐
│     Worker 1 (WORKER_ID=w1)   │             │     Worker 2 (WORKER_ID=w2)   │
│ • Directory: .worktrees/w1/   │             │ • Directory: .worktrees/w2/   │
│ • Branch: feature/worker-1    │             │ • Branch: feature/worker-2    │
│ • Status: worker.w1.status    │             │ • Status: worker.w2.status    │
│ • CLI: agy accept-edits       │             │ • CLI: agy accept-edits       │
│ • Scope: Seam A (e.g. auth)   │             │ • Scope: Seam B (e.g. billing)│
└──────────────┬────────────────┘             └───────────────┬───────────────┘
               │                                              │
               ▼                                              ▼
┌────────────────────────────────────────────────────────────────────────┐
│                  Linear Integration & Sentinel Verifier                │
│   • Fast-forward / Rebase merges into main once verify passes.         │
│   • Watcher Sentinel monitors all worker.*.status states.              │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Key Implementation Invariants
1. **Zero Working Tree Contamination**: Workers NEVER share a physical directory.
2. **Atomic Pop via Directory Lock**: `mkdir tasks.txt.lock` guarantees only one worker claims a line at a time.
3. **Cross-Platform Compatibility**: Uses standard POSIX primitives tested across macOS (Darwin) and Linux (Ubuntu).
4. **Mandatory Configuration Isolation**: Each worker uses its own `.worker.env` or passes `WORKER_ID` to derive isolated status and log files.

---

## 4. Completed Foundation Upgrades
1. **Mandatory `.worker.env` Enforcement**:
   - `worker.sh` verifies `.worker.env` exists in the script's directory and aborts with clear template copy instructions if missing.
2. **OS Switching (macOS & Ubuntu)**:
   - Auto-detection via `uname -s` and `/etc/os-release`.
   - Explicit override supported via `OS_TYPE="mac"`, `OS_TYPE="ubuntu"`, or `OS_TYPE="auto"`.
   - Dynamic CPU detection (`sysctl -n hw.ncpu` vs `nproc`).
   - Dynamic timeout binary selection (`gtimeout` vs `timeout` vs background watchdog).
3. **Multi-Worker Identity (`WORKER_ID`)**:
   - Status files dynamically route to `worker.status` (default) or `worker.<WORKER_ID>.status`.
   - Log files route to `.worker.log` (default) or `.worker.<WORKER_ID>.log`.
   - PIDs route to `.worker.pid` (default) or `.worker.<WORKER_ID>.pid`.
4. **Atomic Task Popping**:
   - Directory-lock (`tasks.txt.lock`) prevents task claim collisions in concurrent runs.
