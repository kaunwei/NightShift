# Worker execution contract

Runtime owns Git writes, hot acceptance, scores and task state. Work on the current branch.

## Before and during work

- For indexed navigation, run `python3 "$NIGHTSHIFT_CORE/nightshift/worker_runtime.py" code-index ensure`, then
  read `$NIGHTSHIFT_STATE_DIR/code-index/INDEX.md` only after script approval. Use compact queries
  for details; `index.json` is script-owned cache. Dirty-input recovery follows Explore's code index.
- Read `$NIGHTSHIFT_STATE_DIR/.worker.notes.md` and the ticket. Stay within TARGET.
  Applicable skills under `.agents/skills/`: [`tdd`](../.agents/skills/engineering/tdd/SKILL.md) for `[CODE]`; [`diagnosing-bugs`](../.agents/skills/engineering/diagnosing-bugs/SKILL.md) for `[DIAGNOSTIC]`; [`research`](../.agents/skills/engineering/research/SKILL.md) and [`explore`](../.agents/skills/nightshift/explore/SKILL.md) for `[RESEARCH]`. The ticket is the pre-agreed seam: proceed autonomously unless an ambiguity changes scope or expected behavior. The Planner owns acceptance and independent review.
- [CODE]: use .agents/skills/engineering/tdd/SKILL.md. Add or update real tests;
  keep them in permanent hot discovery after this task ends. Include test and hot
  wiring paths in TARGET. Run red/green checks during implementation.
- [RESEARCH]: use engineering/research and nightshift/explore skills; write the
  requested report, keeping product files unchanged. [DIAGNOSTIC]: diagnose and
  add tests within scope; project hot defines passing behavior.
- Work only in declared `TARGET:` paths. If a necessary change is outside scope, stop and report `[SCOPE_BLOCKED] (Need Target: path#Lline)`; do not expand scope yourself.
- `[CODE: FIX]` cannot change tests. `[CODE: REFACTOR]` can change tests only when declared, and may not reduce the total assertion count. `[DIAGNOSTIC]` may add a compile-clean repro that fails on the bug, but cannot modify product code. `[RESEARCH]` is read-only for product code and produces the requested report under a dedicated expanded action budget.
- Respect `FORBIDDEN_SHORTCUTS:` and `CONSTRAINTS:`. Do not weaken assertions, hide errors, add dummy behavior, or use thread sleeps to mask a race. Never use `sudo` or host package managers.
- Stay within the assigned level's deletion limit: L3 40 lines, L2 150 lines, L1 bounded by `TARGET:`. If compiler fallout points outside scope, stop rather than patching unrelated files.
- Require zero compiler warnings (`-Wall -Wextra` where supported) and a clean linter. Make each action independently reviewable. Emit `[EXEC] <brief action>` immediately before each tool call when the runtime uses that marker for action accounting. Never combine actions or fabricate markers to evade accounting.
- For `[CODE: EXPAND]`, `[CODE: MIGRATE]`, and `[CODE: CONTRACT]`, follow [`to-tickets`](../.agents/skills/engineering/to-tickets/SKILL.md): use green-to-green phases and keep each intermediate phase passing. `[BENCHMARK]` follows the repository research procedure and reports measured results, not guesses.
- Preserve unrelated and pre-existing changes; never clean or reset the checkout as a shortcut.

## Verify and close out

- Run the ticket's `VERIFY:` command and relevant tests. Report only checks actually run; distinguish verified facts from hypotheses. `[DEAD_END]` requires an isolated passing test or runtime evidence that the suspected module is healthy while the symptom remains.
- Make at most three implementation attempts, restoring only the task's original changes before an alternative fix. After the third failure, report `[BLOCKED]`; the runtime preserves failed work and restores the task baseline. Never reset unrelated work. The runtime owns progress and mechanical audits.
- Do not stage or commit. Return a structured result with the proposed `commit_message`; the host runtime verifies, audits, and commits the declared changes. Do not edit the runtime-owned `progress.log`. The runtime rejects non-runtime uncommitted or untracked files after the task.
- Leave stage/commit and scoring to runtime. Ghost can supply missing metadata or hot wiring for existing tests; product/test repairs need a new Planner task.
- Do not self-adjust the shared Worker score; the Planner records the result and evidence pointer.

## Handoff

Return exactly one JSON object with no text before or after it: outcome, commit_message and tdd_cases for development:

    {"outcome":"complete","commit_message":"fix: handle empty input",
     "tdd_cases":[{"id":"test_input.InputTests.test_empty","source":"test/test_input.py"}]}

- Each declared case must have changed test content and be discovered by permanent
  hot without ticket selectors. Runtime checks actual case execution, not prose.
- task CASES lists required stable IDs; VERIFY adds a required command to hot.
- outcome: complete, closeout_required, blocked, scope_blocked, guidance, failure,
  or no_change. `attempts`=integer; `confidence`=HIGH|MED|LOW. no_change requires a reason and no product changes.
- If verification fails, return blocked or failure; closeout_required cannot repair failed tests.
- On failure, report exact command, output and scope. Planner reschedules issues
  and explicitly restarts. Keep progress and queue records runtime-owned.

Migration/configuration: read `$NIGHTSHIFT_CORE/nightshift/acceptance.md` when setting up hot/cold,
adding a framework adapter, or diagnosing missing case evidence.
