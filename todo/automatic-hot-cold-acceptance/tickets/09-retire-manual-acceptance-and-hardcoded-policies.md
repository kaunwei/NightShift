# 09: Make automatic hot/cold the normal lifecycle and retire obsolete acceptance paths

**What to build:** Existing NightShift entry points consistently use automatic hot/cold acceptance, so confidence tiers, repeated VERIFY and manual review state cannot accidentally reappear.

**Blocked by:** 08: Insert cold after N successful development commits and recover cadence on restart

**Status:** complete

## Acceptance criteria

- [x] Make the completed flow the normal supported runtime path and remove the temporary opt-in compatibility routing used by earlier slices.
- [x] Remove runtime/Planner success dependencies on confidence, retry tiers, manual accept/reject, successful report archival and fixed Tests_Run >=1 claims.
- [x] Remove generic assertion nondecrease, deletion-count restrictions, hard-coded framework-wide tests and human-output zero-test heuristics from runtime acceptance. Project hooks and case evidence own test policy.
- [x] Keep task TARGET scope checks, restricted staging and valid gate-before-commit behavior. No removal may allow out-of-scope source changes into a commit.
- [x] Migrate Worker and Ghost task-case instructions to the single hot contract, eliminating obsolete instruction paths that ask Ghost to implement repairs or commit independently.
- [x] Migrate watcher/sentinel and completion consumers so events terminate correctly with script-owned accepted/failure states; queue waiting does not require a nonexistent pending Planner audit.
- [x] Remove active separate-development-root/branch assumptions where they affect execution; retain historical inspection artifacts and do not prune/delete old worktrees.
- [x] Provide an explicit configuration/migration-required error for old projects lacking the new hot evidence contract. Do not silently map a legacy VERIFY command to a fully evidenced TDD pass.
- [x] Keep internal recovery/idempotence data even though routine successful human reports disappear. Update glossary semantics for the new flow without pretending historical Planner rollback is current automatic behavior.

## Verification

Run the normal launcher, not only direct task-cli, against a configured fixture. Observe handoff→hot→commit→score→next task and cold failure→Ghost→pause→Planner issue insertion/restart. Use legacy confidence/retry inputs to prove they cannot select a different acceptance path. Assert configured project tests run without hidden framework commands.

## Out of scope

Do not delete unrelated administrative APIs solely because they share words such as audit or review; remove only obsolete acceptance behavior/callers.

