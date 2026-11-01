# 10: Deliver runnable hot/cold migration and verify an installed project's full lifecycle

**What to build:** A project owner can install or upgrade NightShift, configure persistent hot/cold tests and case evidence, and follow one documented failure/recovery exercise without reading runtime internals.

**Blocked by:** 09: Make automatic hot/cold the normal lifecycle and retire obsolete acceptance paths

**Status:** complete

## Acceptance criteria

- [x] Publish a migration guide covering project commands/cwd/timeouts, discovery and execution evidence, TDD case declarations, source association, commit-message handoff and task-required case mapping.
- [x] Include a runnable minimal project/fixture using real Python framework discovery/results and an end-to-end command sequence for success and failure. Document the adapter requirements for other frameworks; do not claim Swift or another framework is supported by a prose command alone.
- [x] Show how existing Worker and Ghost task-case verification moves into hot and how a newly added TDD case remains in future hot runs without the original ticket.
- [x] Document user-selected N, successful-development-only counting, silent Git-clean cold success, tested revision tracking and no historical score deductions.
- [x] Document Ghost's exact permitted hot-wiring/metadata edits and forbidden code/test changes, bounded diagnosis and report location.
- [x] Document destructive pre-dispatch cleanup of tracked/nonignored changes, preservation of ignored files, absence of stash/patch recovery, and Planner's explicit schedule/restart operations.
- [x] Exercise the install/upgrade surface in a disposable project; verify runtime configuration/examples survive installation and do not depend on source-checkout-only paths.
- [x] Provide a reproducible lifecycle demonstration: task adds TDD→hot→commit/score; later task still runs that case; N inserts cold; failing cold pauses; Planner inserts ordinary issue and restarts; the next Worker starts clean.
- [x] Verify migration-required diagnostics for a legacy project with no discovery adapter, a missing hot hook and an unsupported evidence format.
- [x] Record the relevant automated checks and demo outcome in implementation delivery, keeping ordinary successful cold executions silent.

## Verification

Run the documented commands against the installed disposable fixture rather than testing text contents. Verify actual Git log/status, case execution markers, score, FIFO ordering, reports and pause/restart behavior. Run repository checks appropriate to the migrated surfaces; no live checkout cleanup.

## Out of scope

No actual deployment to an unrelated project, GitHub publication, broad framework-support claim or implementation work performed merely by authoring these tickets.

