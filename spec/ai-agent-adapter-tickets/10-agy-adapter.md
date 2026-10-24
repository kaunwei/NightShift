# 10: Execute agy tasks through the external adapter

**What to build:** Run agy implementation and closeout through the same protocol without runtime-specific branches.

**Blocked by:** 04: Provide one private ghost closeout per original task.

**Status:** ready-for-agent

- [ ] Implement all five callbacks with agy-specific invocation, capability probing, model/effort handling, output parsing, quota classification, and budget semantics inside the adapter.
- [ ] get_config returns initial score 5 and adapter defaults with registration overrides; runtime does not identify agy.
- [ ] Use common prompts, structured results, and script-owned commits instead of agy-specific commit instructions.
- [ ] Keep execution and ghost artifacts separate; status reads existing local state only.
- [ ] Fake agy transport tests cover completion, budget, quota, cancellation, and closeout without live model calls.
