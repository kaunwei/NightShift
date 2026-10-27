# 01: Query Swift module structure and symbol definitions

**What to build:** A manually invoked script lets a Planner or Worker build the single generated Matronome index and query bounded module relationships and symbol definitions with source-backed evidence. Evaluate the available Swift tooling while delivering this usable path; no standalone tool-research phase is required.

**Blocked by:** None (can start immediately).

**Status:** draft — pending breakdown and test-seam approval

- [ ] Build and query operate through a public CLI for an explicit repository; scripts and configuration are version-controlled, generated index data is not.
- [ ] One current generated index serves the repository; repeated builds replace or update it without accumulating version or worktree copies.
- [x] Results contain source locations, source/generation identity, evidence classification, coverage limitations, and explicit truncation when bounded output omits matches.
- [x] Definitions and import declarations are verified on independently checked Swift fixtures and current Matronome queries; semantic references/callers remain explicitly out of coverage.
- [ ] Missing tooling, malformed source, and unsupported constructs produce explicit diagnostics rather than invented structure.
- [x] Initial CLI tests cover build-to-query behavior without invoking a model.
- [x] Provide minimal index-location, query, and rebuild instructions usable by both roles; skills do not implement indexing logic (see [Swift structure index](../../../nightshift/tools/README.md)).
