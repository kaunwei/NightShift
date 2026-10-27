# Dependency Index Design Interview

Status: design interview in progress. This records confirmed requirements, not an implementation approval or a selected indexing tool.

## Confirmed requirements

- Use Matronome as the first large-refactor validation project before generalizing to other repositories.
- Reduce repeated Planner and Worker research by providing reusable module relationships, symbol definitions and references, and statically resolvable caller leads. Agents still inspect task-relevant source windows.
- The Planner retains control over commit acceptance. After failed acceptance, the Planner rejects candidate commits, restores the last accepted commit, and replans work. This is a Planner acceptance rollback, not simply a cancelled task.
- Script-based AST or semantic indexing approaches may be evaluated. No particular tool is selected. The intended outcomes are reduced unsupported claims and reduced token use; neither outcome is established yet.
- Maintain one logical structural index for reuse by both roles. Do not accumulate index copies per commit, worktree, or ticket. Git-managed storage and rebuilding are both acceptable options; storage and synchronization are not selected yet.
- Scripts supply structural evidence; agents produce task-specific interpretation and refactor recommendations from that evidence rather than receiving the entire project index.
- Distinguish semantic resolution, syntactic leads, and unresolved relationships. Same-name matches are not proof of binding. Unresolved cases require targeted source inspection or compiler probes.
- Compare current research against index-assisted research using the same task and starting commit. Measure tokens and elapsed time including indexing/query costs, incorrect relationship claims, and missed important dependencies. Verify that acceptance rollback cannot expose rejected-version results.
- Git manages the indexing scripts and configuration; the generated index is untracked. Maintain a single generated index, validate it against source revision/content and tool configuration, and update or rebuild when incompatible. Coordinate readers and writers with a lock and keep each query on a consistent index generation.
- Include repeated rebuilds caused by Planner/Worker checkout switching in the measured cost. A single index is a storage constraint, not a claim that switching versions is free.
- The first trial uses manually invoked build/query scripts. Do not integrate commit hooks or automatic Planner/Worker lifecycle updates before trial results justify integration.
- Begin with current Matronome coordinator dependency-recovery queries, including cross-module references and tests. Exercise commits, uncommitted changes, version switches, and acceptance rollback.
- Scripts own index construction, freshness checks, synchronization, query execution, and rebuilding. Skill documentation only supplies index location and the commands to query or rebuild it; it must not duplicate the indexing algorithm or require agents to maintain index contents.
- Stale, failed, or partially parsed indexes must be reported explicitly. Never silently use stale results or interpret missing resolution as proof of no callers. Return usable partial evidence with its unresolved scope; agents fall back to targeted source inspection when necessary.

## Confirmed trial protocol

- Use an exploration task followed by a small-change task, recording two Worker task runs and one Planner session per comparison arm. This describes task roles, not a requirement for two concurrent Worker processes.
- Compare a baseline arm against an index-assisted arm from the same starting revision with the same tasks and model settings, without sharing research answers between arms.
- Deliver byte-identical task tickets to the Planner in both arms and record their hashes. The Planner's derived Worker tickets are outcomes to preserve and compare, not inputs required to be identical.
- Revert all trial product changes and candidate commits after each arm and verify restoration to the pinned baseline before starting the next arm. Preserve trial evidence outside the restored product tree; do not discard pre-existing user changes or the indexing implementation itself.
- Establish reference relationships by checking the source independently of generated index claims. Include cross-module references and relevant tests.
- The primary outcome is Planner token use and, where actual model/rate data is available, Planner cost. The user prioritizes Planner savings because it uses the expensive model. Record Worker usage and total workflow usage separately so shifted costs remain visible.
- Record first build, compatible-index reuse, checkout switching, dirty edits, commit changes, rollback rebuild, fallback, and overall elapsed time. Script execution itself does not consume model tokens; agent interactions around it do.
- Attribute measured usage to each role and arm. Missing provider usage data means token savings cannot be established; do not substitute an estimate presented as measured usage. Record cache usage when available.
- Report wrong-version evidence, incorrect relationship claims, and missed important dependencies. No stale-version evidence is acceptable. If Planner tokens do not decrease, the trial has not met its primary token-saving goal. Report total workflow changes separately rather than treating Planner savings as proof of overall savings.
- The initial trial yields reproducible findings. Automatic integration is a later decision based on the findings, not a promised outcome.

## Existing evidence

- [DETERMINISTIC_EXPLORE_STRATEGY.md](../../nightshift/docs/DETERMINISTIC_EXPLORE_STRATEGY.md) describes a removed Python AST evidence-index experiment. Its unique-name caller leads were explicitly not proof of semantic binding or runtime execution.
- [DETERMINISTIC_EXPLORE_RESULTS.md](../../nightshift/docs/DETERMINISTIC_EXPLORE_RESULTS.md) records historical trials without establishing repeatability, completeness, or token savings.
- `nightshift/worker_runtime.py` already checks research-report freshness and restores still-valid reports after recovery. It does not provide a persistent dependency index.
- Matronome is a Swift Package Manager project with Core, App, and Core-test targets. Swift, Xcode tooling, and SourceKit-LSP are available on PATH; SCIP tooling was not found on PATH. No indexing approach has been tested.
- Matronome's historical TrainerCoordinator extraction is a possible replay or dependency-recovery benchmark. The coordinator already exists in current source inventory; the historical report is not evidence that extraction remains pending.

## Implementation details to resolve during the trial

- Query interface, result bounds, and evidence locations for consumers of the shared structural index.
- Exact invalidation inputs and synchronization mechanics for the approved single-index model.
- The concrete exploration and small-change task pair, independently checked reference answers, and small-change verification command.
- Trial tooling, runtime budget, storage, and eventual lifecycle integration.

## Interview closeout

The user requested specification synthesis followed by ticket decomposition before implementation. Automatic hooks and runtime integration remain outside the initial trial. The formal specification and draft ticket breakdown are colocated in this todo folder: [specification](spec.md), [overview](README.md), and one draft per file in the tickets directory. Ticket publication awaits breakdown approval.
