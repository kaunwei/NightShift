# Worker execution contract

This is the shared execution reference for every queued task. The runtime is authoritative for timeouts, action limits, target/audit checks, progress records, and closeout enforcement; this file tells the Worker how to work within those limits.

## Before and during work

- For indexed navigation, run `python3 nightshift/worker_runtime.py code-index ensure`, then
  read `nightshift/.scratch/code-index/INDEX.md` only after script approval. Use compact queries
  for details; `index.json` is script-owned cache. Dirty-input recovery follows Explore's code index.
- Read `nightshift/.worker.notes.md` and the applicable skill: [`tdd`](../.agents/skills/engineering/tdd/SKILL.md) for `[CODE]`; [`diagnosing-bugs`](../.agents/skills/engineering/diagnosing-bugs/SKILL.md) for `[DIAGNOSTIC]`; [`research`](../.agents/skills/engineering/research/SKILL.md) and [`explore`](../.agents/skills/nightshift/explore/SKILL.md) for `[RESEARCH]`. The ticket is the pre-agreed seam: proceed autonomously unless an ambiguity changes scope or expected behavior. The Planner owns acceptance and independent review.
- Work only in declared `TARGET:` paths. If a necessary change is outside scope, stop and report `[SCOPE_BLOCKED] (Need Target: path#Lline)`; do not expand scope yourself.
- `[CODE: FIX]` cannot change tests. `[CODE: REFACTOR]` can change tests only when declared, and may not reduce the total assertion count. `[DIAGNOSTIC]` may add a compile-clean repro that fails on the bug, but cannot modify product code. `[RESEARCH]` is read-only for product code and produces the requested report under a dedicated expanded action budget.
- Respect `FORBIDDEN_SHORTCUTS:` and `CONSTRAINTS:`. Do not weaken assertions, hide errors, add dummy behavior, or use thread sleeps to mask a race. Never use `sudo` or host package managers.
- Stay within the assigned level's deletion limit: L3 40 lines, L2 150 lines, L1 bounded by `TARGET:`. If compiler fallout points outside scope, stop rather than patching unrelated files.
- Require zero compiler warnings (`-Wall -Wextra` where supported) and a clean linter. Make each action independently reviewable. Emit `[EXEC] <brief action>` immediately before each tool call when the runtime uses that marker for action accounting. Never combine actions or fabricate markers to evade accounting.
- For `[CODE: EXPAND]`, `[CODE: MIGRATE]`, and `[CODE: CONTRACT]`, follow [`to-tickets`](../.agents/skills/engineering/to-tickets/SKILL.md): use green-to-green phases and keep each intermediate phase passing. `[BENCHMARK]` follows the repository research procedure and reports measured results, not guesses.
- Avoid forbidden shortcuts: no sleeps to hide races, swallowed errors (`try?` or empty catches), widened optionals to bypass initialization, dummy returns, weakened assertions, or speculative behavior.

## Verify and close out

- Run the ticket's `VERIFY:` command and relevant tests. Report only checks actually run; distinguish verified facts from hypotheses. `[DEAD_END]` requires an isolated passing test or runtime evidence that the suspected module is healthy while the symptom remains.
- Make at most three implementation attempts, restoring only the task's original changes before an alternative fix. After the third failure, report `[BLOCKED]`; the runtime preserves failed work and restores the task baseline. Never reset unrelated work. The runtime owns progress and mechanical audits.
- Do not stage or commit. Return a structured result with the proposed `commit_message`; the host runtime verifies, audits, and commits the declared changes. Do not edit the runtime-owned progress log. The runtime rejects non-runtime uncommitted or untracked files after the task.
- Keep the JSON result concise: outcome, source/report pointers, test counts/results, per-attempt error/fix evidence, `attempts` as an integer, and `confidence` as HIGH, MED, or LOW. HIGH means first-pass with zero warnings; MED means one or two retries; LOW means brittle or unverified edge cases. Commit titles use feat/fix/refactor/test/docs/perf, a concise English action (at most 60 characters), and the task ID; never the raw queue record. Include scope, verification, attempts, and confidence in JSON fields. Do not self-adjust the shared Worker score; the Planner records the result and evidence pointer.
- If implementation is finished but structured closeout requirements remain, return `closeout_required`. If verification fails, return `blocked` or `failure` with the reason; restricted closeout cannot repair failed tests. If verification cannot finish, return `blocked` with the reason. The runtime may invoke one restricted ghost closeout against the original task. It may verify and provide the missing message, but must not modify project files; if implementation remains, report `closeout_incomplete`.

## Research and report integrity

- Research/benchmark reports follow the artifact and probe requirements in `explore`: `SUMMARY.md` at most 5 KB, runtime `REPORT_META`, verified pointers and topology/strategy, plus `03-micro.md` skeletons.
- Do not claim a report is current after a referenced source path changes. Do not treat `.reports/.archive/` as active evidence.
- Check `nightshift/.worker.notes.md` before work. Append 1–2 lines for non-obvious build/linker quirks and toolchain flags; keep it under 30 lines, without architectural lore, secrets, or task history. Work directly in the project directory. Preserve unrelated and pre-existing changes; never clean or reset the checkout as a shortcut.
