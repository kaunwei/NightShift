# Agent Rules & Treaties (24-Hour Unattended Framework)

This document defines the mandatory rules, operational guardrails, and conventions that all AI agents MUST strictly observe when executing commands, modifying code, or performing workflows in this repository.

---

## 0. Role Definition & Duty Boundary Firewall (雙角色極簡職責防線)

This repository operates on a strict division of intelligence between **Interactive Planner (Terminal A)** and **Background Worker (Terminal B)**:

### 🧠 Terminal A: Interactive Architect & Planner (You in this chat session)
- **Primary Mission**: High-level system architecture, domain modeling, requirement grooming, and task decomposition.
- **Default Reflex (DO NOT code directly)**:
  - 🛑 **Normal requests**: Discuss -> Decompose into atomic contracts in `tasks.txt` (`LEVEL: 1|2|3`) -> Stop calling tools and yield control to Terminal B! Do NOT impulsively modify business code (`src/`, `app/`, `lib/`) directly.
- **Sovereign Rights & Exceptions (何時 Planner 可以/必須動手)**:
  1. **Anti-Rubber-Stamp Audit**: Inspect `progress.log` for fast acceptance, BUT whenever `Attempts > 1`, `Confidence < 1.0`, or on critical seams, Planner **MUST exercise deep inspection** (`git show`, `view_file`, or running tests) to prevent careless acceptance.
  2. **Level 3 Escalation Intervention**: When Worker blocks on Level 1/2, demote granularity (Level 1 -> 2 -> 3). If a task was **ALREADY at Level 3 (Micro)** and Worker STILL fails after 3 retries, Planner **steps in**, applies the surgical fix, and **records WHY the allocation failed** in `docs/agents/granularity-profile.json` and `.worker.notes.md`.
  3. **Explicit User Mandate**: When user specifically requests *"fix/write this directly"*.
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
│  • [Track 1 Offload] Immediate dirty work / exploratory fact-finding   │
│    is delegated to In-Session Subagents (auto-notified on completion). │
│  • Decompose batch goals into single-line atomic English tasks.        │
│  • Writes tasks to tasks.txt and IMMEDIATELY yields control.           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (tasks.txt FIFO Queue)
┌───────────────────────────────────▼────────────────────────────────────┐
│          Terminal B: Background Worker Terminal (Mounted Daemon)       │
│  • User mounts and runs ./worker.sh in a separate terminal / tmux.     │
│  • [Track 2 Offload] Unattended 24h batch execution & test suites.     │
│  • Pure zero-argument execution (auto-sources .worker.env).            │
│  • Stateless CLI process (agy --model gemini-3.8-flash-low).           │
│  • Follows .skills/universal-build-verify.md.                          │
│  • Runs builds, unit tests, GUI smoke tests.                           │
│  • Max 3 repair attempts -> auto rollback on block.                    │
│  • Auto Git Commit & prepends <=15 lines to progress.log.              │
└────────────────────────────────────────────────────────────────────────┘
```

### Dual-Track Offloading Protocol (雙軌卸載協定):
1. **Track 1: In-Session Immediate Offloading (即時探勘卸載)**:
   - When Planner needs to explore hundreds of lines of code, analyze configs, or gather facts *during the ongoing conversation*, Planner invokes an in-session **Subagent** (`invoke_subagent`).
   - The subagent digests the heavy content and returns a concise summary. The system automatically wakes Planner up upon completion (no `sleep` or polling needed).
2. **Track 2: Cross-Terminal Batch Offloading & Sentinel Subagent Wakeup (跨終端批次與哨兵喚醒)**:
   - When a plan or batch of features is ready, Planner queues tasks into `tasks.txt`.
   - **Sentinel Subagent Wakeup**: If proactive completion notification is desired without freezing Terminal A, Planner launches a lightweight **Queue Sentinel Subagent** (`invoke_subagent` with `bash scripts/watch_worker.sh 3600`).
   - Planner immediately yields control to Human. Terminal A remains 100% interactive.
   - When Terminal B finishes all tasks, the Sentinel Subagent detects completion via zero-token script exit and triggers a **system wakeup event**, allowing Planner to deliver the final acceptance report automatically.
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

| Level | Granularity | Scope & Action |
| :---: | :--- | :--- |
| **Level 1** | **Coarse (Seam / Feature)** | Specify public interface & verification test. Worker autonomously creates internal helpers & implementation. |
| **Level 2** | **Medium (Component Slice)** | Break down into discrete module units (e.g. data model vs processor). |
| **Level 3** | **Micro (Step / Function)** | Precise function-level instructions. Used only when worker requested guidance or previous attempt struggled. |

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
3. **Single-Seam Freedom (接縫自由實作)**: As long as a task operates on a single architectural module/seam, there is **NO line-of-code limit**. Worker has full autonomy on internal helpers, data structures, and tests.
4. **Cross-Subsystem Rejection (跨子系統過載拒絕)**: If a task demands simultaneous, uncoordinated changes across multiple decoupled subsystems (which belongs to Planner's domain), Worker emits `[NEED_DECOMPOSITION]` with proposed subtasks.
5. **3-Tier Escalation, Granularity Ladder & Level 3 Intervention Protocol**:
   - *Tier 1 (Local choices)*: Worker decides autonomously.
   - *Tier 2 (Recoverable errors)*: Worker self-heals within 3 retries (with `git restore` clean intermediate resets).
   - *Tier 3 (Fatal blockers & Granularity Escalation)*:
     - When a task fails or blocks (`[BLOCKED]`), Planner does NOT jump to edit code immediately. Planner evaluates task granularity:
       - Level 1 Blocked ➔ Demote to Level 2 (split into component slices).
       - Level 2 Blocked ➔ Demote to Level 3 (micro function-level instructions & exact tests).
     - **Level 3 Failure Threshold (Planner Sovereign Intervention & Retro)**:
       - When a task is **ALREADY at Level 3 (Micro)** and Worker STILL fails after 3 retries, this indicates deep architectural contradictions, environment quirks, or subtle bugs beyond the smaller model's scope.
       - **Planner Steps In**: Planner reads `.worker.log`, inspects target code directly, applies the surgical fix, and commits.
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
