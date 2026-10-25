#!/usr/bin/env python3
"""Aider protocol adapter: RepoMap/Ollama for research and CLI for coding."""
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import time
import uuid


OUTCOMES = {"complete", "no_change", "closeout_required", "blocked",
            "scope_blocked", "guidance", "failure", "no_response"}


def emit(value):
    print(json.dumps(value, ensure_ascii=False))


def read_request():
    value = json.load(sys.stdin)
    if value.get("protocol_version") != 1:
        raise ValueError("protocol_version 1 is required")
    return value


def get_config(request):
    overrides = request.get("overrides", {})
    model_settings_file = overrides.get("model_settings_file", "")
    if not isinstance(model_settings_file, str):
        raise ValueError("model_settings_file must be a string")
    map_tokens = overrides.get("map_tokens", 0)
    if isinstance(map_tokens, bool) or not isinstance(map_tokens, int) or map_tokens < 0:
        raise ValueError("map_tokens must be a non-negative integer")
    map_refresh = overrides.get("map_refresh", "always")
    if map_refresh not in ("auto", "always", "files", "manual"):
        raise ValueError("map_refresh must be auto, always, files, or manual")
    environment = overrides.get("env", {})
    if not isinstance(environment, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in environment.items()):
        raise ValueError("Aider env must map strings to strings")
    initial_score = overrides.get("initial_score", 3)
    if isinstance(initial_score, bool) or not isinstance(initial_score, int) or not 1 <= initial_score <= 5:
        raise ValueError("initial_score must be an integer from 1 through 5")
    read_files = overrides.get("read_files", [])
    if not isinstance(read_files, list) or not all(isinstance(path, str) for path in read_files):
        raise ValueError("read_files must be an array of path strings")
    edit_format = overrides.get("edit_format", "whole")
    if not isinstance(edit_format, str) or not edit_format.strip():
        raise ValueError("edit_format must be a non-empty string")
    mode = overrides.get("mode", "auto")
    if mode not in ("auto", "cli", "explore"):
        raise ValueError("mode must be auto, cli, or explore")
    research_only = overrides.get("research_only", False)
    if not isinstance(research_only, bool):
        raise ValueError("research_only must be a boolean")
    explore_settings = {}
    for key, default, minimum, maximum in (
            ("explore_max_rounds", 6, 1, 20), ("explore_max_files", 16, 1, 100),
            ("explore_files_per_round", 2, 1, 10), ("explore_timeout_seconds", 300, 1, 1800),
            ("max_map_chars", 10000, 1000, 50000),
            ("max_source_chars", 10000, 1000, 50000), ("max_chunks_per_file", 6, 1, 20),
            ("planner_tokens", 350, 64, 4096),
            ("reader_tokens", 300, 64, 4096), ("summary_tokens", 450, 64, 4096),
            ("memory_tokens", 600, 64, 4096), ("final_tokens", 1400, 128, 8192)):
        value = overrides.get(key, default)
        if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
            raise ValueError(f"{key} must be an integer from {minimum} through {maximum}")
        explore_settings[key] = value
    return {"protocol_version": 1, "initial_score": initial_score,
            "limits": {"poll_interval_seconds": 0.25,
                       "callback_timeout_seconds": 30},
            "configuration": {
                "executable": overrides.get("command", overrides.get("executable", "aider")),
                "args": overrides.get("args", []),
                "model": overrides.get("model", ""),
                "model_settings_file": model_settings_file,
                "map_tokens": map_tokens,
                "map_refresh": map_refresh,
                "read_files": read_files,
                "edit_format": edit_format,
                "mode": mode,
                "research_only": research_only,
                **explore_settings,
                "env": environment,
            }}


def checked_targets(request):
    root = Path(request["working_directory"]).resolve()
    targets = request.get("target", "")
    if isinstance(targets, str):
        targets = [part.strip() for part in targets.split(",") if part.strip()]
    if not isinstance(targets, list) or not all(isinstance(path, str) for path in targets):
        raise ValueError("target must be a comma-separated string or string array")
    paths = []
    for target in targets:
        path = Path(target)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"Aider target must be a relative path inside the work tree: {target}")
        resolved = (root / path).resolve()
        if not resolved.is_relative_to(root):
            raise ValueError(f"Aider target escapes the work tree: {target}")
        paths.append((target, resolved))
    return root, paths


def build_command(request, cfg, prompt_path, history_path, output_dir, targets):
    executable = cfg["executable"]
    args = cfg.get("args", [])
    if not isinstance(executable, str) or not executable:
        raise ValueError("Aider executable is required")
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise ValueError("Aider args must be a string array")
    resolved = shutil.which(executable)
    if not resolved and not os.path.dirname(executable):
        for directory in (Path.home() / ".local/bin", Path("/opt/homebrew/bin"),
                          Path("/usr/local/bin")):
            candidate = directory / executable
            if candidate.is_file() and os.access(candidate, os.X_OK):
                resolved = str(candidate)
                break
    command = [resolved or executable, *args]
    if cfg.get("model"):
        command += ["--model", cfg["model"]]
    settings = cfg.get("model_settings_file", "")
    if settings:
        settings_path = Path(settings)
        if not settings_path.is_absolute():
            settings_path = Path(request["working_directory"]) / settings_path
        if not settings_path.is_file():
            raise ValueError(f"Aider model settings file does not exist: {settings_path}")
        command += ["--model-settings-file", str(settings_path.resolve())]
    command += ["--message-file", str(prompt_path), "--yes-always",
                "--no-auto-commits", "--no-dirty-commits",
                "--no-analytics", "--edit-format", cfg["edit_format"],
                "--no-show-model-warnings", "--no-check-update",
                "--no-show-release-notes", "--no-suggest-shell-commands",
                "--no-auto-lint", "--no-auto-test", "--no-gitignore",
                "--add-gitignore-files", "--no-restore-chat-history",
                "--chat-history-file", str(history_path),
                "--input-history-file", str(output_dir / "input.history"),
                "--map-tokens", str(cfg["map_tokens"]),
                "--map-refresh", cfg["map_refresh"]]
    closeout = request.get("kind") == "closeout"
    editable = {str(path.resolve()) for _, path in targets if not closeout and not path.is_dir()}
    read_files = cfg.get("read_files", [])
    if not isinstance(read_files, list) or not all(isinstance(path, str) for path in read_files):
        raise ValueError("Aider read_files must be an array of path strings")
    for name in read_files:
        path = Path(name)
        if not path.is_absolute():
            path = Path(request["working_directory"]) / path
        path = path.resolve()
        if not path.is_file():
            raise ValueError(f"Aider read-only context file does not exist: {path}")
        if str(path) not in editable:
            command += ["--read", str(path)]
    for name, path in targets:
        if path.is_dir():
            continue
        command += ["--read" if closeout else "--file", name]
    return command


def task_prompt(request, targets):
    prompt = Path(request["prompt_path"]).read_text(encoding="utf-8")
    declared = ", ".join(name for name, _ in targets) or "the task's declared target"
    if request.get("kind") == "closeout":
        policy = ("\nAIDER ADAPTER POLICY: This is a restricted closeout. Do not edit files, "
                  "stage, or commit. Inspect the supplied prompt and available evidence only. "
                  "Return one final JSON object with a supported outcome. Do not claim a "
                  "verification command ran unless the prompt includes its actual result.\n")
    else:
        policy = (f"\nAIDER ADAPTER POLICY: This is a single-shot Aider invocation, not an "
                  f"interactive shell agent. Complete the task in this response. Edit only "
                  f"these declared TARGET paths: {declared}. For [RESEARCH], write the "
                  "requested report to the target file; do not only describe it in chat. "
                  "Do not run or claim shell commands; NightShift's host runtime performs "
                  "verification, audit, and Git finalization. Do not stage or commit. End "
                  "your response with exactly one JSON object using outcome=complete, "
                  "no_change, closeout_required, blocked, scope_blocked, guidance, or failure. "
                  "Include changed and verification_evidence; complete also requires "
                  "commit_message, and no_change requires no_change_reason. State only "
                  "evidence actually available to you.\n")
    return prompt + policy


def result_from_history(history_path, prompt_path, diagnostic):
    if not history_path.is_file() or not history_path.stat().st_size:
        return {"outcome": "failure", "error_code": "invalid_result",
                "diagnostic": "Aider produced no chat history."}
    history = history_path.read_text(encoding="utf-8", errors="replace")
    prompt = prompt_path.read_text(encoding="utf-8", errors="replace")
    lines = history.splitlines()
    normalized = [line.strip() for line in lines]
    encoded_prompt = ["#### " + line.strip() for line in prompt.splitlines()]
    prompt_start = -1
    for start in range(max(0, len(normalized) - len(encoded_prompt) + 1)):
        if normalized[start:start + len(encoded_prompt)] == encoded_prompt:
            prompt_start = start
            break
    if prompt_start >= 0:
        text = "\n".join(lines[prompt_start + len(encoded_prompt):])
    else:
        prompt_lines = {line.strip() for line in prompt.splitlines()}
        text = "\n".join(line for line in lines
                         if not (line.startswith("#### ") and line[5:].strip() in prompt_lines))
    candidates = []
    decoder = json.JSONDecoder()
    offset = 0
    while offset < len(text):
        start = text.find("{", offset)
        if start < 0:
            break
        try:
            _, end = decoder.raw_decode(text, start)
            candidates.append(text[start:end])
            offset = end
        except json.JSONDecodeError:
            offset = start + 1
    for candidate in reversed(candidates):
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("outcome") in OUTCOMES:
            value.setdefault("actions_used", 1)
            return value
    # Ignore code blocks when checking textual blocker markers; reports and
    # quoted source often contain protocol examples that are not task results.
    prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    for marker, outcome in (("SCOPE_BLOCKED", "scope_blocked"),
                            ("NEED_GUIDANCE", "guidance"),
                            ("NEED_DECOMPOSITION", "guidance"),
                            ("CLOSEOUT_REQUIRED", "closeout_required"),
                            ("BLOCKED", "blocked"), ("DEAD_END", "blocked")):
        if re.search(r"\[" + marker + r"\]", prose):
            return {"outcome": outcome, "diagnostic": prose.strip()[-4000:]}
    return {"outcome": "failure", "error_code": "invalid_result",
            "diagnostic": "Aider did not return a valid NightShift outcome JSON. "
                          "See the saved Aider history and log.",
            "log_tail": diagnostic[-2000:]}


RUNNER = r'''import json, os, signal, subprocess, sys, time, importlib.util
argv, cwd, env, log_path, history_path, prompt_path, result_path, status_path, adapter_path = sys.argv[1:]
argv, env = json.loads(argv), json.loads(env)
child = None
stopping = False
before = {p.name for p in __import__("pathlib").Path(cwd).glob(".aider*")}
def stop_child(signum, frame):
    global stopping
    stopping = True
    if child is not None and child.poll() is None:
        try: os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError: pass
signal.signal(signal.SIGTERM, stop_child)
signal.signal(signal.SIGINT, stop_child)
try:
    with open(log_path, "w", encoding="utf-8") as log:
        child = subprocess.Popen(argv, cwd=cwd, env={**os.environ, **env},
            stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=(os.name == "posix"))
        while child.poll() is None and not stopping:
            time.sleep(0.1)
        if stopping and child.poll() is None:
            try: child.wait(timeout=2)
            except subprocess.TimeoutExpired:
                try: os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError: pass
        code = child.wait()
    diagnostic = open(log_path, encoding="utf-8", errors="replace").read()
    if stopping:
        state, payload = "cancelled", {"outcome":"failure", "diagnostic":"Aider was cancelled."}
    elif code != 0:
        state = "no_response"
        payload = {"outcome":"no_response", "error_code":"no_response",
                   "diagnostic":"no response", "log_tail":diagnostic[-2000:]}
    else:
        # Import from this adapter file to keep protocol stdout clean and share
        # the same result parser used by contract probes.
        spec = importlib.util.spec_from_file_location("nightshift_aider_adapter", adapter_path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        payload = module.result_from_history(__import__("pathlib").Path(history_path),
            __import__("pathlib").Path(prompt_path), diagnostic)
        outcome = payload.get("outcome")
        payload.setdefault("actions_used", 1)
        if outcome == "complete" and not str(payload.get("commit_message", "")).strip():
            outcome = "closeout_required"
            payload["outcome"] = outcome
        state = "complete" if outcome in ("complete", "no_change") else (
            "closeout_required" if outcome == "closeout_required" else "failed")
    with open(result_path, "w", encoding="utf-8") as result:
        json.dump(payload, result, ensure_ascii=False); result.write("\n")
    with open(status_path, "w", encoding="utf-8") as status:
        json.dump({"status":state, "result_location":result_path, "exit_code":code}, status)
except BaseException as error:
    try:
        with open(result_path, "w", encoding="utf-8") as result:
            json.dump({"outcome":"failure", "diagnostic":str(error)}, result)
        with open(status_path, "w", encoding="utf-8") as status:
            json.dump({"status":"failed", "result_location":result_path, "exit_code":1}, status)
    except OSError: pass
finally:
    for path in __import__("pathlib").Path(cwd).glob(".aider*"):
        if path.name.startswith(".aider.tags.cache.") and path.name not in before:
            try:
                if path.is_file() or path.is_symlink():
                    path.unlink()
                elif path.is_dir():
                    import shutil
                    shutil.rmtree(path)
            except OSError: pass
'''


def start(request):
    cfg = request["configuration"]
    use_explore = (cfg.get("mode") == "explore" or
                   (cfg.get("mode", "auto") == "auto"
                    and "[RESEARCH]" in request.get("title", "")))
    if use_explore and request.get("kind") != "closeout":
        from aider_explore import start as start_explore
        start_explore(request)
        return
    output = Path(request["output_dir"])
    output.mkdir(parents=True, exist_ok=True)
    status_path = output / "status.json"
    result_path = Path(request["result_path"])
    history_path = output / "aider.chat.history.md"
    prompt_path = output / "aider-prompt.txt"
    root, targets = checked_targets(request)
    for _, target in targets:
        target.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(task_prompt(request, targets), encoding="utf-8")
    command = build_command(request, cfg, prompt_path.resolve(), history_path.resolve(), output, targets)
    env = {**request.get("environment", {}), **cfg.get("env", {}),
           "NIGHTSHIFT_TASK_ID": str(request.get("task_id", "")),
           "NIGHTSHIFT_EXECUTION_KIND": str(request.get("kind", "main")),
           "PORT": str(request.get("environment", {}).get("PORT", "3001")),
           "TEST_PORT": str(request.get("environment", {}).get("TEST_PORT", "3001"))}
    proc = subprocess.Popen([sys.executable, "-c", RUNNER, json.dumps(command),
                             str(root), json.dumps(env), str((output / "aider.log").resolve()),
                             str(history_path.resolve()), str(prompt_path.resolve()),
                             str(result_path.resolve()), str(status_path.resolve()),
                             str(Path(__file__).resolve())],
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=(os.name == "posix"))
    emit({"execution_id": str(proc.pid), "status_location": str(status_path.resolve())})


def status(request):
    path = Path(request["status_location"])
    emit(json.loads(path.read_text(encoding="utf-8")) if path.is_file()
         else {"status": "running"})


def cancel(request):
    pid = int(request["execution_id"])
    try:
        os.killpg(pid, signal.SIGTERM) if os.name == "posix" else os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        emit({"stopped": True}); return
    deadline = time.monotonic() + float(request.get("stop_timeout_seconds", 2))
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
            stat = Path(f"/proc/{pid}/stat")
            if stat.exists() and stat.read_text().split()[2] == "Z":
                emit({"stopped": True}); return
        except ProcessLookupError:
            emit({"stopped": True}); return
        time.sleep(0.05)
    emit({"stopped": False})


def main():
    callback = sys.argv[-1]
    request = read_request()
    if callback == "get_config":
        emit(get_config(request))
    elif callback in ("start", "closeout"):
        if callback == "closeout":
            request = {**request, "kind": "closeout"}
        start(request)
    elif callback == "status":
        status(request)
    elif callback == "cancel":
        cancel(request)
    else:
        raise ValueError(f"unsupported callback: {callback}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"aider adapter: {error}", file=sys.stderr)
        sys.exit(1)
