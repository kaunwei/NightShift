# 03: Reject TDD cases that are undeclared, unchanged, absent from permanent hot or not executed

**What to build:** A development task cannot be accepted just by claiming TDD: its added or updated cases must have changed test content, remain part of ordinary hot after the ticket ends, and actually pass the current hot run.

**Blocked by:** 02: Run project hot and required task cases through one precommit gate

**Status:** complete

## Acceptance criteria

- [x] Extend the structured development-task handoff with a nonempty TDD declaration containing stable case identity and test source association. Specify validation errors for missing, empty, duplicate-invalid and malformed declarations.
- [x] Use the clean task-start revision as the comparison baseline. Require an added or substantively updated test associated with each declared case; restaging an unchanged file does not count.
- [x] Use a project test adapter's parsed case/source information to reject declaration-only, registration-only and comment-only changes as substitutes for changed TDD content. If the adapter cannot establish source association, fail explicitly; do not introduce assertion-count heuristics.
- [x] Perform ordinary hot discovery without the current task's selectors, declarations or one-shot VERIFY arguments. Every declared case must still be present; a ticket-only invocation does not establish permanent membership.
- [x] Require all test files and persistent hot registration/configuration needed for membership to be included in the accepted deliverable. Ignored-only or runtime-metadata-only registration fails.
- [x] Read current runtime-produced execution evidence and require all declared TDD and task-required cases to execute and pass. Skipped, deselected, missing, failed or stale case results fail even if the command exits zero.
- [x] Reject a nonzero hot command even when its case report lists passes. Reject a false Worker verification claim or copied report from another attempt.
- [x] Prove persistence by completing task A with a new TDD case, then running task B with A's task metadata absent and observing A's case discovered and executed.
- [x] Provide a working adapter for the project's demonstrated Python fixture using actual framework discovery/results and case/source mapping; define how another framework supplies the same contract. No fake generic output parser may stand in for framework integration.
- [x] Missing tests are a Worker implementation failure: Ghost may wire an existing test but cannot create or rewrite test behavior to satisfy this gate. A no-change claim cannot bypass enforcement when delivering product changes.

## Verification

Table-driven public CLI cases: absent/empty declarations, unchanged source, comment-only edit, registration-only edit, wrong source association, task-only case, ignored wiring, discovered-but-skipped, stale report, false zero exit, nonzero exit with passes, plus valid auto-discovery and explicit-registration cases. Assert rejected tasks create neither commit nor success score.

## Out of scope

No semantic proof that a test captures the right requirement; source association plus discovery/execution is the mechanical guarantee.

