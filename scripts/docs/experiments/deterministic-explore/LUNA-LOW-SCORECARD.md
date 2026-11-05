# Luna-low NightShift Explore Trial

**Model:** `gpt-6-luna`, reasoning effort `low` via Codex CLI.
**Project/task:** NightShift Aider adapter and Worker Explore integration.
**Result:** **79/100** using the same five-category rubric as the Aider Explore reports.

| Category | Score | Finding |
|---|---:|---|
| Selection and coverage | 23/25 | Read the registry, Aider adapter, Explore runner, evidence index, Worker protocol/routing/audit, project notes, and current report conventions. |
| Factual accuracy | 21/30 | Most topology and routing details are correct. It incorrectly says model-rewritten memory is used downstream in the default static-evidence mode, and proposes retiring model selection/synthesis that this mode already bypasses. |
| Source traceability | 13/15 | 67 of 68 citation pointers resolve to existing files and in-range lines. `tasks.done#L1` is invalid because that file is absent. Range validity does not prove claim entailment. |
| NightShift report deliverables | 12/20 | Contains the required topology, callers, coupling, E–M–C, and evidence sections, but is 11,086 bytes (over the 5 KB report limit) and does not produce a `03-micro.md` artifact. |
| Scope and safety | 10/10 | Read-only run; no source files or tests were changed/run. |

## Runtime usage

Codex CLI reported 423,945 input tokens, including 347,136 cached input tokens, and 4,165 output tokens. The report was generated in about one minute. This is cumulative tool-turn usage, not a single active-context size.

Report: `LUNA-LOW-REPORT.md`; event trace: `LUNA-LOW-EVENTS.jsonl`.
