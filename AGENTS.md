# Agent Rules & Treaties (NightShift 24h Framework)

Operational guardrails for autonomous dual-terminal execution. Zero context bloat; strict physical isolation.

## 1. Dual-Terminal Firewall

| Terminal | Role & Mission | Active Skills | Strict Prohibitions |
| :--- | :--- | :--- | :--- |
| **A (Planner)** | Architecture, decomposition, audit. | `/domain-modeling`, `/calibrate-task-granularity`, `/handle-worker-guidance`, `/score-worker-performance`, `/watch-worker-queue`, `/code-review` | No direct coding/debugging. No chat sleep/polling loops. No worker skills. |
| **B (Worker)** | Unattended TDD, atomic commits. | `/universal-build-verify`, `/record-attempt-trace`, `/manage-worker-notes` | No architectural changes. No interactive chat loops. |

**Planner Sovereign Intervention Triggers**:
1. Worker blocks on Level 3 (Micro) after 3 retries.
2. Worker hallucinates diagnostics or fails root cause after 2-3 attempts.
3. **Clean Pivot Privilege**: If fixing side-effects requires >2 patch tickets or triggers `[SCOPE_BLOCKED]` with unexpected coupling, rollback (`git reset --hard nightshift-session-base`) and re-issue a unified vertical-slice ticket or Expand-Migrate-Contract plan. Never stack patch-on-patch.
4. Explicit user mandate. (Log root cause in `.worker.notes.md` and `docs/agents/granularity-profile.json`).

### Skill Catalog (`.agents/skills/` & `.skills/`)
- **Architect**: `/calibrate-task-granularity` (`.agents/skills/architect/calibrate-task-granularity/`), `/handle-worker-guidance` (`.agents/skills/architect/handle-worker-guidance/`), `/score-worker-performance` (`.agents/skills/architect/score-worker-performance/`), `/watch-worker-queue` (`.agents/skills/architect/watch-worker-queue/`).
- **Worker**: `/universal-build-verify` (`.skills/universal-build-verify.md`), `/record-attempt-trace` (`.agents/skills/worker/record-attempt-trace/`), `/manage-worker-notes` (`.agents/skills/worker/manage-worker-notes/`).
- **Foundations**: `/tdd`, `/codebase-design`, `/domain-modeling`, `/diagnosing-bugs`, `/git-guardrails`, `/code-review` (`.agents/skills/engineering/`).

## 2. Execution Modes (`.worker.env`)

- **Mode 1 (`WORKER_ISOLATION=1`, Default)**: Isolated `.worker-tree` (`feature/worker-frontier`). Symlinks dependencies (`node_modules`, `.venv`), uses port offsets (`PORT=3001`), stages verified milestones to `.preview/` with `version.json`. Merged via `git merge --ff-only`. Prevents compiler locks (`ETXTBSY`).
- **Mode 2 (`WORKER_ISOLATION=0`)**: Direct in-place execution for fixed-port or singleton hardware only.

## 3. Task Queue (`tasks.txt`) & Granularity

**Schema**: `TASK-XXX | LEVEL: 1-3 | [AFTER: <id>] | TARGET: <paths> | ACTION: <logic> | VERIFY: <test_cmd> | FORBIDDEN_SHORTCUTS: <hacks> | CONSTRAINTS: <limits>`

| Level | Mode & Granularity | Instruction Density | Blast Radius (Deletions) |
| :---: | :--- | :--- | :--- |
| **1** | **Macro (5⭐)** | High-level acceptance intent. Declare all slice targets in `TARGET:`. | Unlimited (bounded by `TARGET:`) |
| **2** | **Meso (3-4⭐)** | Structural: explicit target files, function signatures, error boundaries. | <= 150 lines |
| **3** | **Micro (1-2⭐)** | Blueprint: zero-ambiguity type signature diffs & step-by-step pseudocode. | <= 40 lines |

- **Task Archetypes**:
  - `[CODE: FIX]`: Bugfix. Modifies `TARGET:` product code only. `Tests/` strictly immutable.
  - `[CODE: REFACTOR]`: Interface refactor. `Tests/` and `Mocks/` permitted in `TARGET:`. Enforces **Assertion Non-Decrease Gate** and structural closure in `VERIFY:` (e.g. `<test_cmd> && ! grep -rn "<Deprecated_Symbol>" Sources/`).
  - `[CODE: EXPAND]` / `[CODE: MIGRATE]` / `[CODE: CONTRACT]`: Phased large refactoring progression.
  - `[RESEARCH]`: Topology & seam discovery. Product code strictly read-only. Produces `.reports/<slug>/SUMMARY.md`. `VERIFY:` defaults to automatic artifact/cleanliness audit or `REPORT_ONLY`.
- **Mandatory `FORBIDDEN_SHORTCUTS:`**: Explicitly ban hacks (thread sleeps / `asyncAfter`, error swallowing via `try?`/empty catch, turning non-optional into optional, deleting assertions).
- **Hot Preemption**: Inject at line 1 via `scripts/reorder_queue.sh`. Known fix = single-seam `[CODE]`; Unknown bug = solitary `[DIAGNOSTIC]`. Never pipeline speculative `[CODE]` tasks behind an unverified diagnostic.
- **Planner Dispatch SOP (Zero-Memory, No-Tag)**:
  - *Physical Cross-Check*: Never trust memory from 5-10 tasks ago; never add tracking tags. Cross-check against disk via 2 commands:
    1. **Existence (現在有沒有)**: `git grep -n "<symbol>" <path>` (or `test -f <path>`).
    2. **Last-Touch (上一動)**: `git log -n 1 -- <path>` (or `-S "<symbol>"`). Cross-reference commit metadata (`Task:`, `Scope:`, `Verification:`) with Planner impression.
  - *Discrepancy Invalidation*: Contradiction = 0% confidence. Invalidate memory immediately and dispatch `[RESEARCH]` (`VERIFY: REPORT_ONLY`). Never guess or read whole files in Terminal A.
  - *`[CODE]` Direct*: 100% files/seams verified on disk (<= 2 files, leaf fix). Scope L1 by directory seam (`TARGET: Sources/Audio/`), L2 by explicit files.
  - *`[RESEARCH]` First*: Unknown callers, interface changes, or uncertain scope $\rightarrow$ dispatch `[RESEARCH]`.
- **Progression**: Top-down (L1 -> L2 -> L3 Diagnostic -> Code). Planner uses Matt's foundations (`/domain-modeling`, `/codebase-design`, `/tdd`, `/diagnosing-bugs`) to compose tickets; at Level 3 (Micro), Planner provides exact TDD blueprints (Red contract -> Green contract -> Seam boundary) so Worker's `/tdd` executes without guesswork.

## 4. Honest Treaty, Verification Gates & Escalation

- **Zero-Guessing**: Verifiable evidence (test outputs/stack traces) required. Label interpretations as `Hypothesis`.
- **Anti-Cheating Verification Gates**:
  1. *False Red-Light Prevention*: In `[DIAGNOSTIC]`, repro test must compile cleanly (`Build PASS`, 0 syntax errors) and fail strictly on assertion (`Test FAIL`). Modifying product code (`Sources/`, `src/`) during diagnostics is strictly forbidden.
  2. *Test Immutability & Assertion Non-Decrease*: Tests are read-only in `[CODE: FIX]`. In `[CODE: REFACTOR]`, total assertion count post-commit must be `>=` pre-commit (`XCTAssert`, `#expect`, `assert`, `expect(`, `self.assert`).
  3. *Proof of Negative for `[DEAD_END]`*: Tangible proof required (isolated passing unit test or log snippet proving module health). Speculative exclusions = task failure.
  4. *Interface Skeleton & Pointer Audit*: In `[RESEARCH]`, pointers (`<File>#L<Line>`) must match real files and valid line numbers. Detailed skeletons/slices belong in `03-micro.md`.
- **Dedicated Mechanical Audits by Archetype**:
  `worker.sh` evaluates tasks via decoupled gates to eliminate shell-quoting accidents:
  - `[CODE]`: Test suite exit 0, Anti-Idle (`Tests_Run >= 1`), whitelist check, blast radius limits.
  - `[RESEARCH]`: Artifact Integrity (non-empty `SUMMARY.md` with markdown headings), Clean Tree (zero uncommitted/modified product code), Pointer Validity (sampled `<File>#L<N>` verified on disk).
  - `[DIAGNOSTIC]`: Production code lock, clean build, repro failure strictly on test assertion.
- **Scope & Compiler Probes**:
  - *Compiler Probe*: In `[RESEARCH]`, Worker may temporarily alter signatures and run `build` to capture 100% of affected call-sites into `SUMMARY.md`, followed by mandatory `git restore .`.
  - *`[SCOPE_BLOCKED]` No-Fault Exit*: When compiler errors hit downstream files outside `TARGET:`, never touch unlisted files. Emit `STATUS: SCOPE_BLOCKED (Need Target: <File>#L<Line>)`. Planner expands `TARGET:` or decomposes; zero star deduction in `granularity-profile.json`.
  - *No Silent Compile-Fix Edits*: Never touch unlisted files (e.g. dummy configs/main.swift) to silence compilers.
- **Multi-Interface & Refactoring Gates**:
  - Seam covers cohesive objects, interfaces, and tests for the slice. Multi-interface tasks require explicit declaration in `TARGET:` or `CONSTRAINTS: Multi-interface refactor approved`.
  - *4 Planner Authorization Gates*: (1) Inseparability (split breaks intermediate builds); (2) Vertical Slice (protocol -> impl -> test, no horizontal sprawl); (3) Profile Credit (>=4.5 stars); (4) Topology Proof (prior verified `[DIAGNOSTIC]` or `[RESEARCH]` in `.reports/`).
  - *Dual-Track Strategy*:
    - **Track A (Vertical-Slice)**: Small/Medium (<=5 files & >=3 stars). Single `[CODE: REFACTOR]` ticket.
    - **Track B (Expand-Migrate-Contract)**: Large-Scale (>5 files or 1-star module). Checkpoint `git tag -f nightshift-refactor-base`. 3 green-to-green phases: `[CODE: EXPAND]`, `[CODE: MIGRATE]`, `[CODE: CONTRACT]`.
- **Ephemeral Diagnostic Dossier Lifecycle**:
  - Ephemeral forensic evidence lives in git-ignored `.reports/<issue-slug>/` (`01-macro.md`, `02-meso.md`, `03-micro.md`, `SUMMARY.md`). Never commit or merge to `main`. Archive to `.reports/.archive/` on fix merge.
  - *Progressive Disclosure*: `SUMMARY.md` is an executive decision digest (<= 5 KB): topology diagrams, coupling bottlenecks, Expand-Migrate-Contract execution matrix, and validated file pointers. Raw inlined 10-line code slices and interface AST skeletons belong in `03-micro.md` to prevent Summary bloat.
- **Clean Tree Gate & Escalation**:
  - `git status --porcelain` must be 100% clean after commit.
  - Worker allowed max 3 retries (with `git restore` cleanups). If blocked, demote granularity (L1->L2->L3).

## 5. Protocol, Acceptance & Git Guardrails

- **Language**: English for all artifacts (`tasks.txt`, logs, commits). (Terminal A chat may be Chinese).
- **Rapid Acceptance & Anti-Rubber-Stamp**:
  - Worker logs <=15 lines in `progress.log`; reports in `.reports/<issue-slug>/` <=30 lines.
  - **Double-Funnel Mechanical Audit**: `worker.sh` mechanically validates tests, anti-idle (`Tests_Run >= 1`), regression checks, and stamps `[MECHANICAL_AUDIT]` at line 1.
  - **Fast-Track (Green Light, <= 5s)**: Permitted ONLY if line 1 has `[MECHANICAL_AUDIT] Status: PASS | Verify_Exit: 0 | Tests_Run: >=1 | Whitelist: PASS | Tree: CLEAN` AND Worker reports `Attempts: 1 | Confidence: HIGH`. Merge immediately via `git merge --ff-only feature/worker-frontier`.
  - **Deep Audit (Yellow Light)**: Mandatory if mechanical audit failed/missing, `Attempts > 1`, `Confidence < 1.0`, line claim needs probe, or critical seam. Inspect via `git show --stat` or targeted tests.
  - **Planner Prohibitions**: Never run bare `git log`, unbounded `git diff`, or `git log -p`.
- **Forbidden Commands**: `git push`, `git reset --hard` (except script rollback), `git clean -f`, `sudo`, `apt/yum`.
- **Conventional Git Commit Standard**:
  ```bash
  git commit -m "<type>(<scope>): <concise action <= 60 chars> (<task_id>)" -m "<1-3 summary bullet points>

  Task: <task_id> (<granularity_level>)
  Scope: <target_files>
  Verification: <test command> (<measurable result>)
  Attempts: <attempts> | Confidence: <score>"
  ```
