# 04: Provide one private ghost closeout per original task

**What to build:** Recover incomplete closeout or a missing commit message through one script-owned ghost, then finalize the original task.

**Blocked by:** 02: Enforce deadlines and cancel asynchronous execution; 03: Complete tasks with invariant prompts and script-owned commits.

**Status:** ready-for-agent

- [ ] closeout starts asynchronously with the common closeout prompt, original execution context, remaining budget, deadline, and distinct artifact locations.
- [ ] Missing commit_message triggers the same rescue opportunity as incomplete verification or closeout; successful rescue enables script-owned commit.
- [ ] Persist a maximum of one issued ghost per original task ID across retries, failover, and restart; ghost cannot recursively request rescue.
- [ ] Ghost stays on the originating registration and cannot modify implementation; verify file state before and after execution.
- [ ] Ghost quota, timeout, failure, or nonresponse never enters main-task failover; report the original task final outcome.
- [ ] Ghost and other script-generated internal AI work create no independent Planner queue items, DONE records, score feedback, review cadence, or watcher notifications.
- [ ] Retain internal cancellation and diagnostics while exposing only original-task outcomes to Planner; legitimate no-change never launches ghost.
