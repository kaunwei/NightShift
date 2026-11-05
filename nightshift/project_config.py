"""Read the project's single persistent NightShift configuration."""
import json
from pathlib import Path


def read(path):
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"invalid NightShift configuration {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"NightShift configuration {path} must be an object")
    if value.get("version") != 1:
        raise ValueError(f"NightShift configuration {path} requires version 1")
    return value


def resolve_project(config_path, selection=None, default_root=None):
    """Resolve project and private state paths before creating any files."""
    import hashlib
    config_path = Path(config_path).resolve()
    cfg = read(config_path)
    projects = cfg.get("projects")
    if projects is None and not selection:
        if default_root is None:
            raise ValueError("default project root is required")
        return None, Path(default_root).resolve(), None
    if not isinstance(projects, dict):
        raise ValueError("projects must be an object of named projects")
    name = selection or cfg.get("default_project")
    if not name and len(projects) == 1:
        name = next(iter(projects.keys()))
    if not isinstance(name, str) or not name or name not in projects:
        raise ValueError(f"unknown project: {name!r}")
    entry = projects[name]
    if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not entry["path"]:
        raise ValueError(f"project {name!r} requires a path")
    path = Path(entry["path"]).expanduser()
    root = (path if path.is_absolute() else config_path.parent / path).resolve()
    if not root.is_dir():
        raise ValueError(f"project {name!r} directory does not exist: {root}")
    import subprocess
    probe = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, check=False)
    if probe.returncode or Path(probe.stdout.strip()).resolve() != root:
        raise ValueError(f"project {name!r} must be a Git worktree root: {root}")
    if "state" in entry and isinstance(entry["state"], str) and entry["state"].strip():
        state_path = Path(entry["state"]).expanduser()
        state = (state_path if state_path.is_absolute() else config_path.parent / state_path).resolve()
    elif len(projects) == 1 and config_path.parent.name == name:
        state = config_path.parent.resolve()
    else:
        identity = hashlib.sha256((name + "\0" + str(root)).encode()).hexdigest()[:16]
        state = config_path.parent / ".scratch" / "projects" / identity
    return name, root, state


def shell_context(config_path, selection, default_root):
    import shlex
    name, root, state = resolve_project(config_path, selection, default_root)
    if name is None:
        return ""
    values = {
        "PROJECT_ROOT": str(root), "NIGHTSHIFT_CONFIG_FILE": str(Path(config_path).resolve()),
        "NIGHTSHIFT_PROJECT_ROOT": str(root), "NIGHTSHIFT_PROJECT_NAME": name,
        "NIGHTSHIFT_STATE_DIR": str(state), "TASKS_FILE": str(state / "tasks.txt"),
        "TASKS_DONE_FILE": str(state / "tasks.done"), "PROGRESS_FILE": str(state / "progress.log"),
        "STATUS_FILE": str(state / "worker.status"), "PAUSE_FILE": str(state / "PAUSE"),
        "WORKER_AGENT_EVENTS_FILE": str(state / ".worker-agent-events.jsonl"),
        "WORKER_AGENT_EVENTS_CURSOR_FILE": str(state / ".worker-agent-events.cursor.json"),
        "WORKER_AGENT_EVENTS_ACK_FILE": str(state / ".worker-agent-events.acks.jsonl"),
        "AGENT_DISPATCH_GATE_FILE": str(state / ".worker-dispatch-gate.json"),
    }
    return "\n".join(f"export {key}={shlex.quote(value)}" for key, value in values.items())


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--project")
    args = parser.parse_args()
    try:
        print(shell_context(args.config, args.project, args.root))
    except ValueError as error:
        parser.exit(2, f"project configuration: {error}\n")
