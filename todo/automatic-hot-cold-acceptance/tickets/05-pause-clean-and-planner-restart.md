# 05: Pause failed execution and restart ordinary tasks from a clean project

**What to build:** After an unresolved failure, no ordinary task starts until Planner reviews the report, schedules new work and explicitly restarts; the new Worker never inherits the failed patch.

**Blocked by:** 04: Let Ghost repair hot wiring and delivery metadata through the common gate

**Status:** complete

## Acceptance criteria

- [x] Persist a paused/failure state before any next ordinary dispatch can occur. Unresolved hot, mechanical, Ghost, commit and cleanup errors cannot fall through to a success or empty-queue continuation.
- [x] Emit one actionable failure notification with report location and durable identity; restarting the observer/daemon must not lose the failure or generate duplicate actionable events.
- [x] Keep the staged/dirty scene available while Ghost diagnoses and Planner inspects. Merely editing or inserting queue items does not acknowledge the failure or resume dispatch.
- [x] Provide an explicit Planner-controlled restart operation using the existing scheduling/supervision surface; document the distinction between queue mutation and restart.
- [x] On restarted dispatch, restore tracked index/worktree to the current committed baseline and delete nonignored untracked files before launching Worker. Verify clean status and block launch if cleanup fails.
- [x] Preserve ignored dependencies, local settings, internal state and diagnostic reports. Do not stash, archive patches, copy failed files into recovery backups or reapply them to the new task.
- [x] Exercise this cleanup even when the pending queue was previously empty: whenever a new Worker is about to start, the clean-start requirement applies.
- [x] Let Planner insert a newly scoped issue task near the front and change its prompt through the scheduling script. The repair executes as an ordinary task; another failure pauses again.
- [x] No automatic post-diagnosis resume or special mandatory repair/cold gate. Planner normally delegates fixes, retaining the existing lowest-level exception.
- [x] Serialize dispatch/cleanup ownership so a second Worker cannot claim a task while the same shared working directory is being verified, diagnosed or cleaned.

## Verification

Disposable repository with staged tracked edits, unstaged edits, new nonignored files, ignored files and a diagnostic report. Fail hot, inspect scene, insert issue without restart and prove no launch, then restart and prove issue launch sees a clean tree. Cover empty-queue restart, cleanup permission failure and repeated failure notification.

## Out of scope

Do not execute these destructive cleanup scenarios in the real checkout. Do not reset successful commits or delete historical branches/worktrees.

