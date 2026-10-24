# 12: Remove legacy provider routing and verify installed execution

**What to build:** Deploy NightShift with only the standard adapter boundary and prove extension works outside the source checkout.

**Blocked by:** 08: Switch unavailable main-task agents through the planning gate; 09: Execute Codex tasks through the external adapter; 10: Execute agy tasks through the external adapter; 11: Migrate generic wrappers to the executable protocol.

**Status:** ready-for-agent

- [ ] Remove legacy provider branches, provider-name inference, fixed allowlists, tool-log parsing, and competing execution paths after all migrations pass.
- [ ] Installer/updater deploy adapters, shared support, protocol documentation, and regression resources while preserving user configuration and work data.
- [ ] Runtime defaults belong to the launcher/launch environment and agent settings to one name-keyed JSON registry with default ordering and config pass-through; launcher/runtime/helpers/Planner never source or require the removed worker env file. Preserve legacy env data for manual migration, remove its example, and document launcher overrides being replaced on update.
- [ ] Update configuration guidance, common execution rules, Planner/watcher guidance, and porting guide to match scores, failover, prompts, commits, private ghost semantics, and matching helper overrides for custom Worker identity/paths.
- [ ] In a temporary installed project, run an unknown fake adapter using only its executable and registration; validate the full lifecycle without source-checkout dependencies.
- [ ] Run meaningful existing and new CLI/state regressions for queue, scope, verification, in-place execution, on-demand trial delivery/resource conflicts, env-file-free configuration, recovery, scores, watcher, failover, and ghost.
- [ ] Publish migration instructions for legacy settings and shared score; no external issue publication or real AI calls are required.
