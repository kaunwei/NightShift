#!/usr/bin/env python3
"""Portable, testable operations behind the worker.sh compatibility entry point.

This module deliberately does not source .worker.env: Bash retains that interface.
Each command receives explicit inputs so callers and tests exercise the same seam.
"""

import argparse
from datetime import datetime, timezone
from io import BytesIO
import json
import os
import platform
from pathlib import Path
import queue
import re
import shutil
import signal
import sys
import subprocess
import tarfile
import tempfile
import time
import threading


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


def prepend_progress(path, entry):
    history = Path(path).read_text(encoding="utf-8") if Path(path).exists() else ""
    atomic_write(path, f"{entry}\n{history}")


def read_score_state(path):
    path = Path(path)
    if not path.exists():
        state = {"version": 1, "score": 5, "success_window": [], "failures": {}, "feedback": []}
        atomic_write(path, json.dumps(state, indent=2) + "\n")
        return state
    state = json.loads(path.read_text(encoding="utf-8"))
    if (state.get("version") != 1 or not isinstance(state.get("score"), int)
            or not 1 <= state["score"] <= 5
            or not isinstance(state.get("success_window"), list)
            or not isinstance(state.get("failures"), dict)):
        raise ValueError(f"invalid worker score state file: {path}")
    state.setdefault("feedback", [])
    return state


def score_task_level(score):
    return 1 if score == 5 else 2 if score >= 3 else 3


def score_summary(state):
    return {"score": state["score"], "task_level": score_task_level(state["score"]),
            "successes_in_window": len(state["success_window"])}


def _record_score_result(path, task_id, result, evidence=""):
    """Update shared Worker score from planner feedback or hard runtime evidence."""
    if result not in ("accept", "reject", "no_fault", "hard_failure", "success"):
        raise ValueError(f"unsupported score result: {result}")
    state = read_score_state(path)
    failures = state["failures"]
    if result == "hard_failure":
        count = int(failures.get(task_id, 0)) + 1
        failures[task_id] = count
        if count in (2, 3):
            state["score"] = max(1, state["score"] - 1)
    elif result == "success":
        failures.pop(task_id, None)
    elif result == "accept":
        failures.pop(task_id, None)
        state["success_window"].append(task_id)
        if len(state["success_window"]) >= 5:
            if all(state["success_window"][-5:]):
                state["score"] = min(5, state["score"] + 1)
            state["success_window"] = []
    elif result == "reject":
        state["success_window"] = []
    # no_fault is deliberately excluded from both scoring windows and penalties.
    state["feedback"].append({"task_id": task_id, "result": result,
                              "evidence": evidence, "at": datetime.now(timezone.utc).isoformat()})
    state["feedback"] = state["feedback"][-20:]
    atomic_write(path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    return {**score_summary(state), "task_id": task_id, "result": result}


def record_score_result(path, task_id, result, evidence=""):
    path = Path(path)
    lock = Path(f"{path}.lock")
    for _ in range(100):
        try:
            lock.mkdir()
            break
        except FileExistsError:
            time.sleep(0.05)
    else:
        raise TimeoutError(f"score state lock remains held: {lock}")
    try:
        return _record_score_result(path, task_id, result, evidence)
    finally:
        lock.rmdir()


def build_ghost_closeout_prompt(task_id, verify, progress_file):
    return f"""CLOSEOUT ONLY for original task {task_id}. You are a verification and Git-finalization helper, not an implementation worker.

You MUST NOT modify source code, tests, documentation, configuration, or any other implementation files. Do not fix, refactor, create, delete, or rewrite files. Do not issue commands that alter project contents. If anything still requires implementation, stop immediately and report [CLOSEOUT_INCOMPLETE] with the reason; do not try a workaround.

Allowed: inspect git status/diff/log, run the required verification command ({verify or 'the task verification command'}), and perform only the Git closeout explicitly allowed by the task. If verification passes, commit only the existing changes; never alter file contents. Do not commit if verification fails or if a code change would be needed. Report a concise evidence-based result for {task_id}. Do not create or count a separate task. The script attributes your outcome to {task_id} and enforces file-change checks.
Progress log: {progress_file}
"""


def workspace_snapshot(work_dir, base):
    changed = subprocess.run(["git", "-C", work_dir, "diff", "--name-only", "-z", base],
                             capture_output=True, check=False).stdout
    untracked = subprocess.run(["git", "-C", work_dir, "ls-files", "--others", "--exclude-standard", "-z"],
                               capture_output=True, check=False).stdout
    paths = {os.fsdecode(item) for item in changed.split(b"\0") + untracked.split(b"\0") if item}
    snapshot = {}
    for name in paths:
        path = Path(work_dir) / name
        if path.is_symlink():
            snapshot[name] = ("symlink", os.readlink(path), path.lstat().st_mode & 0o777)
        elif path.is_file():
            snapshot[name] = ("file", path.read_bytes(), path.stat().st_mode & 0o777)
        else:
            snapshot[name] = None
    return snapshot


def run_codex_closeout(args, environment, output, actions_used):
    remaining = args.step_budget - actions_used
    if remaining <= 0:
        return 125
    before = workspace_snapshot(args.work_dir, args.base)
    original_message = Path(args.result_file) if args.result_file else Path(args.output_file)
    closeout_message = str(original_message.with_name("closeout-message.txt"))
    prompt = build_ghost_closeout_prompt(args.task_id, args.verify, args.progress_file)
    codex = argparse.Namespace(
        last_message=closeout_message, model=args.model, effort=args.effort,
        approval_mode=args.approval_mode, sandbox=args.sandbox,
        ephemeral=args.ephemeral, additional_dirs=args.additional_dirs,
    )
    environment["MAX_STEPS"] = str(remaining)
    command = [args.executable, *codex_args(codex), prompt]
    code = stream_with_timeout(args.timeout, command, args.work_dir,
                               environment, output, append=True, action_budget=remaining)
    after = workspace_snapshot(args.work_dir, args.base)
    if before != after:
        print("[WORKER] Ghost closeout changed implementation files; rejecting closeout.", file=sys.stderr)
        return 126
    output_text = output.read_text(encoding="utf-8", errors="replace") if output.exists() else ""
    if count_codex_actions(output_text) > args.step_budget:
        return 125
    if code == 0 and closeout_message and Path(closeout_message).is_file():
        if "[CLOSEOUT_INCOMPLETE]" in Path(closeout_message).read_text(encoding="utf-8", errors="replace"):
            return 126
    return code


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


def restore_task_front(queue_path, task):
    """Put a claimed task back at the queue head without racing queue editors."""
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
        insertion = next((index for index, line in enumerate(lines)
                          if line.strip() and not line.lstrip().startswith("#")), len(lines))
        task_line = task.rstrip("\r\n") + "\n"
        atomic_write(queue, "".join(lines[:insertion] + [task_line] + lines[insertion:]))
    finally:
        lock.rmdir()


def parse_agent_registry(raw, defaults):
    if not raw.strip():
        return []
    profiles = json.loads(raw)
    if not isinstance(profiles, list) or not profiles:
        raise ValueError("AI_AGENTS_JSON must be a non-empty JSON array")
    agents, seen = [], set()
    for item in profiles:
        if not isinstance(item, dict):
            raise ValueError("each AI_AGENTS_JSON entry must be an object")
        agent_id = str(item.get("id", "")).strip()
        provider = str(item.get("provider", "")).strip().lower()
        command = str(item.get("command", item.get("executable", ""))).strip()
        if not agent_id or agent_id in seen:
            raise ValueError("AI_AGENTS_JSON agent ids must be non-empty and unique")
        if provider not in ("codex", "agy", "generic"):
            raise ValueError(f"unsupported provider for agent {agent_id}: {provider}")
        if not command:
            raise ValueError(f"AI_AGENTS_JSON agent {agent_id} requires a command")
        seen.add(agent_id)
        agents.append({
            "id": agent_id, "provider": provider, "command": command,
            "model": str(item.get("model", defaults["model"])),
            "effort": str(item.get("effort", defaults["effort"])),
            "agy_mode": str(item.get("agy_mode", defaults["agy_mode"])),
        })
    return agents


def quota_error(text):
    patterns = (r"insufficient[_ ]quota", r"quota (?:has been )?exceeded",
                r"rate[_ ]limit(?:[_ ]exceeded)?", r"resource_exhausted",
                r"too many requests", r"billing hard limit", r"out of credits",
                r"usage limit", r"exceeded.{0,40}quota",
                r"(?:http(?: status)?|status(?: code)?|error)\s*[:=]?\s*429\b")
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def read_agent_state(path):
    path = Path(path)
    if not path.exists():
        return {"version": 1, "exhausted": {}}
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("version") != 1 or not isinstance(state.get("exhausted"), dict):
        raise ValueError(f"invalid agent quota state file: {path}")
    return state


def execute_registered_agents(args, agents, state_path, rollback):
    state = read_agent_state(state_path)
    available = [agent for agent in agents if agent["id"] not in state["exhausted"]]
    if not available:
        print("[WORKER] QUOTA_EXHAUSTED: all registered agents are exhausted; task remains queued.")
        return 0, True
    for index, agent in enumerate(available):
        attempt = argparse.Namespace(**vars(args))
        attempt.provider = agent["provider"]
        attempt.executable = agent["command"]
        attempt.model = agent["model"]
        attempt.effort = agent["effort"]
        attempt.agy_mode = agent["agy_mode"]
        for output_name in ("output_file", "result_file"):
            output = Path(getattr(attempt, output_name, "") or ".")
            if output.is_file():
                output.unlink()
        print(f"[WORKER] Launching registered agent {agent['id']} ({agent['provider']}, model={agent['model'] or 'default'})...")
        code = execute_task_cli(attempt)
        output_path = Path(attempt.output_file)
        result_path = Path(attempt.result_file) if attempt.result_file else output_path
        output_text = output_path.read_text(encoding="utf-8", errors="replace") if output_path.exists() else ""
        result_text = result_path.read_text(encoding="utf-8", errors="replace") if result_path.exists() else ""
        if code in (0, 124) or not quota_error(output_text + "\n" + result_text):
            return code, False
        state["exhausted"][agent["id"]] = {
            "provider": agent["provider"], "command": agent["command"],
            "reason": "quota", "detected_at": datetime.now(timezone.utc).isoformat(),
        }
        atomic_write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        print(f"[WORKER] Agent {agent['id']} quota exhausted; switching to the next registered agent.", file=sys.stderr)
        rollback()
        if index + 1 == len(available):
            print("[WORKER] QUOTA_EXHAUSTED: all registered agents are exhausted; task remains queued.")
            return 0, True
    return 0, True


def progress_bar(current, total, width=30):
    if total <= 0:
        return "[------------------------------] 0% (0/0)"
    filled = current * width // total
    return f"[{'#' * filled}{'-' * (width - filled)}] {current * 100 // total}% ({current}/{total})"


def poll_next(args):
    """Claim one queue item and return the scheduler's external state as fields."""
    fields = [""] * 16
    if Path(args.pause).exists():
        fields[0] = "paused"
        return fields
    raw = pop_task(args.tasks)
    def count(path):
        source = Path(path)
        if not source.exists():
            return 0
        return sum(bool(line.strip()) and not line.lstrip().startswith("#")
                   for line in source.read_text(encoding="utf-8").splitlines())
    done = count(args.done)
    remaining = count(args.tasks) + bool(raw)
    total = done + remaining
    fields[:8] = ["task" if raw else "idle", raw, str(done), str(remaining),
                  str(total), str(done + 1 if raw else done),
                  str(done * 100 // total if total else 0), progress_bar(done, total)]
    if raw:
        fields[8] = raw.split("|", 1)[0].replace(" ", "") or "TASK-UNKNOWN"
        level = re.search(r"LEVEL:\s*([0-9])", raw)
        fields[9] = level.group(1) if level else "1"
        for index, key in ((10, "TARGET"), (11, "VERIFY"),
                           (12, "FORBIDDEN_SHORTCUTS"), (13, "CONSTRAINTS")):
            fields[index] = task_field(raw, key)
        targets = [item.strip() for item in fields[10].split(",") if item.strip()]
        file_count = 0
        for target in targets:
            path = Path(args.work_dir) / target
            file_count += max(1, sum(1 for item in path.rglob("*") if item.is_file())) if path.is_dir() else 1
        file_count = max(1, file_count)
        fields[14] = str(file_count)
        fields[15] = str(args.step_base + file_count * args.step_per_file)
    return fields


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
        "worker_score": getattr(args, "worker_score", 5),
        "recommended_task_level": score_task_level(getattr(args, "worker_score", 5)),
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
    print(f"Worker Score   : {data.get('worker_score', 5)}/5 | Recommended task level: L{data.get('recommended_task_level', 1)}")
    if data.get("isolation"):
        print(f"Isolation Mode : ENABLED (Sandboxed in {data.get('work_dir', '-')})")
    else:
        print("Isolation Mode : DISABLED (In-place execution)")


def codex_args(args):
    """Build the Codex adapter invocation without shell splitting or eval."""
    command = ["exec", "--color", "never", "--json", "--output-last-message", args.last_message]
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


def agy_args(args):
    """Build agy's argv from worker settings without shell word splitting."""
    command = []
    if args.sandbox.lower() in ("1", "true"):
        command.append("--sandbox")
    if args.mode:
        command.extend(("--mode", args.mode))
    if args.model:
        command.extend(("--model", args.model))
    command.extend(("--print-timeout", f"{args.timeout}s"))
    for directory in args.additional_dirs.split(","):
        directory = directory.strip()
        if directory and Path(directory).is_dir():
            command.extend(("--add-dir", directory))
    if args.effort and not re.search(r"-(?:low|medium|high|xhigh|max)$", args.model):
        command.extend(("--effort", args.effort))
    try:
        help_text = subprocess.run([args.executable, "--help"], check=False,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True).stdout
        if "--max-turns" in help_text:
            command.extend(("--max-turns", str(args.step_budget)))
        elif "--max-steps" in help_text:
            command.extend(("--max-steps", str(args.step_budget)))
    except OSError:
        # Preserve launch-time diagnostics; the actual invocation reports missing CLI.
        pass
    return command


def count_agy_steps(output):
    pattern = re.compile(r"^\[EXEC\]|Tool Call|edit_file|write_file|run_command|read_file")
    return sum(bool(pattern.search(line)) for line in output.splitlines())


def count_codex_actions(output):
    """Count observable Codex command executions from its JSONL event stream."""
    count = 0
    for line in output.splitlines():
        try:
            event = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        item = event.get("item", {}) if isinstance(event, dict) else {}
        if (isinstance(item, dict) and item.get("type") == "command_execution"
                and event.get("type") == "item.completed"):
            count += 1
    return count


def is_codex_action_event(line):
    try:
        event = json.loads(line)
    except (json.JSONDecodeError, TypeError):
        return False
    item = event.get("item", {}) if isinstance(event, dict) else {}
    return (isinstance(item, dict) and item.get("type") == "command_execution"
            and event.get("type") == "item.completed")


def run_with_timeout(seconds, command):
    """Run a command with inherited output and terminate its process group on timeout."""
    if not command:
        raise ValueError("run-timeout requires a command after --")
    options = {}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    process = subprocess.Popen(command, **options)
    try:
        return_code = process.wait(timeout=seconds)
    except subprocess.TimeoutExpired:
        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(process.pid, signal.SIGTERM)
        except (OSError, ValueError):
            process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                process.kill()
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except OSError:
                    process.kill()
            process.wait()
        return 124
    return 128 + abs(return_code) if return_code < 0 else return_code


def stream_with_timeout(seconds, command, cwd, environment, output_path, append=False,
                        action_budget=None):
    """Stream combined CLI output to the worker console and its audit log."""
    options = {"cwd": cwd, "env": environment, "stdout": subprocess.PIPE,
              "stderr": subprocess.STDOUT, "bufsize": 0}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    process = subprocess.Popen(command, **options)
    chunks = queue.Queue()

    def read_output():
        try:
            while True:
                chunk = process.stdout.read(4096)
                if not chunk:
                    break
                chunks.put(chunk)
        finally:
            chunks.put(None)

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()
    deadline = time.monotonic() + seconds
    timed_out = False
    budget_exceeded = False
    action_count = 0
    event_buffer = ""
    finished_reading = False
    with open(output_path, "ab" if append else "wb") as output:
        while not finished_reading:
            remaining = deadline - time.monotonic()
            if remaining <= 0 and (process.poll() is None or reader.is_alive()):
                timed_out = True
                try:
                    if os.name == "nt":
                        process.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        os.killpg(process.pid, signal.SIGTERM)
                except (OSError, ValueError):
                    process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    if os.name == "nt":
                        process.kill()
                    else:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except OSError:
                            process.kill()
                    process.wait()
                remaining = 0.1
            try:
                chunk = chunks.get(timeout=min(0.1, max(0.01, remaining)))
            except queue.Empty:
                if process.poll() is not None and not reader.is_alive():
                    finished_reading = True
                continue
            if chunk is None:
                finished_reading = True
                continue
            output.write(chunk)
            output.flush()
            if action_budget is not None and not budget_exceeded:
                event_buffer += chunk.decode("utf-8", "replace")
                lines = event_buffer.split("\n")
                event_buffer = lines.pop()
                action_count += sum(is_codex_action_event(line) for line in lines)
                if action_count > action_budget:
                    budget_exceeded = True
                    try:
                        if os.name == "nt":
                            process.send_signal(signal.CTRL_BREAK_EVENT)
                        else:
                            os.killpg(process.pid, signal.SIGTERM)
                    except (OSError, ValueError):
                        process.terminate()
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        if os.name == "nt":
                            process.kill()
                        else:
                            try:
                                os.killpg(process.pid, signal.SIGKILL)
                            except OSError:
                                process.kill()
                        process.wait()
            try:
                sys.stdout.buffer.write(chunk)
                sys.stdout.buffer.flush()
            except (AttributeError, OSError):
                sys.stdout.write(chunk.decode("utf-8", "replace"))
                sys.stdout.flush()
    reader.join(timeout=1)
    if timed_out:
        return 124
    if budget_exceeded:
        return 125
    code = process.wait()
    return 128 + abs(code) if code < 0 else code


def execute_task_cli(args):
    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    environment = os.environ.copy()
    environment.update(PORT=args.worker_port, TEST_PORT=args.worker_port)
    if args.provider in ("codex", "agy"):
        environment["MAX_STEPS"] = str(args.step_budget)
    environment.pop("AI_AGENTS_JSON", None)
    environment.pop("AI_AGENT_STATE_FILE", None)
    if args.provider == "agy":
        environment["AGY_MAX_STEPS"] = str(args.step_budget)
    output = Path(args.output_file)
    result_code = 0
    last_message = Path(args.result_file) if args.result_file else None
    if args.provider == "codex":
        codex = argparse.Namespace(
            last_message=str(last_message), model=args.model, effort=args.effort,
            approval_mode=args.approval_mode, sandbox=args.sandbox,
            ephemeral=args.ephemeral, additional_dirs=args.additional_dirs,
        )
        command = [args.executable, *codex_args(codex), prompt]
        result_code = stream_with_timeout(args.timeout, command, args.work_dir,
                                          environment, output, action_budget=args.step_budget)
        codex_output = output.read_text(encoding="utf-8", errors="replace")
        actions_used = count_codex_actions(codex_output)
        if actions_used > args.step_budget:
            print(f"[WORKER] Codex action budget exceeded ({actions_used}/{args.step_budget}).")
            return 125
        result_path = last_message if last_message and last_message.is_file() and last_message.stat().st_size else output
        if (result_code == 0 and args.approval_mode in ("auto", "approve-for-me")
                and not re.search(r"\[(?:SCOPE_BLOCKED|NEED_GUIDANCE|NEED_DECOMPOSITION|BLOCKED)\]",
                                  result_path.read_text(encoding="utf-8", errors="replace"))):
            closeout_requested = "[CLOSEOUT_REQUIRED]" in result_path.read_text(encoding="utf-8", errors="replace")
            if not closeout_requested:
                targets = [item.strip() for item in args.target.split(",") if item.strip()]
                for target in targets:
                    subprocess.run(["git", "-C", args.work_dir, "add", "-A", "--", target],
                                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                staged = subprocess.run(["git", "-C", args.work_dir, "diff", "--cached", "--quiet"],
                                        check=False)
                if staged.returncode:
                    title = args.title
                    commit_type = ("fix" if "[CODE: FIX]" in title else
                                   "refactor" if "[CODE: REFACTOR]" in title else
                                   "docs" if "[RESEARCH]" in title else
                                   "test" if "[DIAGNOSTIC]" in title else "feat")
                    commit = subprocess.run([
                        "git", "-C", args.work_dir, "commit", "-m",
                        f"{commit_type}(worker): complete {args.task_id}", "-m",
                        f"Task: {args.task_id} (Level {args.level})\nScope: {args.target or '<modified files>'}\n"
                        f"Verification: {args.verify or '<worker post-flight>'}\n"
                        "Attempts: wrapper-managed | Confidence: pending audit",
                    ], check=False)
                    if commit.returncode:
                        print(f"[WORKER] Failed to commit Codex changes for {args.task_id}.", file=sys.stderr)
                        result_code = 1
            if result_code == 0 and closeout_requested:
                result_code = run_codex_closeout(args, environment, output, actions_used)
    elif args.provider == "agy":
        agy = argparse.Namespace(
            sandbox=args.use_sandbox, mode=args.agy_mode, model=args.model,
            timeout=str(args.timeout), additional_dirs=args.additional_dirs,
            effort=args.effort, executable=args.executable,
            step_budget=args.step_budget,
        )
        command = [args.executable, "-p", prompt, "--dangerously-skip-permissions", *agy_args(agy)]
        result_code = stream_with_timeout(args.timeout, command, args.work_dir,
                                          environment, output)
        text = output.read_text(encoding="utf-8", errors="replace")
        steps_used = count_agy_steps(text)
        if result_code == 0 and steps_used >= args.step_budget:
            print(f"[WORKER] AgY action budget exhausted ({steps_used}/{args.step_budget}).")
            return 125
        if result_code == 0 and steps_used < args.step_budget:
            head = subprocess.run(["git", "-C", args.work_dir, "rev-parse", "HEAD"],
                                  capture_output=True, text=True, check=False).stdout.strip()
            dirty = subprocess.run(["git", "-C", args.work_dir, "status", "--porcelain"],
                                   capture_output=True, text=True, check=False).stdout
            dirty = "\n".join(line for line in dirty.splitlines()
                              if not re.search(r"progress\.log|tasks\.txt|tasks\.done|worker\..*\.status|\.preview|\.worker\..*|\.reports/|\.reports", line))
            if head != args.base or not dirty:
                return result_code
            remaining = args.step_budget - steps_used
            print(f"[WORKER] Starting one restricted ghost closeout ({steps_used}/{args.step_budget} actions used).")
            # The ghost may verify and commit existing work, but the diff against
            # the original base must remain byte-for-byte unchanged.
            before_snapshot = workspace_snapshot(args.work_dir, args.base)
            prompt = build_ghost_closeout_prompt(args.task_id, args.verify, args.progress_file)
            environment["MAX_STEPS"] = str(remaining)
            environment["AGY_MAX_STEPS"] = str(remaining)
            continuation = argparse.Namespace(**vars(agy))
            continuation.step_budget = remaining
            command = [args.executable, "-p", prompt, "--dangerously-skip-permissions", *agy_args(continuation)]
            result_code = stream_with_timeout(args.timeout, command, args.work_dir,
                                              environment, output, append=True)
            text = output.read_text(encoding="utf-8", errors="replace")
            after_snapshot = workspace_snapshot(args.work_dir, args.base)
            if before_snapshot != after_snapshot:
                print("[WORKER] Ghost closeout changed implementation files; rejecting closeout.", file=sys.stderr)
                return 126
            added_steps = count_agy_steps(text) - steps_used
            if added_steps > remaining:
                return 125
            if "[CLOSEOUT_INCOMPLETE]" in text:
                return 126
    else:
        result_code = stream_with_timeout(args.timeout, [args.executable, prompt],
                                          args.work_dir, environment, output)
    if result_code == 0 and "print timeout after" in output.read_text(
            encoding="utf-8", errors="replace").lower():
        result_code = 124
    return result_code


def build_task_prompt(task, task_id, level, target, verify, forbidden, constraints,
                      max_steps, target_file_count, step_base, step_per_file, progress_file):
    return f"""Execute one unattended NightShift task. Read .skills/universal-build-verify.md and .worker.notes.md first; follow the applicable skill:
- [CODE]: .agents/skills/engineering/tdd/SKILL.md; consult .agents/skills/engineering/codebase-design/SKILL.md when changing an interface.
- [DIAGNOSTIC]: .agents/skills/engineering/diagnosing-bugs/SKILL.md.
- [RESEARCH]: .agents/skills/engineering/research/SKILL.md and .agents/skills/nightshift/explore/SKILL.md.

TASK:
{task}
TASK_ID: {task_id}

LIMITS
- Action budget: {max_steps} (base {step_base} + {target_file_count} target files × {step_per_file}). Keep the final 3 actions for verification and Git closeout. The runtime enforces this limit; do not evade it by combining actions.
- Timeout is per task invocation. Work only in TARGET ({target or 'the declared target paths'}); report [SCOPE_BLOCKED] with the missing path and line if more scope is required.
- At level {level or '1'}, deletion ceilings are L3 40 lines, L2 150 lines, and L1 TARGET-bounded. [CODE: FIX] keeps tests unchanged; [CODE: REFACTOR] may change declared tests but cannot reduce assertions. [DIAGNOSTIC] may add a compile-clean repro test, never product code. [RESEARCH] reads product code only and writes the requested report.
- Honor FORBIDDEN_SHORTCUTS ({forbidden or 'none specified'}) and CONSTRAINTS ({constraints or 'none specified'}). Never weaken assertions, hide errors, use dummy behavior, or use thread sleeps to mask a race. Do not run sudo or host package managers.

WORK
- Keep each action independent. Before every AgY tool call, emit one `[EXEC] <brief action>` line; the runtime counts these as steps. Codex actions are counted from CLI events. Do not dictate command formatting, bundle actions, or fabricate markers to evade the budget.
- Run {verify or 'the task verification'} and report only checks actually completed. A [DEAD_END] claim needs an isolated passing test or runtime evidence that the suspected module is healthy while the symptom remains.
- Make at most 3 implementation attempts. If blocked, report [BLOCKED] and the cause; the runtime preserves failed work and restores the task baseline. Do not destructively reset files. Do not edit {progress_file}; the runtime records the task and performs mechanical audits.
- Commit only after verification passes, with only task changes staged. Use a concise English Conventional Commit and include the task ID. End your report with Attempts: <N> | Confidence: <HIGH|MED|LOW>. The Planner reviews the evidence and records the score; never adjust the shared score yourself.
- If implementation is complete and only verification/Git closeout remains, stop and emit [CLOSEOUT_REQUIRED]. The runtime may launch one restricted closeout for this task; it may verify and finalize existing changes but may not edit project files. If implementation remains, stop.
"""


def env_bool(name, default="0"):
    return os.environ.get(name, default).lower() in ("1", "true", "yes", "on")


def acquire_worker_lock(path, pid):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            descriptor = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            try:
                old_pid = int(path.read_text(encoding="utf-8").strip())
                if old_pid > 0:
                    os.kill(old_pid, 0)
                    print(f"ERROR: Worker daemon already running with PID {old_pid}.", file=sys.stderr)
                    return False
            except ProcessLookupError:
                pass
            except PermissionError:
                print("ERROR: Existing worker PID cannot be checked; assuming it is active.", file=sys.stderr)
                return False
            except (ValueError, FileNotFoundError):
                pass
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            continue
        else:
            try:
                os.write(descriptor, f"{pid}\n".encode("ascii"))
            finally:
                os.close(descriptor)
            return True


def worker_daemon(root):
    root = Path(root).resolve()
    config = os.environ
    worker_id = config.get("WORKER_ID", "default")

    def resolve(name, default):
        path = Path(config.get(name) or default)
        return path if path.is_absolute() else root / path

    tasks_file = resolve("TASKS_FILE", "tasks.txt")
    done_file = resolve("TASKS_DONE_FILE", "tasks.done")
    progress_file = resolve("PROGRESS_FILE", "progress.log")
    pause_file = resolve("PAUSE_FILE", "PAUSE")
    status_file = (resolve("STATUS_FILE", "worker.status") if worker_id == "default"
                   else root / f"worker.{worker_id}.status")
    log_file = (resolve("LOG_FILE", ".worker.log") if worker_id == "default"
                else root / f".worker.{worker_id}.log")
    pid_file = (resolve("PID_FILE", ".worker.pid") if worker_id == "default"
                else root / f".worker.{worker_id}.pid")
    ai_cli = config.get("AI_CLI", "codex")
    ai_model = config.get("AI_MODEL", "")
    ai_effort = config.get("AI_EFFORT", "")
    agy_mode = config.get("AGY_MODE", "accept-edits")
    agents = parse_agent_registry(config.get("AI_AGENTS_JSON", ""), {
        "model": ai_model, "effort": ai_effort, "agy_mode": agy_mode,
    })
    safe_worker_id = re.sub(r"[^A-Za-z0-9_.-]", "_", worker_id)
    agent_state_path = resolve(
        "AI_AGENT_STATE_FILE", f".worker-agent-state.{safe_worker_id}.json")
    score_state_path = resolve("WORKER_SCORE_FILE", ".worker-score.json")
    timeout_value = float(config.get("TASK_TIMEOUT", "1800"))
    timeout = int(timeout_value) if timeout_value.is_integer() else timeout_value
    step_base = int(config.get("STEP_BASE", "12"))
    step_per_file = int(config.get("STEP_PER_FILE", "5"))
    poll_interval = float(config.get("POLL_INTERVAL", "5"))
    worker_port = config.get("WORKER_PORT", "3001")
    isolated = env_bool("WORKER_ISOLATION", "1")
    work_dir = root / ".worker-tree" if isolated else root
    isolation_flag = "true" if isolated else "false"
    system = platform.system()
    linux_release = Path("/etc/os-release")
    is_ubuntu = (linux_release.is_file()
                 and "ubuntu" in linux_release.read_text(encoding="utf-8", errors="replace").lower())
    detected_os = "mac" if system == "Darwin" else "ubuntu" if system == "Linux" and is_ubuntu else "linux" if system == "Linux" else "unknown"
    active_os = config.get("OS_TYPE", "auto")
    if not active_os or active_os == "auto":
        active_os = detected_os
    platform_name = ("macOS (Darwin)" if active_os in ("mac", "darwin") else
                     "Linux (Ubuntu)" if active_os == "ubuntu" else f"Linux ({active_os})")
    step_args = {"step_base": step_base, "step_per_file": step_per_file}

    for name, default in (("CI", "1"), ("PAGER", "cat"), ("NO_COLOR", "1"),
                          ("DEBIAN_FRONTEND", "noninteractive"), ("TERM", "dumb"),
                          ("NIGHTSHIFT_WORKER", "1")):
        os.environ[name] = config.get(name, default)

    pid = os.getpid()
    if not acquire_worker_lock(pid_file, pid):
        return 1
    stop_requested = threading.Event()
    final_state = "STOPPED"
    def request_stop(signum, frame):
        stop_requested.set()
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    def update_status(state, task="", elapsed=0, current=0, total=0, remaining=0,
                      percentage="0%", bar=""):
        status_args = argparse.Namespace(
            path=str(status_file), worker_id=worker_id, os_name=active_os,
            platform=platform_name, isolation=isolation_flag, work_dir=str(work_dir),
            state=state, current_task=task, elapsed=int(elapsed),
            current_index=int(current), total_tasks=int(total), remaining=int(remaining),
            percentage=percentage, bar=bar or progress_bar(int(current), int(total)),
            pid=pid, model=ai_model, cli=ai_cli, timeout=timeout,
            worker_score=read_score_state(score_state_path)["score"],
        )
        write_status(status_args)

    def append_line(path, line):
        with Path(path).open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    def stamp():
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        for path in (tasks_file, done_file, progress_file):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch(exist_ok=True)
        (root / ".reports/.archive").mkdir(parents=True, exist_ok=True)
        if isolated:
            ensure_worktree(root)
        inside = subprocess.run(["git", "-C", str(work_dir), "rev-parse", "--is-inside-work-tree"],
                                capture_output=True, check=False).returncode == 0
        if inside:
            subprocess.run(["git", "-C", str(work_dir), "tag", "-f", "nightshift-session-base", "HEAD"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(["git", "-C", str(root), "tag", "-f", "nightshift-session-base", "HEAD"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        mode = (f"sandbox={config.get('CODEX_SANDBOX', 'workspace-write')},approval={config.get('CODEX_APPROVAL_MODE', 'auto')},ephemeral={config.get('CODEX_EPHEMERAL', '1')}"
                if ai_cli == "codex" else agy_mode)
        print("=" * 78)
        print(" 24-Hour Unattended AI Worker Daemon Started")
        print(f" Worker ID: {worker_id} | OS: {platform_name} (CPUs: {os.cpu_count() or 4})")
        print(f" PID: {pid} | CLI: {ai_cli} | Model: {ai_model or 'configured default'} | Mode: {mode}")
        print(f" WorkDir: {work_dir} | Isolation: {isolation_flag}")
        print(f" Tasks: {tasks_file} | Status: {status_file}")
        print(f" Progress: {progress_file} | Log: {log_file}")
        print("=" * 78)
        update_status("IDLE", bar="[------------------------------] 0%")
        was_busy = False
        idle_status_shown = False
        run_once = env_bool("RUN_ONCE", "0")

        while not stop_requested.is_set():
            poll_args = argparse.Namespace(tasks=str(tasks_file), done=str(done_file),
                                           pause=str(pause_file), work_dir=str(work_dir),
                                           **step_args)
            fields = poll_next(poll_args)
            if fields[0] == "paused":
                print(f"[{stamp()}] [PAUSED] Found {pause_file}. Sleeping...")
                update_status("PAUSED", f"Paused via {pause_file} file", percentage="0%", bar="[PAUSED]")
                stop_requested.wait(poll_interval)
                continue
            raw_task, done_count, remaining = fields[1], int(fields[2]), int(fields[3])
            total, current = int(fields[4]), int(fields[5])
            percent, bar = f"{fields[6]}%", fields[7]
            if fields[0] == "idle":
                update_status("IDLE", current=done_count, total=total, percentage="100%", bar=bar)
                if was_busy:
                    print(f"\n{'=' * 78}\n[{stamp()}] 🎉 [ALL TASKS COMPLETED] {bar}")
                    print(f"[IDLE] Queue is empty (Total completed: {done_count} tasks).\n{'=' * 78}")
                    was_busy, idle_status_shown = False, True
                    if run_once:
                        print("[WORKER] Exiting because RUN_ONCE is enabled.")
                        break
                elif not idle_status_shown:
                    print(f"[{stamp()}] [IDLE] Queue is empty (Total completed: {done_count} tasks). Waiting for tasks in {tasks_file}...")
                    idle_status_shown = True
                    if run_once:
                        print("[WORKER] Queue is empty and RUN_ONCE is enabled. Exiting.")
                        break
                stop_requested.wait(poll_interval)
                continue

            was_busy, idle_status_shown = True, False
            task, task_id, level = raw_task, fields[8], fields[9]
            target, verify, forbidden, constraints = fields[10], fields[11], fields[12], fields[13]
            target_file_count, max_steps = int(fields[14]), int(fields[15])
            head = subprocess.run(["git", "-C", str(work_dir), "rev-parse", "HEAD"],
                                  capture_output=True, text=True, check=False)
            base = head.stdout.strip() if head.returncode == 0 else "HEAD~1"
            started = time.time()
            is_research = bool(re.search(r"\[RESEARCH\]", f"{task} {constraints}", re.I))
            is_diagnostic = bool(re.search(r"\[DIAGNOSTIC\]", f"{task} {constraints}", re.I))
            if is_research:
                archive_active_reports(root)
            print(f"\n{'=' * 78}\n[{stamp()}] >>> [Task {current} of {total} (In Progress) | Completed: {done_count}/{total} ({fields[6]}%)]")
            print(f">>> Progress: {bar}\n>>> Task: {task}")
            print(f">>> Step Budget: {max_steps} steps (Base: {step_base} + {target_file_count} files * {step_per_file})\n{'=' * 78}")
            update_status("RUNNING", task, current=current, total=total,
                          remaining=max(0, remaining - 1), percentage=percent, bar=bar)
            prompt = build_task_prompt(task, task_id, level, target, verify, forbidden,
                                       constraints, max_steps, target_file_count,
                                       step_base, step_per_file, progress_file)
            with tempfile.TemporaryDirectory(prefix="nightshift-task-") as temporary:
                prompt_path = Path(temporary) / "prompt.txt"
                output_path = Path(temporary) / "cli-output.log"
                result_path = Path(temporary) / "last-message.txt"
                prompt_path.write_text(prompt, encoding="utf-8")
                provider = ai_cli if ai_cli in ("codex", "agy") else "generic"
                print(f"[WORKER] Launching {ai_cli} (Model: {ai_model or 'configured default'}, StepBudget: {max_steps}, WorkDir: {work_dir})...")
                cli_args = argparse.Namespace(
                    provider=provider, executable=ai_cli, work_dir=str(work_dir),
                    prompt_file=str(prompt_path), output_file=str(output_path),
                    result_file=str(result_path) if provider == "codex" else "",
                    timeout=timeout, model=ai_model, effort=ai_effort,
                    approval_mode=config.get("CODEX_APPROVAL_MODE", "auto"),
                    sandbox=config.get("CODEX_SANDBOX", "workspace-write"),
                    ephemeral=config.get("CODEX_EPHEMERAL", "1"),
                    additional_dirs=config.get("ADDITIONAL_DIRS", ""),
                    use_sandbox=config.get("USE_SANDBOX", "0"), agy_mode=agy_mode,
                    step_budget=max_steps, worker_port=worker_port, target=target,
                    task_id=task_id, title=task, level=level, verify=verify,
                    base=base, progress_file=str(progress_file),
                )
                quota_exhausted = False
                try:
                    if agents:
                        exit_code, quota_exhausted = execute_registered_agents(
                            cli_args, agents, agent_state_path,
                            lambda: rollback_failed_task(
                                root, work_dir, task_id,
                                (tasks_file, done_file, progress_file, agent_state_path),
                            ),
                        )
                    else:
                        exit_code = execute_task_cli(cli_args)
                except (OSError, ValueError, subprocess.CalledProcessError) as error:
                    print(f"[WORKER] CLI execution failed: {error}", file=sys.stderr)
                    exit_code = 2
                    quota_exhausted = False
                result_output = result_path if result_path.is_file() and result_path.stat().st_size else output_path
                duration = int(time.time() - started)
                append_line(log_file, f"=== [{stamp()}] Task: {task} (Duration: {duration}s, Exit: {exit_code}) ===")
                with Path(log_file).open("a", encoding="utf-8") as stream:
                    stream.write(output_path.read_text(encoding="utf-8", errors="replace") if output_path.exists() else "")
                    stream.write("\n")
                result_text = result_output.read_text(encoding="utf-8", errors="replace") if result_output.exists() else ""

                outcome = ("quota_exhausted" if quota_exhausted else
                           "timeout" if exit_code == 124 else
                           "step_budget" if exit_code == 125 else
                           "closeout_failed" if exit_code == 126 else
                           "scope" if "[SCOPE_BLOCKED]" in result_text else
                           "guidance" if re.search(r"\[(?:NEED_GUIDANCE|NEED_DECOMPOSITION)\]", result_text) else
                           "error" if exit_code else "success")
                stamp_now = stamp()
                if outcome == "quota_exhausted":
                    restore_task_front(tasks_file, raw_task)
                    final_state = "QUOTA_EXHAUSTED"
                    warning = ("=" * 80 + f"\n[QUOTA_EXHAUSTED] {task_id}: All registered agents are exhausted\n"
                               f"Time: {stamp_now} | Status: QUOTA_EXHAUSTED\n"
                               f"Task returned to {tasks_file}; remove or edit {agent_state_path} after quota resets.\n"
                               "Worker stopped without marking the task failed.\n" + "=" * 80)
                    prepend_progress(progress_file, warning)
                    print(f"[{stamp_now}] [QUOTA_EXHAUSTED] All registered agent quotas are exhausted; stopping worker.")
                    update_status("QUOTA_EXHAUSTED", task, duration, current, total,
                                  remaining, percent, bar)
                    break
                elif outcome == "timeout":
                    print(f"[{stamp_now}] [TIMEOUT] Task exceeded {timeout}s limit!")
                    record_score_result(score_state_path, task_id, "hard_failure",
                                        f"timeout after {timeout}s")
                    rollback_failed_task(root, work_dir, task_id,
                                         (tasks_file, done_file, progress_file))
                    summary = ("=" * 80 + f"\n[BLOCKED] {task_id}: Timeout Exceeded ({timeout}s)\n"
                               f"Time: {stamp_now} | Status: TIMEOUT\nFailure Reason: Task execution timed out after {timeout} seconds.\n"
                               "Action Needed for Human: Task may be too complex. Split into smaller atomic tasks.\n" + "=" * 80)
                    prepend_progress(progress_file, summary)
                    append_line(done_file, f"[{stamp_now}] [FAILED] {task} [TIMEOUT]")
                    update_status("BLOCKED", f"{task} (TIMEOUT)", duration, current, total,
                                  max(0, remaining - 1), percent, bar)
                elif outcome in ("step_budget", "closeout_failed"):
                    reason = ("Codex/AgY action budget exhausted" if outcome == "step_budget"
                              else "Restricted ghost closeout failed or attempted implementation")
                    print(f"[{stamp_now}] [HARD FAILURE] {task_id}: {reason}")
                    record_score_result(score_state_path, task_id, "hard_failure", reason)
                    rollback_failed_task(root, work_dir, task_id,
                                         (tasks_file, done_file, progress_file))
                    prepend_progress(progress_file,
                                     f"[HARD_FAILURE] {task_id}: {reason}; score now {read_score_state(score_state_path)['score']}/5")
                    append_line(done_file, f"[{stamp_now}] [FAILED] {task} [{outcome.upper()}]")
                    update_status("BLOCKED", f"{task} ({outcome.upper()})", duration, current,
                                  total, max(0, remaining - 1), percent, bar)
                elif outcome == "scope":
                    print(f"[{stamp_now}] 🚧 [SCOPE BLOCKED] Worker honestly stopped at unannounced downstream boundaries.")
                    rollback_failed_task(root, work_dir, task_id, (tasks_file, done_file, progress_file))
                    summary = ("=" * 80 + f"\n[SCOPE_BLOCKED] {task_id}: Downstream Scope Boundary Reached\n"
                               f"Time: {stamp_now} | Status: SCOPE_BLOCKED\nDetails: Compiler errors detected in files outside TARGET whitelist.\n"
                               "Worker honestly stopped without violating boundaries. (No credit deduction).\n"
                               "Action Needed for Human: Expand TARGET in tasks.txt or adopt Expand-Migrate-Contract.\n" + "=" * 80)
                    prepend_progress(progress_file, summary)
                    append_line(done_file, f"[{stamp_now}] [SCOPE_BLOCKED] {task}")
                    update_status("SCOPE_BLOCKED", task, duration, current, total,
                                  max(0, remaining - 1), percent, bar)
                elif outcome == "guidance":
                    print(f"[{stamp_now}] ✋ [AWAITING GUIDANCE] Worker honestly requested manager guidance.")
                    rollback_failed_task(root, work_dir, task_id, (tasks_file, done_file, progress_file))
                    append_line(done_file, f"[{stamp_now}] [GUIDANCE_REQUESTED] {task}")
                    update_status("AWAITING_GUIDANCE", task, duration, current, total,
                                  max(0, remaining - 1), percent, bar)
                elif outcome == "error":
                    print(f"[{stamp_now}] [ERROR] CLI exited with code {exit_code}")
                    rollback_failed_task(root, work_dir, task_id, (tasks_file, done_file, progress_file))
                    summary = ("=" * 80 + f"\n[BLOCKED] {task_id}: Execution Failed (Exit Code: {exit_code})\n"
                               f"Time: {stamp_now} | Status: FAILED\nFailure Reason: Worker CLI returned non-zero exit status {exit_code}.\n"
                               "Action Needed for Human: Inspect .worker.log for error details.\n" + "=" * 80)
                    prepend_progress(progress_file, summary)
                    append_line(done_file, f"[{stamp_now}] [FAILED] {task} [EXIT_{exit_code}]")
                    update_status("BLOCKED", f"{task} (ERROR {exit_code})", duration, current, total,
                                  max(0, remaining - 1), percent, bar)
                else:
                    audit_args = argparse.Namespace(
                        work_dir=str(work_dir), base=base, target=target,
                        constraints=constraints, title=task, level=int(level or 1),
                        task_id=task_id, verify=verify, port=worker_port, verify_timeout=180,
                    )
                    audit = mechanical_audit(audit_args)
                    for message in audit["messages"]:
                        print(message)
                    guard_status, guard_error = audit["status"], audit["error"]
                    if guard_status:
                        print(f"[{stamp()}] 🛑 [GUARD REJECTION] Post-flight validation failed: {guard_error}")
                        rollback_failed_task(root, work_dir, task_id,
                                             (tasks_file, done_file, progress_file))
                        summary = (f"[MECHANICAL_AUDIT] Status: FAIL | Verify_Exit: {audit['verify_exit']} | Whitelist: {guard_status} | Tree: DIRTY\n"
                                   + "=" * 80 + f"\n[BLOCKED] {task_id}: Guard Validation Failed\n"
                                   f"Time: {stamp()} | Status: GUARD_VIOLATION\nFailure Reason: {guard_error}\n"
                                   "Action Needed for Human: Inspect error and check target whitelist, forbidden shortcuts, or test assertions.\n"
                                   + "=" * 80)
                        prepend_progress(progress_file, summary)
                        append_line(done_file, f"[{stamp()}] [FAILED] {task} [GUARD_VIOLATION]")
                        update_status("BLOCKED", f"{task} (GUARD VIOLATION)", duration,
                                      current, total, max(0, remaining - 1), percent, bar)
                    else:
                        record_score_result(score_state_path, task_id, "success")
                        attempts_match = re.search(r"Attempts:\s*(\d+)", result_text)
                        if not attempts_match and progress_file.exists():
                            attempts_match = re.search(r"Attempts:\s*(\d+)", progress_file.read_text(encoding="utf-8", errors="replace"))
                        attempts = attempts_match.group(1) if attempts_match else "1"
                        diff = subprocess.run(["git", "-C", str(work_dir), "diff", "--stat", base, "HEAD"],
                                               capture_output=True, text=True, check=False).stdout.splitlines()
                        diff_stat = diff[-1].strip() if diff else "0 files changed"
                        prepend_progress(progress_file, f"[MECHANICAL_AUDIT] Status: PASS | Verify_Exit: 0 | Tests_Run: >=1 | Whitelist: PASS | Tree: CLEAN | Diff: {diff_stat} | Attempts: {attempts}")
                        if not (is_research or is_diagnostic):
                            archive_overlapping_reports(root, work_dir, base)
                        if isolated:
                            try:
                                commit_hash = publish_preview(root, task_id, task)
                                print(f"[WORKER] Staged preview drop-box at .preview/ (Commit: {commit_hash})")
                            except (OSError, ValueError, subprocess.CalledProcessError) as error:
                                print(f"[WORKER] Preview staging failed for {task_id}: {error}", file=sys.stderr)
                        new_done = done_count + 1
                        final_bar = progress_bar(new_done, total)
                        print(f"[{stamp()}] [SUCCESS] Task completed in {duration}s | {final_bar}")
                        append_line(done_file, f"[{stamp()}] [DONE] {task} (Duration: {duration}s)")
                        update_status("IDLE", current=new_done, total=total,
                                      remaining=max(0, remaining - 1),
                                      percentage=f"{new_done * 100 // total if total else 0}%", bar=final_bar)
            stop_requested.wait(poll_interval)
        return 0
    finally:
        try:
            pid_file.unlink(missing_ok=True)
        except OSError:
            pass
        try:
            update_status(final_state, bar="[------------------------------] 0%")
        except (OSError, ValueError):
            pass


def git_audit(args):
    """Return the existing post-flight guard code and a human-readable reason."""
    def git(*command):
        return subprocess.run(["git", "-C", args.work_dir, *command],
                              check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout

    status = git("status", "--porcelain", "--untracked-files=all", "-z")
    ignored = re.compile(r"progress\.log|tasks\.txt|tasks\.done|worker\..*\.status|\.preview|\.reports")
    dirty = [entry.decode("utf-8", "replace") for entry in status.split(b"\0")
             if entry and not ignored.search(entry.decode("utf-8", "replace"))]
    if dirty:
        return 1, "Dirty working tree or untracked ghost files detected after task. " + ", ".join(dirty)

    changed = [name.decode("utf-8", "replace") for name in
               git("diff", "--name-only", "-z", args.base, "HEAD").split(b"\0") if name]
    context = f"{args.title} {args.constraints}"
    diagnostic = bool(re.search(r"\[DIAGNOSTIC\]", context, re.I))
    research = bool(re.search(r"\[RESEARCH\]", context, re.I))
    if diagnostic and any(re.match(r"^(Sources|src|app|lib)/", name, re.I) for name in changed):
        return 4, "Diagnostic Violation: Modifying production code in [DIAGNOSTIC] is strictly forbidden. Only tests and .reports/ allowed."

    if not diagnostic and not research:
        tests = [name for name in changed if re.search(r"(^tests/|^Tests/|^test/|Test\.[a-z]+$|_test\.[a-z]+$)", name, re.I)]
        if tests:
            unauthorized = (bool(re.search(r"\[CODE:\s*FIX\]", args.title, re.I))
                            or not re.search(r"tests/|Tests/|test", args.target, re.I))
            if unauthorized and not re.search(r"test refactor approved", args.constraints, re.I):
                return 5, f"Test Immutability Violation: Modified test files without authorization in TARGET ({', '.join(tests)})."
            diff = git("diff", args.base, "HEAD", "--", *tests).decode("utf-8", "replace")
            assertion = re.compile(r"\s*(XCTAssert|#expect|assert|expect\(|self\.assert)")
            deleted = sum(bool(assertion.match(line[1:])) for line in diff.splitlines()
                          if line.startswith("-") and not line.startswith("---"))
            added = sum(bool(assertion.match(line[1:])) for line in diff.splitlines()
                        if line.startswith("+") and not line.startswith("+++"))
            if deleted > added:
                return 7, f"Assertion Non-Decrease Violation: Deleted {deleted} assertions while adding only {added}."

    numstat = git("diff", "--numstat", args.base, "HEAD").decode("utf-8", "replace")
    deleted_lines = 0
    for line in numstat.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[1].isdigit():
            deleted_lines += int(parts[1])
    if not re.search(r"large deletion approved|unrestricted", args.constraints, re.I):
        limit = {2: 150, 3: 40}.get(args.level)
        if limit is not None and deleted_lines > limit:
            return 8, f"Blast Radius Violation: Level {args.level} tasks cannot delete >{limit} lines (Deleted: {deleted_lines})."

    if args.target and not re.search(r"unrestricted|multi-interface", args.constraints, re.I) and not (diagnostic or research):
        targets = [item.strip().rstrip("/").casefold() for item in args.target.split(",") if item.strip()]
        exempt = {"progress.log", "tasks.txt", "tasks.done", "worker.status", ".gitignore", ".worker.notes.md"}
        for name in changed:
            if name in exempt or name.startswith((".reports/", "docs/reports/")):
                continue
            lowered = name.casefold()
            if not any(lowered == target or lowered.startswith(target + "/") for target in targets):
                return 2, f"Target Whitelist Violation: Modified unannounced file '{name}' outside declared scope."
    return 0, ""


def run_verify(command, work_dir, port, timeout):
    environment = os.environ.copy()
    environment.update(PORT=str(port), TEST_PORT=str(port))
    options = {"cwd": work_dir, "env": environment, "stdout": subprocess.PIPE,
               "stderr": subprocess.STDOUT}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    process = subprocess.Popen(["bash", "-c", command], **options)
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(process.pid, signal.SIGTERM)
        except (OSError, ValueError):
            process.terminate()
        try:
            output, _ = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                process.kill()
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except OSError:
                    process.kill()
            output, _ = process.communicate()
        return 124, output.decode("utf-8", "replace")
    else:
        return process.returncode, output.decode("utf-8", "replace")


def first_report(root, target):
    target_path = Path(root) / target if target else None
    if target_path and target_path.is_file():
        return target_path
    reports = Path(root) / ".reports"
    if reports.exists():
        for current, directories, files in os.walk(reports, followlinks=True):
            if "SUMMARY.md" in files:
                return Path(current) / "SUMMARY.md"
    research = Path(root) / "docs/research"
    if research.exists():
        for current, directories, files in os.walk(research):
            for name in files:
                if name.endswith(".md"):
                    return Path(current) / name
    return None


def mechanical_audit(args):
    guard_status, reason = git_audit(args)
    verify_exit = 0
    messages = []
    if guard_status:
        return {"status": guard_status, "error": reason, "verify_exit": verify_exit,
                "messages": messages}

    context = f"{args.title} {args.constraints}"
    diagnostic = bool(re.search(r"\[DIAGNOSTIC\]", context, re.I))
    research = bool(re.search(r"\[RESEARCH\]", context, re.I))
    verify = args.verify

    if diagnostic:
        messages.append(f"[WORKER_GUARD] 🔍 Executing Mechanical Audit ([DIAGNOSTIC]): {verify or 'None'}")
        if verify:
            verify_exit, output = run_verify(verify, args.work_dir, args.port, args.verify_timeout)
            if re.search(r"error: cannot find|syntax error|compilation failed|build failed|undefined symbol",
                         output, re.I):
                guard_status = 4
                reason = "False Red-Light Detected: Repro failed on compilation/syntax error instead of test assertion."
    elif research:
        messages.append("[WORKER_GUARD] 🔍 Executing Mechanical Audit ([RESEARCH])...")
        status = subprocess.run(["git", "-C", args.work_dir, "status", "--porcelain"],
                                check=False, capture_output=True, text=True).stdout
        dirty = [line for line in status.splitlines() if not re.search(
            r"progress\.log|tasks\.txt|tasks\.done|worker\..*\.status|\.preview|\.worker\..*|\.reports/|\.reports", line)]
        if dirty:
            guard_status = 12
            reason = "Research Zero-Touch Violation: Uncommitted/modified files detected after research (" + "\n".join(dirty) + ")."
        report = first_report(args.work_dir, args.target) if guard_status == 0 else None
        if guard_status == 0:
            if report is None or not report.is_file() or report.stat().st_size == 0:
                guard_status = 11
                reason = "Research Artifact Missing: No non-empty SUMMARY.md found in .reports/ or declared TARGET."
            else:
                content = report.read_text(encoding="utf-8", errors="replace")
                if not re.search(r"^#+\s+", content, re.M):
                    guard_status = 11
                    reason = f"Research Artifact Invalid: Report '{report}' lacks standard markdown headings."
                else:
                    if not content.splitlines()[0].find("REPORT_META:") >= 0:
                        commit = subprocess.run(["git", "-C", args.work_dir, "rev-parse", "--short", "HEAD"],
                                                check=False, capture_output=True, text=True).stdout.strip() or "HEAD"
                        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                        atomic_write(report, f"<!-- REPORT_META: Task={args.task_id} | Commit={commit} | Time={stamp} -->\n{content}")
                        content = report.read_text(encoding="utf-8", errors="replace")
                    messages.append(f"[WORKER_GUARD] ✅ Artifact verified: {report} ({report.stat().st_size} bytes)")
                    pointers = re.findall(r"[a-zA-Z0-9_./-]+\.[a-zA-Z0-9]+#L[0-9]+", content)[:5]
                    for pointer in pointers:
                        file_name, line_number = pointer.rsplit("#L", 1)
                        source = Path(args.work_dir) / file_name
                        if source.is_file():
                            total_lines = source.read_bytes().count(b"\n")
                            if int(line_number) > total_lines:
                                guard_status = 13
                                reason = (f"Pointer Validity Violation: Line {line_number} in pointer '{pointer}' "
                                          f"exceeds total file lines ({total_lines}).")
                                break
                            messages.append(f"[WORKER_GUARD] 🔍 Verified pointer target: {file_name}#L{line_number} (Total lines: {total_lines})")
        if guard_status == 0 and verify and not re.match(r"^(REPORT_ONLY|none)$", verify, re.I):
            messages.append(f"[WORKER_GUARD] 🔍 Executing Custom Research VERIFY: {verify}")
            verify_exit, _ = run_verify(verify, args.work_dir, args.port, args.verify_timeout)
            if verify_exit:
                guard_status = 6
                reason = f"Mechanical Verification Failed: '{verify}' returned exit code {verify_exit} (Expected 0)."
    else:
        messages.append(f"[WORKER_GUARD] 🔍 Executing Mechanical Audit ([CODE]): {verify or 'None'}")
        if verify:
            verify_exit, output = run_verify(verify, args.work_dir, args.port, args.verify_timeout)
            if verify_exit:
                guard_status = 6
                reason = f"Mechanical Verification Failed: '{verify}' returned exit code {verify_exit} (Expected 0)."
            elif re.search(r"(0 tests passed|0 passed|ran 0 tests|0 suites passed|No matching tests)", output, re.I):
                guard_status = 9
                reason = "Empty Test Run Detected (Anti-Idle): VERIFY ran 0 tests. Possible test filter typo."
            elif (Path(args.work_dir) / "Package.swift").is_file():
                messages.append("[WORKER_GUARD] 🔍 Executing Regression Check (swift test)...")
                regression, _ = run_verify("swift test", args.work_dir, args.port, args.verify_timeout)
                if regression:
                    guard_status = 10
                    reason = "Regression Check Failed: Whole-suite regression tests failed."
    return {"status": guard_status, "error": reason, "verify_exit": verify_exit,
            "messages": messages}


def git_at(directory, *argv, check=True):
    return subprocess.run(["git", "-C", str(directory), *argv],
                          check=check, capture_output=True)


def ensure_worktree(root, branch="feature/worker-frontier"):
    root = Path(root).resolve()
    target = root / ".worker-tree"
    if not (target / ".git").is_file():
        if target.exists():
            raise ValueError(f"worktree target exists but is not a Git worktree: {target}")
        present = git_at(root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}", check=False)
        if present.returncode:
            git_at(root, "worktree", "add", "-b", branch, str(target), "HEAD")
        else:
            git_at(root, "worktree", "add", str(target), branch)
    # Only advance the worker branch when the user's branch is ahead and the tree is clean.
    ancestor = git_at(root, "merge-base", "--is-ancestor", branch, "HEAD", check=False)
    if ancestor.returncode == 0 and not git_at(target, "status", "--porcelain").stdout:
        source_head = git_at(root, "rev-parse", "HEAD").stdout.decode().strip()
        git_at(target, "merge", "--ff-only", source_head)
    for name in (".env", ".worker.env"):
        source = root / name
        if source.is_file():
            shutil.copy2(source, target / name)
    for name in ("node_modules", ".venv"):
        source = root / name
        destination = target / name
        if source.is_dir() and not destination.exists() and not destination.is_symlink():
            destination.symlink_to(source, target_is_directory=True)
    reports = root / ".reports"
    (reports / ".archive").mkdir(parents=True, exist_ok=True)
    link = target / ".reports"
    if not link.exists() and not link.is_symlink():
        link.symlink_to(reports, target_is_directory=True)
    return target


def publish_preview(root, task_id, title):
    root = Path(root).resolve()
    worktree = root / ".worker-tree"
    preview = root / ".preview"
    preview.mkdir(parents=True, exist_ok=True)
    archive = git_at(worktree, "archive", "--format=tar", "HEAD").stdout
    with tarfile.open(fileobj=BytesIO(archive)) as content:
        for member in content:
            destination = preview / member.name
            if not destination.resolve().is_relative_to(preview.resolve()):
                raise ValueError(f"unsafe archive path: {member.name}")
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                destination.parent.mkdir(parents=True, exist_ok=True)
                with content.extractfile(member) as source, destination.open("wb") as output:
                    shutil.copyfileobj(source, output)
                destination.chmod(member.mode & 0o777)
            elif member.issym():
                link_target = (destination.parent / member.linkname).resolve()
                if not link_target.is_relative_to(preview.resolve()):
                    raise ValueError(f"unsafe archive link: {member.name}")
                destination.parent.mkdir(parents=True, exist_ok=True)
                if destination.exists() or destination.is_symlink():
                    destination.unlink()
                destination.symlink_to(member.linkname)
    for name in ("build/bin", "target/debug", "bin", "dist"):
        source = worktree / name
        if source.is_dir():
            shutil.copytree(source, preview / name, dirs_exist_ok=True, symlinks=True)
    commit = git_at(worktree, "rev-parse", "--short", "HEAD").stdout.decode().strip()
    metadata = {"task_id": task_id, "commit": commit, "summary": title,
                "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    atomic_write(preview / "version.json", json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    return commit


def report_archive_path(root, timestamp, name):
    archive = Path(root) / ".reports" / ".archive"
    archive.mkdir(parents=True, exist_ok=True)
    return archive / f"{timestamp}-{name}"


def archive_active_reports(root):
    reports = Path(root) / ".reports"
    reports.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for entry in reports.iterdir():
        if entry.name.startswith("."):
            continue
        shutil.move(str(entry), str(report_archive_path(root, timestamp, entry.name)))


def archive_overlapping_reports(root, work_dir, base):
    reports = Path(root) / ".reports"
    reports.mkdir(parents=True, exist_ok=True)
    changed = subprocess.run(
        ["git", "-C", str(work_dir), "diff", "--name-only", base, "HEAD"],
        check=False, capture_output=True, text=True,
    )
    if changed.returncode:
        return
    changed_files = [name for name in changed.stdout.splitlines() if name]
    if not changed_files:
        return
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for entry in reports.iterdir():
        if entry.name.startswith("."):
            continue
        summary = entry / "SUMMARY.md" if entry.is_dir() else entry
        if not summary.is_file():
            continue
        content = summary.read_text(encoding="utf-8", errors="replace")
        if any(changed_file in content for changed_file in changed_files):
            shutil.move(str(entry), str(report_archive_path(root, timestamp, entry.name)))
            print(f"[WORKER] 📦 Archiving stale report '{entry.name}' (referenced file modified in commit)...")


def rollback_failed_task(root, work_dir, task_id, runtime_paths):
    root, work_dir = Path(root).resolve(), Path(work_dir).resolve()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = root / ".scratch" / "failed_tasks" / f"{task_id}_{stamp}"
    suffix = 1
    while backup.exists():
        backup = root / ".scratch" / "failed_tasks" / f"{task_id}_{stamp}_{suffix}"
        suffix += 1
    untracked = subprocess.run(
        ["git", "-C", str(work_dir), "ls-files", "--others", "--exclude-standard", "-z"],
        check=False, capture_output=True,
    )
    (backup / "untracked").mkdir(parents=True)
    print(f"[WORKER] Isolating failed changes to {backup} and resetting clean git tree...",
          file=sys.stderr)

    diff = subprocess.run(["git", "-C", str(work_dir), "diff"],
                          check=False, capture_output=True)
    (backup / "changes.diff").write_bytes(diff.stdout)
    status = subprocess.run(["git", "-C", str(work_dir), "status", "--porcelain"],
                            check=False, capture_output=True)
    (backup / "status.txt").write_bytes(status.stdout)
    for raw_path in untracked.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = Path(os.fsdecode(raw_path))
        source = work_dir / relative
        destination = backup / "untracked" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))

    restore_paths = ["."]
    for runtime_path in runtime_paths:
        try:
            candidate = Path(runtime_path)
            if not candidate.is_absolute():
                candidate = work_dir / candidate
            candidate = candidate.parent.resolve() / candidate.name
            relative = candidate.relative_to(work_dir)
        except ValueError:
            continue
        if str(relative) != ".":
            restore_paths.append(f":(exclude){relative.as_posix()}")
    subprocess.run(["git", "-C", str(work_dir), "restore", "--worktree", "--",
                    *restore_paths], check=False, stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)
    return backup


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    score_read = commands.add_parser("score-read")
    score_read.add_argument("--state", required=True)
    score_record = commands.add_parser("score-record")
    score_record.add_argument("--state", required=True)
    score_record.add_argument("--task-id", required=True)
    score_record.add_argument("--result", choices=("accept", "reject", "no_fault", "hard_failure", "success"), required=True)
    score_record.add_argument("--evidence", default="")
    ghost_prompt = commands.add_parser("ghost-prompt")
    ghost_prompt.add_argument("--output", required=True)
    ghost_prompt.add_argument("--task-id", required=True)
    ghost_prompt.add_argument("--verify", default="")
    ghost_prompt.add_argument("--progress-file", default="progress.log")
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
    agy = commands.add_parser("agy-args")
    agy.add_argument("--executable", default="agy")
    agy.add_argument("--model", default="")
    agy.add_argument("--effort", default="")
    agy.add_argument("--mode", default="")
    agy.add_argument("--timeout", default="1800")
    agy.add_argument("--step-budget", type=int, default=17)
    agy.add_argument("--additional-dirs", default="")
    agy.add_argument("--sandbox", default="0")
    task_cli = commands.add_parser("task-cli")
    task_cli.add_argument("--provider", choices=("codex", "agy", "generic"), required=True)
    task_cli.add_argument("--executable", required=True)
    task_cli.add_argument("--work-dir", required=True)
    task_cli.add_argument("--prompt-file", required=True)
    task_cli.add_argument("--output-file", required=True)
    task_cli.add_argument("--result-file", default="")
    task_cli.add_argument("--timeout", type=float, default=1800)
    task_cli.add_argument("--model", default="")
    task_cli.add_argument("--effort", default="")
    task_cli.add_argument("--approval-mode", default="auto")
    task_cli.add_argument("--sandbox", default="workspace-write")
    task_cli.add_argument("--ephemeral", default="1")
    task_cli.add_argument("--additional-dirs", default="")
    task_cli.add_argument("--use-sandbox", default="0")
    task_cli.add_argument("--agy-mode", default="")
    task_cli.add_argument("--step-budget", type=int, default=17)
    task_cli.add_argument("--worker-port", default="3001")
    task_cli.add_argument("--target", default="")
    task_cli.add_argument("--task-id", default="TASK-UNKNOWN")
    task_cli.add_argument("--title", default="")
    task_cli.add_argument("--level", default="1")
    task_cli.add_argument("--verify", default="")
    task_cli.add_argument("--base", default="")
    task_cli.add_argument("--progress-file", default="progress.log")
    timeout = commands.add_parser("run-timeout")
    timeout.add_argument("seconds", type=float)
    timeout.add_argument("argv", nargs=argparse.REMAINDER)
    audit = commands.add_parser("git-audit")
    audit.add_argument("--work-dir", required=True)
    audit.add_argument("--base", required=True)
    audit.add_argument("--target", default="")
    audit.add_argument("--constraints", default="")
    audit.add_argument("--title", default="")
    audit.add_argument("--level", type=int, default=1)
    setup = commands.add_parser("ensure-worktree")
    setup.add_argument("--root", required=True)
    setup.add_argument("--branch", default="feature/worker-frontier")
    preview = commands.add_parser("publish-preview")
    preview.add_argument("--root", required=True)
    preview.add_argument("--task-id", required=True)
    preview.add_argument("--title", required=True)
    archive = commands.add_parser("archive-reports")
    archive.add_argument("--root", required=True)
    overlap = commands.add_parser("archive-overlapping-reports")
    overlap.add_argument("--root", required=True)
    overlap.add_argument("--work-dir", required=True)
    overlap.add_argument("--base", default="HEAD~1")
    rollback = commands.add_parser("rollback-failed-task")
    rollback.add_argument("--root", required=True)
    rollback.add_argument("--work-dir", required=True)
    rollback.add_argument("--task-id", required=True)
    rollback.add_argument("--tasks", required=True)
    rollback.add_argument("--tasks-done", default="")
    rollback.add_argument("--progress", default="")
    progress = commands.add_parser("progress-prepend")
    progress.add_argument("--path", required=True)
    progress.add_argument("--entry", required=True)
    audit = commands.add_parser("mechanical-audit")
    for name in ("work-dir", "base", "task-id"):
        audit.add_argument(f"--{name}", required=True)
    for name in ("target", "constraints", "title", "verify"):
        audit.add_argument(f"--{name}", default="")
    audit.add_argument("--level", type=int, default=1)
    audit.add_argument("--port", default="3001")
    audit.add_argument("--verify-timeout", type=float, default=180)
    poll = commands.add_parser("poll-next")
    poll.add_argument("--tasks", required=True)
    poll.add_argument("--done", required=True)
    poll.add_argument("--pause", required=True)
    poll.add_argument("--work-dir", required=True)
    poll.add_argument("--step-base", type=int, default=12)
    poll.add_argument("--step-per-file", type=int, default=5)
    daemon = commands.add_parser("daemon")
    daemon.add_argument("--root", required=True)
    args = parser.parse_args(argv)
    if args.command == "score-read":
        state = read_score_state(args.state)
        print(json.dumps(score_summary(state), ensure_ascii=False))
    elif args.command == "score-record":
        print(json.dumps(record_score_result(args.state, args.task_id, args.result, args.evidence), ensure_ascii=False))
    elif args.command == "ghost-prompt":
        atomic_write(args.output, build_ghost_closeout_prompt(args.task_id, args.verify, args.progress_file))
    elif args.command == "queue-pop":
        task = pop_task(args.path)
        if task:
            print(task)
    elif args.command == "task-field":
        print(task_field(args.raw, args.key))
    elif args.command == "status-display":
        display_status(args.path)
    elif args.command == "codex-args":
        sys.stdout.buffer.write(("\0".join(codex_args(args)) + "\0").encode("utf-8"))
    elif args.command == "agy-args":
        sys.stdout.buffer.write(("\0".join(agy_args(args)) + "\0").encode("utf-8"))
    elif args.command == "task-cli":
        return execute_task_cli(args)
    elif args.command == "run-timeout":
        command = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
        return run_with_timeout(args.seconds, command)
    elif args.command == "git-audit":
        code, reason = git_audit(args)
        if reason:
            print(reason)
        return code
    elif args.command == "ensure-worktree":
        print(ensure_worktree(args.root, args.branch))
    elif args.command == "publish-preview":
        print(publish_preview(args.root, args.task_id, args.title))
    elif args.command == "archive-reports":
        archive_active_reports(args.root)
    elif args.command == "archive-overlapping-reports":
        archive_overlapping_reports(args.root, args.work_dir, args.base)
    elif args.command == "rollback-failed-task":
        paths = [path for path in (args.tasks, args.tasks_done, args.progress) if path]
        print(rollback_failed_task(args.root, args.work_dir, args.task_id, paths))
    elif args.command == "progress-prepend":
        prepend_progress(args.path, args.entry)
    elif args.command == "mechanical-audit":
        result = mechanical_audit(args)
        for message in result["messages"]:
            print(message, file=sys.stderr)
        print(json.dumps(result, ensure_ascii=False))
    elif args.command == "poll-next":
        sys.stdout.buffer.write(("\0".join(poll_next(args)) + "\0").encode("utf-8"))
    elif args.command == "daemon":
        return worker_daemon(args.root)
    else:
        write_status(args)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"worker_runtime: {error}", file=sys.stderr)
        sys.exit(2)
