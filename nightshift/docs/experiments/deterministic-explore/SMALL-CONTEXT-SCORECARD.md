# Per-Function / Source-Window Strategy Score

**70/100** for extracting useful local behavior notes from the 2B Ollama model. This is not a passing full NightShift Explore report.

| Category | Score | Finding |
|---|---:|---|
| Coverage | 15/25 | Seven focused functions/windows across the adapter and runtime; not a full repository investigation. |
| Factual accuracy | 21/30 | Most core descriptions were accurate. The model twice falsely said `choose_files` excludes common directories and called AST anchors a verified source index; a runner note also omitted the per-file memory update. |
| Traceability | 12/15 | The extractor attaches exact function/window ranges. Model claims do not consistently cite their own supporting lines. |
| Handoff usefulness | 12/20 | Good component notes, but the model notes alone lack the full topology, coupling map, and E–M–C handoff. The reviewed ledger adds those facts. |
| Reproducibility and safety | 10/10 | Seven short requests ended normally without length truncation; no product source files were changed. |

## Repeatability check

Repeated the same four per-function requests with temperature 0. Exact output matched for 1/4 functions. All four responses ended with `done_reason=stop`, but three varied in wording and one expanded an unsupported statement. Short context prevents long-output truncation; it does not make model-authored claims deterministic or fully accurate.

The related long-function test split `run()` into three source windows (1.4–2.0 KB each). All three outputs ended normally and described their local windows accurately, though the first window omitted the memory-update step that appears in that same source span. A graph-derived call edge plus the source ledger restores that relationship without asking the model to remember it.
