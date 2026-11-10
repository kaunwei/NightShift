# NightShift source coverage index

Baseline: 2026-10-26, updated for external adapters, per-registration scores, env-file-free configuration, in-place execution, on-demand trials, and unified no-response handling. The experimental Aider adapter and deterministic Explore implementation were removed; historical design and trial results are preserved in [DETERMINISTIC_EXPLORE_STRATEGY.md](DETERMINISTIC_EXPLORE_STRATEGY.md) and [DETERMINISTIC_EXPLORE_RESULTS.md](DETERMINISTIC_EXPLORE_RESULTS.md). Companion to [NIGHTSHIFT_SPEC.md](NIGHTSHIFT_SPEC.md). This index records NightShift-owned skills, references, launcher, runtime, helpers, tools, and installer entry points. Skill sources and installed skill files both live under `.agents/skills/` and `.skills/`; `nightshift/` holds deployed runtime code and state.

## Preservation rule

For every later simplification, compare the changed source hashes and each affected function/skill clause with the spec. A source row is not proof of behavioral equivalence: review its conditions, outputs, failure cases, exemptions, and skill-only requirements. Additions need new spec entries; intentional removals need an explicit decision. Keep differences from desired behavior visible instead of silently declaring them implemented.

## Source inventory

| Source | SHA-256 |
| --- | --- |
| [.gitignore](../../.gitignore) | c4a3201f71eeedc867384e177c8d2d761fe7188e7537854631773de0601dde3b |
| [.agents/skills/nightshift/explore/SKILL.md](../../.agents/skills/nightshift/explore/SKILL.md) | 0c7a2bb4d0acb1a705f609e7a9ddfe83f30ede5c6b7303334ddb894f4d7785b0 |
| [.agents/skills/nightshift/planner/SKILL.md](../../.agents/skills/nightshift/planner/SKILL.md) | 8b5edb902d832d55ac7daeac92680048dab60bc382d5d9c8bdf0185d5f1ecb07 |
| [.skills/universal-build-verify.md](../../.skills/universal-build-verify.md) | 240fe45bb911a52888870af8b9c138a7de1b670313db85adf7958c78e1359357 |
| [nightshift/adapters/agents.json](../adapters/agents.json) | 1dcce30d5fe2ebe49fa57c4ea108cab7e90f5d50a24ac97117183fe13608d2ea |
| [nightshift/adapters/agy.py](../adapters/agy.py) | 1af2f11c3143d5f6185ee7d8ee67aba11b28076e7d9c1e05e0c3c086601a4eaa |
| [nightshift/adapters/codex.py](../adapters/codex.py) | 4a3b8ce67ff6ae807ac2487676f6e28bc7f20d25af6719fb6f337e634e210af8 |
| [nightshift/adapters/generic.py](../adapters/generic.py) | 9c1424b4cf06defbd7be4f48abaca32cbc2f274dbe1eb96da8bc24ac467e56db |
| [nightshift/extract_skeleton.sh](../extract_skeleton.sh) | 210ebbf5f00940d9fab650c10347f7c180838e68a824a779baf0f854391f54d6 |
| [nightshift/probe_line.sh](../probe_line.sh) | 6514cfdd8582fe2508d8779a0d18608201a0f9c655c846f2c5f4c03e49a437e3 |
| [nightshift/reorder_queue.sh](../reorder_queue.sh) | 68bf2e6b6d212393ef8c087ce27c2b29e642ddfe8d38e9b7b77f567fa7f42363 |
| [nightshift/status.sh](../status.sh) | 2896954c5e6972d2c6985a79535b9e6a7cf2325b334d650d4d2dddb57c1257f3 |
| [nightshift/watch_worker.sh](../watch_worker.sh) | e2ea3008d90fc8ac20fba59a2c2979633dd0896e0931a7f679d4c41cf43b6f47 |
| [nightshift/worker.sh](../worker.sh) | d430417b8f221222763e0885aa3a7c2d0e9681da2cda4de00e9d22c9005e0cb9 |
| [nightshift/worker_runtime.py](../worker_runtime.py) | ae7809ba8d4ee9339365c51e2baebfb969b674913bc7c0b1c98e8093f272c52b |
| [nightshift/tools/README.md](../tools/README.md) | a35532892107d432df3c4b2175516b28e4310ec3aee357d3184591c2f960c811 |
| [nightshift/tools/index.py](../tools/index.py) | 3c42160f91ae8152b7a272614dc9e0732493caa7aef6cce65751b952bd199b56 |
| [nightshift/tools/languages.json](../tools/languages.json) | fc7f10de17095f0a0930fd7e344bd4d787ecc57ee4f3c4202224485e718faa13 |
| [nightshift/tools/requirements.txt](../tools/requirements.txt) | b80981036c5a1cdb663fd98341f1a0f70b652a25b125a44308f90afad2913632 |
| [nightshift/tools/setup.sh](../tools/setup.sh) | a2cbd18108502b18d4f1a8ad83c3455a94888fbd6cbe65a4ee53c5c1075b3644 |
| [nightshift/tools/setup.ps1](../tools/setup.ps1) | 31fbe3b44ed2b160342d0b507931f1e23f1ba57f62ceba03ec92d7e4cf0802b6 |
| [nightshift/scratch_review.py](../scratch_review.py) | 146f28c2325e9bfee6c3c94877bb37bffbd9dc45d00db16204f4722df4e7964c |
| [nightshift/install-manifest.json](../install-manifest.json) | 51c54a2942df07d4ca0a9f59edced7140272d42821095706b38b8fb4c6011ecf |
| [install.sh](../../install.sh) | fdeeb5921379ed67e230dcc3672017dcd5a2fbc09e0ffbe8059ff89edbd007c0 |
| [remove.sh](../../remove.sh) | dc903ef55e497f8eeaaf5829ffc46f0c0cf81aa72fe78f670a8b3c314837242e |
| [README.md](../../README.md) | dcb943b41c867909a7f697836c2e4a176e7d403d938b4b4ad4c8b3dbf9b81374 |
| [test/README.md](../../test/README.md) | f08d9ab6eb15eb369421ef3b4bc405c8f0f2dd26f60b89aac24dbc139b6a409b |
| [nightshift/docs/NIGHTSHIFT_SPEC.md](../docs/NIGHTSHIFT_SPEC.md) | 9a036cc3693c531ba6e27d7bb0b28a0b39a50c389d04764bcd08c74453de835c |
| [nightshift/docs/PORTING_GUIDE.md](../docs/PORTING_GUIDE.md) | 712fb3d98a5ac77068ccad9dcbc54695af8c7ea82a98dcfa7f8d1346ced65fe8 |
| [nightshift/docs/DETERMINISTIC_EXPLORE_STRATEGY.md](../docs/DETERMINISTIC_EXPLORE_STRATEGY.md) | c832795fb51c7e8ad65e66de0116629a70480172d0628217cb3aafb12683e896 |
| [nightshift/docs/DETERMINISTIC_EXPLORE_RESULTS.md](../docs/DETERMINISTIC_EXPLORE_RESULTS.md) | a624dfe4d49bc5fe167e597b71f86e1c3d86610b9e6084fc0e1d3c49721b068c |
| [scripts/attempt_archive.py](../attempt_archive.py) | 543e1da1ea2effb5e75ac08f642bb67eb438d6fa02bf3604aab4ffbeeb68270c |
| [scripts/preflight.py](../preflight.py) | f41998fdf14d3cca01ae4bd1f6ced0f49de33545e2142742f0c311ca5e8c551c |
| [scripts/environment_probe.py](../environment_probe.py) | 7a6663e1c66b68a2f34df53d11bb84ad31d3439710c40257527241e48cf5f2ca |
| [scripts/verify_process.py](../verify_process.py) | 010aae6a725d3c40e03f37d4ddb08d7a1d5e8729f8efc22cc0c28290bcd066ac |
| [scripts/evidence_capabilities.py](../evidence_capabilities.py) | 570201cfca85010e38a5d4976bc0c1a5616ab1514cd28a4c4e59b3de72cfd91f |
| [scripts/acceptance_hooks.py](../acceptance_hooks.py) | ee9f97b5aa9d96d8fcb318462872a2be3a117b4754fd703249edb3c3809bbfab |
| [scripts/hook_control.py](../hook_control.py) | 66a8ecf356c8376684720fd98faa21a32f034730ec0780b6169585152a976567 |
| [scripts/acceptance.py](../acceptance.py) | 1e54bd8ba0e7797c3cd302787cecdd6be61b2d83ac9046cb735d28477776e4fb |
| [scripts/lifecycle.py](../lifecycle.py) | a058dcf0a6fb5acdd6661eafe77627389262f1a10e6e9bff5749d03acd4de127 |
| [scripts/docs/RUNTIME_HARDENING.md](../docs/RUNTIME_HARDENING.md) | 227b8a8018e1cda4bdddbea439cc889d089542c6f39c608898f4ffda007315de |

| [scripts/docs/AGENT_CONTRACT_REVIEW.md](../docs/AGENT_CONTRACT_REVIEW.md) | 032398bc970747bcb5e736cf956db145db1b143ce24d1f80c069f442ce4b3c61 |

| [scripts/ticket_policy.py](../ticket_policy.py) | 4dc719b7922a2c60845aefa5dafde1127a94e3653059667ec78c33874e20da5c |
| [scripts/outcome_policy.py](../outcome_policy.py) | eba3560478e1a3c318cc7cf2e04e0a394c628add4f4fdfa42b703d08661d34a5 |
| [scripts/docs/TICKET_ACCEPTANCE.md](../docs/TICKET_ACCEPTANCE.md) | 6077d6494ab6a4936d1cfc147425321cc3a57d2aa543f1acba35d6b49fcfec75 |
| [scripts/acceptance.md](../acceptance.md) | fb260373812fe8b09007805f3ce44be14da36b82ceac99a285af687209ea4c62 |

## Runtime function coverage

74 top-level runtime functions are mapped below to numbered clauses in the spec's As-built behavior and limits section; nested closures are covered by their owning function. Anchors are refreshed from the current Python AST, and this is not a regression-test result.

| Function | As-built clause |
| --- | --- |
| [serialize_workspace_state](../worker_runtime.py#L68) | 5, 25 |
| [atomic_write](../worker_runtime.py#L77) | 25 |
| [prepend_progress](../worker_runtime.py#L97) | 25 |
| [update_planner_review](../worker_runtime.py#L115) | 12 |
| [read_score_state](../worker_runtime.py#L154) | 12 |
| [score_task_level](../worker_runtime.py#L173) | 12 |
| [score_summary](../worker_runtime.py#L177) | 12 |
| [registered_agent_score_path](../worker_runtime.py#L195) | 12 |
| [initialize_agent_score](../worker_runtime.py#L201) | 12 |
| [read_agent_score_state](../worker_runtime.py#L230) | 12 |
| [append_agent_event](../worker_runtime.py#L240) | 12 |
| [_read_json_lines](../worker_runtime.py#L278) | 12 |
| [_watch_agent_events_locked](../worker_runtime.py#L305) | 12 |
| [watch_agent_events](../worker_runtime.py#L344) | 12 |
| [acknowledge_agent_event](../worker_runtime.py#L364) | 12 |
| [record_agent_score_result](../worker_runtime.py#L394) | 12 |
| [_record_score_result](../worker_runtime.py#L413) | 12 |
| [record_score_result](../worker_runtime.py#L454) | 12 |
| [build_ghost_closeout_prompt](../worker_runtime.py#L475) | 10 |
| [workspace_snapshot](../worker_runtime.py#L495) | 10 |
| [pop_task](../worker_runtime.py#L517) | 1–2 |
| [restore_task_front](../worker_runtime.py#L568) | 1–2 |
| [insert_task_front](../worker_runtime.py#L590) | 1–2, 20 |
| [parse_agent_registry](../worker_runtime.py#L622) | 11, 25 |
| [load_agent_registry](../worker_runtime.py#L669) | 11, 25 |
| [adapter_callback](../worker_runtime.py#L757) | 6–11 |
| [execute_adapter_protocol](../worker_runtime.py#L806) | 6–11 |
| [should_failover_agent](../worker_runtime.py#L929) | 11, 19 |
| [read_agent_state](../worker_runtime.py#L944) | 11 |
| [agent_supports_task](../worker_runtime.py#L982) | 11, 19 |
| [execute_registered_agents](../worker_runtime.py#L989) | 11–12, 19 |
| [progress_bar](../worker_runtime.py#L1178) | 1–2 |
| [poll_next](../worker_runtime.py#L1185) | 1–2 |
| [task_field](../worker_runtime.py#L1238) | 1–2 |
| [write_status](../worker_runtime.py#L1243) | 5 |
| [display_status](../worker_runtime.py#L1270) | 5 |
| [run_with_timeout](../worker_runtime.py#L1288) | 9 |
| [temporary_git_index](../worker_runtime.py#L1324) | 10 |
| [worktree_tree](../worker_runtime.py#L1336) | 19 |
| [attempt_audit_trees](../worker_runtime.py#L1342) | 10, 13 |
| [changed_tree_paths](../worker_runtime.py#L1354) | 10, 13, 19 |
| [run_code_index](../worker_runtime.py#L1358) | CLI inventory |
| [code_index_inputs](../worker_runtime.py#L1371) | 6 |
| [ensure_code_index_after_commit](../worker_runtime.py#L1393) | 6 |
| [finalize_task_git](../worker_runtime.py#L1414) | 6, 10 |
| [finalize_structured_adapter_result](../worker_runtime.py#L1596) | 6, 10 |
| [claim_ghost_allowance](../worker_runtime.py#L1604) | 10 |
| [run_adapter_ghost](../worker_runtime.py#L1632) | 10 |
| [execute_adapter_task](../worker_runtime.py#L1723) | 10 |
| [build_task_prompt](../worker_runtime.py#L1856) | 6, 25 |
| [env_bool](../worker_runtime.py#L1903) | 25–26 |
| [acquire_worker_lock](../worker_runtime.py#L1907) | 3–5 |
| [worker_daemon](../worker_runtime.py#L1940) | 3–5, 11–12, 17, 19, 25 |
| [git_audit](../worker_runtime.py#L1972) | 13–16 |
| [run_verify](../worker_runtime.py#L2064) | 13–16 |
| [first_report](../worker_runtime.py#L2116) | 13–16 |
| [publish_research_reports](../worker_runtime.py#L2142) | 13–16 |
| [mechanical_audit](../worker_runtime.py#L2178) | 13–16 |
| [report_archive_path](../worker_runtime.py#L2285) | 18 |
| [cleanup_invalid_reports](../worker_runtime.py#L2296) | 18 |
| [settle_invalid_reports](../worker_runtime.py#L2313) | 18 |
| [report_source_paths](../worker_runtime.py#L2347) | 18 |
| [report_staleness](../worker_runtime.py#L2367) | 18 |
| [refresh_active_reports](../worker_runtime.py#L2402) | 18 |
| [archive_active_reports](../worker_runtime.py#L2420) | 18 |
| [archive_overlapping_reports](../worker_runtime.py#L2433) | 18 |
| [_git_path_state](../worker_runtime.py#L2438) | 19 |
| [_runtime_state_root](../worker_runtime.py#L2448) | 5, 19 |
| [_scratch_state_root](../worker_runtime.py#L2457) | 5, 19 |
| [_git_names](../worker_runtime.py#L2464) | 19 |
| [capture_attempt_baseline](../worker_runtime.py#L2471) | 19 |
| [recover_attempt_baseline](../worker_runtime.py#L2495) | 19 |
| [rollback_failed_task](../worker_runtime.py#L2576) | 19 |
| [main](../worker_runtime.py#L2640) | CLI inventory |

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

## Script-only hardening coverage (2026-11-10)

As-built clause 28 covers `attempt_archive.capture/verify` (restore-verified
retention before clean/recovery), `preflight.check` and `environment_probe.probe`
(before-claim prerequisite checks), `verify_process.run` (POSIX live evidence and
bounded memory/cleanup), `evidence_capabilities.validate/supports` (optional
framework declarations), Scheduler persistence/recovery and hook control
list/cancel/retry, and capacity/task metrics. The installer manifest includes the
new runtime dependencies and operating reference. Regression coverage is in
`test_runtime_hardening.py` plus the existing recovery, timeout, hook, TDD and
external-project suites. No skill rules were changed.

Agent contract alignment retains existing role branches; the old/new comparison,
intentional FIX permission correction, bounded research policy, blocked-state
relay/shutdown handling and unchanged score arithmetic are reviewed in
[AGENT_CONTRACT_REVIEW.md](AGENT_CONTRACT_REVIEW.md).

## Ticket acceptance amendment (2026-11-10)

As-built clause 29 and [TICKET_ACCEPTANCE.md](TICKET_ACCEPTANCE.md) supersede
previous automatic score arithmetic and recursive budget observations.
`ticket_policy` owns field parsing, preclaim evidence/VERIFY validation, planned
file estimates and preparation floors. `outcome_policy.classify` owns the
evidence-backed feedback classification; lifecycle persists it with idempotent
registration feedback and capability events. Acceptance keeps full hot and
source/fingerprint checks for explicit existing cases. Generic adapter status
normalization enables actual no-change verification. Worker finalization checks
no-change before and after VERIFY; watcher relays CONTRACT_BLOCKED.
Regression coverage: test_ticket_granularity and test_sentinel_completion.
No Planner/Explore/Sentinel skill was edited for this amendment; complete
acceptance-unit slicing guidance remains ticket 05 for later discussion.
