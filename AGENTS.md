# Agent Rules & Treaties (24h Unattended Framework)

Strict operational guardrails for AI. Emphasize zero-context bloat and physical isolation.

## 1. Dual-Terminal Firewall & Skills

| Terminal | Role & Mission | Active Skills | Strict Prohibitions (NEVER DO) |
| :--- | :--- | :--- | :--- |
| **A (Planner)** | Architecture, task decomposition, audit. | `/domain-modeling`, `/calibrate-task-granularity`, `/handle-worker-guidance`, `/score-worker-performance`, `/watch-worker-queue`, `/code-review` | No direct coding/debugging. No chat sleep/polling loops. No use of Worker skills. |
| **B (Worker)** | Unattended TDD execution, atomic commits. | `/universal-build-verify`, `/record-attempt-trace`, `/manage-worker-notes` | No architectural changes. No entering chat loops. |

*   **Planner Sovereign Intervention (Only step in if):**
    1. Worker blocks on a Level 3 (Micro) task after 3 retries.
    2. Worker hallucinates diagnostics or fails to isolate root cause after 2-3 attempts.
    3. Explicit user mandate. (Log root cause in `.worker.notes.md` and `docs/agents/granularity-profile.json`).

### Skill Catalog & Locations

All skills reside in `.agents/skills/` (and `.skills/`). Reference by exact directory:

| Realm | Skill | Path | Trigger & Purpose |
| :--- | :--- | :--- | :--- |
| **Architect** | `/calibrate-task-granularity` | `.agents/skills/architect/calibrate-task-granularity/` | Size tasks (L1-3) & check 4 multi-interface gates. |
| | `/handle-worker-guidance` | `.agents/skills/architect/handle-worker-guidance/` | Resolve `[NEED_GUIDANCE]` & `[NEED_DECOMPOSITION]`. |
| | `/score-worker-performance` | `.agents/skills/architect/score-worker-performance/` | Audit `progress.log` & score 1-5 stars in profile. |
| | `/watch-worker-queue` | `.agents/skills/architect/watch-worker-queue/` | Sentinel subagent for zero-token batch wakeup. |
| **Worker** | `/universal-build-verify` | `.skills/universal-build-verify.md` | Mandatory execution SOP: TDD, retry limits, clean tree. |
| | `/record-attempt-trace` | `.agents/skills/worker/record-attempt-trace/` | Append <=15 line attempt traces to `progress.log`. |
| | `/manage-worker-notes` | `.agents/skills/worker/manage-worker-notes/` | Cache compiler flags & repo quirks in `.worker.notes.md`. |
| **Foundations** | `/tdd`, `/codebase-design` | `.agents/skills/engineering/` | Test-driven development & deep module seam design. |
| | `/domain-modeling` | `.agents/skills/engineering/domain-modeling/` | Ubiquitous terminology, `GLOSSARY.md`, ADR records. |
| | `/diagnosing-bugs` | `.agents/skills/engineering/diagnosing-bugs/` | Tight feedback loops & root cause isolation. |
| | `/git-guardrails`, `/code-review` | `.agents/skills/engineering/` | Destructive command safety & spec/standard review. |

## 2. Environment & Execution Mode (`.worker.env`)

*   **Mode 1 (`WORKER_ISOLATION=1`, Default)**: 
    *   Worker runs in `.worker-tree` (branch `feature/worker-frontier`). Prevents compiler file locks (`ETXTBSY`).
    *   Symlinks `node_modules`/`.venv`; uses port offsets (e.g., `PORT=3001`) to prevent conflicts.
    *   Verified milestones drop to `.preview/` with `version.json` for live human testing.
    *   Planner merges via `git merge --ff-only` upon completion.
*   **Mode 2 (`WORKER_ISOLATION=0`)**: In-place execution for fixed-port/singleton-hardware projects only.

## 3. Task Queue (`tasks.txt`) & Granularity

**Schema:** `TASK-XXX | LEVEL: 1-3 | [AFTER: <id>] | TARGET: <paths> | ACTION: <logic> | VERIFY: <test_cmd> | CONSTRAINTS: <limits>`

| Level | Granularity | `[CODE]` Scope (Strict 1 Seam) | `[DIAGNOSTIC]`/`[RESEARCH]` Scope (Full-Spectrum) |
| :---: | :--- | :--- | :--- |
| **1** | Macro | Feature public interface & tests. | End-to-end event loops, subsystem topology. |
| **2** | Meso | Component slice (1 module unit). | Cross-module contract, state synchronization. |
| **3** | Micro | Specific function / exact math. | Timing calculations, race conditions, exact logs. |

*   **Hot Preemption & Live Feedback**: Injected at line 1 via `scripts/reorder_queue.sh`. Pre-existing tasks for other modules yield line 1 and resume after.
    *   *Known Fix*: Inject single-seam `[CODE]` directly at line 1.
    *   *Unknown Bug*: Inject **solitary** `[DIAGNOSTIC]` task only.
    *   *No Speculative Pipelining*: NEVER queue speculative `[CODE]` tasks behind an unverified `[DIAGNOSTIC]`. Wait for verified evidence before allocating implementation tickets.
*   **Progression**: Always explore top-down (L1 -> L2 -> L3 Diagnostic) before writing Code tickets.

## 4. Honest Treaty & Escalation

*   **Zero-Guessing**: Worker MUST provide verifiable evidence (test outputs/stack traces) for diagnostics. Vague reports are invalid.
*   **Anti-Cheating & Verification Gates**:
    *   *False Red-Light Prevention*: In `[DIAGNOSTIC]`, repro test must compile cleanly (`Build PASS` / 0 syntax errors) and fail strictly on assertion (`Test FAIL`). Syntax/compiler errors or missing symbols are strictly Invalid Repros (Cheating/Rejection). Modifying product code (`Sources/`, `src/`) is strictly forbidden during diagnostics.
    *   *Test Immutability Gate*: In `[CODE]` fixes, modifying or weakening assertions in existing repro tests is strictly forbidden. Tests are immutable unless explicitly declared in `TARGET:` or flagged `CONSTRAINTS: Test refactor approved`.
    *   *Proof of Negative for `[DEAD_END]`*: Declaring `[DEAD_END]` requires tangible proof of negative (isolated unit test passing or runtime log snippet proving suspect module is innocent while global symptom persists). Speculative exclusions = Task Failure.
    *   *5-Line Code Probe*: Verify line claims in `SUMMARY.md` (`File#L<N>`) using `scripts/probe_line.sh <File>#L<N>` (or `sed -n '<N-3>,<N+3>p' <File>`). Misaligned line references trigger immediate credit demotion to 1 Star.
*   **Single-Seam vs. Full-Spectrum**:
    *   *Seam Scope*: A seam is not 1 file; it covers all cohesive objects, interfaces, protocols, and tests supporting the slice.
    *   *Multi-Interface & Refactor Exception*: Legitimate cross-interface tasks or broad refactors must be declared in `TARGET: <path1>, <path2>, <dir>/` (Declare to Authorize) or flagged in `CONSTRAINTS: Multi-interface refactor approved`. Undeclared cross-subsystem tasks are rejected with `[NEED_DECOMPOSITION]`.
    *   *Planner Authorization Gates (Must satisfy all 4 to approve multi-interface/refactor)*:
        1. *Inseparability*: Splitting into smaller tasks would cause intermediate commit build/test failure.
        2. *Vertical Slice*: Only cohesive protocol -> impl -> test; zero horizontal sprawl across decoupled systems.
        3. *Profile Credit*: Target module has >= 4.5 star rating in `docs/agents/granularity-profile.json` (unrated/low-credit modules restricted to single unit).
        4. *Topology Proof*: Refactors require a prior verified `[DIAGNOSTIC]` or `[RESEARCH]` topology report in `.reports/<issue-slug>/`.
    *   *No Silent Compile-Fix Edits*: Never modify unlisted files (e.g. dummy main.swift or configs) just to satisfy compilers. Emit `[NEED_DECOMPOSITION]` instead.
    *   *Diagnostic Scope*: `[DIAGNOSTIC]` traces across all layers (UI -> OS) without seam limits.
*   **Ephemeral Diagnostic Dossier Lifecycle**:
    *   *Zero Git Pollution*: Diagnostic reports are transient forensic evidence, NEVER committed or merged to `main`. Output to Git-ignored `.reports/<issue-slug>/`.
    *   *Multi-Stage Isolation*: Output to `01-macro.md`, `02-meso.md`, `03-micro.md`, and `SUMMARY.md`. Independent files prevent late-stage hallucinations from corrupting verified early facts.
    *   *Invalidation & Ground Truth*: Mark flawed hypotheses as `[DEAD_END]`. When Planner intervenes: extract verified facts into `SUMMARY.md`, log traps in `.worker.notes.md`.
    *   *Resolution-Driven Archival*: When the issue's `[CODE]` fix passes and merges, `.reports/<issue-slug>/` is archived to `.reports/.archive/`.
*   **Clean Tree Gate**: Tasks must leave `git status --porcelain` 100% clean after commit. Ghost tests or uncommitted files trigger task failure.
*   **Escalation Path**: Worker gets max 3 retries per task (with `git restore` cleanups). If blocked, demote granularity (L1->L2->L3).

## 5. Protocol, Context Protection & Git Guardrails

*   **Inter-AI Language**: All artifacts (`tasks.txt`, logs, commits) MUST be **English**. (Terminal A chat can be Chinese).
*   **Rapid Acceptance & Anti-Rubber-Stamp**: 
    *   Worker prepends `<= 15 lines` to `progress.log`. Daemon stamps machine-certified `[MECHANICAL_AUDIT]` at line 1. Report Executive Summaries in `.reports/<issue-slug>/` `<= 30 lines`.
    *   **Fast-Track (Green Light, <= 5s)**: Permitted ONLY if line 1 has `[MECHANICAL_AUDIT] Status: PASS | Verify_Exit: 0 | Whitelist: PASS | Tree: CLEAN` AND Worker reports `Attempts: 1 | Confidence: HIGH`. Merge immediately via `git merge --ff-only feature/worker-frontier`.
    *   **Deep Audit Required (Yellow Light)**: Mandatory IF `[MECHANICAL_AUDIT]` is missing/failed, `Attempts > 1`, `Confidence < 1.0`, line claim requires verification (`scripts/probe_line.sh`), or critical architectural seam. Run `git show --stat` or targeted test.
    *   **Planner Prohibitions**: Never run bare `git log`, unbounded `git diff`, or `git log -p` in Terminal A.
*   **Forbidden Commands**: `git push`, `git reset --hard` (except script rollback), `git clean -f`, `sudo`, `apt/yum`.
*   **Git Commit Standard (Mandatory for A & B)**:
    ```bash
    git commit -m "<type>(<scope>): <concise action <= 60 chars> (<task_id>)" -m "<1-3 summary bullet points>

    Task: <task_id> (<granularity_level>)
    Scope: <target_files>
    Verification: <test command> (<measurable result>)
    Attempts: <attempts> | Confidence: <score>"
    ```
