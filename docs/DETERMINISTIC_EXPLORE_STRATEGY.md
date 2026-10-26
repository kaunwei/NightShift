# Deterministic Explore Report Strategy (Archived)

This document preserves the implementation direction behind the Aider Explore experiment. The Aider adapter, evidence-index script, registration, and deployment hooks have been removed; this is design history, not a supported NightShift feature.

## Problem

The local fallback model used in the trial had 2B parameters and a 40K-token context. Repeated file selection, summaries, and memory rewrites could lose earlier findings. Free-form synthesis could also invent relationships or cite lines that were never read. Pointer validation alone proves that a path and line exist, not that they support a claim.

## Strategy

Move repository facts and report assembly out of the model context:

1. Build a deterministic Python AST index of declarations, explicit local imports, bare-name calls, unresolved calls, source hashes, and task-relevant seeds.
2. Resolve a bare call only when its name maps to one indexed definition. Label that as a unique-name match, never proof of language binding or runtime execution. Keep ambiguous names, attribute calls, dynamic dispatch, syntax errors, and unsupported languages unresolved or out of scope.
3. Select source files from graph leads and task/path relevance without asking the model to plan file selection. Exclude tests unless the task asks about tests.
4. Read bounded source windows and append each read, source hash, line ranges, chunk hashes, and static facts to an evidence ledger. Keep model notes as separate, explicitly unverified observations; do not let them rewrite prior evidence.
5. Render topology, static caller leads, coupling counts, unknowns, and an Expand–Migrate–Contract matrix from the collected evidence. Require every citation to fall within a source window actually read.
6. Keep NightShift's research deliverables (`SUMMARY.md` and `03-micro.md`), report metadata, size limit, and protocol owned by the surrounding Worker.

## Intended benefits and limits

The harness aims to make report structure, evidence provenance, and repeatability less dependent on the model remembering a long interaction. It does not establish semantic claim entailment, runtime call behavior, broad language support, or Luna-low-equivalent reasoning/coding ability. It also does not prove token savings without comparable provider-level measurements.

## Original implementation seam and test direction

The planned seam was `build_static_evidence(root, paths, task_text)`, producing evidence records consumed by a deterministic renderer. Tests covered imports and unique caller leads, ambiguous names, task-based test inclusion, repeatable rendering, required sections/metadata, inspected-window counts, citation membership, report-size limits, and append-only ledger behavior. The implementation lived in the removed `explore_evidence.py`; the Aider adapter integrated it with Ollama reads and NightShift result delivery.

## Preserved outputs

The archived trial scorecards and generated reports are under [`experiments/deterministic-explore`](experiments/deterministic-explore/README.md). Scores were single-run observations, not guarantees.
