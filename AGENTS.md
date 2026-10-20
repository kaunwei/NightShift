# Agent Rules & Treaties (24-Hour Unattended Framework)

Strict operational guardrails for AI agents operating in this repository.

---

## 1. Role Boundaries (Dual-Terminal Firewall)

Strict physical and logical separation between **Planner (Terminal A)** and **Background Worker (Terminal B)**.

### Terminal A: Interactive Planner (This Session)
- **Mission**: System architecture, domain modeling, task decomposition, and verification audit.
- **Rules**:
  - **Never code directly**: Do NOT modify business code (`Sources/`, `src/`, `app/`, `lib/`, `tests/`) via edit/write tools during routine requests.
  - **Never debug in-session**: Do NOT run exploratory debug loops or subagent sweeps in Terminal A.
  - **Queue and yield**: Decompose requirements into atomic contracts in `tasks.txt`, then **immediately yield control**.
  - **Diagnostic Preemption**: Inject `[DIAGNOSTIC]` and `[RESEARCH]` tasks at line 1 of `tasks.txt` (via `scripts/reorder_queue.sh`). Worker preempts existing tasks to gather facts without context bloat.
  - **Zero-token Wakeup**: Deploy Queue Sentinel (`scripts/watch_worker.sh 3600`) to wait passively. **Never run sleep or polling loops in chat**.
- **Sovereign Intervention Thresholds** (When Planner MUST intervene):
  1. **Level 3 Failure**: A task is already at Level 3 (Micro) and Worker fails all 3 retries.
  2. **Diagnostic Hallucination / Block**: Worker produces speculative/unverified reports or fails to isolate root cause after 2-3 attempts.
  3. **Explicit Mandate**: Human explicitly requests direct action.
  - *Post-Intervention Rule*: Planner applies surgical fix, commits, and logs the root cause in `docs/agents/granularity-profile.json` and `.worker.notes.md`.

### Terminal B: Headless Background Worker (`worker.sh`)
- **Mission**: Hands-on unattended implementation, test-driven execution, and atomic commits.
- **Rules**:
  - Operates exclusively in `.worker-tree` on branch `feature/worker-frontier` (when `WORKER_ISOLATION=1`).
  - Reads `tasks.txt` FIFO queue.
  - Executes `.skills/universal-build-verify.md`. Max 3 repair attempts per task before automated rollback (`git restore`) and `[BLOCKED]` status.
  - Follows Conventional Commit format. Prepends <=15 lines to `progress.log`. Stages verified snapshot to `.preview/`.
  - Never changes high-level architecture; never enters chat loops.

---

## 2. Dynamic Granularity Ladder

Size tasks in `tasks.txt` according to `docs/agents/granularity-profile.json`:

| Level | Granularity | `[CODE]` Implementation Scope | `[DIAGNOSTIC]` / `[RESEARCH]` Scope |
| :---: | :--- | :--- | :--- |
| **Level 1** | Coarse / Macro | Feature seam: specify public interface & test contract. | **Macro Flow**: trace end-to-end event loops, lifecycle hooks, subsystem topology. |
| **Level 2** | Medium / Meso | Component slice: discrete module units. | **Interface Boundary**: trace contract compliance, state sync, and parameter handoff. |
| **Level 3** | Micro | Surgical function logic or exact algorithm. | **Function Deep Dive**: inspect timing calculation, race condition, localized math. |

### Task Schema (Tracer-Bullet)
```text
TASK-XXX | LEVEL: 1 | AFTER: <task_id> | TARGET: <file_paths> | ACTION: <logic details> | VERIFY: <test command> | CONSTRAINTS: <scope limits>
```
*(Note: `AFTER: <task_id>` is optional for DAG dependencies).*

### Hierarchical Progressive Exploration
When addressing complex defects or unknown systems, proceed strictly top-down:
1. `LEVEL: 1 [RESEARCH]` / `[DIAGNOSTIC]` -> Map subsystem topology and project-wide flow.
2. `LEVEL: 2 [DIAGNOSTIC]` -> Trace cross-module protocols and state synchronization.
3. `LEVEL: 3 [DIAGNOSTIC]` -> Deep-dive into specific function logic or race conditions.
4. `[CODE]` -> Execute atomic, single-seam implementation tickets grounded in verified facts.

---

## 3. Worker Execution Guardrails & Honest Treaty

- **Archetypes**: `[CODE]`, `[RESEARCH]`, `[BENCHMARK]`, `[DIAGNOSTIC]`.
- **Zero-Guessing Treaty**: Never speculate on ambiguous code or obscure errors. Clearly separate **Verified Facts** (exact code lines, test outputs, stack traces) from **Hypotheses**.
- **Evidence Gate**: A diagnostic report without a minimal failing test command, exact file/line pointers, or raw error logs is invalid and rejected.
- **Single-Seam Limit for Code**: `[CODE]` tasks modify exactly ONE architectural seam. Cross-subsystem edits MUST be rejected by Worker with `[NEED_DECOMPOSITION]`.
- **Full-Spectrum Diagnostic Authority**: Unlike code tasks, `[DIAGNOSTIC]` and `[RESEARCH]` tasks are exempt from single-seam restrictions. Worker is authorized to trace across all layers (UI -> State -> Engine -> OS).
- **Escalation Protocol**:
  - *Tier 1 (Local choices)*: Worker decides autonomously.
  - *Tier 2 (Recoverable errors)*: Worker self-heals within 3 retries (clean `git restore` between retries).
  - *Tier 3 (Blockers)*: Demote granularity (Level 1 -> 2 -> 3). If Level 3 fails 3 times, escalate to Planner sovereign intervention.

---

## 4. Verification & Context Protection

Keep context token-lean and prevent rubber-stamping:
- **Concise Protocol**: Worker entries in `progress.log` <= 15 lines. Formal reports in `docs/reports/*.md` require an Executive Summary <= 30 lines.
- **Fast Acceptance**: Planner reads `head -n 15 progress.log`.
- **Anti-Rubber-Stamp Audit**: When `Attempts > 1`, `Confidence < 1.0`, or touching critical seams, Planner **MUST deep-inspect**:
  - `git log -n 1 --stat`
  - `git show --stat <commit-hash>`
  - Targeted file inspection on modified line ranges.
  - Run verification tests directly.
- **Forbidden in Planner**:
  - Never run `sleep` or polling loops in chat.
  - Never execute unbounded `git log`, `git log -p`, or full `git diff`.

---

## 5. Git Commit & Command Guardrails

### Unified Commit Standard
All commits by Planner and Worker MUST follow this template:
```bash
git commit -m "<type>(<scope>): <concise action description <= 60 chars> (<task_id>)" -m "<1-3 summary bullet points>

Task: <task_id> (<granularity_level>)
Scope: <target_files>
Verification: <test command> (<measurable result, e.g. 6/6 passed, 100% OK>)
Attempts: <attempts_count> | Confidence: <confidence_score>"
```

### Safety Guardrails
- **Forbidden Git Operations**: `git push`, `git push --force`, `git reset --hard` (except worker.sh automated rollback), `git clean -f / -fd`, `git branch -D`.
- **Forbidden Host Commands**: `sudo`, `apt`, `yum`, `dnf`, `pacman`.
- **Linear Branch Integration**:
  ```bash
  git checkout feature/<batch-name>
  git rebase main
  git checkout main
  git merge --ff-only feature/<batch-name>
  git branch -d feature/<batch-name>
  ```

---

## 6. Language & Communication Policy

- **Human-AI Chat (Terminal A)**: Traditional Chinese or English as preferred by Human.
- **Inter-AI Artifacts**: STRICTLY ENGLISH ONLY (`tasks.txt`, `progress.log`, `worker.status`, `tasks.done`, commit messages, code comments, and documentation).
