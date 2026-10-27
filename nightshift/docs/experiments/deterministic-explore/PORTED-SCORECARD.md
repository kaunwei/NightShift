# Ported Aider Explore score

**50/100** — `TASK-AIDER-EXPLORE-4`, using `openbmb/minicpm5-2b:q8_0` on the local Ollama server.

| Category | Score | Findings |
|---|---:|---|
| Selection and coverage | 13/25 | Relevant adapter/runtime files selected; 4 of 37 indexed files and partial chunks. The report says 3 chunks, while 12 reader chunks were executed. |
| Factual accuracy | 6/30 | It reverses the import direction, invents `dispatch_explore()` and commit behavior, and mixes runtime symbols into the adapter analysis. |
| Source traceability | 5/15 | Four AST-derived `path#Lline` anchors validate, but most claims use bare line numbers without linked citations. |
| NightShift Explore deliverables | 16/20 | Metadata, 5 KB size, required sections/matrix, `03-micro.md`, and two exact slices were produced; mechanical research audit passed. |
| Scope and safety | 10/10 | Product source remained untouched; test output stayed in the isolated checkout. |

The adapter/protocol and artifact path work. The Explore content is not ready to hand to Planner without human source review. NightShift’s mechanical audit verifies report shape and pointer ranges, not whether claims are true.
