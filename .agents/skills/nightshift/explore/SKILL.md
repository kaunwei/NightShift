---
name: explore
description: "Research uncertain code ownership, callers, and interface seams for Planner; never implement changes."
---

# Explore

Deliver evidence, not implementation. Terminal A reads reports, `nightshift/.worker.notes.md`, `nightshift/progress.log`, `nightshift/tasks.txt`, docs, and skills; the research Worker inspects source.

1. **Scope/reuse.** Read `.reports/<slug>/SUMMARY.md`, `nightshift/.worker.notes.md`, and
   `nightshift/progress.log`. For source lookup or dirty-source index errors, use the [code
   index](#code-index). Reports stay current only while referenced source paths remain unchanged;
   the runtime archives them after touching `[CODE]` commits and before research. Ignore
   `.reports/.archive/`. Define component, seam, and local/sibling repositories via
   `ADDITIONAL_DIRS`. `/explore` forces a fresh probe; otherwise reuse sufficient current evidence.
2. **Research.** If evidence is missing, queue `[RESEARCH]` with report `TARGET:` paths and `VERIFY: REPORT_ONLY`; require verified callers, interface skeletons, coupling, `path#Lline` pointers, and applicable Expand–Migrate–Contract strategy. Use `nightshift/reorder_queue.sh` to enqueue/preempt with the daemon running. Compiler probes may temporarily alter signatures to identify callers; immediately restore task-original source, verify cleanliness, and preserve unrelated work.
3. **Sentinel.** Delegate `nightshift/watch_worker.sh 3600` to a Queue Sentinel. After launch, ignore routine `RUNNING`/heartbeats: no status/log polling or progress reports. Intervene only on `BLOCKED`, `FAIL`, `SCOPE_BLOCKED`, failover, or other Planner-decision events. On completion, check fresh task-scoped `[DONE]` and matching `[MECHANICAL_AUDIT]` once; idle queues and stale records do not establish completion.
4. **Verify.** Require passing audit, valid source pointers, clean product tree, and headed, nonempty `.reports/<slug>/SUMMARY.md` (≤5 KB; line 1: `<!-- REPORT_META: Task=<id> | Commit=<sha> -->`) covering topology, coupling bottlenecks, and the Expand–Migrate–Contract matrix. Require `03-micro.md` with AST skeletons from `nightshift/extract_skeleton.sh` and 10-line slices. `[DEAD_END]` and healthy-excluded-subsystem claims require isolated passing probes or runtime evidence.
5. **Handoff.** Send only verified seams to Planner; never invent implementation tickets:

   ```text
   Seam: <public interface or module>
   Target Files: <bounded paths>
   Callers: <verified callers>
   Glossary Additions: <domain terms, if any>
   Refactor Strategy: <Vertical-Slice | Expand-Migrate-Contract>
   ```

## Code index

Navigation map: `nightshift/.scratch/code-index/INDEX.md` (at most 8 KiB).
Entries show symbol kind, owner-qualified name and line; counts stay in detailed queries.
Symbol lookups accept `Type.name`; reference/caller queries use simple names.
Read it after script approval; request compact queries for detailed evidence
(`python` on Windows):

```sh
python3 nightshift/worker_runtime.py code-index query callers NAME --scope project --format compact
python3 nightshift/worker_runtime.py code-index build
```

**Trust:** Cached index evidence is untrustworthy while indexed sources/settings are
Git-dirty, even if HEAD matches. The script checks freshness and blocks queries/builds
until clean. Commits affecting indexed inputs refresh automatically.

**Unavailable:** For dirty inputs, finish the task's
commit/rollback workflow to restore clean, preserving unrelated work. Rerun `build`
above, then retry the query; `current` or `rebuilt` confirms a usable index.

**Output:** Build JSON returns `summary_path` for the map and `index_path` for
`nightshift/.scratch/code-index/index.json`, the script-owned file/symbol preview cache. Detailed evidence
is parsed on demand; query results go to stdout without a saved report.
