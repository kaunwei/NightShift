---
name: explore
description: "Map code ownership, callers, and public seams into a bounded report before planning uncertain changes."
---

# Explore

Use this flow when target files, call sites, or interface ownership are unclear. It produces evidence for the Planner; it does not implement changes.

In Terminal A, read reports, notes, glossary, progress/queue, docs, and skills only; source inspection belongs to the research Worker. Use a Queue Sentinel subagent to wait on the watcher and return the first 15 progress lines.

1. **Check for a current report.** Read `.reports/<slug>/SUMMARY.md`, `.worker.notes.md`, and relevant progress records. `SUMMARY.md` is current only while its source paths are unchanged. The runtime archives reports when a `[CODE]` commit touches a referenced path and before new research; never use `.reports/.archive/` as current evidence.
2. **Bound the question.** Define the component, likely public seam, and local/sibling repositories in `ADDITIONAL_DIRS`. Explicit `/explore` runs a fresh probe; otherwise reuse a current report that answers the question.
3. **Run a `[RESEARCH]` ticket** through the worker queue when evidence is missing. Declare report files in `TARGET:`, use `VERIFY: REPORT_ONLY`, and ask for callers, interface skeletons, coupling points, validated `path#Lline` references, and an Expand–Migrate–Contract plan where relevant. Use `scripts/watch_worker.sh 3600` to wait rather than polling. Compiler probes may temporarily change signatures only when immediately restored and verified clean; never leave product changes.
4. **Check the result.** Require a non-empty `SUMMARY.md` with headings and line-1 `<!-- REPORT_META: Task=<id> | Commit=<sha> -->`, valid source pointers, and a clean product tree. Claims of `[DEAD_END]` or a healthy excluded subsystem need an isolated passing probe or runtime evidence, not speculation.
5. **Return a seam digest** to the Planner:

   ```text
   Seam: <public interface or module>
   Target Files: <bounded paths>
   Callers: <verified callers>
   Glossary Additions: <domain terms, if any>
   Refactor Strategy: <Vertical-Slice | Expand-Migrate-Contract>
   ```

`SUMMARY.md` must be at most 5 KB and cover topology, coupling bottlenecks, and the Expand–Migrate–Contract matrix. Include `03-micro.md` with AST skeletons from `scripts/extract_skeleton.sh` and 10-line slices. Use compiler probes to capture callers, immediately restoring the task's original source state after temporary signature edits. Never restore unrelated work or leave product edits. Enqueue/preempt through `scripts/reorder_queue.sh` while the daemon is active. Do not write implementation tickets from guesses.
