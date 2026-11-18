# Test maintenance implementation and verification

Date: 2026-11-18 (Asia/Taipei). Implementation is on `codex/test-retirement` in the attached isolated NightShift worktree. The running SlugBox checkout, runner configuration and queue have not been changed. GitHub CLI is unavailable in this environment; approved tickets use the configured local Markdown fallback under `.scratch/test-retirement/issues/`.

## Delivered behavior

1. Complete inventories and baseline/candidate added, modified and disappeared ID queries, independent of Hot/Cold policy. Baselines resolve to exact commits; discovery input/provider digests and fresh complete evidence are checked. The SlugBox bridge calls its existing public discovery and requires no live adapter edit.
2. Trusted-ticket maintenance authorization, immutable versioned change records, scenario relations and checks for every disappeared case, including legacy cases. Replacement and remaining verification cases must actually execute with matching evidence. Hot membership cannot silently disappear from execution results.
3. A MAINTENANCE evidence path for rename, merge, observation migration, correction, pure retirement and explicit same-ID reintroduction. EXISTING's unchanged pinned-case semantics remain. Worker-authored acceptance fields are discarded.
4. Versioned requirements and many-to-many case/scenario relations, bidirectional and impact/lineage queries, applicable-version checks, active-scenario coverage checks and incremental legacy adoption. Git files are authoritative; no database is introduced.
5. Evidence-backed unresolved failure dispositions and accepted receipts in the existing lifecycle journal. Receipts bind change IDs, commit, inputs, provider and relations. Committed replay is idempotent; changed inputs before commit and incomplete execution cannot be accepted. Inventory timeouts use existing process supervision and retain timeout classification.
6. A retrospective resize relation import and real isolated engine validation at accepted SlugBox revision `b8706aa1e33e8c0a5ef3f5cd92b9e9668cc54219`. This records an observation migration while preserving the requirement and canonical case. It does not claim that the new runtime accepted the old commit.

The deployment manifest contains every new runtime module and the operation guide. Standalone test fixtures now deploy the production manifest instead of incomplete dependency lists. Prompt checks exclude the exact launcher-contract filesystem path when checking provider-invariant prose, while retaining the independent assertion that the contract source path is present.

## Verification results

| Check | Result |
| --- | --- |
| Final directly affected protocol, ticket and maintenance tests | **56 passed**, including **25 newly added cases** |
| Historical full NightShift suite | 437 ran: 431 passed, 3 failed, 3 skipped; details below; superseded by closeout checks |
| Complete SlugBox inventory at b8706aa | **407 canonical cases**; resize ID present |
| Normal SlugBox hot entry at b8706aa | **50/50 passed**; normal partition 50 hot / 357 cold |
| Full resize source group, unchanged control | **3/3 passed** |
| Shrunk and offset background | Resize case failed as intended |
| Disabled required rear pass | Resize case failed as intended |
| Missing rear geometry | Resize case failed as intended |
| SlugBox documentation patch | `git apply --check` passed against the live source; patch not applied there |
| Changed-module syntax and Git whitespace checks | Passed |

The final affected test command was:

```sh
PYTHONPATH=test:scripts PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  test_hot_protocol test_unittest_hot_cold_partition test_tdd_reconciliation \
  test_ticket_granularity test_case_inventory test_case_maintenance \
  test_case_traceability test_maintenance_lifecycle
```

The full suite used the existing parser environment and `python -m unittest discover -s test`, with a test-only Git author/committer identity supplied through environment variables. Subsequent small changes to inventory supervision and policy independence were verified in the final 56-test affected run, rather than presented as another full-suite run.

The engine checks used public `regression.run_source` and the normal `regression.py hot --max-core 4` entry. Godot was 4.7.2 and GUT reported 9.6.1. Every project copy was owned by a TemporaryDirectory and released before closeout; XML, logs, manifests and JSON remain outside those copies under `.scratch/test-retirement/pilot/`.

The first editor import failed on GUT's unrelated online update check with a TLS handshake error. That attempt was retained as an environment failure. For the successful runs, private user data was seeded from the shipped GUT versions manifest to suppress the GUI update fetch, and Godot validated reused imported resource caches against resource hashes. Product/test source and assertion behavior were unchanged. Fault injection changed only disposable product copies.

## Full-suite failures retained

| Existing case | Observation |
| --- | --- |
| `test_changed_registration_reconsiders_the_same_head` | Failed both the candidate full run and an isolated run on unmodified NightShift HEAD `7b9b8db`. |
| `test_exhausted_head_does_not_reclaim_and_changed_head_wakes` | Failed both the candidate full run and the unmodified baseline. Saved candidate evidence shows a 0.5-second task budget exceeded despite the fixture having written its result. |
| `test_task_cli_streams_output_selects_last_message_and_commits_only_target` | Full run returned timeout exit 124; independent candidate and baseline reruns both passed (about one second). Root cause remains unresolved; this is not claimed fixed. |

The original full-suite log is preserved. The two waiting tests were independently reproduced against the unchanged main checkout, which remained clean. The transient CLI failure was not removed or skipped. These failures supply no basis for retiring their behavior coverage. A separate follow-up records the diagnosis needed before changing execution budgets or supervision.

## Rollout and limits

The code and reviewable artifacts are complete; live activation remains pending an idle-runner rollout. See `scripts/docs/TEST_MAINTENANCE.md` for the schema, trusted-ticket fields, commands and rollback procedure. `examples/slugbox-test-maintenance/` includes the reviewed relation import, an inventory configuration example and a checked patch correcting SlugBox's stale hot-count/atomic-overflow documentation.

Inventory enforcement is opt-in through the selected runner's `acceptance.inventory`. Untouched projects retain their old protocol; the new disappearance gate does not protect them until configured. Review initial relation imports before enabling them. Do not switch a running Worker to partially delivered runtime files or mix another task's edits into this change.

Mechanical checks verify declared scenario preservation and execution evidence; they cannot prove semantic equivalence of assertions. Legacy behavior relations are added as cases are maintained. There is no new automatic quarantine. Retiring the last entire test suite is unsupported because final Hot evidence must remain nonempty. Submodules are unsupported by complete inventory.

Cold cadence is unchanged. No extra full Cold was run: this change modifies runtime validation and relations, and the real product probe used unchanged accepted product/test source. The relevant source group, deliberate defects, normal Hot entry and runtime regression tests cover the introduced behavior; the existing periodic Cold remains responsible for its ordinary scope.

## Review and final closeout

Standards and specification reviews found and resolved these authority gaps:

- Ignored local-only requirement/coverage documents can no longer authorize acceptance.
- Baseline archives disable export-ignore/export-subst using isolated Git metadata.
  Forced indexing preserves tracked-but-ignored inputs in discovery digests.
- Both revision collections must bind the same provider digest.
- Every action's declared verification_cases must execute, including cold cases.
- Reintroduction requires the unique unconsumed baseline removal and exactly one
  new lineage event; stale, ambiguous or duplicate consumption fails closed.
- MAINTENANCE requires hot and complete inventory before early returns or the
  legacy no-hot fallback. It cannot silently become an unchecked ordinary commit.

Each reproduced gap has a regression. The four new maintenance test modules now
contain 35 cases. Reviews have no remaining actionable findings. This remains
mechanical authorization and execution validation, not proof of semantic equivalence.

The first closeout full run exposed outdated L1 prompt assertions and a test
writing logs into read-only checkout metadata. Expectations now retain ASCII
budget formatting and Planner independent review; the timeout test uses its own
temporary state without changing its deadline or assertions. Historical waiting
and CLI-stream cases passed the new full runs without deadline changes.

Final verification:

- An isolated staged snapshot ran **455 tests: 452 passed, 3 skipped, no failures**
  in 287.761 seconds. Log: `/tmp/nightshift-retirement-staged-final.log`.
- The final no-hot guard and its added regression landed after that snapshot.
  All **44 directly affected tests passed** in 37.975 seconds, covering inventory,
  maintenance, traceability, lifecycle, baseline triage and Worker prompt contracts.
  Log: `/tmp/nightshift-retirement-final-gates.log`. No claim of a second full run
  including that final additional test is made.
- Runtime syntax, deployment manifest resolution, whitespace, sample relation
  queries and historical-import identity checks passed. Raw red/green and final
  logs are copied into the local ticket board's verification directory.
- The packaged SlugBox documentation patch was refreshed against `04d010e` and
  passed `git apply --check`. Its already-updated hot-count and retirement text
  are preserved; this task did not apply the patch to the live checkout.

All implementation work is ready for commit. Live activation remains a separate
rollout; no running Worker, queue or product source was changed by this task.
