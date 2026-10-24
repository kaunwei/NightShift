# 07: Pause dispatch and notify Planner of capability changes

**What to build:** Make mid-batch execution changes visible to Planner before more work is assigned under stale granularity assumptions.

**Blocked by:** 06: Track capability and batch feedback per registered agent.

**Status:** ready-for-agent

- [ ] Persist events with identity, cause, affected task, and previous/current registration and score.
- [ ] Watcher reports events through the existing Planner/Sentinel handoff, with restart-safe cursors and duplicate suppression; it does not launch Planner.
- [ ] Pause new dispatch until Planner acknowledges or revises affected queued work; already running main tasks may finish.
- [ ] Runtime never rewrites task scope or automatically decomposes tickets; an unchanged task version keeps its prompt.
- [ ] Exclude ghost and other internal work from change notifications; original-task final outcomes remain observable.
- [ ] CLI/state tests prove notification, acknowledgement, restart recovery, and dispatch gating end to end.
