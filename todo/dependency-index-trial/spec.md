# Script-owned dependency index and controlled Planner cost trial

Status: ready-for-agent

Tracker: local Markdown under the user-selected todo directory; GitHub CLI is not authenticated. Ticket breakdown remains a draft until approved. This specification authorizes no automatic runtime integration.

## Problem Statement

During large projects and broad refactors, NightShift's Planner and Worker repeatedly spend time and model tokens discovering project topology, symbol ownership, references, and callers. The Planner uses an expensive model, making its repeated exploration the primary cost concern. Unverified relationships can also mislead decomposition and acceptance.

Research reports already have freshness checks, but they do not supply a reusable dependency index. The previous deterministic exploration experiment is archived and does not establish current functionality or measured savings.

## Solution

Provide manually invoked scripts that maintain one generated dependency index and return bounded, source-backed answers for a task. Scripts control construction, freshness, queries, synchronization, and rebuilding. Agents use the evidence to reason about the task; skills only explain where the index is and how to query or rebuild it.

Start with Matronome and compare the existing workflow with index assistance. Each arm records one Planner session and two sequential Worker task runs: exploration followed by a small code change. Both arms receive identical Planner task tickets from the same baseline, and every arm's product changes are reverted. Measure Planner usage first, while exposing Worker usage, total costs, rebuilding overhead, and evidence quality.

## User Stories

1. As a Planner, I want to find relevant modules without remapping the entire repository, so that decomposition consumes fewer tokens.
2. As a Planner, I want symbol definitions and references with source locations, so that I can verify ownership before assigning work.
3. As a Planner, I want statically resolvable caller evidence, so that I can identify affected boundaries.
4. As a Worker, I want the same query interface, so that I can inspect my task's dependencies with less repeated searching.
5. As an agent, I want bounded query output, so that a large index does not consume my context window.
6. As an agent, I want semantic resolution distinguished from syntactic leads, so that I do not overstate evidence.
7. As an agent, I want unresolved relationships reported explicitly, so that missing evidence does not become a claim of no dependencies.
8. As an agent, I want current source locations, so that I can read the actual implementation before changing it.
9. As a maintainer, I want scripts to own indexing behavior, so that skills do not become a second implementation.
10. As a maintainer, I want one generated index, so that commits and tasks do not accumulate copies.
11. As a maintainer, I want scripts and configuration under Git, so that indexing behavior is reviewable and reproducible.
12. As an agent, I want incompatible source or configuration to trigger an update or rebuild, so that stale evidence is not returned.
13. As a Planner, I want Planner acceptance rollback to invalidate rejected-version evidence, so that replanning uses the accepted source.
14. As a Worker, I want dirty and newly added source changes considered, so that an unchanged HEAD does not imply a fresh index.
15. As a maintainer, I want coordinated access across checkouts, so that one writer cannot corrupt another reader's answer.
16. As an agent, I want explicit tool failure and partial-coverage diagnostics, so that I can fall back to targeted source inspection.
17. As an evaluator, I want byte-identical Planner tickets in both arms, so that task wording cannot explain the difference.
18. As an evaluator, I want isolated agent sessions and research artifacts, so that one arm cannot inherit the other's answers.
19. As an evaluator, I want identical starting product state and recorded model settings, so that the comparison is interpretable.
20. As an evaluator, I want every trial code change and candidate commit reverted, so that the next arm starts fairly.
21. As a project owner, I want pre-existing work protected during restoration, so that the experiment cannot erase unrelated changes.
22. As an evaluator, I want preserved Planner and both Worker records, so that the result can be audited by role and stage.
23. As an evaluator, I want independently checked reference relationships and small-change verification, so that fluent output is not mistaken for correctness.
24. As a project owner, I want measured Planner tokens and supported cost attribution, so that I can assess expensive-model savings.
25. As a project owner, I want Worker and total workflow costs reported separately, so that displaced work is visible.
26. As an evaluator, I want cold builds, reuse, rebuilds, rollback, retries, and fallback timed, so that indexing overhead is included.
27. As an evaluator, I want missing usage and pricing data labeled unavailable, so that estimates are not presented as measurements.
28. As a maintainer, I want a reproducible manual trial before hooks are added, so that automatic integration depends on evidence.

## Implementation Decisions

- Use a script-owned public CLI as the principal product seam: build or rebuild, inspect freshness, and query a requested repository and symbol or path. Exact command names are implementation details.
- Keep indexing behind that seam. Evaluate Swift-capable AST or semantic tooling against real Matronome examples; AST and SCIP are candidates, not selected dependencies. Do not revive a Python-only implementation as if it resolves Swift.
- Cover module relationships, definitions, references, and statically resolvable callers. An actual use of a symbol is not necessarily a runtime call. Report semantic evidence, syntactic leads, and unresolved scope separately; do not promise a complete runtime graph.
- Return bounded results with source locations, evidence classification, source identity, index generation identity, coverage diagnostics, and truncation status. Agents can request further evidence deliberately.
- Maintain one active, untracked generated index per target repository shared across its checkouts. Do not retain version-, ticket-, or worktree-specific index copies. Git stores scripts and configuration.
- Validate compatibility using relevant source content, revision identity, source inventory, build configuration, and indexer configuration/version. Detect relevant dirty changes, additions, deletions, and renames. Exclude generated artifacts from source identity.
- Coordinate readers and writers. Validate the requested checkout before returning evidence; bind each query to one generation and detect source changes during processing. Interrupted or failed updates must not expose a partly written generation as valid.
- After Planner acceptance rollback, update or rebuild the single index for the accepted source. Repeated checkout switching can force repeated rebuilds; measure this cost rather than hiding it.
- Report parse failures and unavailable semantic tooling explicitly. Partial results retain declared limitations; stale results are never silently reused. Fall back to targeted source inspection or compiler probes where needed.
- Existing report-freshness and recovery behavior is prior art, not an automatic integration point for this phase. Leave production Planner/Worker lifecycle behavior unchanged.
- Keep skill changes limited to index location and operational query/rebuild instructions, including concise explanations of returned status. Do not copy the graph, indexing algorithm, or maintenance procedure into skills.
- Freeze one exploration objective and one small-change objective as the Planner's task input for both arms. Preserve exact bytes and hashes. The index-assisted environment additionally exposes the documented tool; this treatment difference must be recorded separately from the identical task tickets.
- Let the Planner derive Worker tickets; preserve those tickets as outcomes rather than forcing identical Worker decomposition. Record one Planner session and two sequential Worker task runs per arm, not two concurrent Workers.
- Run each arm from the same pinned baseline with fresh sessions and separate research records. Preserve artifacts outside the product restoration boundary. Revert all trial product changes and candidate commits after each arm and verify baseline equality before continuing. Protect pre-existing user changes; never reset an unrelated working tree.
- Record model identities, settings, environment/tool versions, input hashes, source identity, actual usage, cache metrics when available, verification output, retries, and restoration evidence. Report unavoidable provider-cache/order effects and single-pair variability.
- Primary success is lower measured Planner token usage with no wrong-version evidence or degraded required-reference correctness. Attribute Planner monetary cost only when model/rate data supports it. Report Worker and total usage separately; Planner savings do not establish net workflow savings.

## Testing Decisions

- Test externally observable CLI behavior and emitted evidence rather than private parser structures or storage layout. Use the highest public seam possible; the trial runner invokes that same seam.
- Prefer the repository's existing standard-library unittest, temporary Git repositories, subprocess CLI invocation, and fake-agent patterns. Mechanical tests must not call paid models.
- Verify definitions, imports, references, and caller leads on small Swift examples with independently known relationships, including overloads, duplicate names, protocol dispatch, and unresolved calls.
- Verify that query output limits report truncation and that unsupported constructs are unknown rather than fabricated edges.
- Exercise compatible reuse, dirty tracked and untracked source changes, deletion, rename, configuration/tool changes, checkout switching, commit changes, and rollback to an earlier accepted revision.
- Exercise simultaneous readers/writers, interrupted rebuilding, parse/tool failures, and source edits during a query. No result may mix generations or claim stale evidence is current.
- Test trial replay with fake Planner/Worker commands: byte-identical Planner tickets, separate sessions/artifacts, two Worker stages, role-specific usage, missing usage, failed verification, failure-path cleanup, and baseline restoration.
- In the real Matronome trial, independently establish reference relationships and a small-change acceptance command before either arm. Recheck source locations and run change verification in each arm. Do not treat previous generated topology reports as ground truth.
- Report Planner input/output/cache usage, Worker stage usage, total available usage, and supported cost calculations. Include first build, reuse, rebuild, rollback, query, retry/fallback, and full-workflow time; script wall time is not itself model token usage.
- If actual provider usage is unavailable, token savings remain unestablished. A single paired run is a pilot, not proof of repeatability or a universal savings rate.

## Out of Scope

- Commit hooks, automatic runtime refresh, acceptance changes, or automatic deployment.
- A universal multi-language index platform, a complete runtime call graph, or claims that static analysis prevents all hallucinations.
- Persistent index history or one index copy per worktree, task, or commit.
- Replacing agent architectural judgment or loading the complete graph into prompts.
- Keeping the experimental Matronome code change or merging trial candidate commits.
- Choosing a new model or changing provider settings between comparison arms to manufacture savings.
- Executing implementation or paid benchmark runs as part of specification/ticket preparation.

## Further Notes

Matronome is a Swift Package Manager project. Swift and SourceKit-LSP are available; SCIP tooling was not found on PATH. No indexing approach has yet been exercised. Existing coordinators provide dependency-recovery candidates; their historical extraction is not assumed to remain pending.

No feature ADR currently establishes a selected indexer or storage implementation. Preserve the public contract while choosing the simplest approach supported by trial evidence.

Public CLI behavior is the proposed test seam, pending the user's seam check. The ticket breakdown is a review draft; publication of agent-ready implementation tickets awaits the requested granularity and blocking-edge review.
