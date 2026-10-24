# 01: Run a registered external adapter through the protocol

**What to build:** Run a bounded task with an unknown adapter executable using versioned JSON callbacks, without adding provider knowledge to the runtime.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] Define requests and responses for all five callbacks, including required fields, units, versions, execution handles, statuses, result locations, and protocol errors; document the executable contract.
- [ ] A fake adapter completes a task through get_config, asynchronous start, and status; a second registration needs no core changes.
- [ ] Registration overrides are interpreted by the adapter; normalized configuration, environment, task version, attempt identity, and artifact locations reach execution intact.
- [ ] Control responses and logs remain separate; invalid configuration or incompatible versions fail explicitly before task execution.
- [ ] Use the existing CLI/daemon behavioral seam and keep legacy execution working during expansion.
