# Explore Micro Evidence

Generated from the inspected source snapshot.

## AST Skeleton: `scripts/adapters/aider_explore.py`

```python
FunctionDef inventory(root, max_file_bytes)
FunctionDef build_repo_map(root, files, model, map_tokens)
FunctionDef ollama(base, model, task, payload, trace, label, tokens, timeout, json_mode)
FunctionDef read_chunks(path, max_chars)
FunctionDef analyze_file(base, rel, path, memory, summaries, trace, round_number, ollama_base, model, config)
FunctionDef choose_files(files, repo_map, memory, summaries, trace, round_number, ollama_base, model, config)
FunctionDef relevance(path)
FunctionDef update_memory(memory, rel, summary, trace, serial, base, model, config)
FunctionDef source_pointers(text, root)
FunctionDef normalize_source_paths(text, root)
FunctionDef final_summary(root, task_id, commit, task_title, prompt, memory, summaries, trace, base, model, config)
FunctionDef ast_skeleton(path)
FunctionDef make_micro(root, summary_path, summaries)
FunctionDef resolve_aider_python(executable)
FunctionDef start(request)
FunctionDef run(payload_path)
```

### Exact 10-line slice: `scripts/adapters/aider_explore.py#L25`

```python
  25 | def inventory(root, max_file_bytes=400_000):
  26 |     files = {}
  27 |     for base, dirs, names in os.walk(root):
  28 |         dirs[:] = sorted(name for name in dirs
  29 |                          if name not in EXCLUDED_DIRS and not name.startswith("."))
  30 |         for name in sorted(names):
  31 |             path = Path(base) / name
  32 |             if path.is_symlink() or path.suffix.lower() in EXCLUDED_SUFFIXES:
  33 |                 continue
  34 |             try:
```


## AST Skeleton: `scripts/worker_runtime.py`

```python
FunctionDef serialize_workspace_state(function)
FunctionDef serialized()
FunctionDef atomic_write(path, content)
FunctionDef prepend_progress(path, entry)
FunctionDef read_score_state(path)
FunctionDef score_task_level(score)
FunctionDef score_summary(state)
FunctionDef registered_agent_score_path(root, registration_id)
FunctionDef initialize_agent_score(root, registration_id, initial_score)
FunctionDef read_agent_score_state(root, registration_id)
FunctionDef append_agent_event(path, event, gate_path)
FunctionDef _read_json_lines(path)
FunctionDef _watch_agent_events_locked(events_path, cursor_path, acknowledgements_path, gate_path, handoff_path)
FunctionDef watch_agent_events(events_path, cursor_path, acknowledgements_path, gate_path, handoff_path)
FunctionDef acknowledge_agent_event(events_path, acknowledgements_path, event_id, resolution)
FunctionDef record_agent_score_result(root, registration_id, task_id, result, evidence, events_path, mid_batch, gate_path)
FunctionDef _record_score_result(path, task_id, result, evidence)
FunctionDef record_score_result(path, task_id, result, evidence)
FunctionDef build_ghost_closeout_prompt(task_id, verify, progress_file, host_git)
FunctionDef workspace_snapshot(work_dir, base)
FunctionDef pop_task(queue_path)
FunctionDef restore_task_front(queue_path, task)
FunctionDef insert_task_front(queue_path, task)
FunctionDef parse_agent_registry(raw, defaults)
FunctionDef load_agent_registry(config_file)
FunctionDef adapter_callback(command, callback, request, extra_args, timeout)
FunctionDef execute_adapter_protocol(command, request, extra_args, trace, callback_timeout, execution_timeout, start_callback)
FunctionDef cancel(reason)
FunctionDef should_failover_agent(exit_code, result_text)
FunctionDef read_agent_state(path)
FunctionDef execute_registered_agents(args, agents, state_path, rollback)
FunctionDef score_for(registration_id)
FunctionDef progress_bar(current, total, width)
FunctionDef poll_next(args)
FunctionDef count(path)
FunctionDef task_field(raw, key)
FunctionDef write_status(args)
FunctionDef display_status(path)
FunctionDef run_with_timeout(seconds, command)
FunctionDef temporary_git_index(work_dir, tree)
```

### Exact 10-line slice: `scripts/worker_runtime.py#L40`

```python
  40 | def serialize_workspace_state(function):
  41 |     """Keep heartbeat's atomic-write temporaries out of task snapshots."""
  42 |     @wraps(function)
  43 |     def serialized(*args, **kwargs):
  44 |         with _workspace_state_lock:
  45 |             return function(*args, **kwargs)
  46 |     return serialized
  47 |
  48 |
  49 | def atomic_write(path, content):
```
