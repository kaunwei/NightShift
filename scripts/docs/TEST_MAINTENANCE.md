# Test maintenance and retirement

Complete inventory is independent of Hot/Cold execution. Enable it explicitly per project; projects without `acceptance.inventory` keep their existing acceptance protocol. The new disappearance gate does not protect an unconfigured project.

## Complete inventory

Create an inventory configuration with `command` as an argv list, and optional positive `timeout` seconds. For unittest, use the absolute installed `unittest_hot.py` path with `--start test`. For SlugBox, use the absolute installed `slugbox_inventory.py` path followed by `--adapter` and the approved candidate's `scripts/automation/regression.py`. The bridge uses the project's existing public `discover()`; no live project adapter edit is needed.

```json
{"command":["python3","/path/to/NightShift/scripts/unittest_hot.py","--start","test"],"timeout":120}
```

```sh
python3 scripts/case_inventory.py --root /path/to/project --config /path/to/inventory.json list
python3 scripts/case_inventory.py --root /path/to/project --config /path/to/inventory.json diff --base BASE_COMMIT
```

Add the same object as `acceptance.inventory` in the selected runner configuration to enforce disappearance checks. Use a provider path outside the disposable revision tree. The approved candidate provider discovers both revisions, including versions that predate this protocol. Keep custom provider dependencies beside its script; the provider digest binds those Python files. Custom providers must discover the requested working directory and attest `inventory_complete: true` with the supplied run nonce. They must fail on unsupported structures or incomplete exploration. A successful inventory is not execution evidence.

The baseline is an exact archive of a resolved commit; no source worktree is reset. Isolated Git metadata disables archive export exclusions/substitution and indexes tracked files even when ignore rules match them. Candidate and provider digests detect discovery-time changes. Ignored untracked fixtures are outside the manifest: deliver fixture manifests in Git and retain resource checksum checks. Submodules are unsupported. Fingerprints measure test bodies, not helper semantics; the content digest binds the wider tree. Hot/Cold never determines case existence.

## Authorize a maintenance task

Use `[CODE: REFACTOR]`, `[CODE: MIGRATE]` or `[CODE: CONTRACT]` with `EVIDENCE: MAINTENANCE`, `MAINTENANCE: CHG-ONE` and `DECISIONS: DEC-ONE`. Multiple IDs are comma-separated. The trusted ticket authorizes the exact change IDs and decision references. Put test, relation and change-record locations in TARGET. Worker text cannot grant approval. Normal CHANGED tasks still need changed tests; EXISTING still means unchanged pinned cases on an explicit refactor.

Deliver each new change as `.nightshift/changes/CHG-ONE.json` (or configure `inventory.records`). Records must be delivered in Git, remain immutable after baseline acceptance, and cannot disappear. A changed decision needs a new change ID. Only new records named by the ticket can participate in acceptance.

```json
{
  "version":1,
  "id":"CHG-ONE",
  "action":"rename",
  "old_cases":["test_sample.Sample.test_old"],
  "new_cases":["test_sample.Sample.test_new"],
  "reason":"Accepted naming migration preserves the value scenario",
  "decision_ref":"DEC-ONE",
  "scenarios":[{
    "name":"value is one",
    "before":["test_sample.Sample.test_old"],
    "after":["test_sample.Sample.test_new"]
  }]
}
```

Actions:

- `rename`: one disappearing ID to one distinct current ID, including a file move.
- `merge`: multiple original cases to one or more replacements. A retained survivor may keep its ID.
- `migrate` / `correct`: preserve IDs and declare the observation or expectation change. Helper changes need not alter the body fingerprint.
- `retire`: no replacements; name `removed_requirement`, set every scenario's `removed` to true and `after` to an empty list. Supply nonempty `verification_cases` for remaining relevant cases, or `no_remaining_reason` plus a ticket VERIFY command. Acceptance still requires a nonempty passing Hot execution; removing the entire final suite is deliberately unsupported.
- `reintroduce`: empty `old_cases`, one newly discovered `new_cases` ID, and `predecessor_change` naming the unique unconsumed removal in immutable baseline history. Exactly one new lineage event may restore that ID. Ambiguous histories are rejected rather than ordered by filename or date. Scenario `before` is empty. With traceability enabled, the new generation equals the change ID and `previous_change` names that predecessor.

Every disappearing case, including legacy cases, must be accounted for exactly once. Every declared case must participate in a named scenario. All actions may declare `verification_cases`; each must exist and execute alongside replacements, including cases normally in Cold. Missing, skipped, failed or mismatched evidence blocks acceptance. Empty `tdd_cases` on MAINTENANCE does not bypass these executions.

Scenario mappings are reviewable declarations. Mechanical checks cannot prove that two assertions protect equivalent behavior. Review independent expected values and relevant inputs; use a controlled defect when an observation point changes materially. Test count is not a substitute for that review. Existing deletion-size and TARGET limits continue to apply.

## Gradual requirement relations

Requirements and coverage live in Git at `.nightshift/requirements.json` and `.nightshift/coverage.json`, both document version 1. Ignored untracked documents are rejected; local-only relations cannot authorize acceptance. See `examples/slugbox-test-maintenance` for a real import. Omit both files to remain legacy; enabled relations cannot silently disappear. New/modified test bodies and mapped surviving cases require relations; untouched legacy cases need no backfill.

A requirement has `id`, positive `version`, `status` (`active` or `retired`), `behavior`, and `decision_ref`. Published versions are immutable. A successor names `supersedes` and nonempty `affected_scenarios`; `*` means every scenario. Only affected relations become stale, so unrelated requirement edits do not force mass metadata updates. New requirement versions must cite a decision authorized in the ticket. Retiring a mapped requirement requires a matching retired successor and decision reference.

A coverage case has canonical `id`, stable `generation`, and nonempty `verifies` relations with `requirement` (`ID@VERSION`) and `scenario`. Many-to-many relations are supported. Rename/move preserves generation; removal followed by same-name creation gets explicit predecessor lineage and a new generation. Source fingerprints are not historical identities.

```sh
python3 scripts/case_traceability.py --root /path/to/project check
python3 scripts/case_traceability.py --root /path/to/project requirement background.viewport_coverage@1
python3 scripts/case_traceability.py --root /path/to/project case CANONICAL_CASE_ID
python3 scripts/case_traceability.py --root /path/to/project impact background.viewport_coverage
python3 scripts/case_traceability.py --root /path/to/project lineage CANONICAL_CASE_ID
```

`check` validates document relations; acceptance also checks complete inventory. For custom `inventory.records`, use the same directory with the query command's global `--records`. Queries rebuild from the investigated branch's versioned files, without a database or authoritative cache. Retrospective `.nightshift/history.json` entries are query-only imports, never runtime acceptance receipts.

## Failure and acceptance evidence

Failure reports carry a runtime `disposition`: command/phase evidence, base revision, mechanical observation, unresolved semantic conclusion and next diagnostic step. `ticket_regression` indicates a new failure or a baseline/candidate difference; it does not by itself prove that the product violates the currently accepted requirement. Timeout, missing evidence and unsupported isolation remain inconclusive. TDD's expected red remains distinct from final verification failure.

Planner resolves whether to repair product code, migrate an observation, correct an expectation, merge coverage or retire a requirement, using the accepted decisions and execution evidence. When isolated case selection is unsupported, compare supported complete source groups under the same conditions; do not pretend isolation succeeded. Worker should return exact commands, reports, the proposed disposition and any missing decision or scope.

After verification and commit, the existing task journal receives `result.maintenance_receipt`: stable receipt ID, change IDs, base and commit, candidate/provider digests, relation snapshots and execution reports. No second authority store is added. A committed replay creates the same receipt and does not recommit. Failed or interrupted verification cannot produce an accepted receipt. An accepted commit must still belong to the current history before replay is accepted.

## Rollout and rollback

Ship the new runtime files through the deployment manifest. First run inventory/diff read-only, then review the actual baseline/candidate scope. Enable inventory in a selected idle runner, and import only reviewed relations. Preserve unrelated edits and use the normal Planner lifecycle for queue changes. This feature does not change Hot/Cold cadence or add automatic quarantine.

Revert product, tests and versioned relations together with ordinary Git. Receipts remain historical runtime evidence; they do not override the current Git tree. Failed attempts use existing recovery archives and journals. Diagnose incomplete receipts/revisions before retrying; use a new authorized change ID for a different maintenance decision. Disable neither checks nor legacy test execution to conceal a failure.
