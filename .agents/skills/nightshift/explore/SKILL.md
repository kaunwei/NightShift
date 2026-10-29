---
name: explore
description: "Research code ownership, callers and interface seams for Planner; leave implementation unchanged."
---

# Explore

Deliver evidence. Terminal A reads docs/skills, reports, queue, progress and `nightshift/.worker.notes.md`; the research Worker inspects source.

1. **Scope.** Read `.reports/<slug>/SUMMARY.md`, notes and progress. Reports remain current only while referenced sources are unchanged; runtime archives affected reports after CODE commits and before research. Exclude `.reports/.archive/` from current evidence. Define component, seam and local/sibling repositories through ADDITIONAL_DIRS. Explicit `/explore` forces a fresh probe; otherwise reuse sufficient current evidence. Use the [code index](#code-index) for source lookup and dirty-input errors.
2. **Research.** Queue RESEARCH with report TARGET paths and `VERIFY: REPORT_ONLY`. Research tasks receive a decoupled, expanded action budget (default 100 actions via `agents.json` or `RESEARCH_STEP_BUDGET`) to explore broad callers without modifying product code. Require verified callers, interface skeletons, coupling, `path#Lline` evidence and an Expand-Migrate-Contract strategy where applicable. Use `nightshift/reorder_queue.sh` for live enqueue/preemption. Temporary compiler signature probes must immediately restore task-original source, verify cleanliness and preserve unrelated work. Over-budget research escalates to decomposition review without score penalty.
3. **Wait.** Delegate `bash nightshift/watch_worker.sh 0 5 TASK-ID` to a Queue Sentinel. Follow Planner's [event gate and acceptance](../planner/SKILL.md#wait-and-accept): long notification-interruptible waits, expiry renews waiting, no RUNNING/heartbeat polling or progress reports. Intervene on BLOCKED, FAIL, SCOPE_BLOCKED, failover or another decision event. Completion requires fresh task-scoped DONE and matching audit, not an idle queue or stale record.
4. **Verify.** Require passing audit, clean product tree, valid pointers and a headed, nonempty `.reports/<slug>/SUMMARY.md`, <=5 KB. First line:

   ```text
   <!-- REPORT_META: Task=<id> | Commit=<sha> -->
   ```

   Cover topology, coupling bottlenecks and the Expand-Migrate-Contract matrix. Include `03-micro.md` with AST skeletons from `nightshift/extract_skeleton.sh` and relevant 10-line slices. DEAD_END or healthy-excluded-subsystem claims need isolated passing probes or runtime evidence.
5. **Handoff.** Send verified seams to Planner; leave implementation tickets to Planner:

   ```text
   Seam: <public interface or module>
   Target Files: <bounded paths>
   Callers: <verified callers>
   Glossary Additions: <domain terms, if any>
   Refactor Strategy: <Vertical-Slice | Expand-Migrate-Contract>
   ```

## Code index

After script approval, read `nightshift/.scratch/code-index/INDEX.md` for symbol kind, owner-qualified name and line. Counts belong in detailed queries. Symbol queries accept `Type.name`; reference/caller queries use simple names. Use compact queries (`python` on Windows):

```sh
python3 nightshift/worker_runtime.py code-index query callers NAME --scope project --format compact
python3 nightshift/worker_runtime.py code-index build
```

Indexed source/settings must be Git-clean even when HEAD matches; script checks block dirty builds/queries. Commits affecting indexed inputs refresh automatically. Resolve dirty inputs through the task's commit/rollback workflow, preserving unrelated work; rebuild and retry. A current/rebuilt result confirms availability.

Build JSON gives summary_path and index_path. The latter is `nightshift/.scratch/code-index/index.json`, the script-owned file/symbol preview cache. Detailed evidence is parsed on demand; queries write stdout without saved reports.
