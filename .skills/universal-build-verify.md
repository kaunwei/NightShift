---
name: universal-build-verify
description: "Universal execution SOP for unattended background workers (TDD, diagnostics, auto-commit, retry limit)."
---

# Universal Build, Test & Verification SOP (Worker)

Mandatory execution protocol for Background Worker (Terminal B) processing `tasks.txt`.

## 1. Hard Guardrails & Constraints

- **Host Safety**: Never run `sudo`, `apt`, `yum`, or host package managers.
- **Clean Tree**: `git status --porcelain` must be 100% clean after commit. Zero untracked tests or build artifacts.
- **Compiler Cleanliness**: 0 warnings (`-Wall -Wextra`) and clean linter run.
- **Target Whitelist**: Modify declared `TARGET:` paths only (cohesive multi-file slices allowed when declared). Never touch unlisted files to silence compilers; halt and emit `STATUS: SCOPE_BLOCKED (Need Target: <File>#L<Line>)` (zero penalty).
- **Test Immutability & Assertion Non-Decrease**:
  - `[CODE: FIX]`: Product files only; `Tests/` strictly read-only.
  - `[CODE: REFACTOR]`: `Tests/` editable if in `TARGET:`. Added assertions must be `>=` deleted assertions (`XCTAssert`, `#expect`, `assert`, `expect(`, `self.assert`).
- **Proof of Negative for `[DEAD_END]`**: Declaring a lead a dead end or a suspect module innocent requires tangible proof (isolated passing unit test or runtime log proving module health while global symptom persists). Speculative exclusion = immediate task failure.
- **Forbidden Shortcuts**: Honor `FORBIDDEN_SHORTCUTS:`. No thread sleeps (`asyncAfter`, `sleep`), no error swallowing (`try?`, empty catch), no optional-widening to dodge initializers, no dummy returns.
- **Blast Radius Limits**: Max deletions by Level: L3 `<= 40` lines, L2 `<= 150` lines, L1 `TARGET:`-bounded.

## 2. Archetypes & Execution Loops (Skill Pointers)

- **`[CODE: FIX]` / `[CODE: REFACTOR]`**:
  - Follow [`implement`](../.agents/skills/engineering/implement/SKILL.md), [`tdd`](../.agents/skills/engineering/tdd/SKILL.md) (Red $\rightarrow$ Green $\rightarrow$ Refactor at pre-agreed seams), and [`codebase-design`](../.agents/skills/engineering/codebase-design/SKILL.md) (narrow public interfaces; never test ephemeral private helpers).
  - Refactors enforce **Assertion Non-Decrease** and structural closure in `VERIFY:` (e.g. `<cmd> && ! grep -rn "<Deprecated>" Sources/`).
- **`[CODE: EXPAND/MIGRATE/CONTRACT]`**: Phased migration per [`to-tickets`](../.agents/skills/engineering/to-tickets/SKILL.md); every intermediate commit must leave builds and tests 100% green.
- **`[RESEARCH]` / `[BENCHMARK]`**:
  - Follow [`research`](../.agents/skills/engineering/research/SKILL.md) and [`explore`](../.agents/skills/nightshift/explore/SKILL.md). Extract AST skeletons via `scripts/extract_skeleton.sh <path>#L<line>`.
  - *Compiler Probe*: Temporarily alter signatures, run `build` to capture 100% of call-sites into `SUMMARY.md`, and immediately run `git restore .`.
  - *Progressive Disclosure*: `SUMMARY.md` is an executive digest (`<= 5 KB`: topology, coupling bottlenecks, Expand-Migrate-Contract matrix, validated pointers). Full skeletons and 10-line slices belong in `03-micro.md`.
  - *Dedicated Audit*: Audited on Artifact Integrity (non-empty report), Clean Tree (0 uncommitted product edits), and Pointer Validity (`<File>#L<Line>` verified on disk). `VERIFY:` can be `REPORT_ONLY`.
- **`[DIAGNOSTIC]`**:
  - Follow [`diagnosing-bugs`](../.agents/skills/engineering/diagnosing-bugs/SKILL.md) to build a tight pass/fail feedback loop that goes red strictly on this bug. Isolate root cause with minimal repro test or trace in `.reports/<issue-slug>/`.
  - *Valid Red-Light Rule*: Repro test must compile cleanly (0 syntax errors) and fail strictly on assertion.
  - *Product Code Lock*: Production code (`Sources/`, `src/`) is strictly read-only; touch only tests and `.reports/`.

## 3. Honest Treaty & Retries

- **Zero-Guessing**: State verified facts only; label interpretations as `Hypothesis`.
- **Max 3 Retries**:
  1. Analyze $\rightarrow$ Fix $\rightarrow$ Test.
  2. On failure, `git restore <file>` to reset baseline $\rightarrow$ Apply alternative fix.
  3. Final attempt: if failed, restore clean tree, log `[BLOCKED]` at the top of `progress.log`, and exit.

## 4. Acceptance, Logging & Notes

### 4.1 Attempt Trace & Progress Journal (`progress.log`)
- **Strict Limit**: Prepend `<= 15 lines` at the top of `progress.log`. Use pointers (`src/file.py#L10-L20`), zero discursive prose.
- **Confidence**: `HIGH` (1st pass, 0 warnings), `MEDIUM` (1-2 retries needed), `LOW` (brittle or edge cases unverified).
- **Template**:
  ```text
  ================================================================================
  [SUCCESS | BLOCKED] TASK-XXX: <Title>
  Time: <Timestamp> | Duration: <Xs> | Attempts: <N>/3 | Confidence: <HIGH|MED|LOW>
  Task Granularity: <Level 1|Level 2|Level 3>
  Changes: <Files / Report path>
  Verification: Build <PASS|FAIL>, Tests <PASS|FAIL> (<N> passed)
  Attempt Trace:
    • Att 1: <PASS or failure reason with exact error summary>
    • Att 2/3: <Fix applied and result>
  Notes: <Optional observations>
  ================================================================================
  ```

### 4.2 Repository Quirks & Flags (`.worker.notes.md`)
- **Consult & Update**: Check `.worker.notes.md` before every task. Append concise 1-2 line tips when discovering non-obvious build/linker quirks (`< 30 lines` total). Record compiler/toolchain flags only—never architectural lore or task history.

### 4.3 Double-Funnel Mechanical Audit & Commits
- **Mechanical Audit**: `worker.sh` re-runs verification, enforces `Tests_Run >= 1`, checks regressions, and stamps `[MECHANICAL_AUDIT]` at line 1 of `progress.log`.
- **Conventional Commit (English ONLY)**:
  ```bash
  git commit -m "<type>(<scope>): <concise action <= 60 chars> (<task_id>)" -m "<1-3 summary bullets>

  Task: <task_id> (<granularity>)
  Scope: <target_files>
  Verification: <test command> (<result>)
  Attempts: <count> | Confidence: <score>"
  ```

## 5. Execution Modes (`WORKER_ISOLATION`)

- **`1` (Default)**: Isolated `.worker-tree` (`feature/worker-frontier`), auto-staged to `.preview/`.
- **`0` (In-Place)**: Workspace root execution for singleton hardware or fixed ports.
