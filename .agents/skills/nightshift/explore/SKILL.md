---
name: explore
description: "Deep codebase and workspace seam explorer. Discovers caller topology, extracts AST skeletons, and audits boundaries across local repo and workspace references."
---

# Explore: Seam & Topology Discovery

Physical discovery engine for mapping candidate seams, call-sites, and interface skeletons before planning or modifying code.

---

## 1. Scope & Workspace Boundaries

- **Local Repository**: Primary exploration target on disk.
- **Workspace References (`ADDITIONAL_DIRS`)**: When configured in `.worker.env`, explore sibling projects within the parent workspace directory (e.g. `/Volumes/Vault500G/workspace/SharedLib`) for reference interfaces, schemas, and porting sources.
- **Boundary Invariant**: Exploration strictly stays within the declared workspace boundary. Never access unrelated host files.

---

## 2. Two-Tier Exploration Protocol

### Tier 1: Instant Seam Probe (Terminal A, Sub-Second)
Fast verification of known or leaf targets without token bloat:
1. **Physical Existence**:
   ```bash
   test -f <path> && git grep -n "<symbol>" <path>
   ```
2. **Path-Scoped Last Touch**:
   ```bash
   git log -n 1 --oneline -- <path>
   # or symbol-scoped:
   git log -n 1 -S "<symbol>"
   ```
3. **AST Skeleton Extraction**:
   Use `scripts/extract_skeleton.sh` to grab signatures without loading full file bodies:
   ```bash
   ./scripts/extract_skeleton.sh <path>#L<line>
   ```

### Tier 2: Deep Background Probe (Terminal B, Ephemeral Dossier)
Triggered when caller topology is unknown, cross-module boundaries are affected, or compiler probes are required:
1. **Dispatch `[RESEARCH]` Ticket**:
   Planner writes a solitary research ticket into `tasks.txt`. If the worker daemon is currently active, inject the ticket at line 1 via `scripts/reorder_queue.sh` (**Hot Queue Preemption**) so Worker executes it next:
   ```text
   TASK-001 | LEVEL: 1 | TARGET: .reports/<issue-slug>/SUMMARY.md | ACTION: Map callers and extract interface skeletons for <component> | VERIFY: REPORT_ONLY
   ```
2. **Worker Execution Protocol**:
   - Product code is strictly read-only (`git status` must remain 100% clean).
   - Use compiler probes: temporarily tweak signatures, run build to capture 100% of affected call-sites, and immediately `git restore .`.
   - Output structured dossier to `.reports/<issue-slug>/`:
     - `SUMMARY.md`: Executive decision digest (<= 5 KB: topology diagram, coupling bottlenecks, Expand-Migrate-Contract matrix, validated pointers).
     - `03-micro.md`: AST skeletons and sampled 10-line context slices.
3. **Audit Gates**:
   Worker's report is mechanically audited on:
   - Artifact Integrity (valid non-empty `SUMMARY.md` with markdown headings).
   - Clean Tree (0 uncommitted product edits).
   - Pointer Validity (`<File>#L<Line>` verified on disk).

---

## 3. Explore Handoff Contract

When `explore` finishes, return a normalized **Seam Digest** directly to the caller (`planner`):
```text
Seam: <Public_Interface_Or_Module_Path>
Target Files: <File_1>, <File_2> (Bounded list)
Callers: <Caller_A>, <Caller_B>
Glossary Additions: <Domain_Terms>
Refactor Strategy: <Vertical-Slice | Expand-Migrate-Contract>
```
