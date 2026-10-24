# 03: Complete tasks with invariant prompts and script-owned commits

**What to build:** Execute the same assignment across registrations and commit verified changes using a structured commit message.

**Blocked by:** 01: Run a registered external adapter through the protocol.

**Status:** ready-for-agent

- [ ] The same task version has the same worker prompt hash across registrations; model, effort, permissions, timeout, and action limits travel outside the prompt.
- [ ] Remove provider-specific instructions and adapter-added task directives; preserve scope, verification, and common task constraints.
- [ ] Structured results distinguish completion, closeout requirements, failures, scope/guidance, and legitimate no-change outcomes.
- [ ] AI does not commit; script uses commit_message only after applicable verification and audits pass.
- [ ] Legitimate no-change completes without commit or ghost; missing message remains recoverable rather than being scraped from logs.
- [ ] Adapt commit-dependent audit ordering without weakening scope, verification, isolation, or acceptance checks.
