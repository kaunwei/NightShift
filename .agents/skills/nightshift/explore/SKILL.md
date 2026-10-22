---
name: explore
description: "Discover codebase seams, caller topology, and AST skeletons across local repo and workspace references before planning or modifying code."
---

# Explore

Map candidate seams, call-sites, and interface skeletons before planning or editing code.

## 1. Scope & Workspace Boundaries

- **Local Repo**: Primary exploration target on disk.
- **Workspace References (`ADDITIONAL_DIRS`)**: When set in `.worker.env`, explore sibling projects (e.g. `/Volumes/Vault500G/workspace/SharedLib`) for reference interfaces, schemas, and porting sources. Stay strictly within declared workspace directories.

## 2. Two-Tier Exploration Protocol

### Tier 1: Instant Seam Probe (Terminal A, Sub-Second)
Verify known or leaf targets without token bloat:
```bash
test -f <path> && git grep -n "<symbol>" <path>          # 1. Physical existence
git log -n 1 --oneline -- <path>                         # 2. Last touch (or: git log -n 1 -S "<symbol>")
./scripts/extract_skeleton.sh <path>#L<line>             # 3. AST skeleton without full file body
```

### Tier 2: Deep Background Probe (Terminal B, Ephemeral Dossier)
Use when caller topology is unknown, cross-module seams are affected, or compiler probes are needed:
1. **Dispatch `[RESEARCH]` Ticket**: Write to `tasks.txt` (preempt to line 1 via `scripts/reorder_queue.sh` if daemon is active):
   ```text
   TASK-001 | LEVEL: 1 | TARGET: .reports/<issue-slug>/SUMMARY.md | ACTION: Map callers and extract interface skeletons for <component> | VERIFY: REPORT_ONLY
   ```
2. **Worker Protocol**:
   - Keep product code strictly read-only (`git status` 100% clean).
   - **Compiler Probe**: Temporarily alter signatures, run build to capture 100% of call-sites, and immediately run `git restore .`.
   - Write dossier to `.reports/<issue-slug>/`:
     - `SUMMARY.md` (`<= 5 KB` executive digest: topology diagram, coupling bottlenecks, Expand-Migrate-Contract matrix, validated pointers).
     - `03-micro.md` (AST skeletons and 10-line context slices).
3. **Audit Gates**:
   - **Artifact Integrity**: Non-empty `SUMMARY.md` with valid markdown headings.
   - **Clean Tree**: Zero uncommitted product edits.
   - **Pointer Validity**: Every `<File>#L<Line>` verified on disk.
   - **Proof of Negative**: Excluding a subsystem or declaring `[DEAD_END]` requires tangible proof (passing isolated probe or log); speculative exclusion = report rejection.

## 3. Handoff Contract

Return a normalized **Seam Digest** to `planner`:
```text
Seam: <Public_Interface_Or_Module_Path>
Target Files: <File_1>, <File_2> (Bounded list)
Callers: <Caller_A>, <Caller_B>
Glossary Additions: <Domain_Terms>
Refactor Strategy: <Vertical-Slice | Expand-Migrate-Contract>
```
