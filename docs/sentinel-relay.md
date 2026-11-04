# Event-driven Planner handoff

The watcher reports events on stdout. To enqueue an actual follow-up turn, run:

```sh
python3 nightshift/sentinel_relay.py --root "$PWD" --thread YOUR_PLANNER_THREAD_ID
```

The relay runs the existing watcher and calls `codex queue --thread ... --resume`
only for actionable sentinel events. Ordinary task completions do not queue turns.
The selected thread must belong to the intended Planner. This requires an
installed authenticated Codex CLI and a reachable local daemon. CLI errors are
reported rather than treated as successful delivery.

An isolated blocked-worker test on 2026-11-04 produced a queued message and an
actual automated follow-up in the same Planner chat. The fake queue/status files
were removed after receipt. Evidence is retained in ignored runtime scratch.
Completion and inactivity have not yet been tested end to end. This test does
not establish application generation or regression acceptance.

For explicit agent routing use `bash nightshift/watch_worker.sh --agent codex --planner-id THREAD_ID 0 5` or `--agent agy --planner-id CONVERSATION_ID`. AgY uses its existing `--conversation ID -p EVENT` CLI mode. AgY live continuation remains unverified; argument routing is tested. Agent selection is independent of the Worker registration.
