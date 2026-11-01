# Automatic hot/cold acceptance tickets

Implementation status: Complete (All tickets 01–10 implemented and verified; 100% test pass rate across 271 repository tests).

The specification is copied alongside the tickets so this work does not depend on an unpublished scratch document. See [SPEC.md](SPEC.md).

## Execution order and blocking edges

All tickets have completed:

1. **[Unify Worker and Ghost runtime finalization without changing behavior](tickets/01-unify-runtime-finalization.md)** — Status: Complete.
2. **[Run project hot and required task cases through one precommit gate](tickets/02-run-project-hot-before-commit.md)** — Status: Complete.
3. **[Reject TDD cases that are undeclared, unchanged, absent from permanent hot or not executed](tickets/03-enforce-persistent-tdd-hot-evidence.md)** — Status: Complete.
4. **[Let Ghost repair hot wiring and delivery metadata through the common gate](tickets/04-ghost-completes-handoff-or-reports.md)** — Status: Complete.
5. **[Pause failed execution and restart ordinary tasks from a clean project](tickets/05-pause-clean-and-planner-restart.md)** — Status: Complete.
6. **[Commit and score successful tasks automatically without Planner acceptance](tickets/06-automatic-scoring-and-restart-safety.md)** — Status: Complete.
7. **[Execute an independent cold FIFO task with silent success and diagnosed failure](tickets/07-execute-silent-independent-cold-task.md)** — Status: Complete.
8. **[Insert cold after N successful development commits and recover cadence on restart](tickets/08-schedule-cold-after-development-commits.md)** — Status: Complete.
9. **[Make automatic hot/cold the normal lifecycle and retire obsolete acceptance paths](tickets/09-retire-manual-acceptance-and-hardcoded-policies.md)** — Status: Complete.
10. **[Deliver runnable hot/cold migration and verify an installed project's full lifecycle](tickets/10-document-and-verify-project-migration.md)** — Status: Complete.

## Nonnegotiable behavior

- Planner and Worker use the same current branch; hot acceptance means commit, not merge or push.
- A delivered development task must declare changed TDD cases, permanently include them in hot, and prove actual execution. An unchanged file, temporary ticket-only test, skipped case or a bare zero exit cannot satisfy the gate.
- Ghost may complete metadata/hot wiring and diagnose; it cannot change product code or test behavior.
- Unresolved failure pauses ordinary dispatch; Planner schedules ordinary issue tasks and explicitly restarts.
- Before Worker launch, discard tracked and nonignored untracked changes; preserve ignored files and reports. These tickets do not clean this checkout.
- Keep scoring arithmetic; automate terminal outcomes. Cold failures are new issues and never undo old scores.
- Cold is an independent serial script task after N committed development tasks. Success has no notification, Worker score or Git change.

## Review

Review granularity, genuine blocking edges and any desired merge/split before implementation. Detailed acceptance criteria and executable verification scenarios are in each ticket. Proposed primary test seam is the public runtime lifecycle using fake adapters, real test hooks and disposable Git repositories.

