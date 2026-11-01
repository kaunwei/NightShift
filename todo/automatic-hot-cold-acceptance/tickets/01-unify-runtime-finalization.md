# 01: Unify Worker and Ghost runtime finalization without changing behavior

**What to build:** A Worker or Ghost handoff follows one runtime-owned verification/finalization boundary, making the later hot migration possible without introducing a second acceptance implementation.

**Blocked by:** None (can start immediately).

**Status:** complete

## Acceptance criteria

- [x] Extract the shared handoff-to-finalization boundary used by structured Worker completion and Ghost closeout; callers cannot independently stage, verify or commit through newly duplicated paths.
- [x] Preserve current CLI/result compatibility, task VERIFY behavior, failures, score behavior and existing verification invocation counts in this prefactor; do not enable automatic acceptance or remove policy checks yet.
- [x] Keep captured stdout/stderr, command exit, task/attempt identity and commit-message attribution available through the shared boundary.
- [x] Keep adapter-specific behavior outside the common gate; use the public adapter protocol rather than a provider-specific shortcut.
- [x] Demonstrate through the public task CLI that both a fake Worker result and a Ghost closeout reach finalization; failed VERIFY produces no commit and successful verification preserves the supplied commit message.
- [x] Run existing verification-evidence, Ghost and runtime lifecycle checks appropriate to the extraction; changes to their expected behavior belong to later tickets.

## Verification

Use a fake adapter and disposable Git repository through the existing public CLI. Observe outputs, HEAD and commit message. Keep this ticket mechanical: existing production semantics stay green.

## Out of scope

No hot/cold configuration, new scoring policy, TDD enforcement, cleanup policy or Planner prompt migration.

