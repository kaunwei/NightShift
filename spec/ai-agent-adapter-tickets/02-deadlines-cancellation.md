# 02: Enforce deadlines and cancel asynchronous execution

**What to build:** Monitor and stop a running adapter without model calls or unbounded callback waits.

**Blocked by:** 01: Run a registered external adapter through the protocol.

**Status:** ready-for-agent

- [ ] Status reads local execution state only; fake call traces prove monitoring never invokes a model or queries quota.
- [ ] Honor the configured polling interval and separately enforce callback-response and execution deadlines.
- [ ] Quiet logs do not imply nonresponse; continuously responsive status does not bypass an execution deadline.
- [ ] Cancel targets the full execution and confirms termination; acknowledgement alone does not count as stopped.
- [ ] Blocked callbacks, lingering children, and failed cancellation produce bounded, observable outcomes.
