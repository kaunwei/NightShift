# NightShift source coverage index

Baseline: 2026-10-23, working-tree sources after commit ef667e3. Companion to [NIGHTSHIFT_SPEC.md](NIGHTSHIFT_SPEC.md). This index records every NightShift-owned skill/reference, launcher, runtime, helper and installer/update entry. Matt skills are references only.

## Preservation rule

For every later simplification, compare the changed source hashes and each affected function/skill clause with the spec. A source row is not proof of behavioral equivalence: review its conditions, outputs, failure cases, exemptions, and skill-only requirements. Additions need new spec entries; intentional removals need an explicit decision. Keep differences from desired behavior visible instead of silently declaring them implemented.

## Source inventory

| Source | SHA-256 |
| --- | --- |
| [.agents/skills/nightshift/explore/SKILL.md](../.agents/skills/nightshift/explore/SKILL.md) | 20acb1a3011c4b8babaab8bde25f1f775ff73507bff087529aab19e796191ef8 |
| [.agents/skills/nightshift/planner/OPERATIONS.md](../.agents/skills/nightshift/planner/OPERATIONS.md) | e7a8fc373ea3086b8c6e24d71779fce0a9f8854b590d5c55e676bd8582384980 |
| [.agents/skills/nightshift/planner/SKILL.md](../.agents/skills/nightshift/planner/SKILL.md) | 0dfd5bd3fba964469afb8ad150d1851052ecb0ad51628abd37fc2d2d238c7555 |
| [.skills/universal-build-verify.md](../.skills/universal-build-verify.md) | de6f1940b3af14bf3310cafdcbf648b0230a13be4f9591de510e3aeb9dde6b31 |
| [.worker.env.example](../.worker.env.example) | aa1ec275e45463667662bec7042ed2de0d388cd1510d4eb6072179bd7f279da2 |
| [install.sh](../install.sh) | d42f5dad5a21ee69b7f5269191987f3423778a2a164d26ca025e78832a970563 |
| [scripts/extract_skeleton.sh](../scripts/extract_skeleton.sh) | 1ed2a93cee0194d1828336a50298ce3d7d8b981875dfaf36bd1adea469e5db01 |
| [scripts/probe_line.sh](../scripts/probe_line.sh) | 6b56db490c2b82dc864617a88c82c49b75d0f759c3ace06dece014b2c2d87cd3 |
| [scripts/reorder_queue.sh](../scripts/reorder_queue.sh) | 5cfc56907dafd4b22960199cfff8a413d8542a1251357867d7b5468bee88210a |
| [scripts/status.sh](../scripts/status.sh) | 3ae98a6d11024cf865dc78e9a182bee0c0622149c391676471efe2e3884b6349 |
| [scripts/watch_worker.sh](../scripts/watch_worker.sh) | 1428a8e732945280fee17e54975908c1d58637e0440159536268c212657018ef |
| [scripts/worker_runtime.py](../scripts/worker_runtime.py) | 05f14ca021014e4459c09e4732b629442c15e81040c0a578f20fbfb491504f0e |
| [update.sh](../update.sh) | d42f5dad5a21ee69b7f5269191987f3423778a2a164d26ca025e78832a970563 |
| [worker.sh](../worker.sh) | c35fadf0729e61d2806c2bfbdc2e7bd07aede5602ae2353c2489efa0114a9fc0 |

## Runtime function coverage

All 45 top-level runtime functions are mapped below to numbered clauses in the spec's As-built behavior and limits section; nested closures are covered by their owning daemon/streaming function.

| Function | As-built clause |
| --- | --- |
| [atomic_write](../scripts/worker_runtime.py#L33) | 26 |
| [prepend_progress](../scripts/worker_runtime.py#L53) | 26 |
| [read_score_state](../scripts/worker_runtime.py#L58) | 12 |
| [score_task_level](../scripts/worker_runtime.py#L74) | 12 |
| [score_summary](../scripts/worker_runtime.py#L78) | 12 |
| [_record_score_result](../scripts/worker_runtime.py#L83) | 12 |
| [record_score_result](../scripts/worker_runtime.py#L113) | 12 |
| [build_ghost_closeout_prompt](../scripts/worker_runtime.py#L130) | 10 |
| [workspace_snapshot](../scripts/worker_runtime.py#L140) | 10 |
| [run_codex_closeout](../scripts/worker_runtime.py#L158) | 10 |
| [pop_task](../scripts/worker_runtime.py#L188) | 1–2 |
| [restore_task_front](../scripts/worker_runtime.py#L213) | 1–2 |
| [parse_agent_registry](../scripts/worker_runtime.py#L235) | 11 |
| [quota_error](../scripts/worker_runtime.py#L264) | 11 |
| [read_agent_state](../scripts/worker_runtime.py#L273) | 11 |
| [execute_registered_agents](../scripts/worker_runtime.py#L283) | 11 |
| [progress_bar](../scripts/worker_runtime.py#L321) | 1–2 |
| [poll_next](../scripts/worker_runtime.py#L328) | 1–2 |
| [task_field](../scripts/worker_runtime.py#L365) | 1–2 |
| [write_status](../scripts/worker_runtime.py#L377) | 5 |
| [display_status](../scripts/worker_runtime.py#L405) | 5 |
| [codex_args](../scripts/worker_runtime.py#L427) | 6 |
| [agy_args](../scripts/worker_runtime.py#L451) | 7–8 |
| [count_agy_steps](../scripts/worker_runtime.py#L481) | 7–8 |
| [count_codex_actions](../scripts/worker_runtime.py#L486) | 7–8 |
| [is_codex_action_event](../scripts/worker_runtime.py#L501) | 7–8 |
| [run_with_timeout](../scripts/worker_runtime.py#L511) | 9 |
| [stream_with_timeout](../scripts/worker_runtime.py#L546) | 9 |
| [execute_task_cli](../scripts/worker_runtime.py#L651) | 6–11 |
| [build_task_prompt](../scripts/worker_runtime.py#L764) | 25 |
| [env_bool](../scripts/worker_runtime.py#L790) | 26 |
| [acquire_worker_lock](../scripts/worker_runtime.py#L794) | 3–5 |
| [worker_daemon](../scripts/worker_runtime.py#L827) | 3–5 |
| [git_audit](../scripts/worker_runtime.py#L1172) | 13–16 |
| [run_verify](../scripts/worker_runtime.py#L1232) | 13–16 |
| [first_report](../scripts/worker_runtime.py#L1268) | 13–16 |
| [mechanical_audit](../scripts/worker_runtime.py#L1286) | 13–16 |
| [git_at](../scripts/worker_runtime.py#L1372) | 17–18 |
| [ensure_worktree](../scripts/worker_runtime.py#L1377) | 17–18 |
| [publish_preview](../scripts/worker_runtime.py#L1410) | 17–18 |
| [report_archive_path](../scripts/worker_runtime.py#L1447) | 19 |
| [archive_active_reports](../scripts/worker_runtime.py#L1453) | 19 |
| [archive_overlapping_reports](../scripts/worker_runtime.py#L1463) | 19 |
| [rollback_failed_task](../scripts/worker_runtime.py#L1488) | 20 |
| [main](../scripts/worker_runtime.py#L1537) | CLI inventory |

## Complete public CLI inventory

| Command | Contract |
| --- | --- |
| score-read / score-record | JSON score summary/update; state/task/result/evidence inputs |
| ghost-prompt | Write restricted prompt for original task |
| queue-pop | Remove and print first non-comment task |
| task-field | Extract one recognized field, preserving ordinary pipes |
| status-write / status-display | Persist JSON / show state and PID liveness |
| codex-args / agy-args | NUL-delimited provider argv; no shell splitting |
| task-cli | Execute configured provider, stream output, enforce timeout/budget, commit or closeout as applicable |
| run-timeout | Execute argv, preserve normal exit, return 124 on timeout |
| git-audit | Guard code and explanation for diff/scope/test/deletion failures |
| ensure-worktree | Set up/reuse isolated worktree, report its path |
| publish-preview | Export committed tree/build artifacts, write version, return commit |
| archive-reports | Archive active nonhidden entries |
| archive-overlapping-reports | Archive summaries containing changed-file paths |
| rollback-failed-task | Preserve failed work and restore worktree paths with runtime exclusions |
| progress-prepend | Atomically put newest journal entry before history |
| mechanical-audit | JSON status/error/verify_exit/messages; diagnostics on stderr |
| poll-next | NUL-delimited 16-field paused/idle/task claim and progress/budget output |
| daemon | Run configured polling lifecycle |

CLI parsing requires command-specific inputs; malformed configuration, filesystem/JSON/Git errors are reported as worker_runtime diagnostics and exit 2. Full options are discoverable through per-command help; the spec captures behavior rather than duplicating argparse syntax.

## Skill and helper coverage

Planner: lifecycle; full queue/alignment/auto; score ladder and evidence feedback; refactor Tracks A/B and gates; ten-task cadence; sentinel; fast/deep acceptance and integration; guidance/decomposition/blocked; Clean Pivot; preview/env steering; English records; source firewall/interventions; bounded Git and host restrictions.

Explore: explicit/cache routing; Terminal A allowlist; sibling scope; research dispatch/sentinel; compiler probe restoration; summary/skeleton/digest shape; metadata/pointers/negative proof; freshness/archive requirements.

Worker contract/prompt: task-type routing; scope stop; test immutability/assertion non-decrease; deletion ceilings; tool markers/actions; forbidden shortcuts/host safety; warnings/lint; three attempts; verifiable facts/negative proof; commit/report/confidence; runtime progress ownership; notes bounds; restricted closeout. Runtime enforcement limits are recorded separately.

Helpers and deployment: numbered spec clauses 21–24 cover complete file-level behavior, flags, exit states, Worker-only source guard, installation preservation/removal behavior, and syntax validation. update.sh is the installer alias. Regression tests are prior art, not additional runtime features.

Review performed by source inspection and function/CLI inventory comparison, without launching workers or model calls. This documents existing differences; no implementation fixes were made.

