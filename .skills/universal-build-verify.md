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
- **Target Whitelist**: Modify declared `TARGET:` paths only. Unannounced edits are strictly forbidden.
  - *Cohesive Seams*: Multi-file slices permitted only when declared in `TARGET:`.
  - *No Silent Compile-Fix Edits*: Never touch unlisted files (e.g. configs, entrypoints) to silence compilers. Emit `STATUS: SCOPE_BLOCKED` instead.
- **Test Immutability & Assertion Non-Decrease**:
  - `[CODE: FIX]`: Product files only. `Tests/` strictly read-only.
  - `[CODE: REFACTOR]`: `Tests/` editable only if declared in `TARGET:`. Added assertions must be `>=` deleted assertions (`XCTAssert`, `#expect`, `assert`, `expect(`, `self.assert`).
- **Proof of Negative for `[DEAD_END]`**: Declaring a lead a dead end or a suspect module innocent requires tangible proof (an isolated passing unit test or log snippet proving module health while global symptom persists). Speculative exclusions without proof = immediate task failure.
- **Forbidden Shortcuts**: Strictly honor `FORBIDDEN_SHORTCUTS:`. No thread sleeps (`asyncAfter`, `sleep`), no error swallowing (`try?`, empty catch), no converting non-optional to optional, no hardcoded dummy returns.
- **Blast Radius Limits**: Deletions capped by Level: L3 <= 40 lines, L2 <= 150 lines, L1 unlimited (bounded by `TARGET:`).

## 2. Archetypes & Execution Loops (Matt Pocock Skills Binding)

Background Worker automatically binds Matt Pocock's implementation skills based on the task archetype:

- **`[CODE: FIX]` / `[CODE: REFACTOR]`**:
  - **`/implement`**: Implement ticket requirements iteratively. Run typechecking regularly, test individual target files frequently, and verify full test suite once at completion.
  - **`/tdd`**: Execute strict Red $\rightarrow$ Green $\rightarrow$ Refactor at pre-agreed seams. Red before green; write only enough code to pass the failing test.
  - **`/codebase-design`**: Target deep module boundaries. Keep public interface narrow; never test or leak ephemeral private helpers.
  - Refactors enforce **Assertion Non-Decrease** and structural verification in `VERIFY:` (e.g. `<cmd> && ! grep -rn "<Deprecated>" Sources/`).
- **`[CODE: EXPAND/MIGRATE/CONTRACT]`**: Phased migration. Every intermediate commit must leave builds and tests 100% green.
- **`[RESEARCH]` / `[BENCHMARK]`**:
  - **`/research`**: Investigate questions against primary source code and specs. Extract AST skeletons via `scripts/extract_skeleton.sh <path>#L<line>`.
  - *Compiler Probe*: Temporarily alter signatures and run `build` to capture 100% of call-sites into `SUMMARY.md`. Mandatory immediate `git restore .`.
  - *Progressive Disclosure*: `SUMMARY.md` is strictly an executive digest (<= 5 KB: topology, coupling bottlenecks, Expand-Migrate-Contract matrix, validated pointers). Full skeletons and inlined 10-line slices belong in `03-micro.md`.
  - *Dedicated Audit*: Evaluated on Artifact Integrity (valid non-empty report), Clean Tree (zero uncommitted product code), and Pointer Validity (`<File>#L<Line>` verified on disk). `VERIFY:` can be `REPORT_ONLY`.
- **`[DIAGNOSTIC]`**:
  - **`/diagnosing-bugs`**: Build a tight pass/fail feedback loop that goes red strictly on this bug. Isolate root cause with minimal repro test or exact trace in `.reports/<issue-slug>/`. Reject ungrounded speculation.
  - *Valid Red-Light Rule*: Repro test must compile cleanly (0 errors) and fail strictly on assertion. Syntax errors or missing symbols = Invalid Repro.
  - *Product Code Lock*: Modifying production code (`Sources/`, `src/`) during diagnostics is strictly forbidden. Touch only tests and `.reports/`.
- **Worker Operational Standards**:
  - **Attempt Traces**: Record transparent attempt traces, duration, and confidence scores into `progress.log` (<= 15 lines).
  - **Repository Notes**: Consult and maintain compiler quirks and environment flags in `.worker.notes.md` (< 30 lines).

## 3. Honest Treaty & Retries

- **Zero-Guessing**: State verified facts only. Label interpretations as `Hypothesis`.
- **Max 3 Retries**:
  1. Analyze -> Fix -> Test.
  2. If failed, `git restore <file>` to reset baseline -> Apply alternative fix.
  3. Final attempt. If failed, halt immediately, log `[BLOCKED]` in `progress.log`, and exit.
- **`[SCOPE_BLOCKED]` Exit**: Downstream compiler errors outside `TARGET:` -> Halt immediately, emit `STATUS: SCOPE_BLOCKED (Need Target: <File>#L<Line>)`. No penalty.

## 4. Acceptance, Logging & Notes

### 4.1 Attempt Trace & Progress Journal (progress.log)
- **Strict Limit**: Entries MUST be `<= 15 lines`. Pointers over prose (`src/file.py#L10-L20`). Zero discursive prose.
- **Confidence Metrics**:
  - `HIGH`: Tests passed 100%, 0 warnings, standard conventions.
  - `MEDIUM`: Tests passed, but required 1-2 retries to align fixtures/linkers.
  - `LOW`: Tests passed, but code feels brittle or edge cases remain unverified.
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

### 4.2 Repository Quirks & Flags (.worker.notes.md)
- **Consult**: At start of every task, check `.worker.notes.md` and follow project-specific compiler flags and tool paths.
- **Update**: When discovering a non-obvious build quirk or linker dependency, append a concise 1-2 line tip under the relevant section (< 30 lines total).
- **Invariants**: Strictly compiler flags and toolchain quirks. NEVER record architectural lore or task history.

### 4.3 Double-Funnel Mechanical Audit & Commits
- **Double-Funnel Mechanical Audit**: `worker.sh` mechanically re-runs verification, checks Anti-Idle (`Tests_Run >= 1`), runs regression checks, and stamps `[MECHANICAL_AUDIT]` at line 1.
- **Conventional Commit Standard (English ONLY)**:
  ```bash
  git commit -m "<type>(<scope>): <concise action <= 60 chars> (<task_id>)" -m "<1-3 summary bullets>

  Task: <task_id> (<granularity>)
  Scope: <target_files>
  Verification: <test command> (<result>)
  Attempts: <count> | Confidence: <score>"
  ```

## 5. Execution Modes (`WORKER_ISOLATION`)

- **`1` (Default)**: Isolated `.worker-tree` (`feature/worker-frontier`). Milestones auto-staged to `.preview/`.
- **`0` (In-Place)**: Workspace root execution for singleton hardware or fixed ports.
