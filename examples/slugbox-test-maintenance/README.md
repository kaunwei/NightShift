# SlugBox resize pilot

These files describe the accepted `b8706aa` observation migration. Copy the three JSON documents into a disposable Git snapshot's `.nightshift/` directory to exercise queries. Keep them nonignored or explicitly tracked; ignored local-only relations are rejected. All other cases remain legacy and continue to execute.

`history.json` is an explicitly retrospective import. It is not a maintenance authorization or a receipt from the new runtime. The requirement did not change; the case identity and its generation remain the same. Do not replay the product repair.

Before enabling traceability in the live project, verify the current revision and Worker state, review the imported relation, and configure complete inventory in the selected runner. Keep an authorizing ticket's decision references explicit. Do not copy historical imports into the immutable new-change directory.

`inventory-config.example.json` is the complete-discovery command object to adapt for the selected runner's `acceptance.inventory`. Paths are literal argv entries; replace the example paths before use.

`slugbox-docs.patch` corrects the remaining hot-count and explicit atomic-group descriptions. It was refreshed and checked against SlugBox `04d010e`; intervening hot-count and retirement-documentation updates are preserved. Apply only after checking the then-current revision with `git apply --check`, followed by `git apply` at an idle-runner boundary. This task did not modify the live checkout.
