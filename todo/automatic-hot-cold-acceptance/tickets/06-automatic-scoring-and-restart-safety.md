# 06: Commit and score successful tasks automatically without Planner acceptance

**What to build:** A fully verified task commits and receives its existing-rule score automatically; replaying runtime state cannot duplicate its commit, success or failure accounting.

**Blocked by:** 05: Pause failed execution and restart ordinary tasks from a clean project

**Status:** complete

## Acceptance criteria

- [x] Remove Planner accept/reject as the normal success prerequisite. A valid hot/evidence/mechanical result plus successful runtime commit completes the task and lets the next task run.
- [x] Retain existing score arithmetic, caps, streak and existing failure rules; map one terminal task outcome into those rules instead of counting every hot rerun or Ghost attempt as another task.
- [x] Hot failure does not receive success; recoverable metadata/wiring omissions successfully completed through Ghost must not be counted as both a failed and successful completed task.
- [x] Persist task/attempt, committed identity, gate outcome and score transition in ignored runtime state sufficient to recover across process exit.
- [x] Handle restart after gate success but before commit, after commit but before score write, and after score write but before completion delivery. Check actual Git history/state rather than trusting only an in-memory flag.
- [x] Make commit, score and task-completion effects replay-safe: one accepted task has one intended commit, one score transition and one completion event.
- [x] Do not award success or advance cold cadence if git commit fails or no development commit was produced. Preserve explicit handling of nondevelopment/no-change outcomes without TDD bypass for changed product code.
- [x] Planner can read the resulting score to choose work without writing a manual audit resolution. Routine success does not require report archival.
- [x] Ensure observer/sentinel completion pairing works with the automatic accepted outcome; no component waits forever for a removed Planner_Review pending transition.

## Verification

Public lifecycle fixtures around each interruption boundary; resume the same task identity and inspect HEAD/log, score/streak, queue count and delivered events. Exercise five-success score progression, a failure under existing rules, a commit failure and a Ghost-recovered success.

## Out of scope

No new arithmetic, historical cold blame, manual confidence override or automatic push.

