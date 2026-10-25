# NightShift source coverage index

Baseline: 2026-10-25, updated for external adapters, the Aider RepoMap/Ollama Explore path, per-registration scores, env-file-free configuration, in-place execution and on-demand trials. Companion to [NIGHTSHIFT_SPEC.md](NIGHTSHIFT_SPEC.md). This index records every NightShift-owned skill/reference, launcher, runtime, helper and installer/update entry. Matt skills are references only.

## Preservation rule

For every later simplification, compare the changed source hashes and each affected function/skill clause with the spec. A source row is not proof of behavioral equivalence: review its conditions, outputs, failure cases, exemptions, and skill-only requirements. Additions need new spec entries; intentional removals need an explicit decision. Keep differences from desired behavior visible instead of silently declaring them implemented.

## Source inventory

| Source | SHA-256 |
| --- | --- |
| [.agents/skills/nightshift/explore/SKILL.md](../.agents/skills/nightshift/explore/SKILL.md) | 7f721810ae7d94164ae50a90f434657df34c06987ebccbe822d9ebb89551b391 |
| [.agents/skills/nightshift/planner/SKILL.md](../.agents/skills/nightshift/planner/SKILL.md) | f55fdf5fb66f5fea19da8fcd83673936d8c76082a73d53bfe9e6f8bd89951138 |
| [.gitignore](../.gitignore) | 70e4b4166a26ad333e6d637c5548202756c86d766a75f885862b1f49874b753b |
| [.skills/universal-build-verify.md](../.skills/universal-build-verify.md) | e65a72134c609d22936a9943b5edbdd4be350300ec57880da1e11031ae6157ef |
| [README.md](../README.md) | 2184cdf0f0eb91b8c004b73f3b7df821a91312dd9f49c3bd32f2207a9fb3cb93 |
| [scripts/adapters/agents.json](../scripts/adapters/agents.json) | 71efea4a203a9eb9a6678a83cb2e5db4409fd74ece9e5da4bb8e9e2d34129959 |
| [install.sh](../install.sh) | be34d79ad7d2511c8c5d93033dbb630e976d5c84a8d2bbe92f78ecf343932950 |
| [scripts/adapters/agy.py](../scripts/adapters/agy.py) | 4e48a4f8afaf3f2b4d086a7c0dfaf0376edc8adb0087964f352a19d074ad52d0 |
| [scripts/adapters/aider.py](../scripts/adapters/aider.py) | d9446c5eaa87452caa23edf31f592a81161f349a8e6bfb623b6a9f00db71cbc2 |
| [scripts/adapters/aider_explore.py](../scripts/adapters/aider_explore.py) | 13ca9c1a7daef513a9c95549c2b8e48b591e6c401e428e6fea6230a51c491b39 |
| [scripts/adapters/codex.py](../scripts/adapters/codex.py) | 1ca11f13f347d7c58dbc2f2a5429abb569273528411c04a3a7ab219bd78d1814 |
| [scripts/adapters/generic.py](../scripts/adapters/generic.py) | fa8626610244c5d1bb6c037a6e6e6a8490a2b04c3c571108ed9b915d99b348e4 |
| [scripts/extract_skeleton.sh](../scripts/extract_skeleton.sh) | 1ed2a93cee0194d1828336a50298ce3d7d8b981875dfaf36bd1adea469e5db01 |
| [scripts/probe_line.sh](../scripts/probe_line.sh) | 6b56db490c2b82dc864617a88c82c49b75d0f759c3ace06dece014b2c2d87cd3 |
| [scripts/reorder_queue.sh](../scripts/reorder_queue.sh) | 5cfc56907dafd4b22960199cfff8a413d8542a1251357867d7b5468bee88210a |
| [scripts/status.sh](../scripts/status.sh) | 2449d0718c5a364e9358947d88e0ab66723b43a4ae866cde9787d636d2f814f2 |
| [scripts/watch_worker.sh](../scripts/watch_worker.sh) | a073c874ac4c05d9a6e976c682155d19be6ad613e6730575b515f8cce2597c0d |
| [scripts/worker_runtime.py](../scripts/worker_runtime.py) | d141b4711d7ba76fb0d7267b389d77bad78f0682a4999f0d49e248dd0720b75a |
| [test/README.md](../test/README.md) | d6d42b638942f532b6934c4d755f32fc45c9693b29a6628b3bdf328b85095942 |
| [test/fixtures/trial-demo/README.md](../test/fixtures/trial-demo/README.md) | 4384b3061cefc038ccc5b01f566f78afaca4984f7204a43e58f20b44d54db63b |
| [test/test_worker_runtime.py](../test/test_worker_runtime.py) | 2e466dce9f0a4c81db44f2a7ae73dd4d9128218ebc61b570e926b2142172b134 |
| [update.sh](../update.sh) | be34d79ad7d2511c8c5d93033dbb630e976d5c84a8d2bbe92f78ecf343932950 |
| [worker.sh](../worker.sh) | bf3f2e87e111a62d3fad6e7cbaaa0dae2fdd2385084efd454aa37ef0c652e74c |

## Runtime function coverage

All 71 top-level runtime functions are mapped below to numbered clauses in the spec's As-built behavior and limits section; nested closures are covered by their owning function. Function anchors and hashes were refreshed by static inventory; this is not a regression-test result.

| Function | As-built clause |
| --- | --- |
| [serialize_workspace_state](../scripts/worker_runtime.py#L40) | 5, 25 |
| [atomic_write](../scripts/worker_runtime.py#L49) | 25 |
| [prepend_progress](../scripts/worker_runtime.py#L69) | 25 |
| [update_planner_review](../scripts/worker_runtime.py#L87) | 12 |
| [read_score_state](../scripts/worker_runtime.py#L126) | 12 |
| [score_task_level](../scripts/worker_runtime.py#L142) | 12 |
| [score_summary](../scripts/worker_runtime.py#L146) | 12 |
| [registered_agent_score_path](../scripts/worker_runtime.py#L151) | 12 |
| [initialize_agent_score](../scripts/worker_runtime.py#L157) | 12 |
| [read_agent_score_state](../scripts/worker_runtime.py#L186) | 12 |
| [append_agent_event](../scripts/worker_runtime.py#L196) | 12 |
| [_read_json_lines](../scripts/worker_runtime.py#L234) | 12 |
| [_watch_agent_events_locked](../scripts/worker_runtime.py#L252) | 12 |
| [watch_agent_events](../scripts/worker_runtime.py#L292) | 12 |
| [acknowledge_agent_event](../scripts/worker_runtime.py#L312) | 12 |
| [record_agent_score_result](../scripts/worker_runtime.py#L342) | 12 |
| [_record_score_result](../scripts/worker_runtime.py#L361) | 12 |
| [record_score_result](../scripts/worker_runtime.py#L391) | 12 |
| [build_ghost_closeout_prompt](../scripts/worker_runtime.py#L412) | 10 |
| [workspace_snapshot](../scripts/worker_runtime.py#L430) | 10 |
| [pop_task](../scripts/worker_runtime.py#L450) | 1–2 |
| [restore_task_front](../scripts/worker_runtime.py#L475) | 1–2 |
| [insert_task_front](../scripts/worker_runtime.py#L497) | 1–2, 20 |
| [parse_agent_registry](../scripts/worker_runtime.py#L529) | 11, 25 |
| [load_agent_registry](../scripts/worker_runtime.py#L576) | 11, 25 |
| [adapter_callback](../scripts/worker_runtime.py#L651) | 6–11 |
| [execute_adapter_protocol](../scripts/worker_runtime.py#L700) | 6–11 |
| [should_failover_agent](../scripts/worker_runtime.py#L788) | 11, 19 |
| [read_agent_state](../scripts/worker_runtime.py#L803) | 11 |
| [agent_supports_task](../scripts/worker_runtime.py#L816) | 11, 19 |
| [execute_registered_agents](../scripts/worker_runtime.py#L823) | 11–12, 19 |
| [progress_bar](../scripts/worker_runtime.py#L949) | 1–2 |
| [poll_next](../scripts/worker_runtime.py#L956) | 1–2 |
| [task_field](../scripts/worker_runtime.py#L994) | 1–2 |
| [write_status](../scripts/worker_runtime.py#L1007) | 5 |
| [display_status](../scripts/worker_runtime.py#L1034) | 5 |
| [run_with_timeout](../scripts/worker_runtime.py#L1052) | 9 |
| [temporary_git_index](../scripts/worker_runtime.py#L1088) | 10 |
| [worktree_tree](../scripts/worker_runtime.py#L1100) | 19 |
| [attempt_audit_trees](../scripts/worker_runtime.py#L1106) | 10, 13 |
| [changed_tree_paths](../scripts/worker_runtime.py#L1118) | 10, 13, 19 |
| [finalize_task_git](../scripts/worker_runtime.py#L1122) | 6, 10 |
| [finalize_structured_adapter_result](../scripts/worker_runtime.py#L1174) | 6, 10 |
| [claim_ghost_allowance](../scripts/worker_runtime.py#L1238) | 10 |
| [run_adapter_ghost](../scripts/worker_runtime.py#L1266) | 10 |
| [execute_adapter_task](../scripts/worker_runtime.py#L1335) | 10 |
| [build_task_prompt](../scripts/worker_runtime.py#L1435) | 6, 25 |
| [env_bool](../scripts/worker_runtime.py#L1465) | 25–26 |
| [acquire_worker_lock](../scripts/worker_runtime.py#L1469) | 3–5 |
| [worker_daemon](../scripts/worker_runtime.py#L1502) | 3–5, 11–12, 17, 19, 25 |
| [git_audit](../scripts/worker_runtime.py#L2095) | 13–16 |
| [run_verify](../scripts/worker_runtime.py#L2168) | 13–16 |
| [first_report](../scripts/worker_runtime.py#L2204) | 13–16 |
| [publish_research_reports](../scripts/worker_runtime.py#L2224) | 13–16 |
| [mechanical_audit](../scripts/worker_runtime.py#L2260) | 13–16 |
| [report_archive_path](../scripts/worker_runtime.py#L2352) | 18 |
| [cleanup_invalid_reports](../scripts/worker_runtime.py#L2363) | 18 |
| [settle_invalid_reports](../scripts/worker_runtime.py#L2380) | 18 |
| [report_source_paths](../scripts/worker_runtime.py#L2414) | 18 |
| [report_staleness](../scripts/worker_runtime.py#L2434) | 18 |
| [refresh_active_reports](../scripts/worker_runtime.py#L2469) | 18 |
| [archive_active_reports](../scripts/worker_runtime.py#L2487) | 18 |
| [archive_overlapping_reports](../scripts/worker_runtime.py#L2500) | 18 |
| [_git_path_state](../scripts/worker_runtime.py#L2505) | 19 |
| [_save_git_path_state](../scripts/worker_runtime.py#L2515) | 19 |
| [_restore_git_path_state](../scripts/worker_runtime.py#L2524) | 19 |
| [_git_names](../scripts/worker_runtime.py#L2540) | 19 |
| [capture_attempt_baseline](../scripts/worker_runtime.py#L2547) | 19 |
| [recover_attempt_baseline](../scripts/worker_runtime.py#L2580) | 19 |
| [rollback_failed_task](../scripts/worker_runtime.py#L2662) | 19 |
| [main](../scripts/worker_runtime.py#L2721) | CLI inventory |

## Complete public CLI inventory

| Command | Contract |
| --- | --- |
| score-read / score-record | JSON score summary/update; state/task/result/evidence inputs |
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

Helpers and deployment: numbered spec clauses 21–26 cover complete file-level behavior, flags, exit states, Worker-only source guard, installation preservation/removal behavior, and syntax validation. update.sh is the installer alias. Runtime defaults belong to the launcher and agent config to the name-keyed registry; the removed worker env file is legacy migration data only. Regression tests are prior art, not additional runtime features.

Review uses source inspection and function/CLI inventory comparison, without launching workers, running regressions or making model calls. Existing skill text that still reads the worker env file or uses shared-score planning is an alignment gap recorded by the main spec, not a supported configuration contract. No runtime or skill implementation changes were made in this documentation update.

