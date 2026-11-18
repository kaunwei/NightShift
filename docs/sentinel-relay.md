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

`PAUSED_FOR_PLANNER` gates the queue even when `current_task` is empty. The
watcher relays it on the next poll, including when it starts after the pause.
The default 180-second inactivity reminder is a separate fallback, not a delay
before delivering a Planner-required pause. A task-specific watcher also reports
this queue gate while its task remains queued; unrelated historical task results
remain filtered.

An isolated blocked-worker test on 2026-11-04 produced a queued message and an
actual automated follow-up in the same Planner chat. The fake queue/status files
were removed after receipt. Evidence is retained in ignored runtime scratch.
Completion and inactivity have not yet been tested end to end. This test does
not establish application generation or regression acceptance.

For explicit agent routing use `bash nightshift/watch_worker.sh --agent codex --planner-id THREAD_ID 0 5` or `--agent agy --planner-id CONVERSATION_ID`. AgY uses its existing `--conversation ID -p EVENT` CLI mode. AgY live continuation remains unverified; argument routing is tested. Agent selection is independent of the Worker registration.
