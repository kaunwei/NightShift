# Static Evidence Explore Trial

Task: `EXPLORE-STATIC-LEDGER-20261025-3`, using
`openbmb/minicpm5-2b:q8_0` through the local Ollama server.

**Score: 89/100** under the same rubric as the original Aider Explore trial (50/100).

| Category | Score | Finding |
|---|---:|---|
| Selection and coverage | 18/25 | Indexed 43 readable files and 7 Python files; read 4 task-relevant source files across 8 bounded windows. The report does not cover JSON registration data or dynamic Worker dispatch. |
| Factual accuracy | 26/30 | Report claims are rendered from deterministic AST facts and observed spans. Bare-call edges are labeled unique-name heuristics, not binding/runtime proof. Semantic model notes remain outside the report as unverified ledger entries. |
| Source traceability | 15/15 | All 9 report citations resolve to lines inside source windows actually sent to the reader. |
| NightShift Explore deliverables | 20/20 | Metadata, required sections and E–M–C matrix, 3 KB summary, AST skeletons, and exact ten-line micro slices were produced. |
| Scope and safety | 10/10 | Only report artifacts were written; product source remained untouched. |

## Observed result

- Deterministic selection chose `aider.py`, `aider_explore.py`, `worker_runtime.py`, and `explore_evidence.py`; test files were excluded because the task did not request test analysis.
- The report renderer did not consume or repeat the 2B model's unverified final-report claims. The evidence ledger retains per-file model notes, source hashes, chunk ranges, and static facts.
- The first live attempt exposed a citation path-normalization bug (full paths received a duplicate prefix) and invalid citations to skipped source windows. Both failure modes are now covered by tests; deterministic rendering avoids asking the model to invent final citations.

## Limits

This is one successful report run, not a repeatability sample. The report is structurally reliable but less semantically rich: JSON registry relations, dynamic dispatch, attribute calls, and claim-to-source entailment still need dedicated evidence. The ledger is in the Worker execution trace; Planner-facing artifacts remain `SUMMARY.md` and `03-micro.md`.
