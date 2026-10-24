# NightShift source coverage index

Baseline: 2026-10-24, updated for external adapters, per-registration scores, env-file-free configuration, in-place execution and on-demand trials. Companion to [NIGHTSHIFT_SPEC.md](NIGHTSHIFT_SPEC.md). This index records every NightShift-owned skill/reference, launcher, runtime, helper and installer/update entry. Matt skills are references only.

## Preservation rule

For every later simplification, compare the changed source hashes and each affected function/skill clause with the spec. A source row is not proof of behavioral equivalence: review its conditions, outputs, failure cases, exemptions, and skill-only requirements. Additions need new spec entries; intentional removals need an explicit decision. Keep differences from desired behavior visible instead of silently declaring them implemented.

## Source inventory

| Source | SHA-256 |
| --- | --- |
| [.agents/skills/nightshift/explore/SKILL.md](../.agents/skills/nightshift/explore/SKILL.md) | 20acb1a3011c4b8babaab8bde25f1f775ff73507bff087529aab19e796191ef8 |
| [.agents/skills/nightshift/planner/SKILL.md](../.agents/skills/nightshift/planner/SKILL.md) | c474f96c1471344a45fa4e19cf7212d6c70e80802428b5cc5a8450d6ed9e5109 |
| [.gitignore](../.gitignore) | 6bcb06e87cf8ae73bc3d29f56d420ce9112db6693f8a002b59e6d7426354405c |
| [.skills/universal-build-verify.md](../.skills/universal-build-verify.md) | e65a72134c609d22936a9943b5edbdd4be350300ec57880da1e11031ae6157ef |
| [README.md](../README.md) | 0ce554fa199fb2cb3338b29e74980c2cb3394260aea5c7e8423eea47054c6a4c |
| [agents/agents.json](../agents/agents.json) | ba92e28b8b08ef2a65e8fadfdc16e88a843ee8338591ca79f2b0f41659d50702 |
| [install.sh](../install.sh) | fa87bec5026fa7137f67e57de1cda485cbc6570b90809ed07e9fa88b78558f3b |
| [scripts/adapters/agy.py](../scripts/adapters/agy.py) | ef8c29888ee224b876517b088e215a29f662ad53750d7a43394ada6e93e145d5 |
| [scripts/adapters/codex.py](../scripts/adapters/codex.py) | 01365f98b3591ec5a2de3bd8e0d968fae86beb58460ae0ae320c1f938d6fecfa |
| [scripts/adapters/generic.py](../scripts/adapters/generic.py) | 9ec0467e3f7322f117838963c77c7f483c0e6b5c0cc43ef64f48b78157483df7 |
| [scripts/extract_skeleton.sh](../scripts/extract_skeleton.sh) | 1ed2a93cee0194d1828336a50298ce3d7d8b981875dfaf36bd1adea469e5db01 |
| [scripts/probe_line.sh](../scripts/probe_line.sh) | 6b56db490c2b82dc864617a88c82c49b75d0f759c3ace06dece014b2c2d87cd3 |
| [scripts/reorder_queue.sh](../scripts/reorder_queue.sh) | 5cfc56907dafd4b22960199cfff8a413d8542a1251357867d7b5468bee88210a |
| [scripts/status.sh](../scripts/status.sh) | 2449d0718c5a364e9358947d88e0ab66723b43a4ae866cde9787d636d2f814f2 |
| [scripts/watch_worker.sh](../scripts/watch_worker.sh) | a073c874ac4c05d9a6e976c682155d19be6ad613e6730575b515f8cce2597c0d |
| [scripts/worker_runtime.py](../scripts/worker_runtime.py) | 705f17e5c54f7db4547f8f2a35e95662c6248bce3a1e797a1c1efde7fab7c5a8 |
| [test/README.md](../test/README.md) | d6d42b638942f532b6934c4d755f32fc45c9693b29a6628b3bdf328b85095942 |
| [test/fixtures/trial-demo/README.md](../test/fixtures/trial-demo/README.md) | 4384b3061cefc038ccc5b01f566f78afaca4984f7204a43e58f20b44d54db63b |
| [test/test_worker_runtime.py](../test/test_worker_runtime.py) | 79d56f44ee6e47f979db2296a8a5c15f26980eb55ceaab351f28a306be195692 |
| [update.sh](../update.sh) | 53b5b9d14a3dffa163ad2f765b21b77f067f56876614a0a21dfe0bdb612fa5af |
| [worker.sh](../worker.sh) | 246ad3e355ce6972242f950a2063696fc526e8f68d484d62a2cd0e36cf22395e |

## Runtime function coverage

All 59 top-level runtime functions are mapped below to numbered clauses in the spec's As-built behavior and limits section; nested closures are covered by their owning function. Function anchors and hashes were refreshed by static inventory; this is not a regression-test result.

| Function | As-built clause |
| --- | --- |
| [atomic_write](../scripts/worker_runtime.py#L34) | 25 |
| [prepend_progress](../scripts/worker_runtime.py#L54) | 25 |
| [read_score_state](../scripts/worker_runtime.py#L59) | 12 |
| [score_task_level](../scripts/worker_runtime.py#L75) | 12 |
| [score_summary](../scripts/worker_runtime.py#L79) | 12 |
| [registered_agent_score_path](../scripts/worker_runtime.py#L84) | 12 |
| [initialize_agent_score](../scripts/worker_runtime.py#L90) | 12 |
| [read_agent_score_state](../scripts/worker_runtime.py#L119) | 12 |
| [append_agent_event](../scripts/worker_runtime.py#L129) | 12 |
| [_read_json_lines](../scripts/worker_runtime.py#L167) | 12 |
| [_watch_agent_events_locked](../scripts/worker_runtime.py#L185) | 12 |
| [watch_agent_events](../scripts/worker_runtime.py#L225) | 12 |
| [acknowledge_agent_event](../scripts/worker_runtime.py#L245) | 12 |
| [record_agent_score_result](../scripts/worker_runtime.py#L275) | 12 |
| [_record_score_result](../scripts/worker_runtime.py#L294) | 12 |
| [record_score_result](../scripts/worker_runtime.py#L324) | 12 |
| [build_ghost_closeout_prompt](../scripts/worker_runtime.py#L341) | 10 |
| [workspace_snapshot](../scripts/worker_runtime.py#L354) | 10 |
| [pop_task](../scripts/worker_runtime.py#L374) | 1–2 |
| [restore_task_front](../scripts/worker_runtime.py#L399) | 1–2 |
| [insert_task_front](../scripts/worker_runtime.py#L421) | 1–2, 20 |
| [parse_agent_registry](../scripts/worker_runtime.py#L453) | 11, 25 |
| [load_agent_registry](../scripts/worker_runtime.py#L500) | 11, 25 |
| [adapter_callback](../scripts/worker_runtime.py#L541) | 6–11 |
| [execute_adapter_protocol](../scripts/worker_runtime.py#L590) | 6–11 |
| [should_failover_agent](../scripts/worker_runtime.py#L678) | 11, 19 |
| [read_agent_state](../scripts/worker_runtime.py#L693) | 11 |
| [execute_registered_agents](../scripts/worker_runtime.py#L706) | 11–12, 19 |
| [progress_bar](../scripts/worker_runtime.py#L822) | 1–2 |
| [poll_next](../scripts/worker_runtime.py#L829) | 1–2 |
| [task_field](../scripts/worker_runtime.py#L867) | 1–2 |
| [write_status](../scripts/worker_runtime.py#L879) | 5 |
| [display_status](../scripts/worker_runtime.py#L906) | 5 |
| [run_with_timeout](../scripts/worker_runtime.py#L924) | 9 |
| [finalize_task_git](../scripts/worker_runtime.py#L959) | 6, 10 |
| [finalize_structured_adapter_result](../scripts/worker_runtime.py#L985) | 6, 10 |
| [claim_ghost_allowance](../scripts/worker_runtime.py#L1030) | 10 |
| [run_adapter_ghost](../scripts/worker_runtime.py#L1058) | 10 |
| [execute_adapter_task](../scripts/worker_runtime.py#L1122) | 10 |
| [build_task_prompt](../scripts/worker_runtime.py#L1207) | 6, 25 |
| [env_bool](../scripts/worker_runtime.py#L1240) | 25–26 |
| [acquire_worker_lock](../scripts/worker_runtime.py#L1244) | 3–5 |
| [worker_daemon](../scripts/worker_runtime.py#L1277) | 3–5, 11–12, 17, 19, 25 |
| [git_audit](../scripts/worker_runtime.py#L1789) | 13–16 |
| [run_verify](../scripts/worker_runtime.py#L1853) | 13–16 |
| [first_report](../scripts/worker_runtime.py#L1889) | 13–16 |
| [publish_research_reports](../scripts/worker_runtime.py#L1909) | 13–16 |
| [mechanical_audit](../scripts/worker_runtime.py#L1945) | 13–16 |
| [report_archive_path](../scripts/worker_runtime.py#L2037) | 18 |
| [archive_active_reports](../scripts/worker_runtime.py#L2043) | 18 |
| [archive_overlapping_reports](../scripts/worker_runtime.py#L2053) | 18 |
| [_git_path_state](../scripts/worker_runtime.py#L2078) | 19 |
| [_save_git_path_state](../scripts/worker_runtime.py#L2088) | 19 |
| [_restore_git_path_state](../scripts/worker_runtime.py#L2097) | 19 |
| [_git_names](../scripts/worker_runtime.py#L2113) | 19 |
| [capture_attempt_baseline](../scripts/worker_runtime.py#L2119) | 19 |
| [recover_attempt_baseline](../scripts/worker_runtime.py#L2150) | 19 |
| [rollback_failed_task](../scripts/worker_runtime.py#L2232) | 19 |
| [main](../scripts/worker_runtime.py#L2291) | CLI inventory |

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

