---
name: explore
description: "Research code ownership, callers and interface seams for Planner; leave implementation unchanged."
---

# Explore

Deliver evidence. Terminal A reads docs/skills, reports, queue, progress and `$NIGHTSHIFT_STATE_DIR/.worker.notes.md`; the research Worker inspects source.

1. **Scope.** Read `.reports/<slug>/SUMMARY.md`, notes and progress. Reports remain current only while referenced sources are unchanged; runtime archives affected reports after CODE commits and before research. Exclude `.reports/.archive/` from current evidence. Define component, seam and local/sibling repositories through ADDITIONAL_DIRS. Explicit `/explore` forces a fresh probe; otherwise reuse sufficient current evidence. Use the [code index](#code-index) for source lookup and dirty-input errors.
2. **Research.** Queue RESEARCH with report TARGET paths and `VERIFY: REPORT_ONLY`. Use the selected config's `worker.research_step_budget` or `RESEARCH_STEP_BUDGET`/runtime fallback (default 100), separate from code budgets. Set the [bounded research](#bounded-research) contract before dispatch; product code stays unchanged. Require verified callers, interface skeletons, coupling, `path#Lline` evidence and an Expand-Migrate-Contract strategy where applicable. Use `"$NIGHTSHIFT_CORE/scripts/reorder_queue.sh"` for live enqueue/preemption. Temporary compiler signature probes must immediately restore task-original source, verify cleanliness and preserve unrelated work. Over-budget research goes to decomposition review; runtime owns scoring.
3. **Wait.** Delegate `WORKER_INACTIVE_REPEAT=1 bash "$NIGHTSHIFT_CORE/scripts/watch_worker.sh" 0 5 TASK-ID` to a Queue Sentinel (or `ns-watch 0 5 TASK-ID`). Follow Planner's [supervision](../planner/SKILL.md#supervise): long notification-interruptible streaming waits, repeated inactivity relay, and expiry renews waiting on the same watcher. Planner owns the relay contract; RUNNING/heartbeat observations alone require no progress reports. Intervene on BLOCKED, FAIL, SCOPE_BLOCKED, ENVIRONMENT_BLOCKED, HOOK_INTERRUPTED, failover or another decision event. Completion requires fresh task-scoped DONE and matching audit, not an idle queue or stale record.
4. **Verify.** Require passing audit, clean product tree, valid pointers and a headed, nonempty `SUMMARY.md` in the declared `.reports/<slug>/` or selected runner reports directory, <=5 KB. First line:

   ```text
   <!-- REPORT_META: Task=<id> | Commit=<sha> -->
   ```

   Cover topology, coupling bottlenecks and the Expand-Migrate-Contract matrix. Include `03-micro.md` with AST skeletons from code-index queries and relevant 10-line slices. DEAD_END or healthy-excluded-subsystem claims need isolated passing probes or runtime evidence.
5. **Handoff.** Send verified seams to Planner; leave implementation tickets to Planner:

   ```text
   Seam: <public interface or module>
   Target Files: <bounded paths>
   Callers: <verified callers>
   Glossary Additions: <domain terms, if any>
   Refactor Strategy: <Vertical-Slice | Expand-Migrate-Contract>
   ```

## Bounded research

Before dispatch, state the question, attempt cap, total/per-trial deadlines,
commands, required artifacts and next decision. Stop at the first useful failing
sample or the declared bound. Record outcomes, source/revision pointers, method,
limits and unresolved defects; preserve logs even when nothing reproduces.
A valid, complete report may return `outcome=complete` with
`research_conclusion=positive|negative|inconclusive`. Missing artifacts or an
invalid method remain blocked. Unreproduced is not disproved or fixed. Keep the
defect in backlog; dispatch repair only from sufficient evidence. Reopen bounded
research for new evidence, rather than repeating an unchanged reproduction loop.

## Code index

After script approval, read `$NIGHTSHIFT_STATE_DIR/code-index/INDEX.md` for symbol kind, owner-qualified name and line. Counts belong in detailed queries. Symbol queries accept `Type.name`; reference/caller queries use simple names. Use compact queries (`python` on Windows):

```sh
python3 "$NIGHTSHIFT_CORE/scripts/worker_runtime.py" code-index query callers NAME --scope project --format compact
python3 "$NIGHTSHIFT_CORE/scripts/worker_runtime.py" code-index build
```

Indexed source/settings must be Git-clean even when HEAD matches; script checks block dirty builds/queries. Commits affecting indexed inputs refresh automatically. Resolve dirty inputs through the task's commit/rollback workflow, preserving unrelated work; rebuild and retry. A current/rebuilt result confirms availability.

Build JSON gives summary_path and index_path. The latter is `$NIGHTSHIFT_STATE_DIR/code-index/index.json`, the script-owned file/symbol preview cache. Detailed evidence is parsed on demand; queries write stdout without saved reports.
