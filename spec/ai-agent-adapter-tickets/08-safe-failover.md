# 08: Switch unavailable main-task agents through the planning gate

**What to build:** Recover main tasks from quota exhaustion or nonresponse using another registration only after stopping, restoring, and resolving planning changes.

**Blocked by:** 02: Enforce deadlines and cancel asynchronous execution; 04: Provide one private ghost closeout per original task; 05: Restore an attempt baseline before another execution; 07: Pause dispatch and notify Planner of capability changes.

**Status:** ready-for-agent

- [ ] Quota exhaustion and callback/execution timeout select the next available registration in order; ordinary errors and budget exhaustion do not automatically switch.
- [ ] Each registration is tried at most once per original task; persist exhausted-quota state while timeout exclusion applies only to that task.
- [ ] Confirm cancellation, retain diagnostics, and restore the attempt baseline before any replacement execution.
- [ ] Publish the agent change and honor the Planner dispatch gate before starting the replacement; switching alone never changes granularity.
- [ ] If no registration is available, retain/requeue the task and wait without busy retry; run-once mode may exit.
- [ ] Ghost never invokes this policy and failover never replenishes the original task ghost allowance.
