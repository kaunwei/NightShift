#!/usr/bin/env python3
"""Portable, testable operations behind the worker.sh compatibility entry point.

This module deliberately does not source .worker.env: Bash retains that interface.
Each command receives explicit inputs so callers and tests exercise the same seam.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time


FIELD_NAMES = (
    "LEVEL", "TARGET", "ACTION", "GOAL", "VERIFY",
    "FORBIDDEN_SHORTCUTS", "CONSTRAINTS", "DEPENDS_ON",
)


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    old_mode = path.stat().st_mode & 0o777 if path.exists() else None
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="", dir=path.parent,
            prefix=f".{path.name}.", delete=False,
        ) as output:
            temporary = Path(output.name)
            output.write(content)
        if old_mode is not None:
            temporary.chmod(old_mode)
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def pop_task(queue_path):
    """Remove one task under the same directory lock used by reorder_queue.sh."""
    queue = Path(queue_path)
    lock = Path(f"{queue}.lock")
    for attempt in range(50):
        try:
            lock.mkdir()
            break
        except FileExistsError:
            time.sleep(0.1)
    else:
        raise TimeoutError(f"queue lock remains held: {lock}")

    try:
        lines = queue.read_text(encoding="utf-8").splitlines(keepends=True) if queue.exists() else []
        for index, line in enumerate(lines):
            if line.strip() and not line.lstrip().startswith("#"):
                task = line.rstrip("\r\n")
                atomic_write(queue, "".join(lines[:index] + lines[index + 1:]))
                return task
        return ""
    finally:
        lock.rmdir()


def task_field(raw, key):
    if key not in FIELD_NAMES:
        raise ValueError(f"unknown task field: {key}")
    # A pipe only separates fields when followed by a recognized field name.
    start = re.search(rf"(?:^|\|\s*){key}:\s*", raw)
    if start is None:
        return ""
    rest = raw[start.end():]
    end = re.search(r"\s*\|\s*(?:" + "|".join(FIELD_NAMES) + r"):\s*", rest)
    return (rest[:end.start()] if end else rest).strip()


def write_status(args):
    state = {
        "worker_id": args.worker_id,
        "os": args.os_name,
        "platform": args.platform,
        "isolation": args.isolation == "true",
        "work_dir": args.work_dir,
        "state": args.state,
        "current_task": args.current_task or None,
        "elapsed_seconds": args.elapsed,
        "progress": {
            "current_index": args.current_index,
            "total_tasks": args.total_tasks,
            "remaining": args.remaining,
            "percentage": args.percentage,
            "bar": args.bar,
        },
        "pid": args.pid,
        "model": args.model,
        "cli": args.cli,
        "timeout_seconds": args.timeout,
        "last_heartbeat": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    atomic_write(args.path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def display_status(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    pid = data.get("pid")
    alive = False
    if isinstance(pid, int) and pid > 0:
        try:
            os.kill(pid, 0)
            alive = True
        except OSError:
            pass
    flag = f"[ALIVE (PID: {pid})]" if alive else "[DEAD / INACTIVE]"
    print(f"Worker State   : {data.get('state', 'UNKNOWN')} {flag}")
    print(f"Current Task   : {data.get('current_task') or 'None'} "
          f"({data.get('elapsed_seconds', 0)}s elapsed)")
    print(f"Progress       : {data.get('progress', {}).get('bar', '[---]')}")
    if data.get("isolation"):
        print(f"Isolation Mode : ENABLED (Sandboxed in {data.get('work_dir', '-')})")
    else:
        print("Isolation Mode : DISABLED (In-place execution)")


def codex_args(args):
    """Build the Codex adapter invocation without shell splitting or eval."""
    command = ["exec", "--color", "never", "--output-last-message", args.last_message]
    if args.ephemeral.lower() in ("1", "true"):
        command.append("--ephemeral")
    if args.model:
        command.extend(("--model", args.model))
    if args.effort:
        command.extend(("--config", f"model_reasoning_effort={args.effort}"))
    if args.approval_mode in ("auto", "approve-for-me"):
        command.append("--approve-for-me")
    elif args.approval_mode in ("prompt", "default", ""):
        command.extend(("--sandbox", args.sandbox))
    elif args.approval_mode == "bypass":
        command.append("--dangerously-bypass-approvals-and-sandbox")
    else:
        raise ValueError(f"unsupported Codex approval mode: {args.approval_mode}")
    for directory in args.additional_dirs.split(","):
        directory = directory.strip()
        if directory and Path(directory).is_dir():
            command.extend(("--add-dir", directory))
    return command


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pop = commands.add_parser("queue-pop")
    pop.add_argument("path")
    field = commands.add_parser("task-field")
    field.add_argument("raw")
    field.add_argument("key", choices=FIELD_NAMES)
    status = commands.add_parser("status-write")
    for name in ("path", "worker_id", "os_name", "platform", "isolation",
                 "work_dir", "state", "current_task"):
        status.add_argument(name)
    for name in ("elapsed", "current_index", "total_tasks", "remaining"):
        status.add_argument(name, type=int)
    for name in ("percentage", "bar"):
        status.add_argument(name)
    status.add_argument("pid", type=int)
    status.add_argument("model")
    status.add_argument("cli")
    status.add_argument("timeout", type=int)
    display = commands.add_parser("status-display")
    display.add_argument("path")
    codex = commands.add_parser("codex-args")
    codex.add_argument("--last-message", required=True)
    codex.add_argument("--model", default="")
    codex.add_argument("--effort", default="")
    codex.add_argument("--approval-mode", default="auto")
    codex.add_argument("--sandbox", default="workspace-write")
    codex.add_argument("--ephemeral", default="1")
    codex.add_argument("--additional-dirs", default="")
    args = parser.parse_args(argv)
    if args.command == "queue-pop":
        task = pop_task(args.path)
        if task:
            print(task)
    elif args.command == "task-field":
        print(task_field(args.raw, args.key))
    elif args.command == "status-display":
        display_status(args.path)
    elif args.command == "codex-args":
        sys.stdout.buffer.write(("\0".join(codex_args(args)) + "\0").encode("utf-8"))
    else:
        write_status(args)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError) as error:
        print(f"worker_runtime: {error}", file=sys.stderr)
        sys.exit(2)
