---
name: calibrate-task-granularity
description: "Calibrate task granularity (L1 Macro, L2 Meso, L3 Micro) based on profile credit, and compose Matt-aligned TDD blueprints."
---

# Calibrate Task Granularity

Dynamically size ticket resolution and instruction density when decomposing requirements into `tasks.txt`.

## 1. Resolution Ladder & Matt Workflow Alignment

Control **instruction density** and align with Matt's engineering foundations (`/tdd`, `/codebase-design`, `/diagnosing-bugs`):

| Level | Granularity & Mode | Instruction Density & Planner Role | Worker Autonomy |
| :---: | :--- | :--- | :--- |
| **1** | **Macro (Intent-Driven)** | High-level goal & acceptance intent. Declare all slice targets in `TARGET:`. | Worker designs internal helpers and test suite autonomously using `/tdd` and `/codebase-design`. |
| **2** | **Meso (Structural)** | Explicit target files, function signatures, error boundaries, and single-command test. | Worker implements specified contracts directly via TDD. |
| **3** | **Micro (Blueprint Mode)** | **Zero-ambiguity TDD blueprint**: exact signature diffs, input/output fixtures, and step-by-step logic. | Worker executes fill-in-the-blank implementation with 0 guesswork. |

### Level 3 Micro Blueprint Composition (Matt TDD Sequence)
When authoring `ACTION:` for Level 3 tickets, Planner MUST follow Matt's `/tdd` and `/codebase-design` principles:
1. **Red Contract First**: Define the exact test signature, input fixtures, and failing assertion (e.g. `tests/test_foo.py::test_bar asserts ValueError("invalid")`).
2. **Green Contract**: Specify the exact public type/function signature and pseudocode to satisfy the Red contract with minimal code.
3. **Deep Module Boundary**: Anchor tests and contracts to deep public seams (`/codebase-design`). Never test ephemeral private helpers or leak implementation details.
4. **Tight Loop Verification**: `VERIFY:` must specify a fast, deterministic, single-command target (e.g. `pytest tests/test_foo.py -k test_bar`).

## 2. Dispatch SOP: [CODE] vs [RESEARCH] (100% Boundary Rule)

Before drafting tickets, Planner evaluates whether to research or code without relying on unverified memory or creating Git tags:

1. **Two-Step Ground Truth Cross-Check (Anti-Hallucination Gate)**:
   Tasks are dispatched by Planner, but memory drifts over 5-10 tasks. Instead of guessing or reading large files:
   - **Physical Existence ("現在有沒有")**: Confirm symbol or file exists on disk via fast, zero-bloat commands (`git grep -n "<symbol>" <path>` or `test -f <path>`).
   - **Last-Touch Action ("上一動")**: Check the last commit touching that specific seam via `git log -n 1 -- <path>` (or `git log -n 1 -S "<symbol>"`). Cross-reference commit metadata (`Task: <id>`, `Scope: <files>`, `Verification: <cmd>`) against Planner's task memory.
   - **Discrepancy Invalidation**: If disk state or git metadata contradicts Planner's impression, purge memory immediately, treat the seam as 0% known, and dispatch `[RESEARCH]` (`VERIFY: REPORT_ONLY`).
2. **The 100% Boundary Gate**:
   - **Known Seam (100% of affected files known, <= 2 files, or leaf bugfix)**: Dispatch `[CODE]` directly. Zero research latency.
   - **Unknown Boundary (unknown callers, interface refactoring, cross-module seams)**: Dispatch `[RESEARCH]` with `VERIFY: REPORT_ONLY`. Never guess dependencies or read whole codebases in Terminal A.
3. **Hierarchical Scoping**:
   - *Level 1 (Macro / Unresearched)*: Scope by directory or subsystem seam (`TARGET: Sources/Audio/`). Do not guess individual files in the dark.
   - *Level 2/3 (Meso/Micro / Researched)*: Scope by exact files captured in `SUMMARY.md` from compiler probes.

## 3. Multi-Interface & Refactor Authorization Gates

Planner MUST NOT approve multi-interface targets or `[REFACTOR]` tickets without satisfying all 4 gates:
1. **Inseparability**: Splitting breaks intermediate commit builds/tests.
2. **Vertical Slice**: Cohesive protocol -> implementation -> test only; no horizontal sprawl across decoupled systems.
3. **Profile Credit**: Target module has >= 4.5 stars in `docs/agents/granularity-profile.json`. For lower-credit modules, Planner must use Level 3 Blueprint Mode.
4. **Topology Proof**: Prior verified `[DIAGNOSTIC]` or `[RESEARCH]` report in `.reports/<issue-slug>/`.

## 4. Dynamic Sizing & Ticket Formatting Protocol

1. **Read Profile**: Check `docs/agents/granularity-profile.json` for module rating.
2. **Blast Radius Limits**:
   - **Level 3 (Micro / 1-2⭐)**: Max 40 lines deleted per task.
   - **Level 2 (Meso / 3-4⭐)**: Max 150 lines deleted per task.
   - **Level 1 (Macro / 5⭐)**: Deletions unlimited, strictly bounded by `TARGET:`.
3. **Ticket Format**:
   ```text
   TASK-XXX | LEVEL: 1-3 | [AFTER: <id>] | TARGET: <paths> | ACTION: <logic> | VERIFY: <test_cmd> | FORBIDDEN_SHORTCUTS: <hacks> | CONSTRAINTS: <limits>
   ```
4. **Clean Pivot Privilege**: If fixing side-effects requires >2 patch tickets or triggers `[SCOPE_BLOCKED]` with unexpected coupling, rollback to `nightshift-session-base` and re-issue a unified vertical slice or Expand-Migrate-Contract plan. Never stack patch-on-patch.
5. **Post-Task Calibration**: Run `/score-worker-performance` after reading `progress.log`.

## 5. Cross-Module Refactoring Strategies (Dual-Track)

- **Track A: Atomic Vertical-Slice (Small/Medium: <= 5 files & >= 3 stars)**:
  - Single `[CODE: REFACTOR]` ticket with interface, implementations, and tests in `TARGET:`.
  - Enforces **Assertion Non-Decrease Gate** and structural closure in `VERIFY:` (e.g. `<test_cmd> && ! grep -rn "<Deprecated_Symbol>" Sources/`).
- **Track B: Expand-Migrate-Contract (Large-Scale: > 5 files or contains 1-star module)**:
  - Decompose into 3 green-to-green phases:
    1. `[CODE: EXPAND]`: Introduce new interface + shims for old interface (Build & Tests 100% PASS).
    2. `[CODE: MIGRATE]`: Incrementally migrate downstream callers in independent atomic tickets.
    3. `[CODE: CONTRACT]`: Remove old interface and shims once call-sites reach zero.
  - Mandatory checkpoint: `git tag -f nightshift-refactor-base` before Task 1.
