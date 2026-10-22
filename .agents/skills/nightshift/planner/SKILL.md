---
name: planner
description: "Master orchestrator for the 24h unattended AI workflow. Drives requirements through Matt Pocock's complete engineering loop, binds /explore, calibrates TDD blueprints, and handles automated acceptance and worker scoring."
---

# Planner: Autonomous Engineering Orchestrator

Master orchestrator for Terminal A (Interactive Architect). Drives requirements through Matt Pocock's engineering lifecycle, dispatches atomic tracer-bullet tasks to background workers, and guarantees zero token pollution.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        Terminal A: Planner Orchestrator                │
│  1. Domain Alignment (/domain-modeling) -> GLOSSARY.md / ADRs          │
│  2. Deep Seam Design (/codebase-design) -> narrow public interface     │
│  3. Seam Discovery (/explore) -> Tier 1 instant / Tier 2 [RESEARCH]    │
│  4. TDD Blueprinting (/tdd) -> Red Contract -> Green -> Sizing L1-3   │
│  5. Dynamic Gating -> Fast-path direct or Ticket Spec human alignment │
│  6. Queue Dispatch -> tasks.txt FIFO execution by worker.sh           │
│  7. Double-Funnel Acceptance & Auto-Score -> FF-merge into main       │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Lifecycle Progression

Execute this complete closed-loop progression by default. Individual blocks may be triggered independently for surgical interventions.

### Block 1: Domain & Seam Modeling
Define domain language and boundaries before creating tickets:
- **Domain Modeling (`/domain-modeling`)**: Record domain entities and terms in `GLOSSARY.md` and decisions in `docs/adr/`.
- **Deep Seam Design (`/codebase-design`)**: Maximize module depth: narrow, stable public interfaces hiding deep implementation. Anchor tests strictly to public seams; never test ephemeral private helpers.

### Block 2: Mandatory Seam Exploration (`/explore`)
Never guess codebase structure or assume unverified paths:
- **Known Seams (<= 2 files, leaf fix, explicit user target)**: Fast-path direct dispatch without exploration.
- **Unknown Seams (new features, broad refactors, unfamiliar callers)**: Mandatory Tier 2 `[RESEARCH]` probe via `/explore` to capture topology in `.reports/<slug>/SUMMARY.md`.
- **Distant Module Revisit**: Run Tier 1 instant probe (`git grep -n`, `git log -n 1 -- <path>`) before assuming state.
- **Discrepancy Invalidation**: If disk state contradicts Planner memory, confidence drops to zero $\rightarrow$ invoke `/explore` or trigger Clean Pivot.

### Block 3: Granularity Ladder & TDD Blueprints
Calibrate task instruction density using module ratings from `docs/agents/granularity-profile.json`:

| Level | Granularity & Mode | Instruction Density & Blueprint | Blast Radius (Deletions) |
| :---: | :--- | :--- | :--- |
| **1** | **Macro (5⭐)** | High-level acceptance intent. Declare all slice targets in `TARGET:`. Worker designs internal helpers autonomously. | Unlimited (bounded by `TARGET:`) |
| **2** | **Meso (3-4⭐)** | Structural: explicit target files, function signatures, error boundaries, single-command test. | <= 150 lines |
| **3** | **Micro (1-2⭐)** | **Zero-ambiguity TDD blueprint**: exact signature diffs, input/output fixtures, step-by-step logic. | <= 40 lines |

#### Level 3 TDD Blueprint Sequence
1. **Red Contract First**: Exact test signature, input fixtures, failing assertion (`assert ValueError("invalid")`).
2. **Green Contract**: Exact public type/function signature and pseudocode to satisfy the Red contract minimally.
3. **Seam Boundary**: Anchor tests strictly to public seams (`/codebase-design`).
4. **Verification Target**: Deterministic, single-command target (e.g. `pytest tests/test_foo.py -k test_bar`).

### Block 4: Dynamic Gating & Ticket Spec
- **Fast-Path (<= 2 files, leaf fix, known seam)**: Write `tasks.txt` directly without conversational overhead.
- **Gated Path (Large feature / unknown seam)**:
  1. Dispatch `[RESEARCH]` on Task 1.
  2. Once `SUMMARY.md` is produced by `/explore`, present the **Matt Ticket Spec** to the human:
     ```text
     Pre-agreed Public Seam: <Interface_Path>
     Domain Terms: <Glossary_Additions>
     Proposed Tickets:
       1. TASK-001 | LEVEL: 2 | TARGET: ... | ACTION: ... | VERIFY: ...
       2. TASK-002 | LEVEL: 3 | TARGET: ... | ACTION: ... | VERIFY: ...
     Confirmation Prompt: "Does this seam and TDD blueprint match your expectations?"
     ```
  3. Upon human confirmation, enqueue tickets into `tasks.txt`.

### Block 5: Queue Dispatch & Operations
Single-line tracer-bullet format in `tasks.txt`:
```text
TASK-XXX | LEVEL: 1-3 | [AFTER: <id>] | TARGET: <paths> | ACTION: <logic> | VERIFY: <test_cmd> | FORBIDDEN_SHORTCUTS: <hacks> | CONSTRAINTS: <limits>
```

#### Task Archetypes
- `[CODE: FIX]`: Product files only. `Tests/` read-only.
- `[CODE: REFACTOR]`: Interface refactor. `Tests/` allowed in `TARGET:`. Enforces **Assertion Non-Decrease Gate** and structural closure (`<test_cmd> && ! grep -rn "<Deprecated>" Sources/`).
- `[CODE: EXPAND]` / `[CODE: MIGRATE]` / `[CODE: CONTRACT]`: Phased 3-step migration for >5 files.
- `[RESEARCH]`: Read-only seam discovery. Produces `.reports/<slug>/SUMMARY.md`.

### Block 6: Double-Funnel Acceptance & Auto-Scoring
1. **Sentinel Subagent Waiter**: Deploy `/watch-worker-queue` using `scripts/watch_worker.sh 3600`. Zero chat token consumption while waiting.
2. **Double-Funnel Mechanical Audit**: Verify line 1 of `progress.log`:
   `[MECHANICAL_AUDIT] Status: PASS | Verify_Exit: 0 | Tests_Run: >=1 | Whitelist: PASS | Tree: CLEAN`
3. **Acceptance Routing**:
   - **Fast-Track (Green Light, <= 5s)**: Mechanical Audit PASS AND Worker reports `Attempts: 1 | Confidence: HIGH`. Merge immediately:
     ```bash
     git merge --ff-only feature/worker-frontier
     ```
   - **Deep Audit (Yellow Light)**: Mandatory if audit failed, `Attempts > 1`, `Confidence < 1.0`, or critical seam. Inspect via `git show --stat` or `/code-review`.
4. **Automated Scoring (`/score-worker-performance`)**: Parse `progress.log` attempt traces and update ratings in `docs/agents/granularity-profile.json` (1 to 5 stars).
5. **Clean Reset**: Archive `.reports/<issue-slug>/` to `.reports/.archive/`. Clear working context for next requirement.

---

## 2. Multi-Interface & Refactor Authorization Gates

Planner MUST NOT approve multi-interface targets or `[REFACTOR]` tickets without satisfying all 4 gates:
1. **Inseparability**: Splitting breaks intermediate commit builds/tests.
2. **Vertical Slice**: Cohesive protocol $\rightarrow$ implementation $\rightarrow$ test only; no horizontal sprawl across decoupled systems.
3. **Profile Credit**: Target module has >= 4.5 stars in `docs/agents/granularity-profile.json`. Lower credit requires Level 3 Blueprint Mode.
4. **Topology Proof**: Prior verified `[DIAGNOSTIC]` or `[RESEARCH]` report in `.reports/<issue-slug>/`.

---

## 3. Dual-Track Refactoring Strategies

- **Track A (Atomic Vertical-Slice)**: Small/Medium (<= 5 files & >= 3 stars). Single `[CODE: REFACTOR]` ticket with interface, implementation, and tests in `TARGET:`. Enforces Assertion Non-Decrease and structural verification in `VERIFY:`.
- **Track B (Expand-Migrate-Contract)**: Large-Scale (> 5 files or contains 1-star module). 3 green-to-green phases: `[CODE: EXPAND]`, `[CODE: MIGRATE]`, `[CODE: CONTRACT]`.

---

## 4. Safety, Preemption & Worker Feedback

- **Hot Preemption (插隊)**: When urgent diagnostics or caller mapping arise, inject tickets directly to line 1 of `tasks.txt` via `scripts/reorder_queue.sh` (POSIX directory atomic lock). The background worker executes it as its next task without stopping.
- **Worker Feedback Handling**:
  - `[NEED_GUIDANCE]`: Architectural contradiction $\rightarrow$ resolve via `/handle-worker-guidance` and re-inject with `GUIDANCE: <clarification>`.
  - `[NEED_DECOMPOSITION]`: Task oversized $\rightarrow$ split into Level 2/3 atomic tickets and re-queue.
  - `.worker.notes.md`: Worker autonomously maintains repository quirks and compiler flags across stateless runs (`/manage-worker-notes`).
- **Clean Pivot**: If fixing side-effects requires >2 patch tickets or triggers `[SCOPE_BLOCKED]`, rollback (`git reset --hard nightshift-session-base`) and re-issue a unified vertical slice. Never stack patch-on-patch.

---

## 5. On-the-Fly Human Preview & Live Testing (`.preview/`)

While the worker daemon executes in the background, human operators test intermediate builds live without disturbing the worker or switching branches:
1. **Zero-Flicker Dual Worktree (`WORKER_ISOLATION=1`)**: Human works in `main` (workspace root); Worker executes in `.worker-tree` on branch `feature/worker-frontier`. Eliminates IDE file flickering and linker locks (`ETXTBSY`).
2. **Immutable Drop-Box**: On every task PASS, `worker.sh` stages verified code and compiled binaries (`bin/`, `dist/`, `build/`) into `.preview/` with `.preview/version.json`.
3. **Live Testing without Checkout**: Human tests code or executes binaries directly from `.preview/` (e.g. `./.preview/bin/app`) while worker processes subsequent tasks.
4. **Port Offsetting**: Worker runs on `PORT=3001` (`TEST_PORT=3001`), preventing port collisions (`EADDRINUSE`) with human's dev server (`PORT=3000`).
5. **Human Steering Options**:
   - **Continue**: Build verified; let worker finish queue.
   - **Tweak / Refine**: Instruct Planner in Terminal A $\rightarrow$ Planner injects adjusted ticket via `scripts/reorder_queue.sh`.
   - **Safe Hold**: Run `touch PAUSE` to pause worker after current task completes.
   - **Reject / Pivot**: Trigger Clean Pivot (`git reset --hard nightshift-session-base`) to discard faulty path cleanly.
