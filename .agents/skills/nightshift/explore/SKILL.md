---
name: explore
description: "Deep codebase and workspace seam explorer. Discovers caller topology, extracts AST skeletons, and audits boundaries across local repo and workspace references."
---

# Explore: Seam & Topology Discovery

Physical discovery engine for mapping candidate seams, call-sites, and interface skeletons before planning or modifying code.

---

## 1. Scope & Workspace Boundaries

- **Local Repository**: Primary exploration target on disk.
- **Workspace References (`ADDITIONAL_DIRS`)**: When configured in `.worker.env`, explore sibling projects in the parent workspace (e.g. `/Volumes/Vault500G/workspace/SharedLib`) for reference interfaces, schemas, and porting sources.
- **Boundary Invariant**: Stay strictly within the declared workspace boundary; never access unrelated host files.

---

## 2. Two-Tier Exploration Protocol

### Tier 1: Instant Seam Probe (Terminal A, Sub-Second)
Verify known or leaf targets without token bloat:
```bash
test -f <path> && git grep -n "<symbol>" <path>          # 1. Physical existence
git log -n 1 --oneline -- <path>                         # 2. Last touch (or: git log -n 1 -S "<symbol>")
./scripts/extract_skeleton.sh <path>#L<line>             # 3. AST skeleton without loading full file
```

### Tier 2: Deep Background Probe (Terminal B, Ephemeral Dossier)
Use when caller topology is unknown, cross-module boundaries are affected, or compiler probes are required:
1. **Dispatch `[RESEARCH]` Ticket**: Write to `tasks.txt` (if daemon is active, preempt to line 1 via `scripts/reorder_queue.sh`):
   ```text
   TASK-001 | LEVEL: 1 | TARGET: .reports/<issue-slug>/SUMMARY.md | ACTION: Map callers and extract interface skeletons for <component> | VERIFY: REPORT_ONLY
   ```
2. **Worker Protocol**:
   - Product code is strictly read-only (`git status` 100% clean).
   - **Compiler Probe**: Temporarily alter signatures, run build to capture 100% of affected call-sites, and immediately run `git restore .`.
   - Output dossier to `.reports/<issue-slug>/`:
     - `SUMMARY.md`: Executive digest (`<= 5 KB`: topology diagram, coupling bottlenecks, Expand-Migrate-Contract matrix, validated pointers).
     - `03-micro.md`: AST skeletons and sampled 10-line context slices.
3. **Audit Gates**:
   - **Artifact Integrity**: Non-empty `SUMMARY.md` with valid markdown headings.
   - **Clean Tree**: Zero uncommitted product edits.
   - **Pointer Validity**: Every `<File>#L<Line>` verified on disk.
   - **Proof of Negative**: Excluding a subsystem or declaring `[DEAD_END]` requires tangible proof (passing isolated probe or log). Speculative exclusions = report rejection.

---

## 3. Explore Handoff Contract

Return a normalized **Seam Digest** to `planner`:
```text
Seam: <Public_Interface_Or_Module_Path>
Target Files: <File_1>, <File_2> (Bounded list)
Callers: <Caller_A>, <Caller_B>
Glossary Additions: <Domain_Terms>
Refactor Strategy: <Vertical-Slice | Expand-Migrate-Contract>
```
