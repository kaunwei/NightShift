# 11: Migrate generic wrappers to the executable protocol

**What to build:** Preserve custom execution integrations while moving their lifecycle and results to the standard protocol.

**Blocked by:** 04: Provide one private ghost closeout per original task.

**Status:** ready-for-agent

- [ ] Provide a documented migration or compatibility adapter for existing executable wrappers, including arguments, environment, prompt/result paths, ports, model, and effort.
- [ ] Support the five callbacks and structured outcomes without core log parsing; document wrapper-owned budget semantics.
- [ ] Provide the common ghost opportunity for recoverable closeout, including missing message, rather than retaining the old generic prohibition.
- [ ] Fake wrappers demonstrate configuration, execution, cancellation, results, and closeout; no live API is required.
- [ ] Unsupported old wrapper behavior produces actionable migration errors rather than silently changing execution meaning.
