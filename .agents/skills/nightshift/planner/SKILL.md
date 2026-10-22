---
name: planner
description: "Master orchestrator for the 24h unattended AI workflow. Drives requirements through domain modeling, /explore seam discovery, TDD blueprinting, tasks.txt dispatch, and double-funnel acceptance."
---

# Planner: Autonomous Engineering Orchestrator

Master orchestrator for Terminal A. Drives requirements through Matt Pocock's engineering loop, dispatches atomic tracer-bullet tickets to background workers (`worker.sh`), and keeps Terminal A context clean:

`Domain (/domain-modeling) -> Seam (/codebase-design, /explore) -> TDD Blueprint (/tdd) -> Tracer-Bullet Slicing (to-tickets) -> Dispatch (tasks.txt) -> Live Preview (.preview/) & Acceptance`

---

## 1. Lifecycle Progression

Execute this closed-loop progression by default; invoke individual blocks for surgical interventions.

### Block 1: Domain & Seam Modeling
- **Domain Modeling**: Follow [`domain-modeling`](../engineering/domain-modeling/SKILL.md) to record ubiquitous language in `GLOSSARY.md` and decisions in `docs/adr/`.
- **Deep Seam Design**: Follow [`codebase-design`](../engineering/codebase-design/SKILL.md) (and [`grilling`](../productivity/grilling/SKILL.md) when requirements are ambiguous) to design narrow public interfaces hiding deep implementations.

### Block 2: Mandatory Seam Exploration (`/explore`)
Follow [`explore`](../explore/SKILL.md) — never guess file paths or caller topology:
- **Known Seams (`<= 2` files, leaf fix, explicit user target)**: Fast-path direct dispatch.
- **Unknown Seams (new features, wide refactors, unfamiliar callers)**: Dispatch Tier 2 `[RESEARCH]` via [`explore`](../explore/SKILL.md) to produce `.reports/<slug>/SUMMARY.md`.
- **Distant Module Revisit**: Run Tier 1 instant probe (`git grep -n`, `git log -n 1 -- <path>`) before assuming state.
- **Discrepancy Invalidation**: If disk contradicts memory, confidence drops to zero -> run [`explore`](../explore/SKILL.md) or trigger Clean Pivot.

### Block 3: Granularity Ladder & TDD Blueprints
Follow [`tdd`](../engineering/tdd/SKILL.md) and calibrate instruction density from module ratings in `docs/agents/granularity-profile.json`:

| Level | Mode & Rating | Instruction Density & Blueprint | Max Deletions |
| :---: | :--- | :--- | :--- |
| **1** | **Macro (5⭐)** | High-level acceptance intent; declare all slice paths in `TARGET:`. Worker designs internals autonomously. | `TARGET:`-bounded |
| **2** | **Meso (3-4⭐)** | Structural: explicit target files, function signatures, error boundaries, single-command test. | `<= 150` lines |
| **3** | **Micro (1-2⭐)** | **Zero-ambiguity TDD blueprint**: exact signature diffs, input/output fixtures, step-by-step logic. | `<= 40` lines |

#### Level 3 TDD Blueprint Sequence
1. **Red Contract**: Public seam test signature, input fixtures, and exact failing assertion (`assert ValueError("invalid")`).
2. **Green Contract**: Public type/function signature and minimal implementation satisfying Red.
3. **Verification Target**: Deterministic single-command test (`pytest tests/test_foo.py -k test_bar`).

### Block 4: Tracer-Bullet Slicing (`to-tickets`) & Dynamic Gating
Read and follow [`to-tickets`](../engineering/to-tickets/SKILL.md) to decompose work into end-to-end tracer-bullet vertical slices (prefactoring first, each slice independently demoable in `.preview/`, blocking edges mapped to `[AFTER: <id>]`, and wide refactors sequenced as Expand–Migrate–Contract):
- **Fast-Path (`<= 2` files, leaf fix, known seam)**: Write `tasks.txt` directly.
- **Gated Path (large feature / unknown seam)**:
  1. Dispatch `[RESEARCH]` as Task 1.
  2. From `.reports/<slug>/SUMMARY.md`, apply [`to-tickets`](../engineering/to-tickets/SKILL.md) (Steps 3–4) and present the **Matt Ticket Spec** to the human:
     ```text
     Pre-agreed Public Seam: <Interface_Path>
     Domain Terms: <Glossary_Additions>
     Proposed Tickets (end-to-end vertical slices, demoable in .preview/):
       1. TASK-001 | LEVEL: 2 | TARGET: ... | ACTION: ... | VERIFY: ...
       2. TASK-002 | LEVEL: 3 | [AFTER: TASK-001] | TARGET: ... | ACTION: ... | VERIFY: ...
     Confirmation Prompt: "Does this seam, granularity, and blocking order match your expectations?"
     ```
  3. Upon human confirmation, publish the approved slices into `tasks.txt`.

### Block 5: Queue Dispatch & Task Archetypes
Single-line tracer-bullet format in `tasks.txt`:
```text
TASK-XXX | LEVEL: 1-3 | [AFTER: <id>] | TARGET: <paths> | ACTION: <logic> | VERIFY: <test_cmd> | FORBIDDEN_SHORTCUTS: <hacks> | CONSTRAINTS: <limits>
```

- `[CODE: FIX]`: Product files only. `Tests/` strictly read-only.
- `[CODE: REFACTOR]`: Interface refactor (`Tests/` allowed in `TARGET:`). Enforces **Assertion Non-Decrease** and structural closure (`<test_cmd> && ! grep -rn "<Deprecated>" Sources/`).
- `[CODE: EXPAND]` / `[CODE: MIGRATE]` / `[CODE: CONTRACT]`: Phased 3-step migration for `> 5` files.
- `[DIAGNOSTIC]`: Isolate root cause with failing repro test in `Tests/` or trace in `.reports/<slug>/`. Product code strictly locked.
- `[RESEARCH]`: Read-only seam discovery producing `.reports/<slug>/SUMMARY.md`.

### Block 6: Double-Funnel Acceptance & Auto-Scoring
1. **Sentinel Subagent Waiter (Zero-Token Wakeup)**:
   ```json
   {
     "Subagents": [
       {
         "TypeName": "self",
         "Role": "Queue Sentinel",
         "Prompt": "Run `bash scripts/watch_worker.sh 3600`. When it exits, read `head -n 15 progress.log` and report whether tasks completed successfully or if any task is blocked."
       }
     ]
   }
   ```
2. **Mechanical Audit**: Check line 1 of `progress.log`:
   `[MECHANICAL_AUDIT] Status: PASS | Verify_Exit: 0 | Tests_Run: >=1 | Whitelist: PASS | Tree: CLEAN`
3. **Acceptance Routing**:
   - **Fast-Track (Green Light, `<= 5s`)**: Mechanical Audit `PASS` + `Attempts: 1 | Confidence: HIGH` -> `git merge --ff-only feature/worker-frontier`.
   - **Deep Audit (Yellow Light)**: Mandatory on audit fail, `Attempts > 1`, `Confidence < 1.0`, `[DEAD_END]`, or critical seam. Inspect via `git show --stat <commit>` or [`code-review`](../engineering/code-review/SKILL.md).
     * **Proof of Negative for `[DEAD_END]`**: Require tangible proof (isolated passing unit test or runtime log proving module health while global symptom persists). Speculative exclusion = task failure.
4. **Automated Scoring Rubric** (update `docs/agents/granularity-profile.json`):
   | Score | Criteria | Granularity Action |
   | :---: | :--- | :--- |
   | **5⭐** | Passed in 1 attempt (0 retries), clean diff, 0 warnings. | Maintain / Promote to Level 1. |
   | **4⭐** | Passed in 2 attempts (1 self-healed retry), green tests. | Maintain current Level (1 or 2). |
   | **3⭐** | Passed on 3rd attempt (2 retries). | Demote module to Level 2. |
   | **2⭐** | Raised `[NEED_GUIDANCE]` or `[NEED_DECOMPOSITION]`. | Demote to Level 2/3, provide guidance. |
   | **1⭐** | Blocked after 3 retries, timed out, crashed, or failed anti-cheating gate. | Demote to Level 3; re-architect with user. |

   *No-Fault Exemption*: `[SCOPE_BLOCKED]` (compiler errors in downstream files outside `TARGET:`) is boundary compliance—never deduct stars.
5. **Clean Reset**: Archive `.reports/<issue-slug>/` to `.reports/.archive/`.

---

## 2. Refactoring Strategies & Authorization Gates

- **Track A (Atomic Vertical-Slice, `<= 5` files & `>= 3⭐`)**: Single `[CODE: REFACTOR]` ticket with interface, implementation, and tests in `TARGET:`.
- **Track B (Expand-Migrate-Contract, `> 5` files or `1⭐` module)**: 3 green-to-green phases (`[CODE: EXPAND]`, `[CODE: MIGRATE]`, `[CODE: CONTRACT]`).
- **4 Mandatory Authorization Gates** (required before any multi-interface or `[CODE: REFACTOR]` ticket):
  1. **Inseparability**: Splitting breaks intermediate builds/tests.
  2. **Vertical Slice**: Cohesive protocol -> implementation -> test only; no horizontal sprawl.
  3. **Profile Credit**: Target module `>= 4.5⭐` in `granularity-profile.json` (otherwise require Level 3 blueprint).
  4. **Topology Proof**: Prior verified `[DIAGNOSTIC]` or `[RESEARCH]` report in `.reports/<issue-slug>/`.

---

## 3. Queue Preemption, Worker Feedback & Clean Pivot

- **Hot Queue Preemption**: Inject urgent tickets at line 1 of `tasks.txt` via `scripts/reorder_queue.sh` (POSIX directory lock).
- **Worker Feedback**:
  - `[NEED_GUIDANCE]`: Clarify question from `progress.log` with human; re-queue with `GUIDANCE: <clarification>` via `scripts/reorder_queue.sh`.
  - `[NEED_DECOMPOSITION]`: Split into atomic Level 2/3 tickets via `scripts/reorder_queue.sh`.
  - `[BLOCKED]`: Escalate `L1 -> L2 -> L3 -> Planner Sovereign Intervention` (inspect directly, fix, commit, and log post-mortem in `.worker.notes.md`).
- **Clean Pivot**: If side-effects require `> 2` patch tickets or trigger `[SCOPE_BLOCKED]`, rollback (`git reset --hard nightshift-session-base`) and re-issue a unified vertical slice. Never stack patches.

---

## 4. Live Preview (`.preview/`) & Autonomous Config (`.worker.env`)

- **Zero-Flicker Dual Worktree (`WORKER_ISOLATION=1`)**: Human stays on `main` (`PORT=3000`); Worker runs in `.worker-tree` (`feature/worker-frontier`, `PORT=3001` / `TEST_PORT=3001`), preventing IDE flicker, `ETXTBSY`, and `EADDRINUSE`.
- **Immutable Drop-Box**: Every PASS stages verified code and binaries (`bin/`, `dist/`, `build/`) + `.preview/version.json` into `.preview/` for live testing (e.g. `./.preview/bin/app`) without branch checkout.
- **Human Steering**: **Continue** (let queue finish), **Tweak** (inject ticket via `scripts/reorder_queue.sh`), **Safe Hold** (`touch PAUSE`), or **Reject** (Clean Pivot `git reset --hard nightshift-session-base`).
- **Autonomous `.worker.env` Tuning**: Update `ADDITIONAL_DIRS`, `AI_MODEL`, `AI_EFFORT`, `WORKER_ISOLATION`, or `TASK_TIMEOUT` directly when requested; confirm in 1 concise line.

---

## 5. Hard Guardrails (Terminal A)

- **Duty Firewall**: Never modify product/test files directly in Terminal A (exceptions: Level 3 Sovereign Intervention after 3 worker failures, repeated worker diagnostic hallucination/evasion, or explicit user mandate).
- **Artifact Language**: Write all `tasks.txt` entries, logs, and commits strictly in English.
- **Context Explosion Guard**: Never run bare `git log`, unbounded `git diff`, or `git log -p`. Allowed: `git log -n 1 --stat`, `git show --stat <commit>`, `git log --oneline -n 5`, `git diff --stat <commit>`, `scripts/probe_line.sh <file>#L<line>`.
- **Forbidden Commands**: Never run `git push`, `git clean -f`/`-fd`, unauthorized `git reset --hard` (permitted only for Clean Pivot to `nightshift-session-base`), `sudo`, or host package managers (`apt`, `yum`, `brew`).
