# L1 feature slices: implementation and validation

Date: 2026-11-18 (Asia/Taipei).

## Delivered

- Planner dispatch defines L1 as a complete trigger-to-result feature across
  cooperating modules. The inline planning rules cover bounded directory
  TARGET, exact shared/generated siblings, independent FILES estimates, actual
  canonical cases/VERIFY and separate action/wall-clock budgets.
- Worker instructions explain the same boundaries and combined checks. Runtime
  owns automatic acceptance and the final hot/VERIFY; focused Worker checks are
  distinct. Scope gaps require evidence and Planner authorization.
- Recovery guidance distinguishes scope, contract, product, environment, capacity
  and unknown failures. Existing score attribution and clean restart remain in
  charge; scoring prose now reflects current automatic feedback.

No acceptance, scope-audit, budget or capability algorithms were changed for
this work. Earlier uncommitted test-maintenance changes remain in the checkout;
they are separate from this delivery. No live Worker configuration, queue or
product source was changed.

## Automated evidence

The new synthetic fixture runs the real daemon CLI, generic adapter subprocess,
permanent unittest adapter, scope audit and Git commit against isolated temporary
repositories. Its public workflow normalizes a request, updates state and returns
the combined result across three source modules.

Eight scenarios passed:

1. Directory TARGET accepts three source edits, a new generated UID and new tests.
   Five changed files are accepted with FILES=4; the captured Worker prompt uses
   the four-file estimate for its action budget.
2. Module checks pass while the complete workflow returns the wrong result;
   the required integration test rejects the candidate and HEAD stays unchanged.
3. A skipped required integration test rejects acceptance.
4. FILES=100 does not authorize a new sibling directory outside TARGET, even
   after passing hot. The precommit scope audit rejects it.
5. Listing exact source files without their generated UID rejects that UID.
6. With only local tests in hot, real extra VERIFY detects the wrong combined
   result and blocks the commit.
7. The correct workflow passes local hot plus real combined VERIFY; FILES=8
   increases the prompt budget while authorization remains unchanged.
8. A missing explicitly required integration case blocks acceptance.

Affected regression command:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=test:scripts STEP_PER_FILE=5 \
python3 -m unittest test_l1_feature_slices test_ticket_granularity \
  test_worker_prompt_tdd_contract test_hot_protocol test_tdd_reconciliation \
  test_runtime_hardening
```

Result: **62 tests passed** in 36.302 seconds. Log:
`/tmp/nightshift-l1-verification.log` (also copied into the local ticket board).
The new fixture subsequently pins its own STEP_PER_FILE environment so its
budget assertions are independent of the caller's environment. A final run of
all eight new scenarios with caller STEP_PER_FILE=17 passed in 11.867 seconds;
the fixture still used its intended five-step estimate. Final log:
`/tmp/nightshift-l1-final.log` (also copied into the local ticket board).

## Instruction review and limits

Worked scope/UID, integration-regression and missing-import-log examples each
identify a recovery action without automatically decomposing the feature. The
Planner score description matches the current ticket-acceptance contract. The skill is now a single ASCII file; the separate L1 reference was folded into its dispatch and recovery rules.

These are instruction and consistency checks, not automated proof that a model
will always plan correctly. The synthetic fixture demonstrates existing gate
behavior; it does not reproduce a historical large product task, establish its
maximum feasible size, or prove visual/design/requirement completeness. No
automatic resume, cached passes, new TRIAL exemption or relaxed gate was added.

## Precommit review

Standards review found one omitted responsibility: Planner independent review.
It was restored while retaining runtime ownership of automatic acceptance. The
follow-up standards review and separate specification review have no remaining
findings. L1 guidance was shortened; the budget display now uses ASCII `*`.

An isolated export of the exact staged L1 snapshot, excluding earlier unstaged
test-maintenance work, passed all 62 affected tests in 35.498 seconds. The new
fixture also checks its captured Worker prompt is ASCII. Skill/contract/test
files passed ASCII checks; AST comparison with the base confirmed only
`build_task_prompt` changed among runtime functions/classes. All acceptance,
audit, capability and budget algorithms remain unchanged.

Review log: `/tmp/nightshift-l1-staged-review.log`, also copied to the local board.
