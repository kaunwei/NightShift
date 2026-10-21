---
name: calibrate-task-granularity
description: "Calibrate and decide task granularity (Level 1 Coarse, Level 2 Medium, Level 3 Micro) dynamically based on the module's granularity profile and past worker performance."
---

# Calibrate Task Granularity

Dynamically determine task granularity when decomposing requirements into `tasks.txt`.

## 1. Granularity Ladder

| Level | Granularity | Scope | When to Use |
| :---: | :--- | :--- | :--- |
| **1** | **Coarse (Feature / Seam)** | Public interface, contract, and verification test. Worker creates internal helpers autonomously. | Default for verified modules with >= 4.5 star ratings in `granularity-profile.json`. |
| **2** | **Medium (Component / Slice)** | Discrete module slices (e.g., model vs processor vs serializer). Specific files and signatures. | Modules with 3-4 stars, or after 1 retry on past tasks. |
| **3** | **Micro (Function / Step)** | Surgical function logic, exact algorithms, minimal diffs. | Modules with 1-2 stars, previous blocks, or explicit user mandate. |

## 2. Multi-Interface & Refactor Authorization Gates

Planner MUST NOT approve multi-interface targets or `[REFACTOR]` tasks without satisfying all 4 gates:

1. **Inseparability**: Splitting would cause intermediate commit build/test failures.
2. **Vertical Slice**: Cohesive protocol -> implementation -> test only; no horizontal sprawl across decoupled systems.
3. **Profile Credit**: Target module has >= 4.5 stars in `docs/agents/granularity-profile.json`. Unrated or low-credit modules are restricted to Level 2/3 single units.
4. **Topology Proof**: Broad refactors require a prior verified `[DIAGNOSTIC]` or `[RESEARCH]` topology report in `.reports/<issue-slug>/`.

## 3. Dynamic Sizing Protocol

1. **Read Profile**: Inspect `docs/agents/granularity-profile.json` for current subsystem rating.
2. **Blast Radius Limits**:
   - **Level 3 (Micro / 1-2 stars)**: Max 40 lines deleted per task.
   - **Level 2 (Standard / 3-4 stars)**: Max 150 lines deleted per task.
   - **Level 1 (Macro / 5 stars)**: Unlimited deletions, strictly bounded by `TARGET:` whitelist.
3. **Unfamiliar Subsystem Probe**:
   - Start with a **Level 2 Medium Probe** task.
   - If verified in 1 attempt (5 stars), upgrade profile and scale subsequent tasks to **Level 1 Coarse**.
4. **Format Task Line**:
   ```text
   TASK-001 | LEVEL: 1 | TARGET: src/calc.py, tests/test_calc.py | ACTION: Implement Calculator engine with add, subtract, multiply, divide | VERIFY: pytest tests/test_calc.py | CONSTRAINTS: Pure Python stdlib, zero warnings
   ```
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
