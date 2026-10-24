# NightShift source coverage index

Baseline: 2026-10-24, updated for in-place execution and on-demand trials. Companion to [NIGHTSHIFT_SPEC.md](NIGHTSHIFT_SPEC.md). This index records every NightShift-owned skill/reference, launcher, runtime, helper and installer/update entry. Matt skills are references only.

## Preservation rule

For every later simplification, compare the changed source hashes and each affected function/skill clause with the spec. A source row is not proof of behavioral equivalence: review its conditions, outputs, failure cases, exemptions, and skill-only requirements. Additions need new spec entries; intentional removals need an explicit decision. Keep differences from desired behavior visible instead of silently declaring them implemented.

## Source inventory

| Source | SHA-256 |
| --- | --- |
| [.gitignore](../.gitignore) | 6bcb06e87cf8ae73bc3d29f56d420ce9112db6693f8a002b59e6d7426354405c |
| [.agents/skills/nightshift/explore/SKILL.md](../.agents/skills/nightshift/explore/SKILL.md) | 20acb1a3011c4b8babaab8bde25f1f775ff73507bff087529aab19e796191ef8 |
| [.agents/skills/nightshift/planner/SKILL.md](../.agents/skills/nightshift/planner/SKILL.md) | c474f96c1471344a45fa4e19cf7212d6c70e80802428b5cc5a8450d6ed9e5109 |
| [.skills/universal-build-verify.md](../.skills/universal-build-verify.md) | e65a72134c609d22936a9943b5edbdd4be350300ec57880da1e11031ae6157ef |
| [agents/agents.json](../agents/agents.json) | ba92e28b8b08ef2a65e8fadfdc16e88a843ee8338591ca79f2b0f41659d50702 |
| [install.sh](../install.sh) | 53b5b9d14a3dffa163ad2f765b21b77f067f56876614a0a21dfe0bdb612fa5af |
| [scripts/extract_skeleton.sh](../scripts/extract_skeleton.sh) | 1ed2a93cee0194d1828336a50298ce3d7d8b981875dfaf36bd1adea469e5db01 |
| [scripts/probe_line.sh](../scripts/probe_line.sh) | 6b56db490c2b82dc864617a88c82c49b75d0f759c3ace06dece014b2c2d87cd3 |
| [scripts/reorder_queue.sh](../scripts/reorder_queue.sh) | 5cfc56907dafd4b22960199cfff8a413d8542a1251357867d7b5468bee88210a |
| [scripts/status.sh](../scripts/status.sh) | 2449d0718c5a364e9358947d88e0ab66723b43a4ae866cde9787d636d2f814f2 |
| [scripts/watch_worker.sh](../scripts/watch_worker.sh) | a073c874ac4c05d9a6e976c682155d19be6ad613e6730575b515f8cce2597c0d |
| [scripts/worker_runtime.py](../scripts/worker_runtime.py) | 705f17e5c54f7db4547f8f2a35e95662c6248bce3a1e797a1c1efde7fab7c5a8 |
| [update.sh](../update.sh) | 036e5ffc04345a67866be90b2aa158dda852c74df2cc4b65e121ed3aa3ed60d1 |
| [test/test_worker_runtime.py](../test/test_worker_runtime.py) | 31df5178352c115f387cc34350af29240aaf7e857619f0169c542ed72cc6905c |
| [test/fixtures/trial-demo/README.md](../test/fixtures/trial-demo/README.md) | 4384b3061cefc038ccc5b01f566f78afaca4984f7204a43e58f20b44d54db63b |
| [worker.sh](../worker.sh) | 246ad3e355ce6972242f950a2063696fc526e8f68d484d62a2cd0e36cf22395e |

## Runtime function coverage

All 59 top-level runtime functions are mapped below to numbered clauses in the spec's As-built behavior and limits section; nested closures are covered by their owning daemon/streaming function.

| Function | As-built clause |
| --- | --- |
| [atomic_write](../scripts/worker_runtime.py#L33) | 25 |
| [prepend_progress](../scripts/worker_runtime.py#L53) | 25 |
| [read_score_state](../scripts/worker_runtime.py#L58) | 12 |
| [score_task_level](../scripts/worker_runtime.py#L74) | 12 |
| [score_summary](../scripts/worker_runtime.py#L78) | 12 |
| [registered_agent_score_path](../scripts/worker_runtime.py#L83) | 12 |
| [initialize_agent_score](../scripts/worker_runtime.py#L89) | 12 |
| [read_agent_score_state](../scripts/worker_runtime.py#L118) | 12 |
| [append_agent_event](../scripts/worker_runtime.py#L128) | 12 |
| [_read_json_lines](../scripts/worker_runtime.py#L166) | 12 |
| [_watch_agent_events_locked](../scripts/worker_runtime.py#L184) | 12 |
| [watch_agent_events](../scripts/worker_runtime.py#L224) | 12 |
| [acknowledge_agent_event](../scripts/worker_runtime.py#L244) | 12 |
| [record_agent_score_result](../scripts/worker_runtime.py#L274) | 12 |
| [_record_score_result](../scripts/worker_runtime.py#L293) | 12 |
| [record_score_result](../scripts/worker_runtime.py#L323) | 12 |
| [build_ghost_closeout_prompt](../scripts/worker_runtime.py#L340) | 10 |
| [workspace_snapshot](../scripts/worker_runtime.py#L353) | 10 |
| [pop_task](../scripts/worker_runtime.py#L373) | 1–2 |
| [restore_task_front](../scripts/worker_runtime.py#L398) | 1–2 |
| [insert_task_front](../scripts/worker_runtime.py#L420) | 1–2 |
| [parse_agent_registry](../scripts/worker_runtime.py#L452) | 11 |
| [load_agent_registry](../scripts/worker_runtime.py#L497) | 11 |
| [adapter_callback](../scripts/worker_runtime.py#L506) | 11 |
| [execute_adapter_protocol](../scripts/worker_runtime.py#L555) | 11 |
| [should_failover_agent](../scripts/worker_runtime.py#L643) | 11 |
| [read_agent_state](../scripts/worker_runtime.py#L658) | 11 |
| [execute_registered_agents](../scripts/worker_runtime.py#L671) | 11 |
| [progress_bar](../scripts/worker_runtime.py#L787) | 1–2 |
| [poll_next](../scripts/worker_runtime.py#L794) | 1–2 |
| [task_field](../scripts/worker_runtime.py#L832) | 1–2 |
| [write_status](../scripts/worker_runtime.py#L844) | 5 |
| [display_status](../scripts/worker_runtime.py#L871) | 5 |
| [run_with_timeout](../scripts/worker_runtime.py#L889) | 9 |
| [finalize_task_git](../scripts/worker_runtime.py#L924) | 10 |
| [finalize_structured_adapter_result](../scripts/worker_runtime.py#L950) | 10 |
| [claim_ghost_allowance](../scripts/worker_runtime.py#L995) | 10 |
| [run_adapter_ghost](../scripts/worker_runtime.py#L1023) | 10 |
| [execute_adapter_task](../scripts/worker_runtime.py#L1087) | 10 |
| [build_task_prompt](../scripts/worker_runtime.py#L1172) | 25 |
| [env_bool](../scripts/worker_runtime.py#L1205) | 25–26 |
| [acquire_worker_lock](../scripts/worker_runtime.py#L1209) | 3–5 |
| [worker_daemon](../scripts/worker_runtime.py#L1242) | 3–5 |
| [git_audit](../scripts/worker_runtime.py#L1753) | 13–16 |
| [run_verify](../scripts/worker_runtime.py#L1817) | 13–16 |
| [first_report](../scripts/worker_runtime.py#L1853) | 13–16 |
| [publish_research_reports](../scripts/worker_runtime.py#L1873) | 13–16 |
| [mechanical_audit](../scripts/worker_runtime.py#L1909) | 13–16 |
| [report_archive_path](../scripts/worker_runtime.py#L2001) | 19 |
| [archive_active_reports](../scripts/worker_runtime.py#L2007) | 19 |
| [archive_overlapping_reports](../scripts/worker_runtime.py#L2017) | 19 |
| [_git_path_state](../scripts/worker_runtime.py#L2042) | 10 |
| [_save_git_path_state](../scripts/worker_runtime.py#L2052) | 10 |
| [_restore_git_path_state](../scripts/worker_runtime.py#L2061) | 10 |
| [_git_names](../scripts/worker_runtime.py#L2077) | 10 |
| [capture_attempt_baseline](../scripts/worker_runtime.py#L2083) | 10 |
| [recover_attempt_baseline](../scripts/worker_runtime.py#L2114) | 10 |
| [rollback_failed_task](../scripts/worker_runtime.py#L2196) | 20 |
| [main](../scripts/worker_runtime.py#L2255) | CLI inventory |

## Complete public CLI inventory

| Command | Contract |
| --- | --- |
| score-read / score-record | JSON score summary/update; state/task/result/evidence inputs |
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

Planner: lifecycle; full queue/alignment/auto; score ladder and evidence feedback; refactor Tracks A/B and gates; ten-task cadence; sentinel; fast/deep acceptance and integration; guidance/decomposition/blocked; Clean Pivot; on-demand trial task insertion and delivery; English records; source firewall/interventions; bounded Git and host restrictions.

Explore: explicit/cache routing; Terminal A allowlist; sibling scope; research dispatch/sentinel; compiler probe restoration; summary/skeleton/digest shape; metadata/pointers/negative proof; freshness/archive requirements.

Worker contract/prompt: task-type routing; scope stop; test immutability/assertion non-decrease; deletion ceilings; tool markers/actions; forbidden shortcuts/host safety; warnings/lint; three attempts; verifiable facts/negative proof; commit/report/confidence; runtime progress ownership; notes bounds; restricted closeout. Runtime enforcement limits are recorded separately.

Helpers and deployment: numbered spec clauses 21–26 cover complete file-level behavior, flags, exit states, Worker-only source guard, installation preservation/removal behavior, and syntax validation. update.sh is the installer alias. Regression tests are prior art, not additional runtime features.

Review performed by source inspection and function/CLI inventory comparison, without launching workers or model calls. This documents existing differences; no implementation fixes were made.

