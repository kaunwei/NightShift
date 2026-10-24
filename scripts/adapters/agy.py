#!/usr/bin/env python3
"""AgY executable adapter for NightShift's version 1 JSON protocol."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def response(value):
    print(json.dumps(value, ensure_ascii=False))


def read_request():
    value = json.load(sys.stdin)
    if value.get("protocol_version") != 1:
        raise ValueError("protocol_version 1 is required")
    return value


def config(request):
    overrides = request.get("overrides", {})
    return {"protocol_version": 1, "initial_score": int(overrides.get("initial_score", 5)),
            "limits": {"poll_interval_seconds": 0.25,
                       "callback_timeout_seconds": 30},
            "configuration": {"model": overrides.get("model", ""),
                              "effort": overrides.get("effort", "medium"),
                              "mode": overrides.get("mode", "accept-edits"),
                              "sandbox": overrides.get("sandbox", "0"),
                              "executable": overrides.get("executable", "agy")}}


def start(request):
    cfg = request["configuration"]
    output = Path(request["output_dir"])
    output.mkdir(parents=True, exist_ok=True)
    status_path = output / "status.json"
    result_path = Path(request["result_path"])
    log_path = output / "agy.log"
    message_path = output / "agy-message.json"
    prompt = Path(request["prompt_path"]).read_text(encoding="utf-8")
    argv = [cfg["executable"], "-p", prompt, "--dangerously-skip-permissions"]
    if str(cfg["sandbox"]).lower() in ("1", "true"):
        argv.append("--sandbox")
    if cfg["mode"]:
        argv += ["--mode", cfg["mode"]]
    if cfg["model"]:
        argv += ["--model", cfg["model"]]
    if cfg["effort"]:
        argv += ["--effort", cfg["effort"]]
    argv += ["--print-timeout", f"{request.get('limits', {}).get('execution_timeout_seconds', 1800)}s"]
    try:
        help_text = subprocess.run([cfg["executable"], "--help"], cwd=request["working_directory"],
                                   capture_output=True, text=True, timeout=10).stdout
        if "--max-turns" in help_text:
            argv += ["--max-turns", str(request.get("limits", {}).get("action_limit", 12))]
        elif "--max-steps" in help_text:
            argv += ["--max-steps", str(request.get("limits", {}).get("action_limit", 12))]
    except (OSError, subprocess.TimeoutExpired):
        pass
    limit = int(request.get("limits", {}).get("action_limit", 12))
    runner = r'''import json, subprocess, sys
argv, cwd, env, log, message, result, status, limit = sys.argv[1:]
argv, env = json.loads(argv), json.loads(env)
with open(log, "w", encoding="utf-8") as stream:
    code = subprocess.run(argv, cwd=cwd, env={**__import__('os').environ, **env}, input=open(sys.stdin.fileno()).read(), text=True, stdout=stream, stderr=subprocess.STDOUT, check=False).returncode
actions = 0
for line in open(log, encoding="utf-8", errors="replace"):
    try:
        event = json.loads(line); item = event.get("item", {})
        actions += event.get("type") == "item.completed" and item.get("type") == "command_execution"
    except (ValueError, AttributeError):
        actions += any(token in line for token in ("[EXEC]", "Tool Call", "edit_file", "write_file", "run_command", "read_file"))
diagnostic = open(log, encoding="utf-8", errors="replace").read()
quota = any(term in diagnostic.lower() for term in ("insufficient_quota", "rate limit", "resource_exhausted", "429", "out of credits"))
outcome = "quota_exhausted" if quota else "step_budget_exceeded" if actions > int(limit) else "complete" if code == 0 else "failure"
payload = {}
try: payload = json.load(open(message, encoding="utf-8"))
except (OSError, ValueError):
    try: payload = json.loads(diagnostic.strip().splitlines()[-1])
    except (ValueError, IndexError): pass
if outcome == "complete" and not isinstance(payload, dict): outcome = "closeout_required"
if isinstance(payload, dict): payload.setdefault("actions_used", actions)
else: payload = {"outcome": "closeout_required", "actions_used": actions}
payload.setdefault("outcome", outcome)
if outcome != "complete": payload["outcome"] = outcome
json.dump(payload, open(result, "w", encoding="utf-8"))
json.dump({"status": outcome, "result_location": result, "exit_code": code}, open(status, "w", encoding="utf-8"))
'''
    child_env = {**request.get("environment", {}),
                 "NIGHTSHIFT_TASK_ID": request.get("task_id", ""),
                 "PORT": request.get("environment", {}).get("PORT", "3001"),
                 "TEST_PORT": request.get("environment", {}).get("TEST_PORT", "3001")}
    proc = subprocess.Popen([sys.executable, "-c", runner, json.dumps(argv),
                             request["working_directory"], json.dumps(child_env),
                             str(log_path), str(message_path), str(result_path),
                             str(status_path), str(limit)], stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=(os.name == "posix"))
    proc.stdin.write(prompt.encode("utf-8")); proc.stdin.close()
    response({"execution_id": str(proc.pid), "status_location": str(status_path)})


def status(request):
    path = Path(request["status_location"])
    if path.is_file():
        response(json.loads(path.read_text(encoding="utf-8")))
    else:
        response({"status": "running"})


def cancel(request):
    pid = int(request["execution_id"])
    try:
        os.killpg(pid, signal.SIGTERM) if os.name == "posix" else os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        response({"stopped": True}); return
    deadline = time.monotonic() + float(request.get("stop_timeout_seconds", 2))
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
            stat = Path(f"/proc/{pid}/stat")
            if stat.exists() and stat.read_text().split()[2] == "Z":
                response({"stopped": True}); return
        except ProcessLookupError:
            response({"stopped": True}); return
        time.sleep(0.05)
    response({"stopped": False})


def closeout(request):
    request["kind"] = "closeout"
    request.setdefault("limits", {})["action_limit"] = request["limits"].get("action_limit", 1)
    # Closeout uses a distinct, private Codex execution with the same local status contract.
    start(request)


def main():
    callback = sys.argv[-1]
    request = read_request()
    {"get_config": lambda: response(config(request)), "start": lambda: start(request),
     "status": lambda: status(request), "cancel": lambda: cancel(request),
     "closeout": lambda: closeout(request)}[callback]()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"codex adapter: {error}", file=sys.stderr)
        sys.exit(1)
