---
name: planner
description: "Orchestrate the 24h unattended workflow: domain modeling, /explore seam discovery, TDD blueprinting, tracer-bullet tasks.txt dispatch, and double-funnel acceptance."
---

# Planner

`Domain (/domain-modeling) -> Seam (/codebase-design, /explore) -> TDD Blueprint (/tdd) -> Tracer-Bullet Slicing (to-tickets) -> Dispatch (tasks.txt) -> Live Preview (.preview/) & Acceptance`

## 1. Lifecycle

### Block 1: Domain & Seam Modeling
- **Domain**: Follow [`domain-modeling`](../engineering/domain-modeling/SKILL.md) to maintain `GLOSSARY.md` and `docs/adr/`.
- **Deep Seams**: Follow [`codebase-design`](../engineering/codebase-design/SKILL.md) (and [`grilling`](../productivity/grilling/SKILL.md) when requirements are ambiguous) to design narrow public interfaces hiding deep implementations. Anchor tests strictly to public seams; never test private helpers.

### Block 2: Seam Resolution & Exploration (`/explore`)
Resolve target paths and signatures without inspecting source files in Terminal A:
- **Cache Hit (Active Report or Memory)**: If `.reports/<slug>/SUMMARY.md`, `.worker.notes.md`, or `progress.log` already covers the target seams (and `worker.sh` has not archived the report due to overlapping `[CODE]` edits), plan and dispatch `[CODE]` tickets directly without re-running `[RESEARCH]`.
- **Cache Miss or `/explore` Invoked**: Follow [`explore`](../explore/SKILL.md) to enqueue a `[RESEARCH]` ticket to `tasks.txt` + Queue Sentinel and read the resulting `.reports/<slug>/SUMMARY.md`. If disk contradicts report/memory during execution, re-run [`explore`](../explore/SKILL.md) or trigger **Clean Pivot**.

### Block 3: Granularity Ladder & TDD Blueprints
Follow [`tdd`](../engineering/tdd/SKILL.md) and size instruction density from `docs/agents/granularity-profile.json`:

| Level | Rating | Blueprint Density | Max Deletions |
| :---: | :--- | :--- | :--- |
| **1 (Macro)** | `5⭐` | High-level acceptance intent; declare all slice paths in `TARGET:`. Worker designs internals. | `TARGET:`-bounded |
| **2 (Meso)** | `3-4⭐` | Explicit target files, function signatures, error boundaries, single-command test. | `<= 150` lines |
| **3 (Micro)** | `1-2⭐` | Zero-ambiguity TDD: exact signature diffs, input/output fixtures, step-by-step logic:<br>1. **Red**: Public seam test signature, fixtures, failing assertion (`assert ValueError("invalid")`).<br>2. **Green**: Public signature and minimal implementation satisfying Red.<br>3. **Verify**: Single deterministic test command (`pytest tests/test_foo.py -k test_bar`). | `<= 40` lines |

### Block 4: Tracer-Bullet Slicing (`to-tickets`) & Full-Horizon Dispatch
Follow [`to-tickets`](../engineering/to-tickets/SKILL.md) to slice work into end-to-end tracer bullets (prefactoring first, each slice independently demoable in `.preview/`, blocking edges in `[AFTER: <id>]`).
- **Full-Horizon Batching**: Once seams are verified via [`explore`](../explore/SKILL.md), enqueue **100% of discovered tasks at once** in dependency order—never drip-feed 2–3 tasks at a time.
- **Fast-Path / Full-Auto Mode (known seams, aligned direction, or user requests auto)**: Write the full queue directly to `tasks.txt` without confirmation (when `[RESEARCH]` finishes, immediately expand `.reports/<slug>/SUMMARY.md` into the full implementation queue).
- **First-Time Alignment (new/ambiguous feature)**: After [`explore`](../explore/SKILL.md), present the complete `N`-ticket queue once:
  ```text
  Pre-agreed Public Seam: <Interface_Path> | Domain Terms: <Glossary_Additions>
  Proposed Full Queue (end-to-end vertical slices, demoable in .preview/):
    1. TASK-001 | LEVEL: 2 | TARGET: ... | ACTION: ... | VERIFY: ...
    N. TASK-00N | LEVEL: 3 | [AFTER: TASK-...] | TARGET: ... | ACTION: ... | VERIFY: ...
  Confirmation Prompt: "Approve this full queue (or reply 'auto' to dispatch all batches automatically)?"
  ```

### Block 5: Queue Format, Archetypes & 10-Task Cadence
```text
TASK-XXX | LEVEL: 1-3 | [AFTER: <id>] | TARGET: <paths> | ACTION: <logic> | VERIFY: <test_cmd> | FORBIDDEN_SHORTCUTS: <hacks> | CONSTRAINTS: <limits>
```
- `[CODE: FIX]`: Product files only; `Tests/` read-only.
- `[CODE: REFACTOR]` (**Track A**, `<= 5` files & `>= 3⭐`): Atomic vertical slice (`Tests/` allowed in `TARGET:`). Enforces **Assertion Non-Decrease** and structural closure (`<test_cmd> && ! grep -rn "<Deprecated>" Sources/`).
- `[CODE: EXPAND]` / `[CODE: MIGRATE]` / `[CODE: CONTRACT]` (**Track B**, `> 5` files or `1⭐` module): 3 green-to-green phases.
- `[DIAGNOSTIC]`: Isolate root cause with failing repro test in `Tests/` or trace in `.reports/<slug>/`. Product code locked.
- `[RESEARCH]`: Read-only seam discovery producing `.reports/<slug>/SUMMARY.md`.
- **10-Task Review & Refactor Cadence**: Every 10 tasks (`TASK-010`, `TASK-020`, ...), automatically run [`code-review`](../engineering/code-review/SKILL.md) (last 10 tasks) and [`improve-codebase-architecture`](../engineering/improve-codebase-architecture/SKILL.md) (`git log --oneline -n 20` hotspots), and enqueue a `[CODE: REFACTOR]` ticket into `tasks.txt`.

### Block 6: Double-Funnel Acceptance & Scoring
1. **Sentinel Subagent Waiter (Zero-Token Wakeup)**:
   ```json
   {"Subagents":[{"TypeName":"self","Role":"Queue Sentinel","Prompt":"Run `bash scripts/watch_worker.sh 3600`. When it exits, read `head -n 15 progress.log` and report whether tasks completed or blocked."}]}
   ```
2. **Mechanical Audit**: Verify line 1 of `progress.log`:
   `[MECHANICAL_AUDIT] Status: PASS | Verify_Exit: 0 | Tests_Run: >=1 | Whitelist: PASS | Tree: CLEAN`
3. **Acceptance Routing**:
   - **Fast-Track (Green Light, `<= 5s`, 0 Review Tokens)**: Audit `PASS` + `Attempts: 1 | Confidence: HIGH` -> `git merge --ff-only feature/worker-frontier`.
   - **Deep Audit (Yellow Light — Auto `code-review`)**: On audit fail, `Attempts > 1`, `Confidence < HIGH`, `[DEAD_END]`, or critical seam, run `git show --stat <commit>` and [`code-review`](../engineering/code-review/SKILL.md). Inject remedial `[CODE: FIX]` / `[CODE: REFACTOR]` to line 1 via `scripts/reorder_queue.sh`.
     * **Proof of Negative (`[DEAD_END]`)**: Require isolated passing unit test or runtime log proving module health while global symptom persists; speculative exclusion = task failure.
4. **Scoring Rubric** (`docs/agents/granularity-profile.json`):
   - **5⭐**: 1st attempt pass, 0 warnings -> Maintain / Promote to L1.
   - **4⭐**: 2nd attempt pass (1 self-healed retry) -> Maintain L1/L2.
   - **3⭐**: 3rd attempt pass (2 retries) -> Demote module to L2.
   - **2⭐**: `[NEED_GUIDANCE]` or `[NEED_DECOMPOSITION]` -> Demote to L2/L3; see Section 3.
   - **1⭐**: `[BLOCKED]` (3 retries failed), timeout, crash, or cheating -> Demote to L3; execute `[BLOCKED]` protocol (Section 3).
   - *No-Fault Exemption*: `[SCOPE_BLOCKED]` (downstream compiler errors outside `TARGET:`) is boundary compliance—never deduct stars.
5. **Clean Reset**: Archive `.reports/<issue-slug>/` to `.reports/.archive/`.

## 2. Refactor Authorization Gates

Approve multi-interface targets or `[CODE: REFACTOR]` tickets only when all 4 gates pass:
1. **Inseparability**: Splitting breaks intermediate builds/tests.
2. **Vertical Slice**: Cohesive protocol -> implementation -> test only.
3. **Profile Credit**: Module `>= 4.5⭐` in `granularity-profile.json` (otherwise require Level 3 blueprint).
4. **Topology Proof**: Verified `[DIAGNOSTIC]` or `[RESEARCH]` report in `.reports/<issue-slug>/`.

## 3. Queue Preemption, Feedback & Clean Pivot

- **Hot Queue Preemption**: Inject urgent tickets to line 1 of `tasks.txt` via `scripts/reorder_queue.sh` (POSIX lock).
- **`[NEED_GUIDANCE]`**: Clarify question from `progress.log` with human; re-queue with `GUIDANCE: <clarification>` via `scripts/reorder_queue.sh`.
- **`[NEED_DECOMPOSITION]`**: Split into atomic L2/L3 tickets via `scripts/reorder_queue.sh`.
- **`[BLOCKED]` (3 Retries Failed)**: Run [`retro`](../engineering/retro/SKILL.md) on `progress.log` / `.worker.log` to fix missing checks/pointers/standards, update `.worker.notes.md`, and escalate `L1 -> L2 -> L3 -> Planner Sovereign Intervention` (inspect, fix, commit).
- **Clean Pivot**: If side-effects require `> 2` patch tickets or trigger `[SCOPE_BLOCKED]`, run `git reset --hard nightshift-session-base` and re-issue a unified vertical slice.

## 4. Live Preview (`.preview/`) & `.worker.env`

- **Dual Worktree (`WORKER_ISOLATION=1`)**: Human on `main` (`PORT=3000`); Worker in `.worker-tree` (`feature/worker-frontier`, `PORT=3001` / `TEST_PORT=3001`), preventing IDE flicker, `ETXTBSY`, and `EADDRINUSE`.
- **Drop-Box**: Every PASS stages verified code and binaries (`bin/`, `dist/`, `build/`) + `.preview/version.json` to `.preview/` for live testing (`./.preview/bin/app`) without checkout.
- **Human Steering**: **Continue**, **Tweak** (`scripts/reorder_queue.sh`), **Safe Hold** (`touch PAUSE`), or **Reject** (**Clean Pivot**).
- **Autonomous `.worker.env`**: Update `ADDITIONAL_DIRS`, `AI_MODEL`, `AI_EFFORT`, `WORKER_ISOLATION`, or `TASK_TIMEOUT` when requested; confirm in 1 line.

## 5. Hard Guardrails (Terminal A)

- **Duty & `read_file` Firewall**: Never edit or `read_file` product/test source files (`src/`, `include/`, `lib/`, `Sources/`, `tests/`, `firmware/`) in Terminal A (except L3 Sovereign Intervention after 3 worker failures, repeated worker diagnostic hallucination, or explicit user mandate). Use `read_file` strictly on `.reports/<current-slug>/SUMMARY.md`, `progress.log`, `tasks.txt`, `.worker.notes.md`, `GLOSSARY.md`, `docs/`, and skill files.
- **Language**: Write all `tasks.txt` entries, logs, and commits strictly in English.
- **Context Explosion Guard**: Use `git log -n 1 --stat`, `git show --stat <commit>`, `git log --oneline -n 20`, `git diff --stat <commit>`, `scripts/extract_skeleton.sh <file>#L<line>`, or `scripts/probe_line.sh <file>#L<line>`. Never run bare `git log`, unbounded `git diff`, or `git log -p`.
- **Forbidden Commands**: Never run `git push`, `git clean -f`/`-fd`, unauthorized `git reset --hard` (only for **Clean Pivot**), `sudo`, or host package managers (`apt`, `yum`, `brew`).
