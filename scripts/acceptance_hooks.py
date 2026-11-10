"""Session-owned post-acceptance scheduling and project command execution."""

from collections import deque
from pathlib import Path
import hashlib
import math
import re
import shlex
import threading
import time
import uuid

import acceptance as gate


COLD_ID = "nightshift-cold"


def spec(value, trigger):
    if not isinstance(value, dict) or set(value) - {"id", trigger, "argv", "timeout"}:
        raise gate.GateError(f"invalid acceptance hook: expected id, {trigger}, argv, optional timeout")
    identity, when, argv = (value.get(key) for key in ("id", trigger, "argv"))
    if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", identity):
        raise gate.GateError("invalid hook id")
    if trigger == "every" and (type(when) is not int or when < 1):
        raise gate.GateError("hook every must be a positive integer")
    if trigger == "after" and (not isinstance(when, str) or not re.fullmatch(r"TASK-[A-Za-z0-9_.-]+", when)):
        raise gate.GateError("hook after must be an exact task ID")
    if not isinstance(argv, list) or not argv or any(not isinstance(arg, str) or not arg or "\0" in arg for arg in argv):
        raise gate.GateError("hook argv must contain nonempty arguments")
    timeout = value.get("timeout")
    if "timeout" in value and (type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0):
        raise gate.GateError("hook timeout must be finite and positive")
    return dict(value)


def configured(cfg):
    values = cfg.get("hooks", [])
    if not isinstance(values, list):
        raise gate.GateError("acceptance hooks must be a list")
    hooks = [spec(value, "every") for value in values]
    if len({hook["id"] for hook in hooks}) != len(hooks):
        raise gate.GateError("duplicate periodic hook id")
    if any(hook["id"] == COLD_ID for hook in hooks):
        raise gate.GateError(f"periodic hook id {COLD_ID} is reserved")
    if cfg.get("cold_every") is not None:
        hooks.insert(0, cold_spec(cfg))
    return hooks


def cold_spec(cfg):
    command = cfg.get("cold")
    return {"id": COLD_ID, "every": cfg.get("cold_every"), "kind": "cold", "count": "commits",
            "argv": ["bash", "-c", command] if isinstance(command, str) and command.strip() else [],
            "timeout": gate.phase_timeout(cfg, "cold")}


def make_run(hook, trigger, event, task, revision, cfg):
    run_id = hashlib.sha256(f"{trigger}:{hook['id']}:{event}".encode()).hexdigest()[:24]
    return {"id": run_id, "hook": hook["id"], "kind": hook.get("kind", "command"),
            "status": "pending", "argv": hook["argv"],
            "timeout": hook.get("timeout", gate.phase_timeout(cfg, "cold")),
            "trigger_task": task, "trigger_event": event, "revision": revision,
            "audit_event": uuid.uuid4().hex}


class Scheduler:
    def __init__(self, cfg):
        self.cfg = cfg
        self.periodic = configured(cfg)
        self.lock = threading.Lock()
        self.events = {}
        self.oneshots = {}
        self.counts = {}
        self.runs = {}
        self.pending = deque()
        self.cold_passed = None

    def register(self, value):
        hook = spec(value, "after")
        with self.lock:
            old = self.oneshots.get(hook["id"])
            if old:
                if old["spec"] == hook:
                    return False
                raise gate.GateError("one-shot hook id already exists with a different registration")
            if hook["after"] in self.events.values():
                raise gate.GateError("target task already accepted in this session; call the script directly")
            self.oneshots[hook["id"]] = {"spec": hook, "fired": False}
            return True

    def _schedule(self, hook, trigger, event, task, revision):
        run = make_run(hook, trigger, event, task, revision, self.cfg)
        if run["id"] not in self.runs:
            self.runs[run["id"]] = run
            self.pending.append(run["id"])

    def accepted(self, task, event, revision, *, committed=False):
        with self.lock:
            if event in self.events:
                return False
            self.events[event] = task
            previous = len(self.pending)
            for hook in self.periodic:
                if hook.get("count") == "commits" and not committed:
                    continue
                count = self.counts.get(hook["id"], 0) + 1
                if count >= hook["every"]:
                    self._schedule(hook, "periodic", event, task, revision)
                    count = 0
                self.counts[hook["id"]] = count
            for entry in self.oneshots.values():
                hook = entry["spec"]
                if not entry["fired"] and hook["after"] == task:
                    self._schedule(hook, "one-shot", event, task, revision)
                    entry["fired"] = True
            return len(self.pending) != previous

    def enqueue_cold(self, active):
        with self.lock:
            self._schedule(cold_spec(self.cfg), "manual", active["event"], active["task_id"], active["base"])

    def next_run(self):
        with self.lock:
            if not self.pending:
                return None
            run = self.runs[self.pending.popleft()]
            run["status"] = "running"
            return dict(run)

    def settle(self, run_id, status, **extra):
        with self.lock:
            run = self.runs[run_id]
            if status == "passed":
                if run["kind"] == "cold":
                    self.cold_passed = run["revision"]
                del self.runs[run_id]
            else:
                run.update(status=status, **extra)

    def retry(self, run_id):
        with self.lock:
            run = self.runs.get(run_id, {})
            if run.get("status") != "failed":
                raise gate.GateError("only a failed hook in the live worker session can be retried")
            run.update(status="pending", audit_event=uuid.uuid4().hex)
            run.pop("error", None)
            self.pending.appendleft(run_id)


def execute(root, run, verify, *, allow_custom_cold=True, cold_passed=None, cfg=None):
    is_cold = run.get("kind") == "cold"
    before = gate.git(root, "status", "--porcelain", "--untracked-files=all")
    head = gate.git(root, "rev-parse", "HEAD")
    if head != run["revision"]:
        raise gate.GateError(f"hook requires accepted revision {run['revision']}; current HEAD is {head}")
    if before:
        raise gate.GateError(f"hook requires a clean checkout:\n{before}")
    if is_cold and cold_passed == run["revision"]:
        return ""
    variables = {
        "NIGHTSHIFT_HOOK_ID": run["hook"], "NIGHTSHIFT_HOOK_RUN_ID": run["id"],
        "NIGHTSHIFT_HOOK_REVISION": run["revision"], "NIGHTSHIFT_HOOK_TASK": run["trigger_task"],
    }
    started = time.monotonic()
    runner = gate.get_runner(root, cfg) if is_cold and allow_custom_cold else None
    if runner is not None and getattr(type(runner), "run_cold", None) is not gate.DefaultAcceptanceRunner.run_cold:
        runner.run_cold(Path(root), verify)
        code, output = 0, ""
    else:
        if not run["argv"]:
            raise gate.GateError("missing project cold command")
        command = shlex.join(["env", *(f"{k}={v}" for k, v in variables.items()), *run["argv"]])
        code, output = verify(command, str(root), "3001", run["timeout"])
    if (gate.git(root, "status", "--porcelain", "--untracked-files=all") != before
            or gate.git(root, "rev-parse", "HEAD") != run["revision"]):
        raise gate.GateError("hook changed tracked or nonignored project files")
    if is_cold:
        record = {"revision": run["revision"], "exit": code, **gate.verify_evidence(output, run["timeout"], started)}
        if code == 0:
            record["passed"] = run["revision"]
        # Audit output only. The worker never restores control state from it.
        gate.save(gate.state_dir(root) / "cold.json", record)
    if code:
        cause = "timed out" if getattr(output, "timed_out", False) else f"exited {code}"
        raise gate.GateError(f"hook {cause}\n{output[-16384:]}")
    return output[-16384:]
