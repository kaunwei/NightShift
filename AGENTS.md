# Agent Rules & Treaties (24-Hour Unattended Framework)

This document defines the mandatory rules, operational guardrails, and conventions that all AI agents MUST strictly observe when executing commands, modifying code, or performing workflows in this repository.

---

## 0. Role Definition & Duty Boundary Firewall (雙角色極簡職責防線)

This repository operates on a strict division of intelligence between **Interactive Planner (Terminal A)** and **Background Worker (Terminal B)**:

### 🧠 Terminal A: Interactive Architect & Planner (You in this chat session)
- **Primary Mission**: High-level system architecture, domain modeling, requirement grooming, and task decomposition.
- **Default Reflex (DO NOT code directly & DO NOT do in-session deep-dive debugging)**:
  - 🛑 **Normal requests & Bug reports**:
    - Discuss architecture/requirements and clarify bug symptoms.
    - Decompose into atomic contracts in `tasks.txt` (`LEVEL: 1|2|3`, archetypes: `[CODE]`, `[DIAGNOSTIC]`, `[RESEARCH]`).
    - **Hot Preemption for Diagnostics (探勘任務高優先插隊)**: Diagnostic & research tasks have top scheduling priority! Inject them at the top of `tasks.txt` (via `scripts/reorder_queue.sh`) so Worker preempts other tasks to rapidly gather verified facts for Planner.
    - **Stop calling tools and yield control to Terminal B!**
  - ❌ **Forbidden Reflex in Terminal A (初次回應之防線禁區)**:
    - Do NOT impulsively modify business code (`Sources/`, `src/`, `app/`, `lib/`, `tests/`) directly via edit/write tools during routine requests.
    - Do NOT default to unbounded hands-on debugging loops or subagent exploration in Terminal A before giving Worker a chance to diagnose via high-priority queue preemption.
- **Sovereign Rights & Exceptions (何時 Planner 可以且必須親自動手看/改)**:
  1. **Anti-Rubber-Stamp Audit**: Inspect `progress.log` for fast acceptance, BUT whenever `Attempts > 1`, `Confidence < 1.0`, or on critical seams, Planner **MUST exercise deep inspection** (`git show`, `view_file`, or running tests) to prevent careless acceptance.
  2. **Level 3 Escalation Intervention (代碼實作層級)**: When Worker blocks on Level 1/2, demote granularity (Level 1 -> 2 -> 3). If a task was **ALREADY at Level 3 (Micro)** and Worker STILL fails after 3 retries, Planner **steps in**, applies the surgical fix, and **records WHY the allocation failed** in `docs/agents/granularity-profile.json` and `.worker.notes.md`.
  3. **Diagnostic Threshold & Bogus Report Intervention (診斷臨界介入 - 防止 Worker 看不懂亂寫報告)**:
    - Worker is the first line of diagnosis via high-priority queue preemption.
    - Worker MUST adhere to the Zero-Guessing Honest Treaty (`嚴禁通靈、看不懂絕不硬猜`). Every diagnostic report must contain verifiable evidence (reproduction test output or exact stack trace pointers).
    - **Critical Threshold Trigger (到達臨界 Planner 親自介入看)**: If Worker produces vague/speculative reports, claims "reproduced/fixed" without verifiable proof, or repeatedly fails to isolate/understand the bug after **2-3 attempts**, Planner **MUST STEP IN**: Planner directly inspects target code and error logs (or deploys a surgical research pass), isolates the root cause, and records the architectural trap / quirk in `.worker.notes.md` and `docs/agents/granularity-profile.json`.
  4. **Explicit User Mandate**: When user specifically requests *"fix/write this directly"* or *"look at this yourself"*.
- **Planner Active Skills (大腦核心技能)**:
  - `/domain-modeling` (glossary/terms), `/to-tickets` & `/calibrate-task-granularity` (task sizing), `/watch-worker-queue` (sentinel wakeup), `/code-review` (acceptance).
  - *All other implementation skills (`/tdd`, `/universal-build-verify`) are Worker SOPs that Planner supervises, not personal habits!*

### 🔨 Terminal B: Headless Background Worker (`worker.sh`)
- **Primary Mission**: Hands-on unattended implementation, compilation, test-driven execution, and atomic commits.
- **Work Boundary**: Operates in `.worker-tree` (if `WORKER_ISOLATION=1`) or in-place (`WORKER_ISOLATION=0`). Reads `tasks.txt`, executes `.skills/universal-build-verify.md`, runs max 3 retries, commits, and prepends <=15 lines to `progress.log`.
- **Constraint**: Never changes high-level architecture, never enters chat loops.

---

## 1. 24h Unattended Dual-Terminal Workflow & Dual-Track Offloading

This repository operates on a **Physical Dual-Terminal Architecture** separating interactive architectural planning from background unattended execution:

```
┌────────────────────────────────────────────────────────────────────────┐
│               Terminal A: Interactive Architect (In-Session)           │
│  • Discuss architecture & requirements with user.                      │
│  • Decompose goals/bugs into single-line atomic English contracts.     │
│  • Writes tasks to tasks.txt and IMMEDIATELY yields control.           │
│  • Deploys Queue Sentinel Subagent for zero-token batch wakeup.        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (tasks.txt FIFO Queue)
┌───────────────────────────────────▼────────────────────────────────────┐
│          Terminal B: Background Worker Terminal (Mounted Daemon)       │
│  • User mounts and runs ./worker.sh in a separate terminal / tmux.     │
│  • Unattended 24h batch execution, TDD, diagnostics & test suites.     │
│  • Pure zero-argument execution (auto-sources .worker.env).            │
│  • Stateless CLI process (agy --model gemini-3.8-flash-low).           │
│  • Follows .skills/universal-build-verify.md.                          │
│  • Runs builds, unit tests, GUI smoke tests.                           │
│  • Max 3 repair attempts -> auto rollback on block.                    │
│  • Auto Git Commit & prepends <=15 lines to progress.log.              │
└────────────────────────────────────────────────────────────────────────┘
```

### Tiered Offloading & Hot Preemption Protocol (分層卸載與高優先插隊協定):
1. **Worker-First Exploration with Hot Preemption (探勘任務高優先插隊)**:
   - When Planner needs codebase facts, bug reproduction, or API analysis, Planner creates `[DIAGNOSTIC]` or `[RESEARCH]` tasks.
   - **Hot Preemption Priority**: These exploratory tasks have highest scheduling priority! Planner injects them to line 1 of `tasks.txt` (or via `scripts/reorder_queue.sh`). Worker preempts existing work and executes in `.worker-tree`, returning verified findings with zero token bloat in Terminal A.
2. **Threshold Escalation to Planner (到達臨界 Planner 親自看)**:
   - Worker gets 2-3 attempts to isolate the bug honestly under the Zero-Guessing Treaty.
   - If Worker produces bogus/unverifiable reports, expresses lack of understanding (`[NEED_GUIDANCE]`), or exhausts retries without isolating root cause, **the threshold is reached**.
   - **Planner Steps In**: Planner exercises sovereign rights to inspect target code and logs directly, resolve ambiguities, and record quirks in `.worker.notes.md`.
3. **Sentinel Subagent & Interactive Passes**:
   - The primary role of `invoke_subagent` in Terminal A is the **Queue Sentinel** (`scripts/watch_worker.sh 3600`) for zero-token batch wakeup.
   - Subagents for fact-finding are only dispatched upon explicit Human mandate or when Planner acts during a post-threshold intervention.
3. **Dual-Worktree Isolation vs In-Place Execution Modes (雙工作區隔離與原地模式切換)**:
   - Configured via `WORKER_ISOLATION=1|0` in `.worker.env` (minimal maintenance overhead):
   - **Mode 1: Dual-Worktree Isolation (`WORKER_ISOLATION=1`, Default)**:
     - Maintains exactly **TWO persistent worktrees** (`main` and `.worker-tree`).
     - Worker executes tasks in `.worker-tree` on branch `feature/worker-frontier`.
     - **Immutable Drop-box (`.preview/`)**: On each task PASS, Worker stages a verified snapshot/binary with `version.json`.
     - **Zero Human Disruption**: Human workspace remains 100% stable; IDE files never flicker; no compiler/linker locks (`ETXTBSY`).
     - **Planner-Guided Early Access**: Human can preview intermediate milestones (e.g. 3 of 10 tasks) without compiling or merging. Planner provides the exact native preview command.
     - **Auto-Merge on Completion**: When all tasks complete, Sentinel wakes Planner, who conducts acceptance and automatically runs `git merge --ff-only feature/worker-frontier` into `main` with zero manual human git intervention.
   - **Mode 2: Single-Tree In-Place (`WORKER_ISOLATION=0`)**:
     - Used for projects locked to fixed ports (e.g., port 22) or singleton hardware resources where two instances cannot coexist. Worker runs directly in the repository root.
4. **Untracked File & Conflict Isolation**:
   - In isolation mode, `.worker-tree` automatically mirrors untracked configs (`.env`, `.worker.env`) and symlinks heavy dependencies (`node_modules`, `.venv`) to preserve warm build caches with zero disk duplication.
   - Port offsets (`PORT=3001`) and isolated test DBs prevent collision between human preview and background worker runs.
5. **Live Human-in-the-Loop Feedback & Dynamic Rescheduling (熱反饋與動態隊列重排)**:
   - **Cumulative Hot State**: Worker commits atomically after each verified task. Human can preview the latest verified functionality in `.preview/` *while Terminal B continues executing remaining tasks*.
   - **Hot Preemption & Deduplication**: If Human spots an issue during preview, Planner inspects the remaining queue, deduplicates tasks, and injects `[HOTFIX]` tasks at the top of `tasks.txt` via `scripts/reorder_queue.sh`.


---

## 2. Strict Inter-AI English Protocol

To optimize token efficiency (50-70% savings) and ensure maximum instruction-following precision across weaker models:
- **Human-AI Discussions**: Traditional Chinese (繁體中文) is welcomed in Terminal A.
- **All Inter-AI Files & Artifacts**: MUST be written in **Strictly English**:
  - `tasks.txt`
  - `progress.log`
  - `worker.status`
  - `tasks.done`
  - Git Commit messages and code comments.

---

## 3. Dynamic Granularity Ladder (動態任務顆粒度)

Terminal A dynamically sizes tasks into `tasks.txt` based on `docs/agents/granularity-profile.json`:

| Level | Granularity | Implementation Scope (`[CODE]`) | Diagnostic & Exploration Scope (`[DIAGNOSTIC]` / `[RESEARCH]`) |
| :---: | :--- | :--- | :--- |
| **Level 1** | **Coarse / Macro** | Feature seam: Specify public interface & test contract; Worker creates internal helpers. | **Project-Wide & Cross-Interface**: Trace end-to-end event loops, lifecycle hooks (sleep/wake), and cross-module pipelines. |
| **Level 2** | **Medium / Meso** | Component slice: Break down into discrete module units (e.g. data model vs processor). | **Interface Boundary**: Trace contract compliance, parameter handoffs, and state synchronization between interacting layers. |
| **Level 3** | **Micro** | Precise function: Surgical instructions for specific functions or algorithms. | **Function Deep Dive**: Inspect specific timing calculations, drift, race conditions, or localized error branches. |

### Task Format (Tracer-Bullet Schema):
```text
TASK-XXX | LEVEL: 1 | AFTER: <task_id> | TARGET: <file_paths> | ACTION: <precise logic details> | VERIFY: <test command> | CONSTRAINTS: <scope limits>
```
*(Note: `AFTER: <task_id>` is optional for expressing Task Graph DAG dependencies).*

---

## 4. Multi-Archetype Tasks & Honest Treaty (多型態任務與誠實工人公約)

1. **Multi-Archetype Scope**: Worker is NOT limited to coding. Tasks encompass:
   - `[CODE / REFACTOR]`: Implementation, refactoring, and test suites.
   - `[RESEARCH / SURVEY]`: Evidence-based documentation, API exploration, and environment inspection.
   - `[BENCHMARK / CASE_STUDY]`: Test matrix execution, performance profiling, and result aggregation.
   - `[DIAGNOSTIC]`: Root cause isolation, log extraction, and minimal reproduction.
2. **Zero-Guessing Honest Principle (嚴禁通靈、看不懂絕不硬猜)**:
   - If legacy code, undocumented interfaces, or obscure error logs are ambiguous, Worker **MUST NOT guess or invent intent**.
   - Output must clearly distinguish **Verified Facts** (exact code paths, verbatim command outputs) from **Hypotheses**.
   - **Verifiable Evidence Gate for Reports (報告驗證門檻 - 嚴禁通靈報告)**: A `[DIAGNOSTIC]` or `[RESEARCH]` task is invalid without concrete evidence (e.g., minimal failing test reproduction command, exact file/line numbers, or raw error logs). Mere textual speculation or vague claims without test evidence constitutes a task failure.
3. **Full-Spectrum Exploration Scope for Diagnostics (探勘全光譜：微觀函式至宏觀全專案跨介面)**:
   - **Why Necessary**: Real-world bugs, performance leaks, and new capabilities often cut across interfaces (e.g. UI View ➔ ViewModel ➔ State ➔ AudioEngine ➔ OS Lifecycle). If diagnostic scope is artificially constrained to a single file, cross-interface defects can never be isolated or fixed!
   - **Exemption from Single-Seam Constraint**: Unlike `[CODE]` tasks, `[DIAGNOSTIC]` and `[RESEARCH]` tasks are **exempt from single-seam restrictions** and possess full-spectrum exploration authority:
     - **Macro (Project-Wide Flow)**: Trace end-to-end data pipelines, asynchronous event loops, system lifecycle notifications (e.g. sleep/wake), and cross-subsystem protocol boundaries.
     - **Meso (Interface Contract / Seam)**: Verify parameter passing, type marshaling, and state synchronization between interacting components.
     - **Micro (Function / Logic Branch)**: Deep dive into timer calculations, race conditions, memory leaks, and specific arithmetic branches.
   - **Outcome**: The diagnostic report maps the entire cross-interface causal chain. Planner then uses this verified map to decompose subsequent `[CODE]` tasks into atomic, single-seam implementation tickets.
4. **Single-Seam Freedom for Implementation (代碼實作接縫自由)**: For `[CODE]` tasks, as long as the modification operates on a single architectural module/seam, there is **NO line-of-code limit**. Worker has full autonomy on internal helpers, data structures, and tests.
5. **Cross-Subsystem Rejection for Code Modifications (代碼實作之跨子系統拒絕)**: If a `[CODE]` task demands simultaneous, uncoordinated implementation changes across multiple decoupled subsystems, Worker emits `[NEED_DECOMPOSITION]` with proposed subtasks. *(Note: This restriction applies to code modification only; diagnostic exploration has full cross-interface permission).*
6. **3-Tier Escalation, Granularity Ladder & Sovereign Intervention Protocol**:
   - *Tier 1 (Local choices)*: Worker decides autonomously.
   - *Tier 2 (Recoverable errors)*: Worker self-heals within 3 retries (with `git restore` clean intermediate resets).
   - *Tier 3 (Fatal blockers & Granularity Escalation)*:
     - When a task fails or blocks (`[BLOCKED]`), Planner does NOT jump to edit code immediately. Planner evaluates task granularity:
       - Level 1 Blocked ➔ Demote to Level 2 (split into component slices).
       - Level 2 Blocked ➔ Demote to Level 3 (micro function-level instructions & exact tests).
     - **Dual Sovereign Intervention Thresholds (Planner 介入主權雙門檻 - 代碼與報告一致原則)**:
       1. **Implementation Threshold (代碼層級)**: When a coding task is **ALREADY at Level 3 (Micro)** and Worker STILL fails after 3 retries, Planner **steps in**, reads `.worker.log`, inspects code directly, applies surgical fix, and commits.
       2. **Diagnostic & Report Evasion Threshold (報告/診斷層級 - 防止 Worker 看不懂亂寫報告)**: When Worker repeatedly produces vague/hallucinated reports, claims success without reproducible test evidence, or fails to isolate the issue after **2-3 retries** (consistent with the 3-attempt exhaustion rule), Planner **steps in**, inspects target code directly, isolates the root cause, and logs the discovery and why the allocation failed in `docs/agents/granularity-profile.json` and `.worker.notes.md`.
     - **Post-Mortem Allocation Retro**: Planner **MUST record why the allocation failed** in `docs/agents/granularity-profile.json` (module rating & notes) and `.worker.notes.md` (compiler traps / repo quirks discovered) to permanently enhance future task allocation efficiency!
   - *Minor ambiguities*: Advance with Best-Effort and leave a non-blocking `Notes:` entry in `progress.log` so 24h workflow is not unnecessarily interrupted.

---

## 5. Dual-Skill Ecosystem

- **Global**: Matt Pocock foundations (`/tdd`, `/codebase-design`, `/domain-modeling`, `/diagnosing-bugs`, `/git-guardrails`, `/chief-of-staff`).
- **Architect Skills** (`.agents/skills/architect/`): `/calibrate-task-granularity`, `/score-worker-performance`, `/handle-worker-guidance`, `/watch-worker-queue`.
- **Worker Skills** (`.skills/`, `.agents/skills/worker/`): `/universal-build-verify`, `/record-attempt-trace`, `/manage-worker-notes`.

---

## 6. Verification & Safe Inspection Protocol (Zero Context Pollution)

To maximize token efficiency and prevent context exhaustion across the 24h cycle:
1. **Ultra-Concise Inter-AI Protocol (AI 間極簡資訊交換規範)**:
   - Worker log entries in `progress.log` are strictly capped at **<= 15 lines**.
   - Dedicated reports (`docs/reports/*.md`) MUST feature an **Executive Summary <= 30 lines** with bulleted facts, metrics, and line pointers. No discursive prose.
2. **Primary Acceptance**:
   - Terminal A (Planner) reads only the top block of `progress.log` (`head -n 15 progress.log`) for rapid, low-token acceptance.
3. **Planner On-Demand Inspection Right (Anti-Rubber-Stamping / 防止胡亂驗收)**:
   - Planner is NOT a rubber stamp. Whenever a task involves critical architectural seams, or whenever Worker reports `Attempts > 1` or `Confidence < 1.0`, Planner **MUST exercise its deep inspection right**:
     - `git log -n 1 --stat`
     - `git show --stat <commit-hash>`
     - Targeted file inspection (`view_file` on modified line ranges).
     - Running verification tests directly to prevent simulated or hallucinated passes.
4. **STRICTLY FORBIDDEN in Terminal A (Planner Guardrails)**:
   - ❌ **Busy-Loop Polling / Sleep Loops**: NEVER run `sleep` or repeatedly poll `progress.log` / `worker.status` in a tool loop waiting for Worker to finish. Once `tasks.txt` is written, Planner MUST immediately yield control and stop calling tools! Inspection is strictly event-driven (when Human asks or during next turn).
   - ❌ Bare `git log` (dumps unbounded commit history).
   - ❌ `git log -p` / bare `git show <hash>` (dumps hundreds of lines of code diffs).
   - ❌ `git diff main...HEAD` (full diff).

---

## 7. Branch Strategy: Linear Git Rebase & Auto-Cleanup

All batch feature development should happen on integration branches and integrate linearly into `main`:

```bash
# 1. Rebase feature branch onto latest main
git checkout feature/<batch-name>
git rebase main

# 2. Fast-forward merge into main
git checkout main
git merge --ff-only feature/<batch-name>

# 3. Safely delete the feature branch after confirmed merged
git branch -d feature/<batch-name>
```

---

## 8. Unified Git Commit Standard (Planner & Worker)

To ensure consistent git history and enable instantaneous acceptance by the Planner without opening code diffs, all commits made by both **Planner (Terminal A)** and **Worker (Terminal B)** MUST adhere to the **Unified Conventional Commit Standard**:

```bash
git commit -m "<type>(<scope>): <concise action description in English <= 60 chars> (<task_id>)" -m "<1-3 summary bullet points of changes>

Task: <task_id> (<granularity_level>)
Scope: <target_files>
Verification: <test command> (<measurable result, e.g. 6/6 passed, 100% OK>)
Attempts: <attempts_count> | Confidence: <confidence_score>"
```

### Commit Format Rules:
1. **Title Line (Header)**:
   - Max 70 characters.
   - Types: `feat`, `fix`, `refactor`, `test`, `perf`, `docs`.
   - Scope: Module or component name in parentheses (e.g. `calc`, `auth`, `worker`).
   - `(<task_id>)` appended at the end of the title line (e.g. `(TASK-002)`).
   - **Strictly Prohibited**: NEVER dump raw task schema strings (`| LEVEL: ... | TARGET: ... | ACTION: ...`) into the commit title!
2. **Commit Body (Rapid Acceptance Block)**:
   - Summary of concrete functional changes (1-3 bullets).
   - Explicit `Task`, `Scope`, `Verification`, and `Attempts` lines so Planner can verify everything via `git log -n 1` in under 5 seconds.

---

## 9. Mandatory Command Execution & Git Guardrails

Whenever executing commands in this workspace, the agent MUST obey the following safety rules:
- **No Destructive Git Operations**: Under NO circumstances should the agent run:
  - `git push` / `git push --force`
  - `git reset --hard` (except worker.sh automated isolated rollback)
  - `git clean -f` / `git clean -fd`
  - `git branch -D`
  unless specifically and explicitly requested by the user.
- **No Host-Level Modifying Commands**: Under NO circumstances run `sudo`, `apt`, `yum`, `dnf`, `pacman`.

---

## 10. Engineering & Domain Treaties

- **Test-Driven Development (TDD)**: Follow Red-Green-Refactor cycle. Unit tests must pass 100%.
- **Deep Modules**: Design deep modules with simple, narrow interfaces.
- **Glossary Adherence**: Strictly adhere to terms in [GLOSSARY.md](GLOSSARY.md).
- **ADR Review**: Respect architectural records in [docs/adr/](docs/adr/).

---

## 11. Framework Portability & Adoption

If you are an AI migrating this framework to another project, read the autonomous porting manual at [docs/PORTING_GUIDE.md](docs/PORTING_GUIDE.md) and execute [.agents/skills/engineering/setup-unattended-workflow/SKILL.md](.agents/skills/engineering/setup-unattended-workflow/SKILL.md).
