---
name: explore
description: "Discover codebase seams, caller topology, and AST skeletons via background [RESEARCH] probes before planning or modifying code."
---

# Explore

Map candidate seams, call-sites, and interface skeletons before planning or editing code.

## 1. Terminal A Source-Code Firewall & Report Cache

- **Terminal A Inputs (`read_file` Whitelist)**: Read ONLY `.reports/<slug>/SUMMARY.md`, `.worker.notes.md`, `GLOSSARY.md`, `progress.log`, `tasks.txt`, `docs/`, and skill files. Never inspect product or test source files (`src/`, `include/`, `lib/`, `Sources/`, `tests/`, `firmware/`) via `read_file` or shell scripts in Terminal A.
- **Report Freshness (`REPORT_META`)**: Active `.reports/<slug>/SUMMARY.md` files carry `<!-- REPORT_META: Task=<id> | Commit=<sha> -->` on line 1. `worker.sh` automatically archives any report to `.reports/.archive/` as soon as a `[CODE]` commit modifies any file referenced in that report, or before a new `[RESEARCH]` task begins. Any report still in `.reports/<slug>/SUMMARY.md` is live; never read `.reports/.archive/`.
- **Scope**: Local repo plus any sibling workspace paths in `.worker.env` (`ADDITIONAL_DIRS`).

## 2. Background `[RESEARCH]` Probe (`tasks.txt` + Queue Sentinel)

When `/explore` is invoked or target seams are missing from active `.reports/<slug>/SUMMARY.md` and `.worker.notes.md`:
1. **Enqueue `[RESEARCH]` Ticket**: Write to `tasks.txt` (or preempt to line 1 via `scripts/reorder_queue.sh` if the worker daemon is active):
   ```text
   TASK-001 | LEVEL: 1 | TARGET: .reports/<issue-slug>/SUMMARY.md | ACTION: [RESEARCH] Map callers and extract interface skeletons for <component> | VERIFY: REPORT_ONLY
   ```
2. **Launch Queue Sentinel**:
   ```json
   {"Subagents":[{"TypeName":"self","Role":"Queue Sentinel","Prompt":"Run `bash scripts/watch_worker.sh 3600`. When it exits, read `head -n 15 progress.log` and report whether the research task completed or blocked."}]}
   ```
3. **Worker Execution & Mechanical Audit (`worker.sh`)**:
   - Product code stays 100% read-only (`git status` clean).
   - **Compiler Probe**: Temporarily alter signatures, run build to capture 100% of call-sites, and immediately run `git restore .`.
   - Output `.reports/<issue-slug>/SUMMARY.md` (`<= 5 KB` executive digest: topology, coupling bottlenecks, Expand-Migrate-Contract matrix, validated `<File>#L<Line>` pointers) and `03-micro.md` (AST skeletons via Worker-only `scripts/extract_skeleton.sh` + 10-line slices).
   - **Audit Gates**: Artifact Integrity (non-empty `SUMMARY.md` with headings + `REPORT_META` stamp), Clean Tree (0 product edits), Pointer Validity (verified on disk), and Proof of Negative (declaring `[DEAD_END]` or excluding a subsystem requires a passing isolated probe or log; speculative exclusion = rejection).

## 3. Handoff Contract

Read `.reports/<issue-slug>/SUMMARY.md` and return a normalized **Seam Digest** to `planner`:
```text
Seam: <Public_Interface_Or_Module_Path>
Target Files: <File_1>, <File_2> (Bounded list)
Callers: <Caller_A>, <Caller_B>
Glossary Additions: <Domain_Terms>
Refactor Strategy: <Vertical-Slice | Expand-Migrate-Contract>
```
