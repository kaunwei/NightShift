"""Bounded environment readiness; failure leaves queue and score untouched."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil

import environment_probe


def validate(value):
    if not isinstance(value, dict) or set(value) - {"argv", "timeout", "required_tools"}:
        raise ValueError("worker.preflight expects argv, timeout, required_tools")
    argv = value.get("argv", [])
    tools = value.get("required_tools", [])
    if not isinstance(argv, list) or any(not isinstance(x, str) or not x or "\0" in x for x in argv):
        raise ValueError("worker.preflight.argv must be nonempty strings")
    if not isinstance(tools, list) or any(not isinstance(x, str) or not x or "\0" in x for x in tools):
        raise ValueError("worker.preflight.required_tools must be strings")
    timeout = value.get("timeout", 15)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("worker.preflight.timeout must be finite and positive")
    return value


def check(root, state, agents, run):
    """Explicit argv is the operator's exact sandbox/profile probe, not a guess."""
    evidence = []
    try:
        environment_probe.probe(root, Path(state) / "preflight")
        for agent in agents:
            if "preflight" not in agent.get("worker", {}):
                continue
            cfg = validate(agent["worker"]["preflight"])
            env = {**os.environ, **agent.get("env", {})}
            for tool in cfg.get("required_tools", []):
                if not shutil.which(tool, path=env.get("PATH")):
                    raise ValueError(f"required tool missing for {agent['id']}: {tool}")
            values = {"{executable}": agent["command"], "{project}": str(root),
                      "{state}": str(Path(state) / "preflight"),
                      "{probe}": str(Path(environment_probe.__file__).resolve())}
            argv = [values.get(arg, arg) for arg in cfg.get("argv", [])]
            if not argv:
                continue
            import shlex
            command = shlex.join(["env", *(f"{k}={v}" for k, v in agent.get("env", {}).items()), *argv])
            code, output = run(command, str(root), "3001", cfg.get("timeout", 15))
            record = {"registration_id": agent["id"], "argv": argv, "exit": code,
                      "output": str(output)[-16384:], "timed_out": getattr(output, "timed_out", False)}
            evidence.append(record)
            if code:
                return {"status": "environment-blocked", "reason": "configured_probe_failed", "evidence": evidence}
        return {"status": "ready", "sandbox_probes": len(evidence), "evidence": evidence}
    except (OSError, ValueError) as error:
        return {"status": "environment-blocked", "reason": str(error), "evidence": evidence}


def identity(result):
    return hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
