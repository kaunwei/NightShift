# 04: Let Ghost repair hot wiring and delivery metadata through the common gate

**What to build:** A task with an incomplete handoff can still finish when Ghost supplies a message or connects an already-written test to hot; actual implementation failures produce bounded diagnostic reports instead of Ghost code repair.

**Blocked by:** 03: Reject TDD cases that are undeclared, unchanged, absent from permanent hot or not executed

**Status:** complete

## Acceptance criteria

- [x] Invoke Ghost for missing commit messages, missing or incomplete hot wiring, and failed gate diagnosis. Pass actual failing phase, command/output, declarations and task/attempt identity.
- [x] Allow Ghost to supply a commit message, edit explicitly scoped hot registration/configuration, invoke the shared hot entry point and write diagnostic artifacts.
- [x] Enforce that Ghost cannot change product source, test content/assertions/behavior, delete tests, weaken tests or edit unrelated scripts. Wiring exceptions must not make all config/script edits implicitly allowed.
- [x] Record the Worker-to-Ghost boundary separately from the task-start baseline, so pre-existing Worker test changes are not mistaken for Ghost edits.
- [x] Return a valid Ghost supplement to the same script-owned gate. Only that gate may commit, and every required case must still pass.
- [x] If Ghost cannot fix the handoff without implementation changes, emit a diagnostic result rather than attempting product repair or silently requeueing.
- [x] Bound Ghost execution and ensure timeout, invalid output or forbidden edits produce a usable fallback report with available original test output.
- [x] Ghost writes reports outside the future cleanup scope. Include task/attempt, phase, command, exit, case evidence, baseline/current commit where available and Ghost completion status.
- [x] Specify and enforce how many Ghost supplement attempts are permitted per failed handoff so a deterministic bad handoff cannot loop forever.

## Verification

Public lifecycle scenarios: missing message supplied; existing test registered then accepted; true failing test diagnosed; forbidden source/test edit rejected; Ghost timeout/invalid output still leaves failure evidence. Show one shared hot gate owns the final commit.

## Out of scope

Ghost does not author replacement TDD tests, implement issue fixes or independently run git commit.

