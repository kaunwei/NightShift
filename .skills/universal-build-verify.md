---
name: universal-build-verify
description: "Universal build, test, GUI smoke verification, honest retry tracking, and auto-commit SOP for unattended background workers."
---

# Universal Build, Test & Verification SOP (Background Worker)

This document is the **mandatory standard operating procedure** that the unattended background Worker AI MUST strictly follow when executing tasks popped from `tasks.txt`.

---

## 1. Strict Security & Anti-Rot Constraints (安全與防腐門禁)

1. **NO Global System Modifications**:
   - Under NO circumstances run `sudo`, `apt`, `apt-get`, `yum`, `dnf`, `pacman`, or any host system-level package manager.
2. **Local Environment Only**:
   - Dependencies must be managed locally within the project (`.venv`, `cmake` local prefix, `pkg-config`).
3. **Zero Compiler / Lint Warnings (零警告門禁)**:
   - Code must build cleanly with zero compiler warnings (e.g. `-Wall -Wextra`) and pass static checks without errors.
4. **Interface Immutability**:
   - When a task specifies `CONSTRAINTS: Do not change public API`, do not alter public method signatures.

---

---

## 2. Multi-Archetype Workflow & Verification

Worker tasks are not limited to coding. The worker autonomously adapts its execution and verification strategy according to the task archetype:

### Archetype A: Implementation & Refactoring (`[CODE]`, `[REFACTOR]`)
1. **Single-Seam Freedom**: Full autonomy within a single cohesive seam/module (no LOC limit).
2. **Cross-Subsystem Rejection**: Emit `[NEED_DECOMPOSITION]` if uncoordinated changes across multiple independent subsystems are requested.
3. **Execution**: Follow TDD, build cleanly (0 compiler/lint warnings), run automated unit/integration tests, and perform GUI smoke checks if applicable.

### Archetype B: Research & Data Gathering (`[RESEARCH]`, `[SURVEY]`)
1. **Primary Sources & Extraction**: Inspect codebases, configs, or docs to gather concrete data into designated output files (e.g., `docs/research/*.md`).
2. **Verifiable Citations**: Include file paths, line numbers, or raw command outputs for every fact.

### Archetype C: Case Studies, Benchmarks & Test Matrix (`[BENCHMARK]`, `[CASE_STUDY]`)
1. **Execution**: Run designated parameter suites, test suites, or profiling scripts.
2. **Tabulation**: Aggregate results into clean markdown/CSV tables with summary metrics.

### Archetype D: Diagnostic & Bug Isolation (`[DIAGNOSTIC]`)
1. **Reproduction Proof Gate**: Create minimal failing test cases or capture exact error reproduction traces. Pure textual explanations without a verifiable command output or stack pointer are strictly rejected.
2. **Root Cause Analysis**: Isolate the exact failing branch with evidence. If the root cause is obscure or cannot be verified after 2 attempts, Worker MUST NOT invent explanations; emit `[NEED_GUIDANCE]` or report verified facts vs unknown gaps honestly.

---

## 3. Strict Zero-Guessing Honest Treaty (嚴禁通靈硬猜之誠實公約)

Across all task archetypes (Code, Research, Benchmarking, Diagnostics), Worker MUST strictly observe:

1. **Anti-Hallucination / Zero Speculation (看不懂絕不硬猜、嚴禁胡亂寫報告)**:
   - If legacy code, obscure macros, complex math, or undocumented behaviors are ambiguous, Worker **MUST NOT guess or invent intent**.
   - State strictly: *Observed behavior*, *Verified code paths*, and *Uncertain/Ambiguous areas*.
   - Never claim a bug is "diagnosed" or "fixed" without reproducible test evidence.
2. **Fact vs Hypothesis Separation (事實與假設嚴格分離)**:
   - In research, benchmarks, and diagnostic logs, raw output is recorded as **Facts**.
   - Any interpretation is explicitly labeled as **Hypothesis** with verification suggestions.
3. **Transparent Evidence Gate**:
   - Every completed task must provide reproducible proof (test command pass, benchmark output summary, or linked file locations).

---

## 4. Error Retry Limit & Intermediate Clean Reset (修復上限與中間重置)

When build, compilation, tests, or scripts fail:
1. **Maximum 3 Fix Attempts**:
   - **Attempt 1**: Analyze error trace, apply surgical fix, rebuild/retest.
   - **Attempt 2**: If Attempt 1 made things worse, run `git restore <file>` to clean intermediate state back to baseline before trying an alternative fix.
   - **Attempt 3**: Final attempt.
2. **Immediate Stop on 3rd Failure**:
   - If unable to pass after 3 attempts, STOP immediately. Do NOT enter an infinite loop.
   - Mark task as `[BLOCKED]` in `progress.log` and exit.

---

## 5. Honest Escalation Protocol (誠實求助與務實推進協議)

### 3-Tier Escalation:
- **Tier 1 (Local Choices)**: Private helpers, internal data structures, data presentation formatting ➔ Worker decides autonomously.
- **Tier 2 (Recoverable Errors)**: Compiler/test errors, script typos ➔ Self-heal within 3 attempts.
- **Tier 3 (Fatal Blockers)**: Spec contradictions, missing host dependencies, or 3 failed retries ➔ Emit `[NEED_GUIDANCE]` or `[BLOCKED]` and pause cleanly.

### Best-Effort with Note (非阻塞標記推進):
For minor ambiguities that do not threaten core integrity:
- Make a standard, idiomatic engineering decision.
- Finish the task, verify, and commit normally.
- Append a note in `progress.log`: `Notes: [Brief explanation of the choice made, allowing Architect to review/refine]`.
- DO NOT halt the unattended pipeline for non-critical ambiguities.

---

## 6. Completion Standard & Evidence Logging (結案標準與超精簡協議)

### Ultra-Concise Inter-AI Information Protocol (AI 間極簡資訊交換規範):
1. **Length Limit**:
   - `progress.log` entry MUST NOT exceed **15 lines**.
   - Dedicated report files (e.g. `docs/reports/*.md`) MUST begin with an **Executive Summary <= 30 lines** (key metrics, pass/fail table, raw pointers).
2. **Dense & High-Signal**: No polite greetings, narrative essays, or verbose explanations. Only include:
   - Target files & line references (`file:///path/to/file#L10-L25`)
   - Exact command exit codes & execution time
   - Measurable metrics (e.g. `12/12 passed, 0 warnings`)
3. **Planner On-Demand Inspection Right (Planner 保留按需抽查權)**:
   - The worker's summary is designed for fast acceptance without token bloat.
   - Planner retains the sovereign right to inspect underlying source files, run targeted commands, or check git stats whenever summary information is deemed insufficient.

Upon 100% verification success:
1. **Auto Git Commit (Unified Conventional Commits Standard)**:
   Stage the modified target files and commit using standard Conventional Commit format (concise title <= 70 chars, plus structured acceptance body):
   ```bash
   git commit -m "<type>(<scope>): <concise action description in English <= 60 chars> (<task_id>)" -m "<1-3 summary bullet points of changes>

Task: <task_id> (<granularity_level>)
Scope: <target_files>
Verification: <test command> (<measurable result, e.g. 6/6 passed, 100% OK>)
Attempts: <attempts_count> | Confidence: <confidence_score>"
   ```
   - **Allowed types**: `feat`, `fix`, `refactor`, `test`, `perf`, `docs`.
   - **Scope**: Target module or subsystem name (e.g. `calc`, `auth`, `api`, `ui`).
   - **Strict Rule**: NEVER dump raw task schema strings (`| LEVEL: ... | TARGET: ...`) into the commit title line. The title line must remain clean and readable for `git log --oneline`.
2. **Prepend Structured Summary & Attempt Trace to `progress.log` (Strictly <= 15 lines)**:
```text
================================================================================
[SUCCESS] TASK-XXX: <Task Title>
Time: <YYYY-MM-DD HH:MM:SS> | Duration: <Xs> | Attempts: <N>/3 | Confidence: <HIGH|MED|LOW>
Task Granularity: <Level 1|Level 2|Level 3>
Changes: <Modified files / Report path>
Verification: Build PASS, Tests PASS (<N> passed), GUI Smoke PASS
Attempt Trace:
  • Attempt 1: <PASS or failure reason with exact error summary>
  • Attempt 2: <Fix applied, if any>
Granularity Feedback: <Worker observation on module granularity>
================================================================================
```

---

## 7. Dual-Worktree Isolation & Preview Drop-Box Support

The background worker supports workspace isolation modes via `WORKER_ISOLATION` in `.worker.env`:
- **Dual-Worktree Isolation (`WORKER_ISOLATION=1`, Default)**:
  - Worker operates exclusively in `.worker-tree` on branch `feature/worker-frontier`.
  - Commits land cleanly on `feature/worker-frontier`.
  - Upon task verification success, `worker.sh` publishes an immutable snapshot to `.preview/` with `version.json`.
  - Human and Planner can preview verified builds at any time without colliding with worker compilation, tests, or mid-edit files.
- **Single-Tree In-Place Mode (`WORKER_ISOLATION=0`)**:
  - Worker operates directly in the project root.
  - Commits land directly on the active branch (e.g., `main`).
  - Recommended for hardware-locked environments or fixed ports (e.g. port 22).

