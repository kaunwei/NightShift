# NightShift Planner / Worker / Explore: 24-hour development contract

Status: ready-for-agent

## Problem Statement

NightShift is intended to develop continuously for up to 24 hours without a person dispatching each task. A single long-running agent can accumulate stale conversational context and spend premium reasoning on routine implementation. The system needs a durable work queue, a capable persistent Planner, and fresh, economical Worker sessions that can make verifiable progress without losing project knowledge.

## Solution

Explore supplies read-only, evidence-based knowledge of code ownership, callers, public seams, and report freshness. The Planner continuously reads the accepted specification and current Explore reports, creates dependency-aware tickets, dispatches ready work, evaluates evidence, records acceptance, and advances the queue. Each Worker starts a new session, handles one bounded ticket using a configurable low-cost, fast model, verifies it, and leaves durable output. The Planner uses a stronger model for decomposition, ambiguity, integration, and acceptance. The design optimizes accepted progress per total token; it does not assume a particular savings percentage.

## User Stories

1. As a project owner, I want the Planner to continue drawing ready work from the accepted specification, so development can run unattended.
2. As a project owner, I want a capable model used for planning and acceptance, so important judgment gets adequate reasoning.
3. As a project owner, I want routine implementation assigned to an economical fast Worker model, so continuous work costs less.
4. As a project owner, I want every Worker invocation to start fresh with only durable task context, so stale conversation does not accumulate.
5. As a Worker, I want a ticket with a clear outcome, target scope, verification, dependencies, and constraints, so I can execute without reconstructing the original discussion.
6. As a Planner, I want task size to reflect the shared reliability score, so weak performance leads to smaller and clearer tickets.
7. As a Planner, I want independent tickets to run concurrently and dependent tickets to wait, so parallelism preserves ordering.
8. As a Worker, I want an explicit timeout and action budget for one task, so I can prioritize implementation, verification, and closeout.
9. As a project owner, I want timeout and exhausted budget treated as hard failures, so repeated overruns change ticket size rather than encouraging score inflation.
10. As a Planner, I want to judge quality and evidence and record a compact outcome with an evidence pointer, so the runtime can update score without narrative scoring tokens.
11. As a project owner, I want five consecutive accepted tasks to raise score by one, a rejection to reset that window, and `no_fault` to be excluded, so increases reflect reliable accepted work.
12. As a project owner, I want the second and third hard failure for the same task ID to lower score by one each, so repeated failures affect future task granularity.
13. As a project owner, I want one score shared across providers and Worker identities, so granularity follows system reliability.
14. As a human, I want model selection and manual score correction to remain mine, so automation cannot silently change either.
15. As a Worker, I want to hand off when implementation is done and only verification or Git closeout remains, so closeout can finish within the budget.
16. As a project owner, I want a ghost closeout tied to the original task and barred from editing project files, so it cannot become hidden implementation work.
17. As a Planner, I want reports to carry freshness evidence, so later Workers can reuse current findings without repeating exploration.
18. As a project owner, I want failed work preserved and the task baseline restored for retries, so a retry starts clean while failure remains inspectable.
19. As a project owner, I want isolated Worker worktrees and preview artifacts, so work does not disrupt my checkout and successful output is easy to inspect.
20. As a human, I want to pause, steer, or reject the queue at meaningful points, so I can direct unattended work without managing routine steps.
21. As a project owner, I want unresolved product intent or a real external blocker escalated, so the Planner does not invent requirements.
22. As a project owner, I want clear work to proceed without repeated approval, so unattended development does not stall on routine dispatch.
23. As a project owner, I want outcomes, verification, attempts, confidence, and commits or reports recorded, so continuous work remains auditable.
24. As a project owner, I want total tokens measured across planning, workers, retries, review, and verification, so model choices reflect cost per accepted task.
25. As a project owner, I want quality and throughput measured separately, so speed or low token use cannot replace acceptance.
26. As a Planner, I want Explore reports for unknown seams and callers, so I can create tickets from evidence rather than guesses.
27. As an Explore worker, I want to reuse only current reports and validate source pointers, so stale or invalid research does not mislead planning.
28. As a project owner, I want Explore to keep product code read-only and provide a bounded seam digest, so research informs implementation without modifying it.

## Implementation Decisions

- Explore is the read-only seam-discovery role; it creates compact reports with freshness metadata, verified source pointers, caller topology, coupling, and migration strategy. Reports are reusable only while referenced paths remain unchanged; an explicit Explore request runs a fresh probe.
- Planner, Worker, and Explore are NightShift roles, each tested through its CLI/state contract. Durable state includes the specification, queue/dependencies, Explore reports, task outcomes, and shared score. Worker conversation history is not a durable dependency.
- Planner remains responsible for ticket quality, dependency ordering, granularity, acceptance, compact score feedback, and deciding whether work can proceed. Worker handles one claimed ticket per fresh invocation.
- Ticket fields are ID, level, optional dependency, target paths, behavior, verification, forbidden shortcuts, and constraints. Uncertain code topology is investigated with a read-only research ticket; unresolved user intent is escalated.
- Independent ready tickets may run concurrently. Runtime audits enforce declared scope and task rules and own status/progress records.
- Before each dispatch batch the Planner reads the shared score: 5 → L1, 3–4 → L2, 1–2 → L3. The Planner judges quality/evidence; script owns score arithmetic. Five eligible accepts add one up to 5; rejection resets the window; `no_fault` is excluded. Same-task runtime timeout/budget failures lower score on failures two and three. Successful audit clears that task's failure count. Unchanged retries keep the same task ID.
- Timeout is per invocation. AgY retains its native step/turn limit; Codex actions are counted from CLI command events. Preserve the budget formula `base + target_file_count × per_file`; AgY `[EXEC]` markers are part of the step-counting contract.
- `[CLOSEOUT_REQUIRED]` allows one ghost invocation only after implementation is complete. It may verify and perform allowed Git finalization, cannot edit project files, remains attributed to the original task, and is excluded from task/score cadence.
- Completion requires the ticket verification and runtime mechanical audit, followed by Planner acceptance. A successful process exit or commit alone is not acceptance.
- Reports are reusable only while referenced source paths remain unchanged. Failed work is retained for inspection while runtime recovery restores the task baseline. Default isolation uses a Worker worktree and publishes successful previews; in-place mode remains available where required.
- Human controls include model choice, manual score correction, pause/steer/reject, and clarification. Planner continues automatically when scope is clear and ready work exists.
- Measure total tokens per accepted task alongside quality and cycle time; include both roles, context loading, retries, review, and verification.

### Collaboration SOP and decision ownership

- **Continuous loop:** check `PAUSE`; read status/queue; read domain docs and current Explore report; read shared score; select/size ready work; enqueue the full known dependency graph; run/wait for Workers; inspect audit and evidence; record Planner outcome; accept/integrate or remediate; repeat while work is ready. Stop for a human only on missing product intent, required authorization, quota exhaustion, or a real blocker.
- **Planner owns:** spec interpretation; architecture and seam choices; decomposition/dependency graph; task levels; first-time alignment where direction is ambiguous; deciding dispatch concurrency; interpreting logs/reports; quality/confidence judgment; `accept`/`reject`/`no_fault` feedback; corrective ticket design; acceptance and integration.
- **Runtime owns:** queue claim/locking, pause and polling, process launch, per-invocation timeout and action budget, provider quota detection/switching, status/progress/log writes, worktree setup, mechanical audits, failure snapshot/rollback, report archiving, shared score arithmetic, and preview publication.
- **Worker owns:** one ticket's bounded implementation or research, executing the declared verification, reporting facts/evidence/attempts/confidence, and committing only verified in-scope changes. Worker does not set score, widen `TARGET`, change models, edit runtime-owned progress, or turn closeout into implementation.
- **Explore owns:** read-only source topology discovery for the Planner. Reports contain topology/callers, interface skeletons, coupling bottlenecks, source pointers, and migration strategy. Explicit Explore invocation requests a new probe; cache reuse is allowed only when source references remain current.
- **Queue ticket contract:** `TASK-ID | LEVEL | [AFTER: TASK-ID] | TARGET: paths | ACTION: observable change | VERIFY: command | FORBIDDEN_SHORTCUTS: ... | CONSTRAINTS: ...`. `[GUIDANCE]` carries human clarification. New IDs mean changed scope/granularity; unchanged retries keep the original ID.
- **Task type contract:** `[CODE: FIX]` may change product files but not tests. `[CODE: REFACTOR]` may change declared tests, preserves assertion count, and proves structural closure. `[CODE: EXPAND/MIGRATE/CONTRACT]` is phased green-to-green. `[DIAGNOSTIC]` proves a failing repro without changing product code. `[RESEARCH]` leaves product files untouched and emits validated reports. `[BENCHMARK]` reports measured results.
- **Granularity:** L1 at score 5 gives bounded acceptance intent/paths and lets Worker choose internals. L2 at score 3–4 names target files, signatures/error boundaries, and deterministic verification. L3 at score 1–2 gives exact behavior, fixtures, and red/green/verify steps. L2 deletion ceiling is 150 lines; L3 is 40; L1 is target bounded. Multi-interface/refactor gate requires inseparability, one cohesive vertical slice, score-compatible blueprint (L3 below 3), and topology proof.
- **Planner acceptance SOP:** first require mechanical audit PASS, verification exit 0, at least one test for code tasks, whitelist PASS, and clean tree. Then judge requested behavior, evidence quality, test relevance, scope, report pointer validity, and declared confidence. A clean first attempt with HIGH confidence may fast-track integration; retries, MED/LOW confidence, critical seams, audit failure, or `[DEAD_END]` require focused diff and code review. `[DEAD_END]` requires an isolated passing test or runtime evidence that the suspected subsystem is healthy while the symptom remains. Record a compact result and evidence pointer; do not write narrative scoring rationale into script state.
- **Confidence contract:** HIGH = first attempt with zero warnings; MED = one or two retries; LOW = brittle result or unverified edge cases. Worker reports attempt trace and evidence pointers; runtime prepends task status and mechanical audit to progress.
- **Cadence and intervention:** every 10 completed tasks, review the last 10 and inspect recent hotspots, then queue a refactor ticket. `NEED_GUIDANCE` waits for a human answer; `NEED_DECOMPOSITION` splits to smaller tickets; `SCOPE_BLOCKED` stops with no penalty; three failed attempts become blocked and require re-slicing. Clean Pivot preserves the session base, archives failed changes, and reissues one coherent slice. Ghost closeout is one continuation, same task ID, no code edits, and no score-window entry.
- **Isolation and steering:** default isolated worktree separates human checkout from Worker work, then publishes successful builds/previews. In-place execution supports projects with fixed hardware/ports. Human can Continue, reorder/tweak queue, create `PAUSE`, or Reject/replan. `ADDITIONAL_DIRS`, model, effort, isolation, and timeout remain configured by the human when needed.

### Runtime script capabilities and state contracts

- **Daemon/queue:** claims one task atomically under a queue lock; preserves comments and task ordering; honors `PAUSE`, polling interval, and run-once mode; calculates progress and budget from queue state; restores quota-exhausted work to the front.
- **Provider execution:** constructs Codex or AgY CLI arguments with configured model/effort/sandbox/approval; streams output; applies an independent timeout per invocation; counts Codex JSONL command events and AgY step markers; detects quota errors only, switches among registered agent commands, persists exhausted-agent state, and stops with a warning only when all registered agents are exhausted. Non-quota CLI errors do not cause provider switching.
- **Outcome states:** success proceeds to mechanical audit and preview; timeout/action-budget/closeout failure are hard failures and lower score on same-task attempts 2 and 3; scope and guidance outcomes are reported without score penalty; ordinary CLI/audit errors are blocked failures; quota exhaustion requeues without marking task failed. Status and progress distinguish idle/running/paused, completed, blocked, scope-blocked, awaiting-guidance, and quota-exhausted states.
- **Score CLI/state:** `score-read` initializes/reads shared 1–5 state and maps score to level. `score-record` serializes updates under a lock, records a bounded feedback history/evidence pointer, applies accept/reject/no-fault/hard-failure rules, and clears hard-failure count on audited success. Planner controls which quality result to submit; runtime owns arithmetic.
- **Git/mechanical audit:** verifies task diff is committed and clean; checks target whitelist; disallows product changes for diagnostic/research; protects tests for FIX; checks assertion non-decrease; enforces L2/L3 deletion limits; runs VERIFY with timeout and port environment; rejects empty test runs; runs full Swift regression when applicable. Research audit checks no product edits, required report artifact/headings, stamps `REPORT_META`, validates source pointers, and runs optional custom verification.
- **Worktree/preview:** `ensure-worktree` creates or reuses the worker branch; `publish-preview` exports successful source/build outputs and version metadata; isolation may be disabled for in-place work.
- **Report cache:** `archive-reports` archives active reports before new research; `archive-overlapping-reports` archives reports whose referenced files changed in a code commit. It is path-based invalidation; it does not semantically re-evaluate unreferenced facts.
- **Failure recovery:** `rollback-failed-task` saves tracked diff and untracked files under failed-task storage, restores the task workspace baseline, and retains queue/progress runtime state needed to report or retry.
- **Status/diagnostics:** `status-write` and `status-display` maintain/read machine status; shell helpers watch worker, reorder queue, print status, extract bounded skeletons, and probe source lines. Status and logs are observability interfaces, not score authorities.
- **Configuration contract:** environment settings choose CLI/agent registry/state, model and effort, timeout, budget base/per-file, task/progress/status/log paths, polling, run-once, isolation, sandbox/approval, preview port, sibling directories, and pause file. Human owns model choice; script reads configuration and must not query model quota proactively.

## Further Notes

### Repository document responsibilities

- `GLOSSARY.md`: canonical NightShift vocabulary used in tickets and reports.
- `docs/adr/`: durable architectural decisions and rationale; relevant ADRs constrain planning.
- `.agents/skills/nightshift/planner/SKILL.md`: Planner's compact workflow, decision ownership, score and acceptance rules.
- Planner `OPERATIONS.md`: detailed dispatch gates, cadence, acceptance routing, recovery, isolation, preview, and interventions.
- `.agents/skills/nightshift/explore/SKILL.md`: report cache, research procedure, audit requirements, and Planner handoff shape.
- `.skills/universal-build-verify.md`: Worker execution contract for task types, limits, retries, verification, commit, progress, and closeout.
- `.worker.env.example` / `.worker.env`: documented defaults / local runtime choices; model and operational settings are configuration, not duplicated policy.
- `.worker.notes.md`: short-lived reusable build/toolchain quirks only; not architecture, task history, or secrets.
- `tasks.txt`, `tasks.done`, `progress.log`: pending queue, completed/outcome history, and latest audit/worker evidence respectively.
- `.worker-score.json` and agent-state file: shared reliability arithmetic state and quota-exhaustion state respectively; these are separate concerns.
- `.reports/<slug>/SUMMARY.md`, `03-micro.md`, and `.reports/.archive/`: active research digest, detailed source skeletons, and invalidated historical reports.
- `worker.status` / `.worker.log`: current machine-readable lifecycle state and execution diagnostics.
- `.preview/`: published successful output/version metadata for checkout-free inspection.
- `test/README.md` and `test/`: public CLI/state regression patterns that protect script behavior without calling live models.
- Matt engineering skills such as `to-spec`, `to-tickets`, `tdd`, and `code-review` are referenced workflows only; this spec does not redefine their behavior or scope.

### Complete NightShift document and script inventory

- **Planner skill:** defines the interactive role, lifecycle from domain/seam understanding through dispatch and evidence-based acceptance, shared score use, and allowed feedback outcomes.
- **Planner operations reference:** defines task-size blueprints, Track A/Track B refactor rules, four refactor gates, full-horizon dispatch, alignment versus auto mode, ten-task review cadence, sentinel waiting, double-funnel acceptance, fast integration/deep review, queue preemption, Clean Pivot, live preview, env steering, Terminal A source firewall, and bounded Git inspection.
- **Explore skill:** defines Terminal A read allowlist, report cache/freshness, explicit versus cache-hit behavior, read-only RESEARCH ticket, watcher/Sentinel handoff, compiler probe restoration, artifact gates, source pointer validation, 5 KB summary, detailed skeleton artifact, and seam digest returned to Planner.
- **Worker execution SOP:** defines per-task skill selection, target whitelist, task archetypes, assertion non-decrease, deletion ceilings, forbidden shortcuts, language/verification/evidence expectations, retry/commit/report contract, AgY step markers, Codex event-based action counting, closeout signal, and repository-note rules.
- **Worker launcher:** requires local env configuration, validates Python and runtime presence, exports only the documented worker settings, and execs the Python daemon. It contains no task-planning prompt; the Python runtime builds that prompt.
- **Python runtime daemon:** owns lock/PID lifecycle; queue polling/atomic claims; pause/run-once; task parsing and budget; agent registry and quota failover; CLI argument construction; subprocess streaming/timeouts; Codex/AgY step accounting; prompt creation; status/progress/logs; score state; worktree/preview; report archives; rollback; Git and mechanical audits.
- **Queue reorder helper:** takes replacement queue content from a file or stdin, obtains the queue lock, and atomically replaces the queue. Planner uses it for urgent preemption or clarified/re-sliced tickets.
- **Worker watcher:** polls queue and worker state without model calls; exits distinctly for completion, blocked/guidance, scope-blocked, or wait timeout. The Planner/Sentinel reads progress evidence after wakeup.
- **Status dashboard:** read-only display of worker lifecycle, preview version, pause flag, completed/queued counts, HEAD commit, and recent progress.
- **Source probe helper:** `probe_line` prints a bounded line-centered slice; `extract_skeleton` lists likely declarations plus an optional slice. Both are Worker-only under the Terminal A firewall and support Explore report validation.
- **Installer/updater:** deploys launcher, runtime, skills, worker SOP, and regression tests into target projects; preserves user config/state and avoids duplicate ignore entries. Installation is in scope only where needed to keep deployed NightShift documents and runtime behavior aligned.

### On-the-fly development acceptance contract

1. Maintain an accepted spec as the durable product goal. Planner turns it into the complete known dependency graph; each ticket is a vertical, independently verifiable increment. Do not wait for a person between clear tickets.
2. Use Explore before ticketing when target seams/callers are unknown. Do not run duplicate research when a current report already answers the question, unless `/explore` is explicitly requested.
3. Before each batch, use the current shared score to set task level. Dispatch only independent ready work in parallel. Queue lock protects script claims and Planner reordering.
4. Worker owns implementation and first-line verification. Runtime independently reruns required verification and audits scope, tests, report artifacts, and repository cleanliness. If runtime audit fails, isolate failed changes, restore the task baseline, record failure, and block or re-slice according to outcome.
5. Planner acceptance is a second funnel: audit PASS is necessary but not sufficient. Planner checks feature intent, credible evidence, test adequacy, task scope, confidence, report freshness, and negative claims. Clean first-pass HIGH can use fast integration; all other risk signals receive focused review and remedial ticketing.
6. Only Planner feedback records accepted quality. Runtime increments/decrements score under the defined cadence; hard runtime evidence bypasses model judgment. Ghost completion and no-fault environment/scope outcomes are excluded from normal acceptance cadence as defined above.
7. Runtime publishes successful previews for live inspection while the isolated Worker continues. Human can hold or redirect the queue. When ambiguity requires product judgment, preserve the question in task/progress state and wait rather than guessing.

These specifications are the behavior contract for future edits to NightShift-owned skills and scripts. Implementation may change internal modules or helper names while preserving these role contracts, state transitions, failure semantics, audit gates, and handoffs. Changes to those externally observable behaviors require an explicit spec update and corresponding CLI/state regression coverage.

### Source audit baseline

The source audit and coverage index in [NIGHTSHIFT_SOURCE_COVERAGE.md](NIGHTSHIFT_SOURCE_COVERAGE.md) enumerate every NightShift-owned input and runtime function. Preserve both the skill requirements above and the as-built behavior below when simplifying; changes to either require an explicit decision.

### As-built behavior and limits (source audit)

The following records what scripts actually do, including differences from the skill contract. These differences are documentation findings, not implementation changes.

1. Queue claims are FIFO: skip blank/comment lines, remove the first task, and preserve the rest under a directory lock. Dependencies are not evaluated by runtime. One daemon processes one task at a time; Planner must arrange dependency order and independent concurrency. Claims are removed before execution, not a durable lease with crash replay.
2. Task field parsing recognizes LEVEL, TARGET, ACTION, GOAL, VERIFY, FORBIDDEN_SHORTCUTS, CONSTRAINTS, DEPENDS_ON. Pipes split fields only when followed by one of those names; AFTER/GUIDANCE are not separately parsed fields. LEVEL defaults to 1. Targets are comma-separated; directory targets count contained files recursively, minimum one; missing/empty targets also count at least one for budget.
3. PID files prevent duplicate daemon instances per Worker ID. Dead/malformed PID files may be replaced; permission failure is treated as an active process. SIGINT/SIGTERM request loop shutdown. Status is updated at lifecycle transitions, not continuously while a model is running. Shutdown removes PID and writes STOPPED, except all-quota exhaustion writes QUOTA_EXHAUSTED.
4. Pause is checked before claims and holds future work, not a running invocation. RUN_ONCE exits when queue becomes empty, rather than after exactly one task. Normal per-task failure records state then the loop continues to remaining tasks; BLOCKED does not automatically stop the entire daemon.
5. Status JSON contains worker identity, OS/platform, isolation/work directory, state/task/elapsed, queue progress, PID, configured model/CLI/timeout, shared score/recommended level, and UTC heartbeat. Completed-count progress counts all non-comment outcome history lines, including failures, not only accepted work.
6. Codex uses exec, JSON output, last-message capture, optional ephemeral/model/effort, approval mode and allowed extra directories. Auto uses approve-for-me; prompt/default uses configured sandbox; bypass skips approval/sandbox. Unknown approval modes fail. Auto mode may stage declared targets and create a wrapper commit when no closeout/blocking marker is present; this occurs before runtime post-flight verification and is not acceptance.
7. AgY uses configured mode/model/sandbox, print-timeout, and existing additional directories. Model effort suffix prevents a duplicate effort argument. CLI help chooses max-turns before max-steps when available. AgY invocation uses the permission-skipping flag. Generic providers receive executable plus prompt and a timeout; no provider-specific action counter is added.
8. Codex counts completed command_execution events only, terminates when count exceeds budget, and checks the count after exit. AgY counts lines matching EXEC/tool marker patterns, rejects successful first calls at or above budget, and checks continuation additions against remaining budget. These are different measures and do not count tokens or every possible model action.
9. Subprocess output streams to console and capture file. Timeout terminates the process group, waits two seconds, then escalates; POSIX and Windows have separate signal paths. Return codes are 124 timeout, 125 action limit, 126 closeout rejection; signalled exits are normalized. A successful CLI containing a provider print-timeout message is also treated as timeout.
10. Codex closeout requires successful auto/approve-for-me execution plus CLOSEOUT_REQUIRED and no blocking marker. AgY closeout is triggered by successful under-budget execution with unchanged HEAD and a non-runtime dirty tree. Both are fresh restricted calls, share the original remaining action budget, have their own invocation timeout, and compare before/after file snapshots. Snapshots compare changed/untracked nonignored file bytes, modes, and symlink targets; this is final-state auditing, not an OS read-only sandbox.
11. Registry entries require unique nonempty IDs, codex/agy/generic provider, and command (or executable alias); model/effort/mode inherit defaults. Exhausted profiles persist and are skipped until state is edited/reset. Only failed non-timeout calls with recognized quota/rate-limit/429/resource-exhausted/billing/credit patterns trigger failover; partial work is rolled back between providers. All exhausted requeues the task at the head and stops without a failed-task entry. No automatic quota-reset detection or preflight query exists.
12. Score state version 1 contains score, success_window, per-task failures, and feedback (last 20 timestamped entries). It initializes to 5, validates its shape, writes atomically, and uses a bounded lock wait. Accept entries are not deduplicated by task ID. Hard failure does not reset the accept window; reject does. Runtime success clears failures but does not add an accept. Scope/guidance are not automatically recorded as no_fault; Planner must submit quality feedback.
13. Git audit checks non-runtime dirty/untracked state, committed changes since base, diagnostic product paths, test naming patterns, assertion counts, deletions, and declared targets. It has explicit exemptions: runtime/report paths; test-refactor-approved can authorize test edits; large-deletion-approved or unrestricted bypass deletion limits; unrestricted/multi-interface and diagnostic/research bypass normal target checking. Missing TARGET skips whitelist checks. These exemptions must be retained or deliberately revised.
14. Code VERIFY runs only if supplied. Nonzero exit rejects; known zero-test output patterns reject; Swift projects run a full regression after a successful nonempty VERIFY. There is no universal parsed test count or compiler/linter-warning detector. A PASS journal line prints Tests_Run >=1 even when this was not measured. The skill requires real verification and Planner must check its evidence.
15. Diagnostic audit permits a failing verification except recognized compile/syntax/link failure patterns; it does not prove that the failure is an assertion. Research audit checks dirty state/artifact/headings, adds metadata when absent, and checks only the first five recognized pointers and only their existing-file line upper bounds. Missing referenced files, 5 KB limit, required skeleton attachment, all pointer validity, and proof-of-negative are not fully enforced by script. Existing metadata is not revalidated against HEAD.
16. Research artifact selection uses declared file first, then a SUMMARY under reports, then a research Markdown fallback. Code/research custom VERIFY has 180-second default audit timeout and receives PORT/TEST_PORT. Research REPORT_ONLY/none skips command verification. Audit outputs status/error/verify_exit/messages; CLI returns the JSON report rather than using the guard status as its process exit.
17. Worktree setup creates/reuses the frontier branch from HEAD; fast-forwards only when the branch is an ancestor and the tree is clean. It copies env files, symlinks dependency caches and shared reports. Session startup resets the session-base tag. Multiple Worker IDs still share the default isolated directory/branch unless arranged externally.
18. Preview exports committed source through Git archive plus build/bin, target/debug, bin, dist; rejects unsafe archive paths/links; writes task/commit/summary/time metadata. It overlays existing preview contents without removing obsolete files. Publication errors are logged without failing an otherwise audited task. Preview is not Planner acceptance or integration.
19. New research archives all nonhidden active report entries. Code overlap invalidation uses changed-path substring matches in each active summary; it does not hash every dependency or scan arbitrary source relationships. Diagnostic commits do not trigger overlap invalidation. Archive names include timestamps.
20. Rollback saves unstaged tracked diff, status, and nonignored untracked files, then restores worktree contents while excluding specified runtime paths. It does not reset HEAD, undo staged changes/commits, or restore ignored files. Clean Pivot is a separate Planner recovery policy and requires authorized destructive recovery scope.
21. Queue reorder replaces the complete queue from an existing file argument or stdin; there is no implemented prepend subcommand. It shares the directory lock, writes through a temporary file, and retries lock acquisition; after the retry threshold it attempts to remove the lock. Caller supplies reordered/prepended content.
22. Watcher exit codes are 0 empty queue with IDLE/STOPPED, 1 BLOCKED/AWAITING_GUIDANCE, 2 wait timeout, 3 SCOPE_BLOCKED. It searches progress for PASS but does not prove the latest record passed. QUOTA_EXHAUSTED is not a special watcher exit and may wait until timeout. Defaults are one hour/five seconds. Status dashboard shows HEAD and outcome counts, not proof of Planner acceptance.
23. Both source helpers require NIGHTSHIFT_WORKER=1; probe prints numbered context around a requested line, while skeleton uses declaration-pattern matching capped at 40 lines, not a compiler AST. Both support file-plus-line or file#L syntax. Language hints cover Swift/Python/TS/JS/Rust/Go.
24. Installer requires exactly one existing target, resolves physical paths before its self-install guard, and no-ops on self-install. It detects install/update, overwrites deployed runtime/helpers/skills/examples/tests, preserves an existing skill manifest, env/queue/history/notes, initializes missing state/legacy granularity metadata, removes named obsolete skill directories, adds missing ignore entries once, and performs deployed Bash/Python syntax checks. It does not alter target AGENTS/CLAUDE/README. update.sh shares installer behavior. It does not run the regression suite as part of installation.
25. Skills retain requirements not enforced by runtime: Terminal A firewall with intervention exceptions, full-horizon slicing, four refactor gates, Track A/B thresholds, ten-task review, fast/deep acceptance, fast-forward integration, human clarification, compact evidence, confidence meanings, zero warnings/lint, no unsafe shortcuts, bounded notes, and authorized Clean Pivot. A resident Planner agent must execute this SOP; the daemon does not itself read specs, launch a premium Planner, or implement the full dependency graph.
26. Atomic state writes preserve file permissions and replace a sibling temporary file. Queue and score locks have distinct bounded waits. Additional directories must exist to be passed to providers. Child model environments omit registry/state configuration; default noninteractive environment and Worker identity marker are set at daemon startup. Worker IDs namespace PID/log/status/quota state but share score by default.

27. End-to-end startup and helpers still require Bash/Git and shell tools; Windows process-control branches alone do not establish a native Windows deployment contract. Research can currently commit product edits without the research dirty-state check detecting them: product read-only is a skill requirement, not complete script enforcement. Planner/Explore are agent skills, not standalone implemented CLI schedulers.

## Testing Decisions

- Test each NightShift role at its highest stable CLI/state contract. Assert observable dispatch, report freshness/artifacts, persisted state, process outcome, audit, or handoff; avoid private helpers, prompt wording, and chain-of-thought. Planner/Explore CLI/state seams describe role-level verification, not a claim that separate executable schedulers already exist.
- Planner tests cover queue selection/dependencies, score-to-level mapping, feedback, evidence-based acceptance, stop/continue and recovery after a Worker exits.
- Worker tests cover fresh invocation, model/effort, timeout/budget propagation, target/archetype enforcement, verification, progress/commit, hard-failure classification, and restricted closeout attribution.
- Explore tests cover read-only behavior, report metadata and pointer validation, invalidation/archive, bounded report artifacts, and seam-digest output.
- Cross-role tests pass a Planner-created ticket to a fresh Worker, audit its result, expose compact evidence, and select the next eligible ticket without losing dependency or score state.
- Prior art is the standard-library Worker runtime suite covering queue/polling, Codex/AgY CLI, timeout, mechanical/Git audit, reports, rollback, score transitions, and ghost closeout. Use deterministic fake CLIs and repository states; tests must not contact models or consume tokens.
- A good test asserts externally visible behavior through the role's CLI/state interface, not its implementation details.

## Out of Scope

- Automatic model changes, Planner self-scoring, or using model-reported confidence as score arithmetic.
- Ghost closeout implementation or treating it as a new ticket.
- Accepting work solely because it was fast, cheap, exited successfully, or committed.
- Promising token savings before comparable work is measured.
- Removing human pause, clarification, model selection, or score correction.
- Requiring a specific vendor, tracker, language, build system, or test framework.

### Architecture tradeoffs

The architecture trades repeated coordination and context loading for role specialization, fresh Worker sessions, and durable handoffs. It should perform best when tickets are independently verifiable, reports stay current, and Workers succeed quickly; tiny tickets and retries can erase savings. Future skill or script changes should preserve this contract or deliberately revise it.

Matt skills such as to-spec, to-tickets, tdd, and code-review are workflow references for agents using NightShift. They do not define NightShift runtime behavior and are outside this spec implementation scope. The selected NightShift test seams are Planner, Worker, and Explore CLI/state interfaces; cross-role tests cover their durable handoff.
