"""Session-owned post-acceptance scheduling and project command execution."""

from collections import deque
from pathlib import Path
import hashlib
import json
import math
import re
import shlex
import threading
import time
import uuid

import acceptance as gate
import background_hooks


COLD_ID = "nightshift-cold"


def spec(value, trigger):
    if not isinstance(value, dict) or set(value) - {"id", trigger, "argv", "timeout", "second_stage"}:
        raise gate.GateError(f"invalid acceptance hook: expected id, {trigger}, argv, optional timeout/second_stage")
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
    if "second_stage" in value:
        second = value["second_stage"]
        if trigger != "every" or not isinstance(second, dict) or set(second) - {"argv", "timeout"}:
            raise gate.GateError("second_stage is supported only on periodic hooks with argv and optional timeout")
        spec({"id": identity, "every": 1, **second}, "every")
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
    def __init__(self, cfg, *, state_path=None, project=None):
        self.cfg = cfg
        all_hooks = configured(cfg)
        self.background = background_hooks.BackgroundHooks([h for h in all_hooks if "second_stage" in h], cfg)
        self.periodic = [h for h in all_hooks if "second_stage" not in h]
        self.lock = threading.Lock()
        self.events = {}
        self.oneshots = {}
        self.counts = {}
        self.runs = {}
        self.pending = deque()
        self.cold_passed = None
        self.state_path = Path(state_path) if state_path else None
        self.project = str(Path(project).resolve()) if project else ""
        self.config_hash = hashlib.sha256(json.dumps(self.periodic, sort_keys=True).encode()).hexdigest()
        self.persistence_failed = False
        if type(cfg.get("durable_hooks", False)) is not bool:
            raise gate.GateError("durable_hooks must be boolean")
        if cfg.get("durable_hooks"):
            if self.state_path is None or not self.project:
                raise gate.GateError("durable hooks require explicit project and state path")
            self._restore()
        else:
            self.state_path = None

    def _persist(self):
        if self.state_path is not None:
            try:
                gate.save(self.state_path, {"version": 1, "project": self.project,
                          "config_hash": self.config_hash, "events": self.events,
                          "oneshots": self.oneshots, "counts": self.counts, "runs": self.runs,
                          "pending": list(self.pending), "cold_passed": self.cold_passed})
                self.state_path.chmod(0o600)
            except OSError:
                self.persistence_failed = True
                raise

    def _restore(self):
        if not self.state_path.exists():
            return
        data = json.loads(self.state_path.read_text())
        if (data.get("version") != 1 or data.get("project") != self.project
                or data.get("config_hash") != self.config_hash):
            raise gate.GateError("durable hook state belongs to an incompatible project/configuration; retained for review")
        for name in ("events", "oneshots", "counts", "runs"):
            if not isinstance(data.get(name), dict):
                raise gate.GateError(f"invalid durable hook {name}")
            setattr(self, name, data[name])
        if not isinstance(data.get("pending"), list) or len(set(data["pending"])) != len(data["pending"]):
            raise gate.GateError("invalid durable hook pending list")
        self.pending = deque(data["pending"])
        for identity in self.pending:
            if self.runs.get(identity, {}).get("status") != "pending":
                raise gate.GateError("invalid pending hook reference")
        for run in self.runs.values():
            if run.get("status") == "running":
                run.update(status="interrupted", error="worker stopped before recording completion; inspect side effects before retry")
        self.cold_passed = data.get("cold_passed")
        self._persist()

    def list_runs(self, offset=0):
        with self.lock:
            if type(offset) is not int or offset < 0:
                raise gate.GateError("hook list offset must be a nonnegative integer")
            runs = list(self.runs.values())
            rows = [{key: run.get(key) for key in ("id", "hook", "status", "revision", "trigger_task")}
                    for run in runs[offset:offset + 20]]
            registrations = [{"id": value["spec"]["id"], "after": value["spec"]["after"], "fired": value["fired"]}
                             for value in list(self.oneshots.values())[offset:offset + 20]]
            return {"durable": self.state_path is not None, "runs": rows, "registrations": registrations,
                    "background": self.background.list(offset),
                    "offset": offset, "total_runs": len(runs), "total_registrations": len(self.oneshots)}

    def interrupted(self):
        with self.lock:
            return any(run.get("status") == "interrupted" for run in self.runs.values())

    def cancel(self, identity):
        with self.lock:
            if self.background.cancel_run(identity):
                return
            run = self.runs.get(identity)
            if run is not None:
                if run["status"] not in ("pending", "failed", "interrupted"):
                    raise gate.GateError("only pending, failed or interrupted hooks can be cancelled")
                run["status"] = "cancelled"
                self.pending = deque(n for n in self.pending if n != identity)
            elif identity in self.oneshots and not self.oneshots[identity]["fired"]:
                del self.oneshots[identity]
            else:
                raise gate.GateError("unknown or already fired hook")
            self._persist()

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
            self._persist()
            return True

    def _schedule(self, hook, trigger, event, task, revision):
        run = make_run(hook, trigger, event, task, revision, self.cfg)
        if run["id"] not in self.runs:
            self.runs[run["id"]] = run
            self.pending.append(run["id"])

    def accepted(self, task, event, revision, *, committed=False, registration=None):
        with self.lock:
            if event in self.events:
                return False
            self.events[event] = task
            self.background.accepted(task, event, revision, committed, registration)
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
            self._persist()
            return len(self.pending) != previous

    def enqueue_cold(self, active):
        with self.lock:
            self._schedule(cold_spec(self.cfg), "manual", active["event"], active["task_id"], active["base"])
            self._persist()

    def next_run(self):
        with self.lock:
            if self.persistence_failed:
                raise gate.GateError("hook persistence failed; restart after repairing storage")
            if any(run.get("status") == "interrupted" for run in self.runs.values()):
                raise gate.GateError("interrupted hook requires explicit retry or cancel")
            if not self.pending:
                return None
            run = self.runs[self.pending.popleft()]
            run["status"] = "running"
            self._persist()
            return dict(run)

    def settle(self, run_id, status, **extra):
        with self.lock:
            run = self.runs[run_id]
            if status == "passed":
                if run["kind"] == "cold":
                    self.cold_passed = run["revision"]
                if self.state_path is None:
                    del self.runs[run_id]
                else:
                    run.update(status="passed", **extra)
            else:
                run.update(status=status, **extra)
            self._persist()

    def retry(self, run_id):
        with self.lock:
            run = self.runs.get(run_id, {})
            if run.get("status") not in ("failed", "interrupted"):
                raise gate.GateError("only a failed or interrupted hook can be retried")
            run.update(status="pending", audit_event=uuid.uuid4().hex)
            run.pop("error", None)
            self.pending.appendleft(run_id)
            self._persist()


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
    variables.update(run.get("environment", {}))
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
