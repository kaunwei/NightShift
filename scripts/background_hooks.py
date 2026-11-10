"""Volatile two-stage hooks; supervised children read independent Git clones."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import threading
import uuid

import acceptance as gate


def manifest(directory):
    """Hash supplied artifacts without following links out of their snapshot."""
    directory = Path(directory).resolve()
    result = {}
    for path in sorted(directory.rglob("*")):
        name = path.relative_to(directory).as_posix()
        if path.is_symlink():
            if not path.resolve().is_relative_to(directory):
                raise gate.GateError(f"hook input link escapes snapshot: {name}")
            result[name] = {"link": os.readlink(path)}
        elif path.is_file():
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            result[name] = {"sha256": digest.hexdigest(), "mode": path.stat().st_mode & 0o777}
    return result


def snapshot(root, revision, destination):
    # A real independent repository, with no worktree administration or alternates.
    subprocess.run(["git", "clone", "--quiet", "--no-local", "--no-checkout", str(root), str(destination)],
                   check=True, capture_output=True, timeout=120)
    subprocess.run(["git", "-C", str(destination), "checkout", "--quiet", "--detach", revision],
                   check=True, capture_output=True, timeout=120)
    if gate.git(destination, "rev-parse", "HEAD") != revision:
        raise gate.GateError("hook snapshot revision mismatch")
    names = subprocess.check_output(["git", "-C", str(destination), "ls-files", "-z"])
    for name in names.decode().split("\0"):
        if not name:
            continue
        path = destination / name
        if path.is_symlink() and not path.resolve().is_relative_to(destination.resolve()):
            raise gate.GateError(f"hook source link escapes snapshot: {name}")
        if path.is_dir():
            raise gate.GateError(f"hook snapshot does not support uninitialized submodules: {name}")


def unchanged(run):
    root = Path(run["snapshot"])
    if (gate.git(root, "rev-parse", "HEAD") != run["revision"]
            or gate.git(root, "status", "--porcelain", "--untracked-files=all")):
        raise gate.GateError("background hook changed snapshot source or HEAD")
    if manifest(run["inputs"]) != run["input_manifest"]["artifacts"]:
        raise gate.GateError("background hook changed sealed first-stage artifacts")


def freshness(root, revision):
    try:
        head = gate.git(root, "rev-parse", "HEAD")
        dirty = gate.git(root, "status", "--porcelain", "--untracked-files=all")
        return {"observed_head": head, "freshness": "checkout_changed" if dirty else
                "same_revision" if head == revision else "older_snapshot"}
    except (OSError, subprocess.SubprocessError):
        return {"freshness": "unknown"}


class Output(str):
    def __new__(cls, text, **metadata):
        value = super().__new__(cls, text)
        value.__dict__.update(metadata)
        return value


def supervise(run, owner_fd):
    """Pipe EOF kills owned commands even when the daemon itself is killed."""
    import verify_process
    environment = dict(os.environ)
    for key in ("NIGHTSHIFT_CONFIG_FILE", "NIGHTSHIFT_STATE_DIR", "NIGHTSHIFT_PROJECT_NAME"):
        environment.pop(key, None)
    environment.update(run["environment"], NIGHTSHIFT_PROJECT_ROOT=run["snapshot"])
    receipt = {"id": run["id"], "hook": run["hook"], "revision": run["revision"],
               "input_manifest": run["input_manifest"], "status": "failed", "phase": "second_stage",
               "trigger_task": run["trigger_task"],
               "first_stage": gate.load(Path(run["directory"]) / "first-stage.json", {})}
    try:
        code, output = verify_process.run(shlex.join(run["second_stage"]["argv"]), run["snapshot"],
            "3001", run["second_stage"]["timeout"], Output, cancel_fd=owner_fd,
            environment=environment, directory=Path(run["directory"]) / "logs")
        receipt.update(exit=code, output=str(output)[-16384:], log_path=output.log_path,
                       timed_out=output.timed_out, cancelled=output.cancelled)
        if output.cancelled:
            raise gate.GateError("background hook cancelled by owner shutdown")
        unchanged(run)
        if code or output.empty_test_run:
            raise gate.GateError("background hook " + ("cancelled" if output.cancelled else
                                 "timed out" if output.timed_out else f"exited {code}") +
                                 ("; empty test run" if output.empty_test_run else ""))
        receipt["status"] = "passed"
    except Exception as error:
        receipt["error"] = str(error)
    gate.save(Path(run["directory"]) / "result.json", receipt)
    return 0


class BackgroundHooks:
    def __init__(self, hooks, cfg):
        self.hooks, self.cfg = hooks, cfg
        self.lock = threading.RLock()
        self.counts = {hook["id"]: 0 for hook in hooks}
        self.latest = None
        self.slot = None
        self.runs = {}
        self.cursor = 0
        self.await_commit = False
        self.project = None

    def accepted(self, task, event, revision, committed, registration):
        if not committed:
            return
        with self.lock:
            self.await_commit = False
            self.latest = {"trigger_task": task, "trigger_event": event, "revision": revision,
                           "registration": json.loads(json.dumps(registration)) if registration else None}
            for hook in self.hooks:
                self.counts[hook["id"]] = min(hook["every"], self.counts[hook["id"]] + 1)

    def has_work(self):
        with self.lock:
            return bool(self.slot or (not self.await_commit and any(self.counts[h["id"]] >= h["every"] for h in self.hooks)))

    def busy(self):
        with self.lock:
            return self.slot is not None

    def list(self, offset=0):
        with self.lock:
            return {"counts": dict(self.counts), "runs": [{**run, **freshness(self.project, run["revision"])}
                    for run in list(self.runs.values())[offset:offset+20]],
                    "total_runs": len(self.runs)}

    def blocked(self):
        with self.lock:
            return any(run["status"] == "failed" for run in self.runs.values())

    def cancel_run(self, identity):
        with self.lock:
            if identity not in self.runs:
                return False
            if self.runs[identity]["status"] != "failed":
                raise gate.GateError("only failed background hooks can be acknowledged with hook-cancel")
            self.runs[identity]["status"] = "cancelled"
            return True

    def next(self, root, directory):
        with self.lock:
            if self.slot or not self.latest or self.await_commit or self.blocked():
                return None
            for offset in range(len(self.hooks)):
                index = (self.cursor + offset) % len(self.hooks)
                hook = self.hooks[index]
                if self.counts[hook["id"]] < hook["every"]:
                    continue
                self.counts[hook["id"]] = 0
                self.cursor = (index + 1) % len(self.hooks)
                identity = uuid.uuid4().hex
                location = Path(directory) / identity
                location.mkdir(parents=True, mode=0o700)
                run = {**self.latest, "id": identity, "hook": hook["id"], "kind": "command",
                       "status": "preparing", "argv": hook["argv"], "timeout": hook.get("timeout", gate.phase_timeout(self.cfg, "cold")),
                       "second_stage": {**hook["second_stage"], "timeout": hook["second_stage"].get("timeout", gate.phase_timeout(self.cfg, "cold"))},
                       "directory": str(location), "snapshot": str(location / "snapshot"),
                       "inputs": str(location / "inputs"), "prepared": str(location / "prepared"), "reports": str(location / "reports")}
                for name in ("inputs", "prepared", "reports"):
                    Path(run[name]).mkdir()
                run["environment"] = {"NIGHTSHIFT_HOOK_ARTIFACT_DIR": run["inputs"],
                                      "NIGHTSHIFT_HOOK_REPORT_DIR": run["reports"],
                                      "NIGHTSHIFT_HOOK_REVISION": run["revision"],
                                      "NIGHTSHIFT_HOOK_RUN_ID": identity, "NIGHTSHIFT_HOOK_ID": run["hook"],
                                      "NIGHTSHIFT_HOOK_TASK": run["trigger_task"]}
                self.slot = {"run": run, "process": None, "owner": None}
                self.project = Path(root)
                self.runs[identity] = {**{key: run[key] for key in ("id", "hook", "status", "revision", "trigger_task", "directory")}, "phase": "first_stage"}
                return run
            return None

    def launch(self, root, run):
        # Seal a copy: a producer retaining its output path cannot alter input data.
        manifest(run["prepared"])
        shutil.copytree(run["prepared"], run["inputs"], dirs_exist_ok=True, symlinks=True)
        snapshot(Path(root), run["revision"], Path(run["snapshot"]))
        run["input_manifest"] = {"revision": run["revision"],
                                 "source_tree": gate.git(run["snapshot"], "rev-parse", "HEAD^{tree}"),
                                 "artifacts": manifest(run["inputs"])}
        gate.save(Path(run["directory"]) / "input-manifest.json", run["input_manifest"])
        gate.save(Path(run["directory"]) / "request.json", {key: value for key, value in run.items() if key != "registration"})
        read_fd, write_fd = os.pipe()
        try:
            with (Path(run["directory"]) / "supervisor.log").open("wb") as log:
                process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()),
                    str(Path(run["directory"]) / "request.json"), str(read_fd)],
                    pass_fds=(read_fd,), stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        except BaseException:
            os.close(write_fd)
            raise
        finally:
            os.close(read_fd)
        with self.lock:
            self.slot.update(process=process, owner=write_fd)
            self.runs[run["id"]].update(status="background", phase="second_stage", pid=process.pid)

    def failed_preparation(self, run, error):
        receipt = {"id": run["id"], "hook": run["hook"], "revision": run["revision"],
                   "status": "failed", "phase": "first_stage", "error": str(error),
                   "first_stage": gate.load(Path(run["directory"]) / "first-stage.json", {})}
        gate.save(Path(run["directory"]) / "result.json", receipt)
        with self.lock:
            self.slot["receipt"] = receipt

    def poll(self):
        with self.lock:
            if not self.slot:
                return None
            slot = self.slot
            if slot.get("receipt") is None:
                if slot["process"] is None or slot["process"].poll() is None:
                    return None
                slot["receipt"] = gate.load(Path(slot["run"]["directory"]) / "result.json", {
                    "status": "failed", "error": "background supervisor exited without a result"})
            run, receipt = slot["run"], slot["receipt"]
            receipt.update(freshness(self.project, run["revision"]))
            gate.save(Path(run["directory"]) / "result.json", receipt)
            if slot["owner"] is not None:
                os.close(slot["owner"])
            self.runs[run["id"]].update(status=receipt["status"], phase=receipt.get("phase"),
                                        log_path=receipt.get("log_path"), error=receipt.get("error"))
            self.slot = None
            if receipt["status"] == "passed":
                try:
                    shutil.rmtree(run["snapshot"])
                    shutil.rmtree(run["inputs"])
                    shutil.rmtree(run["prepared"])
                except OSError as error:
                    receipt["cleanup_error"] = str(error)
                    gate.save(Path(run["directory"]) / "result.json", receipt)
            else:
                self.counts[run["hook"]] = 0
                self.await_commit = True
            return run, receipt

    def close(self):
        self.cancel()
        with self.lock:
            slot, self.slot = self.slot, None
        if slot and slot["process"] is not None:
            slot["process"].wait(timeout=6)

    def cancel(self):
        with self.lock:
            if self.slot and self.slot["owner"] is not None:
                os.close(self.slot["owner"])
                self.slot["owner"] = None


def diagnose(run, runtime, agents, *, stopped=None):
    """One read-only ghost per RAM-owned hook run, never a development allowance."""
    agent = run.get("registration")
    if not agent or agent not in agents or not Path(run["snapshot"]).is_dir():
        return {"error": "triggering registration or snapshot unavailable; Planner must inspect raw report"}
    directory = Path(run["directory"]) / "ghost"
    directory.mkdir()
    prompt = directory / "prompt.txt"
    prompt.write_text("Diagnose this background hook failure. Read the snapshot, sealed inputs, run receipt and logs. "
        "Do not edit code, tests, configuration, wiring or inputs; do not commit, repair or run deployment. "
        "Return one JSON object with outcome=blocked and diagnostic describing observed evidence, "
        "root-cause candidates and a proposed bounded repair ticket. Do not claim repair.\n" +
        json.dumps({"hook": run["hook"], "revision": run["revision"], "inputs": run["inputs"],
                    "receipt": str(Path(run["directory"]) / "result.json"),
                    "manifest": str(Path(run["directory"]) / "input-manifest.json")}, ensure_ascii=True))
    request = {"protocol_version": 1, "registration_id": agent["id"], "overrides": agent.get("overrides", {}),
               "task_id": "TASK-HOOK-" + run["id"], "kind": "closeout", "execution_id": run["id"],
               "working_directory": run["snapshot"], "prompt_path": str(prompt),
               "output_dir": str(directory), "result_path": str(directory / "result.json"),
               "environment": {**agent.get("env", {}), **run["environment"], "NIGHTSHIFT_PROJECT_ROOT": run["snapshot"]},
               "limits": {"action_limit": 25, "execution_timeout_seconds": 180, "closeout_deadline_seconds": 180}}
    try:
        unchanged(run)
        status = runtime.execute_adapter_protocol(sys.executable, request,
            [str(Path(__file__).resolve().parent / "adapters" / f"{agent['adapter']}.py")],
            execution_timeout=180, start_callback="closeout", cancel_event=stopped)
        unchanged(run)
        result = gate.load(status.get("result_location") or directory / "result.json", {})
        return {"status": status["status"], "diagnostic": result.get("diagnostic", "no diagnostic returned")}
    except Exception as error:
        return {"error": str(error)}


if __name__ == "__main__":
    raise SystemExit(supervise(gate.load(sys.argv[1]), int(sys.argv[2])))
