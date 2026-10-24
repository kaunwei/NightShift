# 06: Track capability and batch feedback per registered agent

**What to build:** Plan and review batches using independent capability histories for each registration.

**Blocked by:** 01: Run a registered external adapter through the protocol.

**Status:** ready-for-agent

- [ ] Initialize scores exclusively from get_config, with registration overrides; core code contains no named-agent score defaults.
- [ ] Persist independent score, acceptance window, and failure history per registration, including multiple models sharing one adapter.
- [ ] Preserve the existing 1–5 mapping and score arithmetic, attributed to the actual executing registration; ghost has no independent score.
- [ ] Support normal batch-boundary feedback and durable agent/score/level change events for mid-batch changes.
- [ ] Document migration of shared historical score without guessing agent ownership; preserve old state for inspection.
