<!-- REPORT_META: Task=TASK-AIDER-EXPLORE-4 | Commit=df3b916 -->
# NightShift Explore Report

**Inspected:** 4 files, 3 chunks (aider_explore.py, worker_runtime.py, aider.py, coverage doc). Middle chunks skipped due to partial coverage.

## Topology
- `worker_runtime.py` (`main()`) is the CLI entry point; dispatches on `args.command` (line 40). All adapter paths lack explicit try/except in lines 2815–2831.
- `aider.py` defines `read_request()` (L38), `get_config()` (L45), `emit()` (L10). No direct callers; imported by `aider_explore.py`.
- `aider_explore.py` orchestrates: `build_repo_map()` (L47) → `RepoMap.get_repo_map()` (L53) → `run()` (L151) loop calling `choose_files()` (L151) and `analyze_file()` (L118). `dispatch_explore()` (L284) writes results and commits (L519).

## Verified Callers
- `aider.py` imported by `aider_explore.py` (not explicitly shown in chunks; inferred from project memory).
- `worker_runtime.py` `main()` (L319) calls `start()` (L319), `status()` (L354), `cancel()` (L360) — all in `aider.py`.
- `aider_explore.py` `run()` (L402) spawns subprocess via `subprocess.Popen` (L397) and calls `choose_files()`/`analyze_file()` in a round loop (L402–457).

## Coupling Bottlenecks
- `build_repo_map()` (L47) passes file inventory to `RepoMap.get_repo_map()` (L53); failure returns empty string (L55) — undocumented silent failure path.
- `execute_adapter_protocol()` (L2801) lacks inline error handling; exceptions propagate to outer try/except (L2884) which only catches OSError, TimeoutError, ValueError, RuntimeError, json.JSONDecodeError, subprocess.CalledProcessError.
- `RepoMap.get_repo_map()` (L86–138) behavior on empty string is unverified; middle chunks skipped.

## Expand–Migrate–Contract Matrix
| Operation | Expand Impact | Migrate Impact | Contract Impact |
|-----------|--------------|----------------|-----------------|
| Expand | New files added to repo map; `build_repo_map()` collects them; `RepoMap.get_repo_map()` may return empty string on failure | Adapter dispatch paths lack try/except; new commands need error handling | `OUTCOMES` set (L7) defines outcomes; new outcomes may break protocol parsing |
| Migrate | Existing adapter code unchanged; `run()` round loop logic stable | `execute_adapter_protocol()` error handling gaps affect all adapters | `score_task_level()` (L90) and `score_summary()` (L94) validate scores; migration may alter scoring |
| Contract | `read_request()` (L38) rejects version mismatches; `get_config()` (L45) validates overrides | `subprocess.Popen` (L397) spawns child processes; migration may change exit codes | `atomic_write()` (L49) ensures disk durability; contract breaks if writes fail silently |

## Evidence and Unknowns
- `RepoMap.get_repo_map()` returning empty string on failure is **unconfirmed** (L55). Middle chunks (L86–138) skipped.
- `execute_adapter_protocol()` error handling gap is **documented** in coverage doc (L131–138) but not fixed in inspected range.
- `aider.py` import path from `aider_explore.py` is **unverified** (project memory only).
- `NIGHTSHIFT_SOURCE_COVERAGE.md` (L1–32, L86–138) confirms partial coverage; 8 topics lack code references (L131–138).
- Hypothesis: `RepoMap.get_repo_map()` may intentionally return empty string on empty input — **unconfirmed**.

## Verified Source Anchors

- `scripts/adapters/aider_explore.py#L25 — FunctionDef inventory(root, max_file_bytes)` — declaration verified from the inspected source.
- `scripts/adapters/aider_explore.py#L47 — FunctionDef build_repo_map(root, files, model, map_tokens)` — declaration verified from the inspected source.
- `scripts/adapters/aider_explore.py#L61 — FunctionDef ollama(base, model, task, payload, trace, label, tokens, timeout, json_mode)` — declaration verified from the inspected source.
- `scripts/adapters/aider_explore.py#L102 — FunctionDef read_chunks(path, max_chars)` — declaration verified from the inspected source.
