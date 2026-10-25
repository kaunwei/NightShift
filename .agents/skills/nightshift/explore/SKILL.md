---
name: explore
description: "Research uncertain code ownership, callers, and interface seams for Planner; never implement changes."
---

# Explore

Deliver evidence, not implementation. Terminal A reads reports, notes, glossary, progress/queue, docs, and skills; the research Worker inspects source.

1. **Scope/reuse.** Read `.reports/<slug>/SUMMARY.md`, `.worker.notes.md`, and progress. Reports stay current only while referenced source paths remain unchanged; the runtime archives them after touching `[CODE]` commits and before research. Ignore `.reports/.archive/`. Define component, seam, and local/sibling repositories via `ADDITIONAL_DIRS`. `/explore` forces a fresh probe; otherwise reuse sufficient current evidence.
2. **Research.** If evidence is missing, queue `[RESEARCH]` with report `TARGET:` paths and `VERIFY: REPORT_ONLY`; require verified callers, interface skeletons, coupling, `path#Lline` pointers, and applicable Expand–Migrate–Contract strategy. Use `scripts/reorder_queue.sh` to enqueue/preempt with the daemon running. Compiler probes may temporarily alter signatures to identify callers; immediately restore task-original source, verify cleanliness, and preserve unrelated work.
3. **Sentinel.** Delegate `scripts/watch_worker.sh 3600` to a Queue Sentinel. After launch, ignore routine `RUNNING`/heartbeats: no status/log polling or progress reports. Intervene only on `BLOCKED`, `FAIL`, `SCOPE_BLOCKED`, failover, or other Planner-decision events. On completion, check fresh task-scoped `[DONE]` and matching `[MECHANICAL_AUDIT]` once; idle queues and stale records do not establish completion.
4. **Verify.** Require passing audit, valid source pointers, clean product tree, and headed, nonempty `.reports/<slug>/SUMMARY.md` (≤5 KB; line 1: `<!-- REPORT_META: Task=<id> | Commit=<sha> -->`) covering topology, coupling bottlenecks, and the Expand–Migrate–Contract matrix. Require `03-micro.md` with AST skeletons from `scripts/extract_skeleton.sh` and 10-line slices. `[DEAD_END]` and healthy-excluded-subsystem claims require isolated passing probes or runtime evidence.
5. **Handoff.** Send only verified seams to Planner; never invent implementation tickets:

   ```text
   Seam: <public interface or module>
   Target Files: <bounded paths>
   Callers: <verified callers>
   Glossary Additions: <domain terms, if any>
   Refactor Strategy: <Vertical-Slice | Expand-Migrate-Contract>
   ```
