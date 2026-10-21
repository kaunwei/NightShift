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
    *   *No Silent Compile-Fix Edits*: Never touch unlisted files (e.g. creating dummy `main.swift` or modifying configs) just to satisfy compilers. If an unlisted dependency is missing, STOP and emit `[NEED_DECOMPOSITION]`.
    *   `[DIAGNOSTIC] / [RESEARCH]` tasks have full authority to trace across all layers (UI -> OS).

## 2. Execution Archetypes
*   **[CODE] / [REFACTOR]**: Follow Red-Green-Refactor TDD. Implement -> Unit Test -> GUI Smoke Check (if applicable).
*   **[RESEARCH] / [BENCHMARK]**: Gather facts/metrics -> Format into Markdown/CSV -> Output to `.reports/<issue-slug>/` (or `docs/research/` if permanent).
*   **[DIAGNOSTIC]**: Isolate root cause with minimal failing tests or exact error traces. Output to `.reports/<issue-slug>/<phase>.md` and update `SUMMARY.md`. **Reject pure textual speculation.**

## 3. Honest Treaty (Anti-Hallucination)
*   **Zero-Guessing**: If legacy code/logs are obscure, state ONLY verified facts/paths. Label all interpretations as `Hypothesis`.
*   **Evidence Gate**: Never claim success without verifiable proof (test pass output, raw log snippets, or exact file line pointers).

## 4. Retry Limits & Clean Resets
*   **Max 3 Attempts**:
    1. Analyze error -> Apply fix -> Retest.
    2. If failed, `git restore <file>` to reset baseline -> Apply alternative fix.
    3. Final attempt.
*   **Immediate Stop**: If Attempt 3 fails, STOP immediately. Emit `[BLOCKED]` in `progress.log` and exit.
*   **Best-Effort Notes**: For minor non-blocking ambiguities, make a standard choice, commit, and append `Notes:` in `progress.log`.

## 5. Protocol & Evidence Logging (Token-Lean)

*   **Log Limits**: `progress.log` entries `<= 15 lines`. Report Executive Summaries in `.reports/<issue-slug>/` `<= 30 lines`. No verbose prose.
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
