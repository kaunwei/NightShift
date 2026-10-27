# NightShift source coverage index

Baseline: 2026-10-26, updated for external adapters, per-registration scores, env-file-free configuration, in-place execution, on-demand trials, and unified no-response handling. The experimental Aider adapter and deterministic Explore implementation were removed; historical design and trial results are preserved in [DETERMINISTIC_EXPLORE_STRATEGY.md](DETERMINISTIC_EXPLORE_STRATEGY.md) and [DETERMINISTIC_EXPLORE_RESULTS.md](DETERMINISTIC_EXPLORE_RESULTS.md). Companion to [NIGHTSHIFT_SPEC.md](NIGHTSHIFT_SPEC.md). This index records NightShift-owned skills, references, launcher, runtime, helpers, tools, and installer entry points. Skill sources and installed skill files both live under `.agents/skills/` and `.skills/`; `nightshift/` holds deployed runtime code and state.

## Preservation rule

For every later simplification, compare the changed source hashes and each affected function/skill clause with the spec. A source row is not proof of behavioral equivalence: review its conditions, outputs, failure cases, exemptions, and skill-only requirements. Additions need new spec entries; intentional removals need an explicit decision. Keep differences from desired behavior visible instead of silently declaring them implemented.

## Source inventory

| Source | SHA-256 |
| --- | --- |
| [.gitignore](../../.gitignore) | c4a3201f71eeedc867384e177c8d2d761fe7188e7537854631773de0601dde3b |
| [.agents/skills/nightshift/explore/SKILL.md](../../.agents/skills/nightshift/explore/SKILL.md) | 381637e3f90d82fa0fdb9ddcfb30c4103a5f3c200dadf978353c06b5d0c3e997 |
| [.agents/skills/nightshift/planner/SKILL.md](../../.agents/skills/nightshift/planner/SKILL.md) | d5b91113051cfad6a1071c5416c92646b1b663a4480b257a6b5e5980cd8b0fee |
| [.skills/universal-build-verify.md](../../.skills/universal-build-verify.md) | e48ea16cd6f0db848007ee6ac84802d84bf3fa56389affd2f9c0242db2b00719 |
| [nightshift/code-index.toml](../code-index.toml) | fbc96e3391801fe826f77c1aa0a5d8a1ce0100eb6493f964b5d8406325e46f30 |
| [nightshift/adapters/agents.json](../adapters/agents.json) | 1dcce30d5fe2ebe49fa57c4ea108cab7e90f5d50a24ac97117183fe13608d2ea |
| [nightshift/adapters/agy.py](../adapters/agy.py) | 1af2f11c3143d5f6185ee7d8ee67aba11b28076e7d9c1e05e0c3c086601a4eaa |
| [nightshift/adapters/codex.py](../adapters/codex.py) | 4a3b8ce67ff6ae807ac2487676f6e28bc7f20d25af6719fb6f337e634e210af8 |
| [nightshift/adapters/generic.py](../adapters/generic.py) | fa8626610244c5d1bb6c037a6e6e6a8490a2b04c3c571108ed9b915d99b348e4 |
| [nightshift/extract_skeleton.sh](../extract_skeleton.sh) | 210ebbf5f00940d9fab650c10347f7c180838e68a824a779baf0f854391f54d6 |
| [nightshift/probe_line.sh](../probe_line.sh) | 6514cfdd8582fe2508d8779a0d18608201a0f9c655c846f2c5f4c03e49a437e3 |
| [nightshift/reorder_queue.sh](../reorder_queue.sh) | 68bf2e6b6d212393ef8c087ce27c2b29e642ddfe8d38e9b7b77f567fa7f42363 |
| [nightshift/status.sh](../status.sh) | 2896954c5e6972d2c6985a79535b9e6a7cf2325b334d650d4d2dddb57c1257f3 |
| [nightshift/watch_worker.sh](../watch_worker.sh) | 5030632dbebb92a2985e7b0adaae7bdd738c25f15bc2eb265e2adcd9428b9baa |
| [nightshift/worker.sh](../worker.sh) | d430417b8f221222763e0885aa3a7c2d0e9681da2cda4de00e9d22c9005e0cb9 |
| [nightshift/worker_runtime.py](../worker_runtime.py) | 59a8ec1924060551724798a92a54243f6430aa051d1a893fa3ae8b575ba2af51 |
| [nightshift/tools/README.md](../tools/README.md) | a35532892107d432df3c4b2175516b28e4310ec3aee357d3184591c2f960c811 |
| [nightshift/tools/index.py](../tools/index.py) | 3c42160f91ae8152b7a272614dc9e0732493caa7aef6cce65751b952bd199b56 |
| [nightshift/tools/languages.json](../tools/languages.json) | fc7f10de17095f0a0930fd7e344bd4d787ecc57ee4f3c4202224485e718faa13 |
| [nightshift/tools/requirements.txt](../tools/requirements.txt) | b80981036c5a1cdb663fd98341f1a0f70b652a25b125a44308f90afad2913632 |
| [nightshift/tools/setup.sh](../tools/setup.sh) | a2cbd18108502b18d4f1a8ad83c3455a94888fbd6cbe65a4ee53c5c1075b3644 |
| [nightshift/tools/setup.ps1](../tools/setup.ps1) | 31fbe3b44ed2b160342d0b507931f1e23f1ba57f62ceba03ec92d7e4cf0802b6 |
| [nightshift/scratch_review.py](../scratch_review.py) | 146f28c2325e9bfee6c3c94877bb37bffbd9dc45d00db16204f4722df4e7964c |
| [nightshift/install-manifest.json](../install-manifest.json) | 9dd5d9f680653ab32c258d78e73baf5926830c6d70d165a75dddaddff95b5b3e |
| [install.sh](../../install.sh) | 12fea53a8c397697338ac31675795578289d89fb2ad37bbdc864d416ba467163 |
| [remove.sh](../../remove.sh) | 81f147d5efd6e24cf2ba68ae39b97dbbf17ca5fe79fdc55233e1a164f3eeb359 |
| [README.md](../../README.md) | dcb943b41c867909a7f697836c2e4a176e7d403d938b4b4ad4c8b3dbf9b81374 |
| [test/README.md](../../test/README.md) | f08d9ab6eb15eb369421ef3b4bc405c8f0f2dd26f60b89aac24dbc139b6a409b |
| [nightshift/docs/NIGHTSHIFT_SPEC.md](../docs/NIGHTSHIFT_SPEC.md) | 20cca335a8cb295023fc54bf3b653958218310fc7b53dd4fdea07f009bd77664 |
| [nightshift/docs/PORTING_GUIDE.md](../docs/PORTING_GUIDE.md) | 3e130caf0a8991533d61ed40cefe82222844d1865a5c4548de4e7b613a8eff1f |
| [nightshift/docs/DETERMINISTIC_EXPLORE_STRATEGY.md](../docs/DETERMINISTIC_EXPLORE_STRATEGY.md) | c832795fb51c7e8ad65e66de0116629a70480172d0628217cb3aafb12683e896 |
| [nightshift/docs/DETERMINISTIC_EXPLORE_RESULTS.md](../docs/DETERMINISTIC_EXPLORE_RESULTS.md) | a624dfe4d49bc5fe167e597b71f86e1c3d86610b9e6084fc0e1d3c49721b068c |
## Runtime function coverage

74 top-level runtime functions are mapped below to numbered clauses in the spec's As-built behavior and limits section; nested closures are covered by their owning function. Anchors are refreshed from the current Python AST, and this is not a regression-test result.

| Function | As-built clause |
| --- | --- |
| [serialize_workspace_state](../worker_runtime.py#L43) | 5, 25 |
| [atomic_write](../worker_runtime.py#L52) | 25 |
| [prepend_progress](../worker_runtime.py#L72) | 25 |
| [update_planner_review](../worker_runtime.py#L90) | 12 |
| [read_score_state](../worker_runtime.py#L129) | 12 |
| [score_task_level](../worker_runtime.py#L145) | 12 |
| [score_summary](../worker_runtime.py#L149) | 12 |
| [registered_agent_score_path](../worker_runtime.py#L154) | 12 |
| [initialize_agent_score](../worker_runtime.py#L160) | 12 |
| [read_agent_score_state](../worker_runtime.py#L189) | 12 |
| [append_agent_event](../worker_runtime.py#L199) | 12 |
| [_read_json_lines](../worker_runtime.py#L237) | 12 |
| [_watch_agent_events_locked](../worker_runtime.py#L255) | 12 |
| [watch_agent_events](../worker_runtime.py#L295) | 12 |
| [acknowledge_agent_event](../worker_runtime.py#L315) | 12 |
| [record_agent_score_result](../worker_runtime.py#L345) | 12 |
| [_record_score_result](../worker_runtime.py#L364) | 12 |
| [record_score_result](../worker_runtime.py#L394) | 12 |
| [build_ghost_closeout_prompt](../worker_runtime.py#L415) | 10 |
| [workspace_snapshot](../worker_runtime.py#L433) | 10 |
| [pop_task](../worker_runtime.py#L454) | 1–2 |
| [restore_task_front](../worker_runtime.py#L479) | 1–2 |
| [insert_task_front](../worker_runtime.py#L501) | 1–2, 20 |
| [parse_agent_registry](../worker_runtime.py#L533) | 11, 25 |
| [load_agent_registry](../worker_runtime.py#L580) | 11, 25 |
| [adapter_callback](../worker_runtime.py#L655) | 6–11 |
| [execute_adapter_protocol](../worker_runtime.py#L704) | 6–11 |
| [should_failover_agent](../worker_runtime.py#L825) | 11, 19 |
| [read_agent_state](../worker_runtime.py#L840) | 11 |
| [agent_supports_task](../worker_runtime.py#L857) | 11, 19 |
| [execute_registered_agents](../worker_runtime.py#L864) | 11–12, 19 |
| [progress_bar](../worker_runtime.py#L995) | 1–2 |
| [poll_next](../worker_runtime.py#L1002) | 1–2 |
| [task_field](../worker_runtime.py#L1040) | 1–2 |
| [write_status](../worker_runtime.py#L1053) | 5 |
| [display_status](../worker_runtime.py#L1080) | 5 |
| [run_with_timeout](../worker_runtime.py#L1098) | 9 |
| [temporary_git_index](../worker_runtime.py#L1134) | 10 |
| [worktree_tree](../worker_runtime.py#L1146) | 19 |
| [attempt_audit_trees](../worker_runtime.py#L1152) | 10, 13 |
| [changed_tree_paths](../worker_runtime.py#L1164) | 10, 13, 19 |
| [run_code_index](../worker_runtime.py#L1168) | CLI inventory |
| [code_index_inputs](../worker_runtime.py#L1179) | 6 |
| [ensure_code_index_after_commit](../worker_runtime.py#L1199) | 6 |
| [finalize_task_git](../worker_runtime.py#L1220) | 6, 10 |
| [finalize_structured_adapter_result](../worker_runtime.py#L1278) | 6, 10 |
| [claim_ghost_allowance](../worker_runtime.py#L1342) | 10 |
| [run_adapter_ghost](../worker_runtime.py#L1370) | 10 |
| [execute_adapter_task](../worker_runtime.py#L1439) | 10 |
| [build_task_prompt](../worker_runtime.py#L1539) | 6, 25 |
| [env_bool](../worker_runtime.py#L1571) | 25–26 |
| [acquire_worker_lock](../worker_runtime.py#L1575) | 3–5 |
| [worker_daemon](../worker_runtime.py#L1608) | 3–5, 11–12, 17, 19, 25 |
| [git_audit](../worker_runtime.py#L2305) | 13–16 |
| [run_verify](../worker_runtime.py#L2389) | 13–16 |
| [first_report](../worker_runtime.py#L2425) | 13–16 |
| [publish_research_reports](../worker_runtime.py#L2445) | 13–16 |
| [mechanical_audit](../worker_runtime.py#L2481) | 13–16 |
| [report_archive_path](../worker_runtime.py#L2580) | 18 |
| [cleanup_invalid_reports](../worker_runtime.py#L2591) | 18 |
| [settle_invalid_reports](../worker_runtime.py#L2608) | 18 |
| [report_source_paths](../worker_runtime.py#L2642) | 18 |
| [report_staleness](../worker_runtime.py#L2662) | 18 |
| [refresh_active_reports](../worker_runtime.py#L2697) | 18 |
| [archive_active_reports](../worker_runtime.py#L2715) | 18 |
| [archive_overlapping_reports](../worker_runtime.py#L2728) | 18 |
| [_git_path_state](../worker_runtime.py#L2733) | 19 |
| [_runtime_state_root](../worker_runtime.py#L2743) | 5, 19 |
| [_scratch_state_root](../worker_runtime.py#L2748) | 5, 19 |
| [_git_names](../worker_runtime.py#L2753) | 19 |
| [capture_attempt_baseline](../worker_runtime.py#L2760) | 19 |
| [recover_attempt_baseline](../worker_runtime.py#L2784) | 19 |
| [rollback_failed_task](../worker_runtime.py#L2862) | 19 |
| [main](../worker_runtime.py#L2925) | CLI inventory |

## Complete public CLI inventory

| Command | Contract |
| --- | --- |
| score-read / score-record | JSON score summary/update; state/task/result/evidence inputs |
| code-index | Run the bundled indexer through the parser environment; publish bounded INDEX.md and compact script cache under nightshift/.scratch/code-index; dirty indexed inputs block building/querying, clean HEAD determines reuse |
| agent-events-watch / agent-event-ack | Persist deduplicated capability handoffs and acknowledge/revise events before dispatch resumes |
| attempt-snapshot / attempt-recover | Capture HEAD/index/workspace baseline and archive/restore a stopped failed attempt |
| ghost-prompt | Write restricted prompt for original task |
| queue-pop | Remove and print first non-comment task |
| queue-insert | Idempotently insert a task before pending work under the claim lock |
| task-field | Extract one recognized field, preserving ordinary pipes |
| status-write / status-display | Persist JSON / show state and PID liveness |
| adapter-exec / task-cli | Execute the configured protocol executable; enforce deadlines, cancellation, structured results, verification, script-owned commits, and one private closeout |
| run-timeout | Execute argv, preserve normal exit, return 124 on timeout |
| git-audit | Guard code and explanation for diff/scope/test/deletion failures |
| archive-reports | Archive active nonhidden entries |
| archive-overlapping-reports | Archive summaries containing changed-file paths |
| rollback-failed-task | Preserve failed work and restore project-directory paths with runtime exclusions |
| progress-prepend | Atomically put newest journal entry before history |
| mechanical-audit | JSON status/error/verify_exit/messages; diagnostics on stderr |
| poll-next | NUL-delimited 16-field paused/idle/task claim and progress/budget output |
| daemon | Run configured polling lifecycle |

CLI parsing requires command-specific inputs; malformed configuration, filesystem/JSON/Git errors are reported as worker_runtime diagnostics and exit 2. Full options are discoverable through per-command help; the spec captures behavior rather than duplicating argparse syntax.

## Skill and helper coverage

Planner: lifecycle; full queue/alignment/auto; score ladder and evidence feedback; refactor Tracks A/B and gates; ten-task cadence; sentinel; fast/deep acceptance; guidance/decomposition/blocked; Clean Pivot; on-demand trial task insertion and delivery; English records; source firewall/interventions; bounded Git and host restrictions.

Explore: explicit/cache routing; Terminal A allowlist; sibling scope; research dispatch/sentinel; compiler probe restoration; summary/skeleton/digest shape; metadata/pointers/negative proof; freshness/archive requirements.

Worker contract/prompt: task-type routing; scope stop; test immutability/assertion non-decrease; deletion ceilings; tool markers/actions; forbidden shortcuts/host safety; warnings/lint; three attempts; verifiable facts/negative proof; commit/report/confidence; runtime progress ownership; notes bounds; restricted closeout. Runtime enforcement limits are recorded separately.

Helpers and deployment: numbered spec clauses 21–26 cover complete file-level behavior, flags, exit states, Worker-only source guard, installation preservation/removal behavior, and syntax validation. `install.sh` is the single install/update entry point. Runtime defaults belong to the launcher and agent config to the name-keyed registry; the removed worker env file is legacy migration data only. Regression tests are prior art, not additional runtime features.

Review uses source inspection and function/CLI inventory comparison, without launching workers, running regressions or making model calls. Existing skill text that still reads the worker env file or uses shared-score planning is an alignment gap recorded by the main spec, not a supported configuration contract. This index records the current implementation and is not itself a regression-test result.


Scratch pressure scheduling, completion receipts and the bounded Worker prompt are implemented in `nightshift/scratch_review.py`; see the porting guide’s Scratch review section and `test/test_scratch_review.py`.
