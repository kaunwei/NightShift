# 07: Execute an independent cold FIFO task with silent success and diagnosed failure

**What to build:** A manually inserted cold task runs the project's cold command directly in the script, remains silent and Git-clean on success, and uses the shared failure/Planner workflow on failure.

**Blocked by:** 06: Commit and score successful tasks automatically without Planner acceptance

**Status:** complete

## Acceptance criteria

- [x] Introduce an explicit internal cold task kind through the existing queue format/parser and claim path; it is not a Worker prompt disguised as a normal development task.
- [x] Resolve the project cold command and timeout, record execution-time HEAD internally and execute serially with no active Worker in the shared project directory.
- [x] Successful cold produces no model invocation, routine report, user notification, Git commit, branch change or Worker score update; only ignored runtime/scheduling state may change.
- [x] Cold result artifacts belong outside tracked/nonignored product paths. Unexpected product-file mutation fails the cold task rather than being committed or silently removed as success.
- [x] Cold command failure, timeout or missing/invalid configuration invokes Ghost diagnosis, pauses ordinary dispatch and notifies Planner, including the tested commit and actual command/output.
- [x] Cold diagnosis uses the project's relevant common test context; Ghost remains prohibited from product/test repair and cannot commit during a cold task.
- [x] Treat failure as a new issue without retracting any prior success score, attributing blame to an earlier Worker or reverting earlier commits.
- [x] Preserve the same explicit Planner scheduling/restart workflow; no special repair lane is introduced.

## Verification

Manually enqueue cold between two fake development tasks. Assert serial order, no Worker for cold, unchanged HEAD/status/score and no success notification. Then fail/timeout/mutate tracked output and assert report, pause and unchanged historical score. Include Ghost failure fallback.

## Out of scope

Automatic N-task insertion and hash-based skip/coalescing are delivered by the next ticket.

