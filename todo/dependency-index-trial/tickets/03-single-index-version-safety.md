# 03: Keep single-index queries correct across edits and acceptance rollback

**What to build:** The shared script interface checks freshness, reuses compatible data, and updates or rebuilds the one index when Planner or Worker source changes. Queries after edits, checkout switches, and Planner acceptance rollback cannot silently return rejected-version evidence.

**Blocked by:** 01 — Query Swift module structure and symbol definitions.

**Status:** draft — pending breakdown and test-seam approval

- [ ] Freshness considers source revision/content/inventory, relevant build settings, and indexer configuration/version; generated artifacts do not cause endless invalidation.
- [ ] Tracked edits, relevant untracked source additions, deletions, renames, commit changes, and restoration to an accepted baseline are detected.
- [ ] Compatible queries reuse the active generation; incompatible queries rebuild/update or fail explicitly without silently using stale data.
- [ ] Shared access across differing checkouts is coordinated so each result uses one consistent generation; changes during a query trigger safe retry or explicit failure.
- [ ] Interrupted updates, parser failures, and unavailable tools never publish partially written data as a valid generation.
- [ ] Cold build, reuse, query, update/rebuild, and repeated checkout-switch costs are observable for later measurement.
- [ ] Temporary Git repository and CLI tests demonstrate rollback correctness, concurrent access, and failure handling without live models.
- [ ] There is no persistent index history and no automatic commit hook or production runtime integration.
- [ ] Skills only describe where to look and which commands to invoke; scripts own all correctness and maintenance behavior.
