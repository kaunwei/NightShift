# Agent contract preservation review

Baseline: `eb5d972`. Scope: Planner, Worker, Explore and Sentinel contracts.
All four edited documents are ASCII. Edits are local; original steps, branches
and guards remain unless an intentional policy correction is listed below.

## Old-line accounting

Each old nonempty line is either retained verbatim or listed as a reviewed
replacement. Unexplained removals: zero.

| Document | Old nonempty lines | Reviewed replacements |
| --- | ---: | ---: |
| `.agents/skills/nightshift/explore/SKILL.md` | 30 | 3 |
| `.agents/skills/nightshift/planner/SKILL.md` | 75 | 5 |
| `.agents/skills/nightshift/sentinel/SKILL.md` | 22 | 0 |
| `.skills/universal-build-verify.md` | 41 | 2 |

## Behavior comparison

| Old behavior | New behavior / evidence |
| --- | --- |
| Role ownership, English tickets, ASCII skills, Terminal A read boundary | Retained |
| Environment activation, project-info, code-index navigation, glossary/ADRs | Retained |
| Score-to-level mapping, FIFO blockers, queue insertion, green phases, 10-task review | Retained; score-read remains the Planner input |
| Sentinel delegation, same-process inactivity relay, observer faults, no heartbeat wakeups | Retained; before-claim environment/hook blocks now relay too |
| Failure report, explicit restart, separate PAUSE/event gates, clean next Worker | Retained; report path corrected to lifecycle/reports |
| Retained failure evidence | Explicitly diagnostic; resume CLI remains unavailable |
| Trial staging, launch verification, manifest, atomic delivery, dependency classification, secret exclusion | Retained |
| TARGET/scope stop, forbidden shortcuts, diagnostic/research product boundaries | Retained |
| FIX blanket test-edit ban | Intentional correction: scoped regression tests allowed; strength/count and scope guards remain |
| Refactor assertions, deletion limits, compiler/lint, EXEC accounting, three attempts | Retained |
| VERIFY/actual evidence, DEAD_END proof, no manual commit/progress/score writes, restricted Ghost | Retained |
| JSON outcomes, TDD ID/source, permanent discovery, required CASES, confidence/no_change/failure rules | Retained |
| Research cache/freshness, sibling scope, compiler probe restoration, pointers, 5 KB summary, micro artifact, seam handoff | Retained; report root also permits the already-supported selected runner |
| Stale agents.json budget reference | Corrected to config plus RESEARCH_STEP_BUDGET/runtime fallback; default/independent research budget retained |
| Broken Explore wait-and-accept pointer | Corrected to Planner supervise; wait/relay/fresh DONE+audit requirements retained |
| Research completion lacked an explicit bounded stopping policy | Valid bounded inconclusive findings may complete; invalid/missing evidence stays blocked and defects stay unresolved |
| Research blanket no-penalty wording | Corrected to runtime score ownership; actual arithmetic unchanged |
| Requested extra Planner capacity/attribution review | Withdrawn by owner; existing optional diagnostic CLI retained |
| Sentinel routing targets/authentication/single watcher/mock-only AgY limit | Retained |

## Executable checks

FIX gate tests cover scoped regression changes, undeclared tests and assertion
loss; task-header/body routing, research/diagnostic restrictions and TDD evidence
remain covered. Watcher tests cover late startup with unclaimed queued tasks;
public daemon tests preserve new blocked states across RUN_ONCE shutdown.
Existing score, research budget, audit, hook and acceptance tests remain active.

AST comparison confirms unchanged scoring implementations: `_record_score_result`, `record_score_result`, `record_agent_score_result`, `score_task_level`, `score_summary`, `score_once`.
No attribution algorithm or verification-resume feature is introduced.

Validation: 121 targeted contract/regression tests passed in 102.604 seconds.
Baseline comparison found 158 retained old nonempty lines and 10 reviewed
replacements, with zero unexplained removals. All four documents are ASCII.
