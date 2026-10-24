# AI Agent Adapter Implementation Tickets

Source: [AI Agent Adapter Protocol](../ai-agent-adapter-protocol.md).

Reviewable local breakdown; no tasks have been enqueued or executed. Each ticket is a complete behavioral slice with its own acceptance criteria. Blockers must be completed before a ticket starts.

Use expand–migrate–contract: introduce the protocol beside legacy execution, migrate each built-in adapter independently, then remove legacy routing. Each intermediate ticket must keep existing checks green. Early tickets validate behavior with fake adapters; production cutover waits for the final integration ticket.

| Ticket | Blocked by | What it delivers |
|---|---|---|
| [01: Run a registered external adapter through the protocol](01-protocol-execution.md) | None | Run a bounded task with an unknown adapter executable using versioned JSON callbacks, without adding provider knowledge to the runtime. |
| [02: Enforce deadlines and cancel asynchronous execution](02-deadlines-cancellation.md) | 01 | Monitor and stop a running adapter without model calls or unbounded callback waits. |
| [03: Complete tasks with invariant prompts and script-owned commits](03-shared-prompt-commit.md) | 01 | Execute the same assignment across registrations and commit verified changes using a structured commit message. |
| [04: Provide one private ghost closeout per original task](04-ghost-rescue.md) | 02, 03 | Recover incomplete closeout or a missing commit message through one script-owned ghost, then finalize the original task. |
| [05: Restore an attempt baseline before another execution](05-attempt-recovery.md) | 02 | Archive failed attempt work and restore its exact starting point without losing preexisting work. |
| [06: Track capability and batch feedback per registered agent](06-agent-scores.md) | 01 | Plan and review batches using independent capability histories for each registration. |
| [07: Pause dispatch and notify Planner of capability changes](07-watcher-dispatch-gate.md) | 06 | Make mid-batch execution changes visible to Planner before more work is assigned under stale granularity assumptions. |
| [08: Switch unavailable main-task agents through the planning gate](08-safe-failover.md) | 02, 04, 05, 07 | Recover main tasks from quota exhaustion or nonresponse using another registration only after stopping, restoring, and resolving planning changes. |
| [09: Execute Codex tasks through the external adapter](09-codex-adapter.md) | 04 | Run Codex implementation and closeout through the same executable protocol used by unknown adapters. |
| [10: Execute agy tasks through the external adapter](10-agy-adapter.md) | 04 | Run agy implementation and closeout through the same protocol without runtime-specific branches. |
| [11: Migrate generic wrappers to the executable protocol](11-generic-adapter.md) | 04 | Preserve custom execution integrations while moving their lifecycle and results to the standard protocol. |
| [12: Remove legacy provider routing and verify installed execution](12-contract-deploy.md) | 08, 09, 10, 11 | Deploy NightShift with only the standard adapter boundary and prove extension works outside the source checkout. |

Initial frontier: **01**. After 01, tickets **02**, **03**, and **06** can proceed independently. Tickets **09**, **10**, and **11** can proceed independently after 04. All work converges at 12.

Review points: confirm ticket size, check that blockers are genuine prerequisites, and identify any desired merges or splits before execution.
