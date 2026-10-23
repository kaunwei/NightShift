# Universal Build, Test & Verification SOP (Worker)

Execution protocol for Background Worker (Terminal B) processing `tasks.txt`.

## 1. Hard Guardrails & Constraints

- **Host Safety**: Never run `sudo`, `apt`, `yum`, or host package managers.
- **Clean Tree**: `git status --porcelain` must be 100% clean after commit; zero untracked tests or build artifacts.
- **Compiler Cleanliness**: 0 warnings (`-Wall -Wextra`) and clean linter run.
- **Target Whitelist**: Touch declared `TARGET:` paths only (cohesive multi-file slices allowed when declared). On downstream compiler errors outside `TARGET:`, do NOT touch unlisted files; halt and emit `STATUS: SCOPE_BLOCKED (Need Target: <File>#L<Line>)` (zero penalty).
- **Test Immutability & Assertion Non-Decrease**:
  - `[CODE: FIX]`: Product files only; `Tests/` strictly read-only.
  - `[CODE: REFACTOR]`: `Tests/` editable if in `TARGET:`. Added assertions must be `>=` deleted assertions (`XCTAssert`, `#expect`, `assert`, `expect(`, `self.assert`), with structural closure in `VERIFY:` (e.g. `<cmd> && ! grep -rn "<Deprecated>" Sources/`).
- **Proof of Negative for `[DEAD_END]`**: Declaring `[DEAD_END]` or excluding a suspect module requires tangible proof (isolated passing unit test or runtime log proving module health while global symptom persists). Speculative exclusion = task failure.
- **Forbidden Shortcuts**: Honor `FORBIDDEN_SHORTCUTS:`. No thread sleeps (`asyncAfter`, `sleep`), no error swallowing (`try?`, empty catch), no optional-widening to dodge initializers, no dummy returns.
- **Blast Radius Limits**: Max deletions by Level: L3 `<= 40` lines, L2 `<= 150` lines, L1 `TARGET:`-bounded.

## 2. Archetypes & Skill Pointers

- **`[CODE: FIX]` / `[CODE: REFACTOR]`**: Follow [`implement`](../.agents/skills/engineering/implement/SKILL.md) (skip `/code-review` per task), [`tdd`](../.agents/skills/engineering/tdd/SKILL.md) (Red $\rightarrow$ Green $\rightarrow$ Refactor at pre-agreed seams), and [`codebase-design`](../.agents/skills/engineering/codebase-design/SKILL.md) (narrow public interfaces; never test ephemeral private helpers).
- **`[CODE: EXPAND/MIGRATE/CONTRACT]`**: Phased migration per [`to-tickets`](../.agents/skills/engineering/to-tickets/SKILL.md); every intermediate commit must stay 100% green.
- **`[RESEARCH]` / `[BENCHMARK]`**: Follow [`research`](../.agents/skills/engineering/research/SKILL.md) and [`explore`](../.agents/skills/nightshift/explore/SKILL.md) Tier 2 (`scripts/extract_skeleton.sh <path>#L<line>`, compiler probe + immediate `git restore .`, `SUMMARY.md <= 5 KB` + `03-micro.md`, `VERIFY: REPORT_ONLY`).
- **`[DIAGNOSTIC]`**: Follow [`diagnosing-bugs`](../.agents/skills/engineering/diagnosing-bugs/SKILL.md) to build a tight pass/fail loop that goes red strictly on the bug. Repro test must compile cleanly (0 syntax errors) and fail strictly on assertion. Production code (`Sources/`, `src/`) is locked; touch only tests and `.reports/`.

## 3. Honest Treaty & Retries

- **Zero-Guessing**: State verified facts only; label interpretations as `Hypothesis`.
- **Max 3 Retries**:
  1. Analyze $\rightarrow$ Fix $\rightarrow$ Test.
  2. On failure, `git restore <file>` to reset baseline $\rightarrow$ Apply alternative fix.
  3. Final attempt: if failed, restore clean tree, report `[BLOCKED]` in the final response, and exit. `worker.sh` owns `progress.log` updates outside the agent sandbox.

## 4. Acceptance, Logging & Notes

### 4.1 Attempt Trace (`progress.log`)
- **Ownership**: The agent reports its attempt count and confidence in its final response; `worker.sh` prepends the trace to `progress.log` outside the agent sandbox.
- **Strict Limit**: Keep the reported trace concise. Use pointers (`src/file.py#L10-L20`), zero discursive prose.
- **Confidence**: `HIGH` (1st pass, 0 warnings), `MEDIUM` (1-2 retries needed), `LOW` (brittle or edge cases unverified).
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

### 4.2 Repository Quirks (`.worker.notes.md`)
- Check `.worker.notes.md` before every task. Append 1-2 line tips when discovering non-obvious build/linker quirks (`< 30 lines` total). Record compiler/toolchain flags only—never architectural lore or task history.

### 4.3 Mechanical Audit & Commits
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
