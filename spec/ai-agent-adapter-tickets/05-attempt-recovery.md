# 05: Restore an attempt baseline before another execution

**What to build:** Archive failed attempt work and restore its exact starting point without losing preexisting work.

**Blocked by:** 02: Enforce deadlines and cancel asynchronous execution.

**Status:** ready-for-agent

- [ ] Capture HEAD, index, tracked changes, untracked files, and relevant preexisting workspace state before an attempt.
- [ ] Confirm the old execution stopped before archiving or restoring; halt safely if termination or recovery cannot be established.
- [ ] Restore attempt-created commits and staged changes as well as worktree edits; preserve preexisting dirty, staged, and untracked content.
- [ ] Preserve diagnostics and failed artifacts for every attempt without overwriting previous attempts.
- [ ] Behavioral tests in temporary repositories cover successful recovery and deliberate recovery failure.
