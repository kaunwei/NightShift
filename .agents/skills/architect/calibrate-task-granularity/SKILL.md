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
2. **Unfamiliar Subsystem Probe**:
   - Start with a **Level 2 Medium Probe** task.
   - If verified in 1 attempt (5 stars), upgrade profile and scale subsequent tasks to **Level 1 Coarse**.
3. **Format Task Line**:
   ```text
   TASK-001 | LEVEL: 1 | TARGET: src/calc.py, tests/test_calc.py | ACTION: Implement Calculator engine with add, subtract, multiply, divide | VERIFY: pytest tests/test_calc.py | CONSTRAINTS: Pure Python stdlib, zero warnings
   ```
4. **Post-Task Calibration**: Update `granularity-profile.json` using `/score-worker-performance` after reading `progress.log`.
