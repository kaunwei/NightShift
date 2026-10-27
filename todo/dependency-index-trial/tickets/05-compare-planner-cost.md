# 05: Run the controlled Matronome comparison and report Planner savings

**What to build:** Run the baseline and index-assisted workflows with the approved replay protocol, then deliver a reproducible comparison focused on Planner usage while exposing correctness, Worker costs, and all indexing overhead. Preserve evidence and restore the product baseline after both arms.

**Blocked by:** 02 — Recover task-relevant Swift references and caller evidence; 03 — Keep single-index queries correct across edits and acceptance rollback; 04 — Replay identical Planner tickets with isolated Worker stages and restoration.

**Status:** draft — pending breakdown and test-seam approval

- [ ] Both arms use byte-identical Planner tickets and the same pinned starting revision/model settings; tool access is the documented treatment difference.
- [ ] Each arm preserves one Planner record and two sequential Worker task records, including derived tickets, source-backed findings, and small-change verification.
- [ ] All trial product changes and candidate commits are undone; the preserved final evidence demonstrates restoration after each arm.
- [ ] Compare findings with independent reference relationships; report incorrect claims, important missing dependencies, unresolved scope, and any wrong-version evidence.
- [ ] Measure cold build, reuse, dirty-source update, commit change, checkout switch, rollback rebuild, query, retry/fallback, and full-workflow elapsed time. Supplemental lifecycle measurements are identified separately from the paired workflow.
- [ ] Report measured Planner input/output/cache token usage as the primary result; calculate Planner monetary cost only with explicit supported model/rate data.
- [ ] Report exploration Worker, change Worker, and total workflow usage separately. Missing telemetry is unavailable, not zero, and unsupported token-saving claims are withheld.
- [ ] Lower Planner tokens count as success only without wrong-version evidence or degraded required-reference correctness; disclose total-cost changes and repeatability limits.
- [ ] Preserve runnable commands, versions/settings, task hashes, source identities, artifact locations, and limitations including cache/order effects.
- [ ] Recommend whether automatic integration deserves a later change; do not introduce hooks or production lifecycle changes in this ticket.
