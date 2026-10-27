# Dependency index trial

- Specification: [spec.md](spec.md), stored under the user-selected todo directory with `ready-for-agent` status.
- Design record: [design.md](design.md).
- Ticket drafts: [01](tickets/01-query-swift-structure.md), [02](tickets/02-query-references-callers.md), [03](tickets/03-single-index-version-safety.md), [04](tickets/04-replay-planner-workflow.md), [05](tickets/05-compare-planner-cost.md).
- Tickets remain review drafts pending breakdown approval. Maintain one file per ticket in the tickets directory; mark them ready-for-agent after approval.
- Proposed testing seam: public script CLI; the trial runner drives that interface. Mechanical tests use temporary Git repositories and fake agents; only the final trial consumes model tokens.

## Blocking graph

01 unblocks 02 and 03. 04 can start immediately and does not depend on an index. 05 is blocked by 02, 03, and 04.

## Review requested

Confirm that the public CLI is the intended testing seam, that slices fit a fresh context window, that the blocking edges are necessary, and whether tickets should be merged or split. GitHub publication is unavailable because the CLI is not authenticated; local fallback is configured by the project.

## Ticket 01 CLI

See [code index instructions](../../nightshift/tools/README.md) for the manual build, definition query, import query, generated index location, and coverage limits. The first implementation indexes declarations and import syntax only; it does not resolve references or callers.
