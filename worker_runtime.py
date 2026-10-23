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
from pathlib import Path
import re
import shutil
import signal
import sys
import subprocess
import tarfile
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
    else:
        write_status(args)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, TimeoutError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as error:
        print(f"worker_runtime: {error}", file=sys.stderr)
        sys.exit(2)
