# 02: Run project hot and required task cases through one precommit gate

**What to build:** A configured project hands a completed task to the script, which runs project hot plus task-required cases and commits only when the entire configured gate passes.

**Blocked by:** 01: Unify Worker and Ghost runtime finalization without changing behavior

**Status:** complete

## Acceptance criteria

- [x] Define and document the project hot execution contract and configuration validation, including commands, working directory, timeout, discovery/result-adapter invocation and machine-readable result ownership.
- [x] Map the existing task VERIFY or equivalent required-case field into this hot gate; project hot success cannot bypass a failing task command, and task success cannot bypass failing project hot.
- [x] Execute the script-owned hot gate after Worker exits and before commit. Staging task paths first is permitted; do not let the Worker or Ghost commit independently.
- [x] Remove the outer mechanical audit's duplicate execution for tasks using the new gate, while retaining scope/staging protections. Worker-internal red/green runs are not duplicate runtime acceptance.
- [x] Capture actual exit/output and task/attempt identity; missing configuration, timeout, command failure or malformed evidence is an explicit handoff failure, never converted into a successful no-op.
- [x] Ensure only task-allowed paths are staged/committed; an unexpected out-of-scope edit fails acceptance rather than silently disappearing from the commit.
- [x] Deliver a real executable Python test fixture using the new contract, not a stub that always exits zero; publish the minimal config and invoke it through the public runtime CLI.
- [x] Keep this first slice explicitly opt-in until the full migration ticket makes it the normal path. Do not silently switch existing installations to an incomplete flow.

## Verification

Prove project-hot failure, task-case failure, both passing, missing command and timeout. On success observe exactly one script-owned acceptance hot execution and the intended commit; on failure HEAD stays unchanged. Test on a non-main starting branch to prove no checkout/merge/push.

## Out of scope

Mandatory TDD integration evidence and automated scoring are added by later tickets.

