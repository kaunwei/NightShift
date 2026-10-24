# 09: Execute Codex tasks through the external adapter

**What to build:** Run Codex implementation and closeout through the same executable protocol used by unknown adapters.

**Blocked by:** 04: Provide one private ghost closeout per original task.

**Status:** ready-for-agent

- [ ] Implement all five callbacks with Codex-specific invocation, model/effort translation, event parsing, quota classification, and action accounting inside the adapter.
- [ ] get_config returns initial score 5 and appropriate defaults, honoring registration overrides; runtime does not identify Codex.
- [ ] Use unchanged common prompts and structured results, including commit_message; no AI-owned commit or provider-specific task instructions.
- [ ] Main and ghost prompt/result paths are consistent and isolated; status queries never invoke Codex.
- [ ] Fake Codex transport tests cover completion, budget, quota, cancellation, and closeout without live model calls.
