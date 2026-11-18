# Plan complete L1 feature slices

L1 delivers one observable workflow across cooperating modules and behaviors.
Runtime checks executable evidence and mechanical constraints, not requirement
completeness, visual quality or design correctness.

## Before dispatch

1. Define trigger, cooperating behaviors and combined result. Keep mature work
   together within budget; resolve unknown verification methods through bounded
   research before promising their results.
2. Map necessary outcomes to discovered canonical CASES or executable VERIFY.
   Mark uncovered claims unverified. Local tests, prose and clean diffs cannot
   replace integration checks; completed research is not product acceptance.
3. Use existing contracts: behavior changes need changed permanent tests and hot;
   REFACTOR/EXISTING pins unchanged baseline cases; VERIFY requires an executable
   command and no product edits. TRIAL alone adds no artifact acceptance contract.
4. Bound TARGET with directories and exact shared files covering source, tests,
   wiring and known generated siblings, including UID files. Directories authorize
   new descendants; the ordinary scope guard rejects unrelated paths.
5. Estimate changed files separately with FILES. Planned effort uses
   max(1, distinct TARGET entries, FILES), not directory contents. FILES grants no
   paths, caps no changed-file count and extends no wall-clock deadline.
6. Check capability, actions, Worker timeout and the shared hot discovery/run/VERIFY
   deadline separately. Estimate from receipts/logs, not test count alone. Worker
   runs focused checks; runtime owns the final gate. Repeat full suites only for
   an explicit ticket requirement or concrete diagnosis.

Planning is complete when these choices and remaining delivery obligations are
explicit. Split only at independently acceptable behavior boundaries, tracking
remaining obligations. Required checks for a claimed result stay required.

## Worked synthetic example

A request normalizes input, updates state and returns the result through separate
input/state/workflow modules in `src`, permanent `tests` and a generated source
UID. `TARGET: src,tests | FILES: 5` authorizes those directories with five expected
changed files. A sixth file inside is allowed; an outside file needs authorization.

The fixture's `test_workflow.Workflow.test_combined` checks `" 5 "` produces `10`
through the public workflow, alongside local normalization/state tests. A separate
VERIFY exercises combined behavior beyond local tests. Discover real project IDs;
this synthetic ID is not a product ticket ID.

## Recover from evidence

Read runtime_error, score_attribution, commands and retained outputs before
choosing the next task. Runtime attribution and scoring remain authoritative.

| Evidence | Planner action |
| --- | --- |
| Required file outside TARGET or scope_blocked | Establish why it is needed; revise bounded authorization and FILES if justified, using a new task ID for changed scope. Otherwise correct the implementation direction. |
| Proven ticket regression | Assign the concrete behavioral repair, retaining the gate. A smaller feature is not automatically needed. |
| Baseline or environment failure | Diagnose or repair the prerequisite using existing reports and recovery controls. |
| Evidence-contract failure | Correct ticket mode, canonical identities, wiring or result format. Do not manufacture test changes to disguise verification-only work. |
| Action/time exhaustion | Inspect actual work and phase costs. Adjust an authorized estimate or budget, choose a qualified Worker, or split at independently acceptable behavior boundaries when capacity evidence supports it. |
| Early stop or unknown cause | Request bounded diagnosis or clearer closeout evidence; neither near-completion nor excessive scope has been established. |

A required UID outside an exact-file TARGET calls for justified scope correction,
not three module tickets. An integration assertion failing while local tests pass
calls for workflow repair. An import failure without a usable log needs diagnosis.

Inspect archived attempts as evidence. Continue the existing clean-start and
explicit restart process; retained work is not authorization to restore rejected
changes. Keep valid checks intact. No automatic resume or cached passes are added.
