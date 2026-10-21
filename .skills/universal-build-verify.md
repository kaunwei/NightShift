---
name: universal-build-verify
description: "Universal execution SOP for unattended background workers (TDD, diagnostics, auto-commit, retry limit)."
---

# Universal Build, Test & Verification SOP (Worker)

MANDATORY execution protocol for Background Worker (Terminal B) when processing `tasks.txt`.

## 1. Safety & Constraints (Zero-Tolerance)
*   **NO Host/Global Edits**: Never run `sudo`, `apt`, `yum`, or host package managers.
*   **Zero Warnings Gate**: Code must compile with 0 warnings (`-Wall -Wextra`) and pass linters cleanly.
*   **Clean Tree Gate**: `git status --porcelain` must be 100% clean after commit. Never leave untracked tests or build residue.
*   **Target Scope & Multi-Interface Exception**:
    *   `[CODE]` tasks modify declared `TARGET` paths ONLY.
    *   *Cohesive Seams*: Legitimate seams can cover multiple objects/interfaces (protocols, classes, tests) when declared in `TARGET:`.
    *   *Deliberate Refactors*: Large-scale multi-interface refactors must be declared in `TARGET` or marked `CONSTRAINTS: Multi-interface refactor approved`.
    *   *No Silent Compile-Fix Edits*: Never touch unlisted files (e.g. creating dummy `main.swift` or modifying configs) just to satisfy compilers. If an unlisted dependency is missing, STOP and emit `[SCOPE_BLOCKED]` or `[NEED_DECOMPOSITION]`.
    *   `[DIAGNOSTIC] / [RESEARCH]` tasks have full authority to trace across all layers (UI -> OS).
*   **Test Immutability & Refactor Gates**:
    *   `[CODE: FIX]`: Test files are strictly read-only. Worker can only touch product files declared in `TARGET:`.
    *   `[CODE: REFACTOR]`: `Tests/` and `Mocks/` can be declared in `TARGET:`. **Assertion Non-Decrease Gate**: Worker may update method call signatures, but total assertion count must NEVER decrease (`count(assert) >= old_count`).
*   **Forbidden Shortcuts (Symptom Masking Ban)**: Worker must strictly follow `FORBIDDEN_SHORTCUTS:`. Never use thread sleeps (`asyncAfter`, `sleep`) to mask race conditions, never swallow errors with `try?` or empty catch blocks, never alter non-optional properties to optional just to dodge initializers, and never hardcode dummy return values.
*   **Blast Radius Gate**: Line deletions limited dynamically by Level: Level 3 (Micro) <= 40 lines, Level 2 (Standard) <= 150 lines, Level 1 (Macro) unlimited (TARGET-bounded).

## 2. Execution Archetypes
*   **[CODE: FIX] / [CODE: REFACTOR]**: Follow Red-Green-Refactor TDD. Refactors must satisfy Assertion Non-Decrease and structural verification in `VERIFY:` (e.g. `<test_cmd> && ! grep -rn "<Deprecated_Symbol>" Sources/`).
*   **[CODE: EXPAND] / [CODE: MIGRATE] / [CODE: CONTRACT]**: Phased refactoring progression. Each step must leave build and tests 100% PASS.
*   **[RESEARCH] / [BENCHMARK]**: Gather facts/metrics -> Format into Markdown/CSV -> Output to `.reports/<issue-slug>/` (or `docs/research/` if permanent).
    *   *Compiler Probe & Signature Skeletons*: In addition to `grep`, Worker may temporarily modify interface signatures and execute `build` to capture 100% of affected call-sites from compiler diagnostics. Worker MUST immediately run `git restore .`. `SUMMARY.md` MUST append Interface Skeletons and 10-line context slices (`scripts/extract_skeleton.sh <files>`).
*   **[DIAGNOSTIC]**: Isolate root cause with minimal failing tests or exact error traces. Output to `.reports/<issue-slug>/<phase>.md` and update `SUMMARY.md`. **Reject pure textual speculation.**
    *   *Valid Red-Light Rule*: Repro tests MUST compile cleanly (`Build PASS` / 0 syntax errors) and fail strictly on assertion (`Test FAIL`). Compilation failures or missing symbols are Invalid Repros.
    *   *Production Code Lock*: Strictly forbidden from modifying production code (`Sources/`, `src/`, etc.) during diagnostics. Only tests and `.reports/` may be touched.
    *   *Signature Skeleton*: `SUMMARY.md` must include pure declaration skeletons and 10-line slices of suspect files.

## 3. Honest Treaty (Anti-Hallucination)
*   **Zero-Guessing**: If legacy code/logs are obscure, state ONLY verified facts/paths. Label all interpretations as `Hypothesis`.
*   **Evidence Gate**: Never claim success without verifiable proof (test pass output, raw log snippets, or exact file line pointers).
*   **Proof of Negative for [DEAD_END]**: Declaring `[DEAD_END]` requires empirical proof of negative (isolated unit test passing or runtime log snippet proving the suspect module functions correctly while symptom persists). Unsubstantiated exclusions are treated as task failure.

## 4. Retry Limits & Clean Resets
*   **Max 3 Attempts**:
    1. Analyze error -> Apply fix -> Retest.
    2. If failed, `git restore <file>` to reset baseline -> Apply alternative fix.
    3. Final attempt.
*   **Immediate Stop**: If Attempt 3 fails, STOP immediately. Emit `[BLOCKED]` in `progress.log` and exit.
*   **Scope Blocked Escape Hatch**: If compiler errors point to downstream files outside declared `TARGET:`, DO NOT touch them! Stop immediately and emit `STATUS: SCOPE_BLOCKED (Need Target: <File>#L<Line>)`. This is a no-fault compliance exit without credit loss.
*   **Best-Effort Notes**: For minor non-blocking ambiguities, make a standard choice, commit, and append `Notes:` in `progress.log`.

## 5. Protocol & Evidence Logging (Token-Lean)

*   **Log Limits**: `progress.log` entries `<= 15 lines`. Report Executive Summaries in `.reports/<issue-slug>/` `<= 30 lines`. No verbose prose.
*   **Double-Funnel Mechanical Audit**: `worker.sh` mechanically re-runs verification, checks Anti-Idle (`Tests_Run >= 1`), runs regression checks, and stamps `[MECHANICAL_AUDIT] Status: PASS | Verify_Exit: 0 | Tests_Run: >=1 | Whitelist: PASS | Tree: CLEAN | Diff: <stat> | Attempts: <N>` directly at line 1 of `progress.log`. Planner Fast-Track requires this stamp.
*   **Auto-Commit Standard (English ONLY)**:
    ```bash
    git commit -m "<type>(<scope>): <concise action <= 60 chars> (<task_id>)" -m "<1-3 summary bullets>
    
    Task: <task_id> (<granularity>)
    Scope: <target_files>
    Verification: <test command> (<result>)
    Attempts: <count> | Confidence: <score>"
    ```
    *(Allowed types: `feat`, `fix`, `refactor`, `test`, `perf`, `docs`. NO raw task schemas in title).*

*   **progress.log Appended Format (<= 15 lines)**:
    ```text
    ================================================================================
    [SUCCESS | BLOCKED] TASK-XXX: <Title>
    Time: <Timestamp> | Duration: <Xs> | Attempts: <N>/3 | Confidence: <HIGH|MED|LOW>
    Changes: <Files / Report path>
    Verification: Build <PASS|FAIL>, Tests <PASS|FAIL>
    Attempt Trace:
      • Att 1: <Summary>
      • Att 2/3: <Fix applied or rollback>
    Notes: <Optional best-effort choices or granularity feedback>
    ================================================================================
    ```

## 6. Workspace Modes (`WORKER_ISOLATION`)
*   **`1` (Default)**: Executes in `.worker-tree` (`feature/worker-frontier`). Verified milestones auto-staged to `.preview/` for human review.
*   **`0` (In-Place)**: Executes in project root (for singleton hardware / fixed-port projects).
