---
name: calibrate-task-granularity
description: "Calibrate and decide task granularity (Level 1 Coarse, Level 2 Medium, Level 3 Micro) dynamically based on the module's granularity profile and past worker performance."
---

# Calibrate Task Granularity

Dynamically determine ticket resolution (instruction density) and target scopes when decomposing requirements into `tasks.txt`.

## 1. Ticket Resolution Ladder (No Arbitrary File Caps)

Do not restrict necessary vertical-slice files (interfaces, implementations, call-sites, tests). Instead, control **instruction density**:

| Level | Granularity & Mode | Planner Instruction Style | Worker Autonomy |
| :---: | :--- | :--- | :--- |
| **1** | **Macro (Intent-Driven)** | High-level goals & acceptance intent. Declare all slice targets in `TARGET:`. | Worker implements internal helpers autonomously using Matt Skills. |
| **2** | **Standard (Structural)** | Explicit target files, function signatures, and error boundaries. | Worker implements specified contracts directly. |
| **3** | **Micro (Blueprint Mode)** | **Zero-ambiguity blueprint**: exact type signature diffs & step-by-step pseudocode in `ACTION:`. | Worker executes fill-in-the-blank instructions with 0 guesswork. |

## 2. Multi-Interface & Refactor Authorization Gates

Planner MUST NOT approve multi-interface targets or `[REFACTOR]` tasks without satisfying all 4 gates:

1. **Inseparability**: Splitting would cause intermediate commit build/test failures.
2. **Vertical Slice**: Cohesive protocol -> implementation -> test only; no horizontal sprawl across decoupled systems.
3. **Profile Credit**: Target module has >= 4.5 stars in `docs/agents/granularity-profile.json`. For lower-credit modules, Planner must use **Level 3 Blueprint Mode**.
4. **Topology Proof**: Broad refactors require a prior verified `[DIAGNOSTIC]` or `[RESEARCH]` topology report with interface skeletons in `.reports/<issue-slug>/`.

## 3. Dynamic Sizing & Ticket Formatting Protocol

1. **Read Profile**: Inspect `docs/agents/granularity-profile.json` for current subsystem rating.
2. **Blast Radius Limits**:
   - **Level 3 (Micro / 1-2 stars)**: Max 40 lines deleted per task.
   - **Level 2 (Standard / 3-4 stars)**: Max 150 lines deleted per task.
   - **Level 1 (Macro / 5 stars)**: Unlimited deletions, strictly bounded by `TARGET:` whitelist.
3. **Format Task Line (Mandatory Schema with `FORBIDDEN_SHORTCUTS:`)**:
   ```text
   TASK-001 | LEVEL: 1 | TARGET: src/calc.py, tests/test_calc.py | ACTION: Implement Calculator engine | VERIFY: pytest tests/test_calc.py | FORBIDDEN_SHORTCUTS: No sleeps, no error swallowing with try?, no assertion deletion | CONSTRAINTS: Pure stdlib
   ```
4. **Clean Pivot Privilege**: If fixing side-effects from a previous ticket requires >2 additional patch tickets or triggers `[SCOPE_BLOCKED]`, DO NOT stack patches. Roll back to `nightshift-session-base` and re-issue a unified vertical slice or Expand-Migrate-Contract plan.
5. **Post-Task Calibration**: Update `granularity-profile.json` using `/score-worker-performance` after reading `progress.log`.

## 4. Cross-Module Refactoring Strategies (Dual-Track)

When refactoring across multiple interfaces or files based on `[RESEARCH]` findings:

*   **Track A: Atomic Vertical-Slice (Small/Medium: <= 5 files & >= 3 stars)**:
    - Issue a single `[CODE: REFACTOR]` ticket with Interface, implementations, call-sites, and tests in `TARGET:`.
    - Enforces **Assertion Non-Decrease Gate** (test calls updated, but assertion count cannot decrease).
    - Structural verification in `VERIFY:` (e.g. `<test_cmd> && ! grep -rn "<Deprecated_Symbol>" Sources/`).

*   **Track B: Expand-Migrate-Contract (Large-Scale: > 5 files or contains 1-star module)**:
    - Strictly forbids broken intermediate commits. Decompose into 3 green-to-green phases:
      1. `[CODE: EXPAND]`: Introduce new interface and provide temporary default adapters/shims for old interface. (Build & Test 100% PASS).
      2. `[CODE: MIGRATE]`: Incrementally migrate downstream caller modules in independent atomic tickets.
      3. `[CODE: CONTRACT]`: Once old interface references reach 0, remove old interface and shims.
    - Mandatory Safety Checkpoint: Planner creates `git tag -f nightshift-refactor-base` before issuing Task 1.
