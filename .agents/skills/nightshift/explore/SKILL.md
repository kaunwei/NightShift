---
name: explore
description: "Discover codebase seams, caller topology, and AST skeletons via background [RESEARCH] probes before planning or modifying code."
---

# Explore

Map candidate seams, call-sites, and interface skeletons before planning or editing code.

## 1. Terminal A Source-Code Firewall & Report Freshness

- **`read_file` Whitelist (Terminal A)**: Call `read_file` ONLY on control-plane and report files (`.reports/<current-slug>/SUMMARY.md`, `progress.log`, `tasks.txt`, `.worker.notes.md`, `GLOSSARY.md`, `docs/`, and skill files). **NEVER call `read_file` on product or test source code** (`src/`, `include/`, `lib/`, `Sources/`, `tests/`, `firmware/`, etc.).
- **Report Freshness (`REPORT_META`)**: Read only `.reports/<current-slug>/SUMMARY.md` whose line-1 `<!-- REPORT_META: Task=<id> | Commit=<sha> -->` matches the active task and `HEAD`. Never read `.reports/.archive/` (`worker.sh` auto-archives prior reports before new `[RESEARCH]` runs and after `[CODE]` commits).
- **Scope**: Local repo plus any sibling workspace paths in `.worker.env` (`ADDITIONAL_DIRS`).

## 2. Exploration Protocol (Default to Tier 2)

### Step 1 (Default): Tier 2 Background Probe (`tasks.txt` + Queue Sentinel)
When `/explore` is invoked, do NOT inspect source files in Terminal A. Immediately dispatch a background `[RESEARCH]` task and wait for its `SUMMARY.md`:
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
   - Output `.reports/<issue-slug>/SUMMARY.md` (`<= 5 KB` executive digest: topology, coupling bottlenecks, Expand-Migrate-Contract matrix, validated `<File>#L<Line>` pointers) and `03-micro.md` (AST skeletons via `scripts/extract_skeleton.sh` + 10-line slices).
   - **Audit Gates**: Artifact Integrity (non-empty `SUMMARY.md` with headings + `REPORT_META` stamp), Clean Tree (0 product edits), Pointer Validity (verified on disk), and Proof of Negative (declaring `[DEAD_END]` or excluding a subsystem requires a passing isolated probe or log; speculative exclusion = rejection).

### Step 2 (Exception Only): Tier 1 Pin Verification (Terminal A)
Only when verifying a single known `<path>#L<line>` pin in Terminal A, run these 3 whitelisted shell commands (never `read_file` on source files):
```bash
test -f <path> && git grep -n "<symbol>" <path>          # 1. Physical existence
git log -n 1 --oneline -- <path>                         # 2. Last touch (or: git log -n 1 -S "<symbol>")
./scripts/extract_skeleton.sh <path>#L<line>             # 3. AST skeleton without loading file body
```

## 3. Handoff Contract

Read `.reports/<issue-slug>/SUMMARY.md` and return a normalized **Seam Digest** to `planner`:
```text
Seam: <Public_Interface_Or_Module_Path>
Target Files: <File_1>, <File_2> (Bounded list)
Callers: <Caller_A>, <Caller_B>
Glossary Additions: <Domain_Terms>
Refactor Strategy: <Vertical-Slice | Expand-Migrate-Contract>
```
