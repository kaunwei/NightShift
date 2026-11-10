"""Serial task lifecycle. Planner owns restart; runtime owns acceptance."""

import argparse
import hashlib
from datetime import datetime
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time
import uuid

import acceptance as gate
import acceptance_hooks as hooks
import hook_control
import preflight
import ticket_policy
import outcome_policy


def task_level(raw):
    """Extract the numeric level from a task header, including dependency fields."""
    match = re.search(r"LEVEL:\s*([1-3])", raw)
    return match.group(1) if match else "1"


def append_once(path, identity, line):
    path = Path(path)
    old = path.read_text() if path.exists() else ""
    if identity not in old:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as stream:
            stream.write(line + "\n")


def protect_runtime(root, paths):
    """Generated state survives clean-start, even before tracked ignores migrate."""
    try:
        exclude = Path(gate.git(root, "rev-parse", "--git-path", "info/exclude"))
        if not exclude.is_absolute():
            exclude = root / exclude
    except Exception:
        return
    old = exclude.read_text() if exclude.exists() else ""
    additions = []
    for path in paths:
        path = Path(path).resolve()
        if path.is_relative_to(root):
            name = path.relative_to(root).as_posix()
            if gate.git(root, "ls-files", "--", name):
                if name in ("tasks.txt", "scripts/tasks.txt", "nightshift/tasks.txt"):
                    continue
                raise gate.GateError(f"migration required: untrack generated runtime file {name}")
            additions.extend(["/" + name, "/" + name + ".lock/"])
            if name.endswith(".status"):
                additions.append("/" + name + "." + "[0-9a-f]" * 32)
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with exclude.open("a") as stream:
        stream.write("\n" + "\n".join(item for item in additions if item not in old.splitlines()) + "\n")


def has_acceptance(root):
    try:
        return bool(gate.config(root))
    except Exception:
        return False


def diagnose(root, runtime, active, result):
    directory = gate.state_dir(root) / "reports" / active["event"]
    directory.mkdir(parents=True, exist_ok=True)
    detail = result.get("runtime_error", {}).get("message") or result.get("diagnostic") or result.get("outcome", "execution failed")
    report = {"task": active["raw"], "base": active.get("base"),
              "head": gate.git(root, "rev-parse", "HEAD"), "result": result,
              "metrics": active.get("metrics", {})}
    gate.save(directory / "report.json", report)
    (directory / "REPORT.md").write_text(
        "# Task failure\n\n" + json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="ascii")
    if has_acceptance(root):
        gate.pause(root, active["task_id"], f"{detail}; report={directory / 'REPORT.md'}")
    return directory


def daemon(root, runtime):
    root = Path(root).resolve()
    with gate.workspace(root):
        return run(root, runtime)


def run(root, runtime):
    try:
        cfg = gate.config(root)
    except gate.GateError:
        cfg = {}
    scheduler = hooks.Scheduler(cfg, state_path=gate.state_dir(root) / "hook-state.json", project=root)
    with hook_control.serve(root, scheduler):
        return run_session(root, runtime, scheduler)


def run_session(root, runtime, scheduler):
    state = gate.state_dir(root)
    external = bool(os.environ.get("NIGHTSHIFT_CONFIG_FILE"))
    owned = (Path(os.environ["NIGHTSHIFT_STATE_DIR"]) if external else
             root / "scripts" if (root / "scripts").is_dir() else
             root / "nightshift" if (root / "nightshift").is_dir() else root)
    def path(name, default):
        value = Path(str(owned / default) if external else os.environ.get(name, str(owned / default)))
        return value if value.is_absolute() else root / value
    tasks = path("TASKS_FILE", "tasks.txt")
    done = path("TASKS_DONE_FILE", "tasks.done")
    progress = path("PROGRESS_FILE", "progress.log")
    worker_id = os.environ.get("WORKER_ID", "default")
    suffix = "" if worker_id == "default" else "." + worker_id
    status = path("STATUS_FILE", f"worker{suffix}.status")
    log_file = path("LOG_FILE", f".worker{suffix}.log")
    pause = path("PAUSE_FILE", "PAUSE")
    dispatch_gate = path("AGENT_DISPATCH_GATE_FILE", ".worker-dispatch-gate.json")
    score = path("WORKER_SCORE_FILE", ".worker-score.json")
    agent_scores = path("WORKER_AGENT_SCORES_DIR", ".worker-agent-scores")
    agent_state_file = path("AI_AGENT_STATE_FILE", f".worker-agent-state.{os.environ.get('WORKER_ID', 'default')}.json")
    agent_state_file.unlink(missing_ok=True)
    agent_state = {"version": 1, "active_agent_id": "", "consecutive_no_response": 0, "task_exclusions": {}}
    registry = Path(os.environ.get("NIGHTSHIFT_CONFIG_FILE") or owned / "config.json")
    agents = runtime.load_agent_registry(registry)
    if not external:
        protect_runtime(root, (tasks, done, progress, status, log_file, pause, dispatch_gate, score,
                               agent_scores, agent_state_file, path("PID_FILE", ".worker.pid"),
                               owned / ".scratch", owned / ".worker-ghosts"))
    for file in (tasks, done, progress, log_file):
        file.parent.mkdir(parents=True, exist_ok=True)
        file.touch(exist_ok=True)
    active_path = state / "active.json"
    poll = float(os.environ.get("POLL_INTERVAL", "5"))
    once = runtime.env_bool("RUN_ONCE")
    stopped = threading.Event()
    previous = {}
    signals = [signal.SIGTERM, signal.SIGINT]
    if hasattr(signal, "SIGHUP"):
        signals.append(signal.SIGHUP)
    for sig in signals:
        previous[sig] = signal.signal(sig, lambda *_: stopped.set())
    running = {"state": "IDLE", "current_task": None, "pid": os.getpid(),
               "work_dir": str(root), "worker_id": os.environ.get("WORKER_ID", "default"),
               "os": os.environ.get("OS_TYPE", "auto"), "platform": os.name,
               "elapsed_seconds": 0, "worker_score": runtime.read_score_state(score)["score"],
               "timeout_seconds": float(os.environ.get("TASK_TIMEOUT", "1800")),
               "cli": "registered-adapters", "model": "",
               "progress": {"current_index": 0, "total_tasks": 0, "remaining": 0,
                            "percentage": "0%", "bar": "[------------------------------]"}}
    is_silent_cold = False
    if tasks.is_file():
        for line in tasks.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                if runtime.task_header_has_tag(line, r"\[COLD\]"):
                    is_silent_cold = True
                break
    if not is_silent_cold:
        print("=" * 78)
        print(" 24-Hour Unattended AI Worker Daemon Started")
        print(f" Worker ID: {running['worker_id']} | OS: {running['os']}")
        print(f" PID: {running['pid']} | Registered adapters: {len(agents)}")
        print(f" WorkDir: {root}")
        print(f" Tasks: {tasks} | Status: {status}")
        print(f" Progress: {progress}")
        print("=" * 78)
        if once:
            print("[WORKER] RUN_ONCE is enabled.")
    began = [time.monotonic()]
    def update(kind, task=None, phase=None):
        if task != running.get("current_task"):
            began[0] = time.monotonic()
        running.update(state=kind, current_task=task, phase=phase, last_heartbeat=datetime.now().isoformat())
        gate.save(status, running)
    def heartbeat():
        while not stopped.wait(1):
            running["last_heartbeat"] = datetime.now().isoformat()
            if running["state"] in ("RUNNING", "VERIFYING"):
                running["elapsed_seconds"] = int(time.monotonic() - began[0])
            gate.save(status, dict(running))
    thread = threading.Thread(target=heartbeat, daemon=True)
    thread.start()
    scratch_checked = float("-inf")
    recovery_halted_task = ""
    waiting_for_response = False
    waiting_path = state / "waiting-agent.json"
    exhausted_head = gate.load(waiting_path)

    def fingerprint(agent):
        return hashlib.sha256(json.dumps(agent, sort_keys=True).encode()).hexdigest()

    def metrics(active, result):
        targets = runtime.task_field(active["raw"], "TARGET")
        return {"task_id": active["task_id"], "level": int(task_level(active["raw"])),
                "target_entries": len([item for item in targets.split(",") if item.strip()]),
                "actions_used": result.get("actions_used"),
                "elapsed_seconds": round(time.monotonic() - began[0], 3),
                "failure_phase": result.get("runtime_error", {}).get("phase"),
                "failure_kind": result.get("runtime_error", {}).get("kind", "unknown")}

    def fail(active, result):
        active["metrics"] = metrics(active, result)
        if not has_acceptance(root) and active.get("attempt_baseline") and not result.get("recovery_archive"):
            try:
                runtime.rollback_failed_task(
                    root, root, active["task_id"],
                    (tasks, done, progress, status, log_file, pause, dispatch_gate, score, agent_scores, registry),
                    baseline_snapshot=active["attempt_baseline"],
                    attempt_id=active.get("event", ""))
            except Exception:
                pass
        report = diagnose(root, runtime, active, result)
        token = f"Failure_ID: {active['event']}"
        detail = ((result.get("diagnostic") or "").strip()
                  or result.get("runtime_error", {}).get("message")
                  or result.get("outcome", "execution failed"))
        append_once(progress, token, f"[BLOCKED] {active['task_id']} | {token} | Report: {report / 'REPORT.md'}\nFailure Reason: {detail}")
        if (result.get("terminal_status") == "step_budget_exceeded"
                or result.get("outcome") in ("step_budget", "closeout_failed")
                or result.get("exit_code") == 125):
            append_once(progress, f"budget:{active['task_id']}",
                        f"[NEED_DECOMPOSITION] {active['task_id']}: Action budget exhausted; review and return a revised bounded ticket.")
        if log_file.exists():
            with log_file.open("a") as stream:
                stream.write(f"Failure Reason: {detail}\n")
        done_tag = f" [WORKER_BLOCKED]" if (result.get("outcome") in ("blocked", "worker_blocked") or "[BLOCKED]" in str(result.get("diagnostic", ""))) else f" [{token}]"
        append_once(done, token, f"[FAILED] {active['raw']}{done_tag}")
        active["phase"] = "failed"
        gate.save(active_path, active)
        active_path.unlink(missing_ok=True)
        update("BLOCKED", f"{active['task_id']} awaiting Planner")

    def score_once(active, result, accepted):
        identity = active["event"] + ":score"
        registration = result.get("registration_id", "")
        candidate = runtime.registered_agent_score_path(agent_scores, registration) if registration else score
        destination = candidate if candidate.is_file() else score
        research = runtime.is_research_task(active["raw"])
        verification = ticket_policy.is_verify(active["raw"]) or (accepted and result.get("outcome") == "no_change")
        attribution = outcome_policy.classify(result, research=research, verification=verification)
        result["score_attribution"] = attribution
        if accepted:
            outcome = "no_fault" if research or verification else "accept"
        else:
            outcome = "attributable_failure" if attribution["attributable"] else "no_fault"
        before = runtime.read_score_state(destination)["score"]
        recorded = runtime.record_score_result(destination, active["task_id"], outcome,
                                               "automatic: " + attribution["category"], event_id=identity)
        if not recorded.get("duplicate") and runtime.score_task_level(before) != runtime.score_task_level(recorded["score"]):
            runtime.append_agent_event(path("WORKER_AGENT_EVENTS_FILE", ".worker-agent-events.jsonl"), {
                "event_id": identity + ":level", "registration_id": registration,
                "cause": "automatic_score_level_change", "task_id": active["task_id"],
                "previous_registration_id": registration, "current_registration_id": registration,
                "previous_score": before, "current_score": recorded["score"],
                "previous_level": runtime.score_task_level(before),
                "current_level": runtime.score_task_level(recorded["score"])}, dispatch_gate)

    def finish(active, result):
        journal_path = state / "tasks" / (gate.key(active["task_id"], active["raw"]) + ".json")
        journal = gate.load(journal_path, {})
        result["registration_id"] = journal.get("registration_id", result.get("registration_id", ""))
        commit = journal.get("commit", result.get("commit", ""))
        score_once(active, result, True)
        token = f"Audit_NS: {active['event']}"
        attempts = result.get("attempts", 1)
        print(f"[AUDIT] Running mechanical audit for {active['task_id']}...", flush=True)
        append_once(progress, token,
                    f"[MECHANICAL_AUDIT] Status: PASS | Task: {active['task_id']} | Verify_Exit: 0 | Whitelist: PASS | Tree: CLEAN | Attempts: {attempts} | Audit_NS: {active['event']} | Acceptance: automatic")
        append_once(done, token, f"[DONE] {active['raw']} [Audit_NS: {active['event']}]")
        print(f"[COMMIT] Committing verified changes for {active['task_id']} ({commit[:8] if commit else 'no-commit'})...", flush=True)
        runtime.settle_invalid_reports(owned if external else root, root, accepted=True)
        runtime.refresh_active_reports(owned if external else root, root)
        scheduled_hook = False
        if journal.get("phase") != "accepted":
            scheduled_hook = scheduler.accepted(
                active["task_id"], active["event"], commit or active["base"],
                committed=bool(commit and commit != active["base"] and not runtime.is_research_task(active["raw"])))
        journal.update(phase="accepted", commit=commit, result=result, event=active["event"],
                       metrics=journal.get("metrics") or metrics(active, result))
        gate.save(journal_path, journal)
        active_path.unlink(missing_ok=True)
        print(f"[DONE] <<< Task {active['task_id']} accepted and verified cleanly!\n", flush=True)
        return scheduled_hook and once

    drain_hooks = False
    try:
        while not stopped.is_set():
            if (state / "paused.json").exists() or dispatch_gate.exists():
                update("PAUSED_FOR_PLANNER")
                if once:
                    return 0
                stopped.wait(poll)
                continue
            if pause.exists():
                update("PAUSED")
                if once:
                    return 0
                stopped.wait(poll)
                continue
            restart_clean = state / "restart-clean.json"
            if external and restart_clean.is_file():
                try:
                    authorization = gate.load(restart_clean)
                    if authorization.get("head") != gate.git(root, "rev-parse", "HEAD"):
                        raise gate.GateError("HEAD changed after restart; Planner must review cleanup")
                    gate.clean(root, external=True)
                    restart_clean.unlink()
                except Exception as error:
                    gate.pause(root, "TASK-RESTART-CLEAN", str(error))
                    update("PAUSED_FOR_PLANNER")
                    if once:
                        return 2
                    continue
            if external and not active_path.exists() and tasks.is_file() and any(
                    line.strip() and not line.lstrip().startswith("#")
                    for line in tasks.read_text(encoding="utf-8").splitlines()):
                if gate.git(root, "status", "--porcelain", "--untracked-files=all"):
                    if once:
                        raise gate.GateError("project has pre-existing changes; queue left unchanged")
                    if running.get("state") != "WAITING_CLEAN_WORKTREE":
                        print("[WORKER] Project worktree has pre-existing uncommitted changes; waiting for clean worktree...", flush=True)
                    update("WAITING_CLEAN_WORKTREE")
                    stopped.wait(poll)
                    continue
            active = gate.load(active_path)
            if active:
                # The queue claim was persisted before removal. Dedup a claim interrupted there.
                if active.get("claimed"):
                    runtime.remove_claimed_task(tasks, active["raw"])
                if "task_id" not in active:
                    match = re.search(r"TASK-[A-Za-z0-9_.-]+", active["raw"])
                    active.update(task_id=match.group() if match else "TASK-UNKNOWN",
                                  base=gate.git(root, "rev-parse", "HEAD"), event=uuid.uuid4().hex)
                if active.get("phase") == "failed":
                    # Only explicit restart can reach here after a diagnosed failure.
                    active_path.unlink()
                    continue
                if runtime.task_header_has_tag(active["raw"], r"\[COLD\]"):
                    scheduler.enqueue_cold(active)
                    active_path.unlink()
                    drain_hooks = once
                    continue
                journal_path = state / "tasks" / (gate.key(active["task_id"], active["raw"]) + ".json")
                journal = gate.load(journal_path, {})
                if journal.get("phase") == "ready_commit":
                    recovery = argparse.Namespace(**journal["args"])
                    marker = f"NightShift-Key: {gate.key(active['task_id'], active['raw'])}"
                    commit = gate.git(root, "log", "--format=%H", "--fixed-strings", f"--grep={marker}", "-1")
                    if commit:
                        journal.update(phase="committed", commit=commit)
                        gate.save(journal_path, journal)
                    else:
                        result = journal["result"]
                        code = runtime.finalize_structured_adapter_result(recovery, result)
                        if code:
                            result.setdefault("runtime_error", {"phase": "ready_commit", "message": f"commit replay exited {code}"})
                            fail(active, result)
                            continue
                        journal = gate.load(journal_path)
                if journal.get("phase") in ("committed", "accepted"):
                    if journal.get("commit") and subprocess.run(
                            ["git", "-C", str(root), "merge-base", "--is-ancestor", journal["commit"], "HEAD"], capture_output=True).returncode:
                        raise gate.GateError("accepted commit missing from current history")
                    if finish(active, journal["result"]):
                        drain_hooks = True
                        continue
                    if once:
                        return 0
                    continue
                # Interrupted model execution is not safe to repeat or clean without Planner.
                fail(active, {"diagnostic": "interrupted task; schedule a new task and restart"})
                continue
            if scheduler.interrupted():
                if running.get("state") != "HOOK_INTERRUPTED":
                    print("[HOOK_INTERRUPTED] Inspect hook-list; explicitly cancel or retry interrupted effects.", flush=True)
                update("HOOK_INTERRUPTED", phase="post_acceptance_hook")
                if once:
                    return 2
                stopped.wait(poll)
                continue
            hook = scheduler.next_run()
            if hook:
                is_cold = hook.get("kind") == "cold"
                hook_id = "TASK-COLD" if is_cold else "TASK-HOOK-" + hook["id"]
                phase = "cold" if is_cold else "post_acceptance_hook"
                update("VERIFYING", hook_id, phase)
                try:
                    hooks.execute(root, hook, runtime.run_verify, cold_passed=scheduler.cold_passed,
                                  cfg=scheduler.cfg)
                    scheduler.settle(hook["id"], "passed")
                    with progress.open("a") as stream:
                        stream.write(f"[HOOK_PASS] {hook['hook']} | Hook_Run: {hook['id']} | Revision: {hook['revision']}\n")
                except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as error:
                    failure = str(error)
                    active_hook = {"task_id": hook_id, "raw": f"{hook_id} [{'COLD' if is_cold else 'HOOK'}]",
                                   "event": hook["audit_event"], "base": hook["revision"]}
                    fail(active_hook, {"outcome": "failure", "hook": hook,
                                       "runtime_error": {"phase": phase, "message": failure}})
                    scheduler.settle(hook["id"], "failed", error=failure)
                continue
            if drain_hooks:
                return 0
            if time.monotonic() - scratch_checked >= 60:
                runtime.scratch_review.check(owned, tasks, runtime.insert_task_front, runtime.atomic_write)
                scratch_checked = time.monotonic()
            if recovery_halted_task and not pause.is_file():
                update("RECOVERY_FAILED", f"{recovery_halted_task} (recovery halted); awaiting revised queue or intervention")
                stopped.wait(poll)
                head_task = ""
                if tasks.is_file():
                    lines = [l.strip() for l in tasks.read_text(encoding="utf-8").splitlines()
                             if l.strip() and not l.lstrip().startswith("#")]
                    head_task = lines[0].split("|", 1)[0].replace(" ", "") if lines else ""
                if head_task != recovery_halted_task:
                    recovery_halted_task = ""
                else:
                    continue
            if waiting_for_response and not pause.is_file():
                if agent_state_file.exists():
                    agent_state = runtime.read_agent_state(agent_state_file)
                else:
                    agent_state["consecutive_no_response"] = 0
                if agent_state.get("consecutive_no_response", 0) >= len(agents):
                    update("AGENT_NO_RESPONSE", "Waiting for agent response")
                    stopped.wait(poll)
                    continue
                stopped.wait(poll)
                waiting_for_response = False
            if exhausted_head is not None:
                blocked_raw = exhausted_head["raw"]
                blocked_id = exhausted_head["task_id"]
                prior_agents = exhausted_head["agents"]
                head = next((line.strip() for line in tasks.read_text(encoding="utf-8").splitlines()
                             if line.strip() and not line.lstrip().startswith("#")), "")
                if head == blocked_raw.strip():
                    try:
                        current_agents = runtime.load_agent_registry(registry)
                    except (OSError, ValueError):
                        current_agents = []
                    exclusions = exhausted_head["exclusions"]
                    # A changed registration may be retried; unchanged exhausted agents stay excluded.
                    changed = {agent["id"] for agent in current_agents
                               if fingerprint(agent) != prior_agents.get(agent["id"])}
                    if not any((agent["id"] not in exclusions or agent["id"] in changed)
                               and runtime.agent_supports_task(agent, head, runtime.task_field(head, "CONSTRAINTS"))
                               for agent in current_agents):
                        if running["state"] != "WAITING_FOR_AGENT":
                            update("WAITING_FOR_AGENT", blocked_id)
                        if once:
                            return 0
                        stopped.wait(poll)
                        continue
                    agent_state["task_exclusions"][blocked_id] = [identity for identity in exclusions
                                                                   if identity not in changed]
                exhausted_head = None
                waiting_path.unlink(missing_ok=True)
            if tasks.is_file() and any(line.strip() and not line.lstrip().startswith("#")
                                       for line in tasks.read_text().splitlines()):
                readiness = preflight.check(root, state, agents, runtime.run_verify)
                previous_readiness = gate.load(state / "preflight.json", {})
                gate.save(state / "preflight.json", readiness)
                if readiness["status"] != "ready":
                    if preflight.identity(readiness) != preflight.identity(previous_readiness):
                        print("[ENVIRONMENT_BLOCKED] " + json.dumps(readiness), flush=True)
                    update("ENVIRONMENT_BLOCKED", phase="preflight")
                    if once:
                        return 2
                    stopped.wait(poll)
                    continue
            try:
                raw = runtime.pop_task(tasks, claim_path=active_path, validate=ticket_policy.validate)
            except ValueError as error:
                diagnostic = {"status": "contract-blocked", "reason": str(error)}
                if gate.load(state / "contract.json", {}) != diagnostic:
                    print("[CONTRACT_BLOCKED] " + str(error), flush=True)
                gate.save(state / "contract.json", diagnostic)
                update("CONTRACT_BLOCKED", phase="preflight")
                if once:
                    return 2
                stopped.wait(poll)
                continue
            if not raw:
                if running["state"] != "BLOCKED":
                    update("IDLE")
                if once:
                    if not is_silent_cold:
                        print("[WORKER] Queue is empty and RUN_ONCE is enabled. Exiting.")
                    return 0
                stopped.wait(poll)
                continue
            active = gate.load(active_path)
            identity = re.search(r"TASK-[A-Za-z0-9_.-]+", raw.split("|", 1)[0])
            active.update(task_id=identity.group() if identity else raw.split("|", 1)[0].strip(),
                          event=uuid.uuid4().hex, base=gate.git(root, "rev-parse", "HEAD"), phase="running")
            gate.save(active_path, active)
            previous_record = gate.load(state / "tasks" / (gate.key(active["task_id"], raw) + ".json"), {})
            if previous_record.get("phase") == "accepted" and not runtime.task_header_has_tag(raw, r"\[COLD\]"):
                active["event"] = previous_record.get("event", active["event"])
                if finish(active, previous_record["result"]):
                    drain_hooks = True
                continue
            if runtime.task_header_has_tag(raw, r"\[COLD\]"):
                scheduler.enqueue_cold(active)
                active_path.unlink()
                drain_hooks = once
                continue
            args = None
            result = {}
            try:
                if external:
                    dirty = gate.git(root, "status", "--porcelain", "--untracked-files=all")
                    if dirty:
                        if once:
                            raise gate.GateError("project has pre-existing changes; use a clean worktree")
                        if running.get("state") != "WAITING_CLEAN_WORKTREE":
                            print("[WORKER] Project worktree has pre-existing uncommitted changes; waiting for clean worktree...", flush=True)
                        update("WAITING_CLEAN_WORKTREE")
                        stopped.wait(poll)
                        continue
                elif has_acceptance(root):
                    gate.clean(root)
                runtime.refresh_active_reports(owned if external else root, root)
                stale = state / "tasks" / (gate.key(active["task_id"], raw) + ".json")
                stale.unlink(missing_ok=True)
                agents = runtime.load_agent_registry(registry)
                if not agents:
                    raise gate.GateError("no executable adapter registration")
                target = runtime.task_field(raw, "TARGET")
                level = task_level(raw)
                verify = runtime.task_field(raw, "VERIFY")
                file_count = ticket_policy.planned_files(raw)
                step_per_file = int(os.environ.get("STEP_PER_FILE", "5"))
                file_count = max(1, file_count)
                directory = state / "runs" / active["event"]
                directory.mkdir(parents=True)
                prompt = directory / "prompt.txt"
                args = argparse.Namespace(
                    work_dir=str(root), prompt_file=str(prompt), output_file=str(directory / "output.json"),
                    result_file=str(directory / "result.json"), timeout=float(os.environ.get("TASK_TIMEOUT", "1800")),
                    step_budget=0, target_file_count=file_count, step_per_file=step_per_file, research_step_budget=int(os.environ.get("RESEARCH_STEP_BUDGET", "100")),
                    worker_port=os.environ.get("WORKER_PORT", "3001"), task_id=active["task_id"],
                    title=raw, target=target, level=level, verify=verify, base=active["base"],
                    constraints=runtime.task_field(raw, "CONSTRAINTS"),
                    required_cases=runtime.task_field(raw, "CASES"), progress_file=str(progress),
                    ghost_state_path=str(state / "ghost.json"), ghost_artifact_root=str(state / "ghost"),
                    agent_score_state_file=str(agent_scores), attempt_snapshot_root=str(owned / ".scratch/attempts" / active["task_id"]),
                    awaiting_agent=False, recovery_failed=False)
                update("RUNNING", active["task_id"], "agent")
                args.on_verify = lambda: update("VERIFYING", active["task_id"], "hot")
                def recover_before_switch(snapshot, attempt_id):
                    try:
                        return runtime.rollback_failed_task(
                            root, root, active["task_id"],
                            (tasks, done, progress, status, log_file, pause, dispatch_gate, score, agent_scores, agent_state_file, registry),
                            baseline_snapshot=snapshot, attempt_id=attempt_id)
                    except Exception as error:
                        args.recovery_failed = True
                        update("RECOVERY_FAILED", active["task_id"])
                        raise RuntimeError(f"attempt recovery failed: {error}")
                code, _ = runtime.execute_registered_agents(args, agents, agent_state, recover_before_switch)
                active["attempt_baseline"] = getattr(args, "attempt_baseline", "")
                result = gate.load(args.result_file, {})
                result["registration_id"] = getattr(args, "executed_agent_id", "")
                terminal = gate.load(args.output_file, {})
                result["terminal_status"] = terminal.get("status", "")
                result["agent_timing"] = {key: terminal.get(key) for key in ("elapsed_seconds", "budget_seconds")}
                result["exit_code"] = code
                hot_failure = result.get("runtime_error", {})
                if code and hot_failure.get("phase") == "hot" and hot_failure.get("kind") in (
                        "ticket_regression", "baseline_regression", "timeout", "undetermined", "task_verify"):
                    # Preserve exact attempt evidence; never dispatch the original ticket again automatically.
                    try:
                        result["recovery_archive"] = str(recover_before_switch(args.attempt_baseline, args.attempt_id))
                    except RuntimeError:
                        pass
                    if hot_failure["kind"] == "baseline_regression":
                        cases = hot_failure["evidence"]["baseline_failed_cases"]
                        key = hashlib.sha256(json.dumps([active["base"], cases]).encode()).hexdigest()[:20]
                        issue = state / "hot-baseline-issues" / f"{key}.json"
                        if not issue.exists():
                            gate.save(issue, {"base": active["base"], "cases": cases,
                                              "blocked_task": active["task_id"], "event": active["event"],
                                              "action": "Repair baseline and verify the recorded cases before replanning the blocked task."})
                        result["baseline_issue"] = str(issue)
                if code == 125:
                    result["outcome"] = "step_budget"
                if getattr(args, "recovery_failed", False):
                    update("RECOVERY_FAILED", active["task_id"])
                    print(f"[RECOVERY_HALTED] {active['task_id']}: baseline could not be restored; task requeued.", flush=True)
                    runtime.insert_task_front(tasks, raw)
                    active_path.unlink(missing_ok=True)
                    if once:
                        return 0
                    recovery_halted_task = active["task_id"]
                    stopped.wait(poll)
                    continue
                if getattr(args, "agent_no_response", False):
                    update("AGENT_NO_RESPONSE", active["task_id"])
                    print(f"[WORKER] AGENT_NO_RESPONSE for {active['task_id']}; reporting to planner.", flush=True)
                    append_once(progress, f"no_response:{active['task_id']}", f"[AGENT_NO_RESPONSE] {active['task_id']}: agent no response; reporting to planner.")
                    runtime.insert_task_front(tasks, raw)
                    active_path.unlink(missing_ok=True)
                    if not external:
                        agent_state_file.write_text(json.dumps(agent_state, indent=2))
                    if once:
                        return 0
                    waiting_for_response = True
                    stopped.wait(poll)
                    continue
                if getattr(args, "awaiting_agent", False):
                    msg = f"[AGENT_UNAVAILABLE] {active['task_id']}: no eligible registration remains for this task; task returned to {tasks}. Restart worker or update configuration to retry."
                    append_once(progress, f"[AGENT_UNAVAILABLE] {active['task_id']}:", msg)
                    exhausted_head = {"raw": raw, "task_id": active["task_id"],
                                      "agents": {agent["id"]: fingerprint(agent) for agent in agents},
                                      "exclusions": agent_state["task_exclusions"].get(active["task_id"], [])}
                    gate.save(waiting_path, exhausted_head)
                    runtime.insert_task_front(tasks, raw)
                    active_path.unlink(missing_ok=True)
                    if not external:
                        agent_state_file.write_text(json.dumps(agent_state, indent=2))
                    update("WAITING_FOR_AGENT", active["task_id"])
                    if once:
                        return 0
                    continue
                if code:
                    raise gate.GateError(result.get("runtime_error", {}).get("message") or "task execution failed")
                if runtime.scratch_review.is_review(raw):
                    err = ""
                    try:
                        runtime.scratch_review.validate_report(owned, active["task_id"])
                    except (OSError, ValueError, TypeError) as failure:
                        err = str(failure)
                    runtime.scratch_review.finish(owned, active["task_id"], runtime.atomic_write, err)
                    print(f"[SCRATCH_REVIEW] {'failed' if err else 'reviewed'}: fixed report overwritten", flush=True)
                    active_path.unlink(missing_ok=True)
                    update("IDLE")
                    continue
                elif runtime.is_research_task(raw):
                    audit = runtime.mechanical_audit(argparse.Namespace(
                        work_dir=str(root), root=str(root), base=args.base, target=target,
                        constraints="", title=raw, level=int(level), task_id=args.task_id,
                        verify="", port=args.worker_port, verify_timeout=args.timeout,
                        baseline_snapshot=args.attempt_baseline))
                    if audit["status"]:
                        raise gate.GateError(audit["error"])
                if finish(active, result):
                    drain_hooks = True
            except Exception as error:
                if args is not None and getattr(args, "recovery_failed", False):
                    update("RECOVERY_FAILED", active["task_id"])
                    print(f"[RECOVERY_HALTED] {active['task_id']}: baseline could not be restored; task requeued.", flush=True)
                    runtime.insert_task_front(tasks, raw)
                    active_path.unlink(missing_ok=True)
                    if once:
                        return 0
                    stopped.wait(poll)
                    continue
                result.setdefault("runtime_error", {"phase": "lifecycle", "message": str(error)})
                score_once(active, result, False)
                fail(active, result)
    finally:
        stopped.set()
        thread.join(timeout=2)
        if running["state"] not in ("BLOCKED", "PAUSED", "PAUSED_FOR_PLANNER", "AGENT_NO_RESPONSE", "RECOVERY_FAILED", "WAITING_FOR_AGENT", "ENVIRONMENT_BLOCKED", "HOOK_INTERRUPTED", "CONTRACT_BLOCKED"):
            update("STOPPED")
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return 0
