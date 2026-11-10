"""Project-owned tests; runtime-owned evidence and durable lifecycle state."""

from contextlib import contextmanager
try:
    import project_config
except ImportError:
    import sys
    from pathlib import Path
    _ns_dir = str(Path(__file__).resolve().parent)
    if _ns_dir not in sys.path:
        sys.path.insert(0, _ns_dir)
    try:
        import project_config
    except ImportError:
        project_config = None
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import time
import uuid
import ticket_policy


class GateError(ValueError):
    pass


class HotFailure(GateError):
    def __init__(self, kind, message, evidence):
        super().__init__(message)
        self.kind, self.evidence = kind, evidence


def verify_evidence(output, budget, started):
    return {"timed_out": getattr(output, "timed_out", False),
            "log_path": getattr(output, "log_path", None),
            "output_bytes": getattr(output, "output_bytes", len(str(output).encode())),
            "elapsed_seconds": round(getattr(output, "elapsed", time.monotonic() - started), 3),
            "budget_seconds": getattr(output, "budget", budget)}


def remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise HotFailure("timeout", "shared hot deadline exhausted before the next phase", {})
    return value


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True).stdout.decode("utf-8", "replace").strip()


def state_dir(root):
    selected = os.environ.get("NIGHTSHIFT_STATE_DIR")
    if selected:
        path = Path(selected) / "lifecycle"
        path.mkdir(parents=True, exist_ok=True)
        return path
    try:
        path = Path(git(root, "rev-parse", "--git-path", "nightshift"))
        path = path if path.is_absolute() else Path(root) / path
    except Exception:
        path = Path(root) / "scripts" if (Path(root) / "scripts").is_dir() else Path(root) / "nightshift"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex)
    try:
        temporary.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def load(path, default=None):
    return json.loads(Path(path).read_text()) if Path(path).exists() else default


@contextmanager
def workspace(root):
    # OS locks release on exit/crash; all Worker IDs share this checkout lock.
    import fcntl
    if os.environ.get("NIGHTSHIFT_STATE_DIR"):
        identity = hashlib.sha256(str(Path(root).resolve()).encode()).hexdigest()
        lock = Path(os.environ["NIGHTSHIFT_STATE_DIR"]).parent / ".locks" / (identity + ".lock")
        lock.parent.mkdir(parents=True, exist_ok=True)
    else:
        lock = state_dir(root) / "workspace.lock"
    with lock.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise GateError("another runtime owns this project workspace") from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def config(root):
    explicit = os.environ.get("NIGHTSHIFT_CONFIG_FILE")
    local_path = (Path(root) / "scripts/config.json"
                  if (Path(root) / "scripts/config.json").is_file()
                  else Path(root) / "nightshift/config.json")
    path = None
    if explicit:
        explicit_path = Path(explicit)
        if explicit_path.is_file():
            try:
                raw_test = project_config.read(explicit_path) if project_config is not None else json.loads(explicit_path.read_text(encoding="utf-8"))
                root_resolved = Path(root).resolve()
                name = os.environ.get("NIGHTSHIFT_PROJECT_NAME")
                if name and name in raw_test.get("projects", {}):
                    p_entry = raw_test["projects"][name]
                    if isinstance(p_entry, dict) and "path" in p_entry:
                        p_path = (explicit_path.parent / p_entry["path"]).resolve()
                        if p_path == root_resolved:
                            path = explicit_path
                if path is None:
                    for p_entry in raw_test.get("projects", {}).values():
                        if isinstance(p_entry, dict) and "path" in p_entry:
                            p_path = (explicit_path.parent / p_entry["path"]).resolve()
                            if p_path == root_resolved:
                                path = explicit_path
                                break
            except Exception:
                pass
    if path is None:
        path = Path(explicit) if (explicit and not local_path.is_file()) else local_path
    try:
        raw = project_config.read(path) if project_config is not None else (json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {})
    except ValueError as error:
        raise GateError(str(error)) from error
    value = raw.get("acceptance")
    name = os.environ.get("NIGHTSHIFT_PROJECT_NAME")
    if name:
        entry = raw.get("projects", {}).get(name, {})
        override = entry.get("acceptance", {})
        if not isinstance(override, dict):
            raise GateError(f"project {name!r} acceptance must be an object")
        value = {**(value if isinstance(value, dict) else {}), **override}
        for kind in ("hot", "cold"):
            script = override.get(kind + "_script")
            if script is not None:
                if not isinstance(script, str) or not script:
                    raise GateError(f"project {name!r} acceptance.{kind}_script must be a path")
                candidate = Path(script).expanduser()
                if candidate.is_absolute():
                    script_path = candidate
                elif (Path(root) / candidate).is_file():
                    script_path = Path(root) / candidate
                else:
                    script_path = path.parent / candidate
                value[kind] = "bash " + shlex.quote(str(script_path.resolve()))
    if isinstance(value, dict):
        value = dict(value)
        value.setdefault("version", raw["version"])
    if not isinstance(value, dict) or value.get("version") != 1:
        raise GateError("acceptance config requires version 1")
    if "capabilities" in value:
        import evidence_capabilities
        evidence_capabilities.validate(value["capabilities"])
    for field in ("timeout", "hot_timeout", "cold_timeout"):
        if field in value:
            timeout = value[field]
            if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
                raise GateError(f"acceptance {field} must be finite and positive")
    value.setdefault("hot_timeout", phase_timeout(value, "hot"))
    value.setdefault("cold_timeout", phase_timeout(value, "cold"))
    interval = value.get("cold_every")
    if interval is not None and (type(interval) is not int or interval < 1):
        raise GateError("cold_every must be a positive integer or absent")
    wiring = value.get("wiring", [])
    if not isinstance(wiring, list) or any(not safe_path(item) for item in wiring):
        raise GateError("wiring must list exact project-relative files")
    return value



def phase_timeout(cfg, phase):
    """Explicit phase budget wins; legacy timeout remains an explicit fallback."""
    defaults = {"hot": 300, "cold": 1800}
    return cfg.get(phase + "_timeout", cfg.get("timeout", defaults[phase]))


def safe_path(name):
    return (isinstance(name, str) and bool(name) and not Path(name).is_absolute()
            and ".." not in Path(name).parts and ".git" not in Path(name).parts)


def command(value, name):
    text = value.get(name)
    if not isinstance(text, str) or not text.strip():
        raise GateError(f"missing project {name} command")
    return text


class AcceptanceRunner:
    """Abstract interface defining project hot and cold acceptance."""

    def run_hot(self, args, result, run):
        raise NotImplementedError

    def run_cold(self, root, run_id=None):
        raise NotImplementedError


class DefaultAcceptanceRunner(AcceptanceRunner):
    """Default runner executing configured commands with TDD evidence checking."""

    def invoke(self, root, cfg, name, phase, base, run, task="", required=(),
               deadline=None, only=(), allow_failure=False, evidence_root=None):
        if only and "capabilities" in cfg and not cfg["capabilities"].get("case_selection", False):
            raise GateError("isolated case selection unsupported by declared adapter capabilities")
        nonce = uuid.uuid4().hex
        output = state_dir(evidence_root or root) / "evidence" / f"{nonce}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        environment = {"NIGHTSHIFT_PHASE": phase, "NIGHTSHIFT_RESULT": str(output.resolve()),
                       "NIGHTSHIFT_RUN": nonce, "NIGHTSHIFT_BASE": base,
                       "NIGHTSHIFT_TASK": task, "NIGHTSHIFT_REQUIRED": json.dumps(list(required)),
                       "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPYCACHEPREFIX": str(output.with_suffix(".cache")),
                       "NIGHTSHIFT_PROJECT_ROOT": str(root.resolve())}
        # Discover permanent membership with no ticket context.
        if phase == "discover":
            environment.update(NIGHTSHIFT_TASK="", NIGHTSHIFT_REQUIRED="[]")
        environment["NIGHTSHIFT_ONLY_CASES"] = json.dumps(list(only))
        if only:
            environment["PROJECT_ROOT"] = str(root.resolve())
        prefix = "env " + " ".join(shlex.quote(f"{key}={val}") for key, val in environment.items())
        actual = f"{prefix} bash -c {shlex.quote(command(cfg, name))}"
        budget = remaining(deadline) if deadline is not None else phase_timeout(cfg, name)
        started = time.monotonic()
        code, text = run(actual, str(root), "3001", budget)
        evidence = {"phase": phase, "command": command(cfg, name), "exit": code,
                    "output": text[-16384:], "run": nonce, **verify_evidence(text, budget, started)}
        save(output.with_suffix(".log.json"), evidence)
        if evidence["timed_out"]:
            raise HotFailure("timeout", f"{name}/{phase} timed out after {budget:.1f}s", evidence)
        if code and not allow_failure:
            raise GateError(f"{name}/{phase} exited {code}\n{text[-16384:]}")
        data = load(output)
        if not isinstance(data, dict) or data.get("run") != nonce or not isinstance(data.get("cases"), list):
            raise HotFailure("undetermined", f"{name}/{phase}: missing or stale case evidence: {output}", evidence)
        evidence["supports_case_selection"] = data.get("supports_case_selection") is True
        if "capabilities" in cfg:
            import evidence_capabilities
            capabilities = evidence_capabilities.validate(cfg["capabilities"])
            if ("case_selection" in capabilities and
                    evidence["supports_case_selection"] != capabilities["case_selection"]):
                raise GateError("adapter case-selection evidence contradicts declared capabilities")
            if only and not capabilities.get("case_selection", False):
                raise GateError("isolated case selection unsupported by declared adapter capabilities")
        cases = {}
        for case in data["cases"]:
            if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"] or case["id"] in cases:
                raise GateError("case evidence requires unique nonempty IDs")
            cases[case["id"]] = case
            if "capabilities" in cfg and not evidence_capabilities.supports(capabilities, case["id"]):
                raise GateError(f"adapter emitted unsupported framework/ID namespace: {case['id']}")
        return cases, evidence

    def classify_failure(self, root, cfg, args, run, permanent, executed, evidence):
        failed = sorted(identity for identity, case in executed.items() if case.get("status") == "failed")
        details = {"candidate": evidence, "failed_cases": failed}
        if not failed or any(c.get("status") not in ("passed", "failed") for c in executed.values()):
            return HotFailure("undetermined", "hot did not produce conclusive assertion results", details)
        baseline_candidates = [identity for identity in failed if identity in permanent
                               and permanent[identity].get("baseline_fingerprint") is not None]
        if not baseline_candidates:
            return HotFailure("ticket_regression", "new hot case failed on the ticket", details)
        def inconclusive(limitation):
            details["classification_limitation"] = limitation
            output = str(evidence.get("output", ""))[-16384:]
            message = "candidate hot failed: " + ", ".join(failed)
            if output:
                message += "\n" + output
            return HotFailure("undetermined", message + "\nBaseline classification: " + limitation, details)
        if not evidence.get("supports_case_selection"):
            return inconclusive("hot runner does not support isolated case selection")
        deadline = time.monotonic() + phase_timeout(cfg, "hot")
        try:
            # A linked worktree retains the Git metadata required by the hot protocol.
            with tempfile.TemporaryDirectory(prefix="nightshift-hot-base-") as temp:
                checkout = Path(temp) / "checkout"
                git(root, "worktree", "add", "--quiet", "--detach", str(checkout), args.base)
                try:
                    baseline_cfg = dict(cfg)
                    argv = shlex.split(command(cfg, "hot"))
                    if len(argv) == 2 and argv[0] == "bash" and Path(argv[1]).is_absolute():
                        script = Path(argv[1]).resolve()
                        if script.is_relative_to(root.resolve()):
                            baseline_cfg["hot"] = shlex.join(["bash", str(checkout / script.relative_to(root.resolve()))])
                    baseline, record = self.invoke(checkout, baseline_cfg, "hot", "run", args.base,
                                                   run, args.task_id, baseline_candidates, deadline=deadline,
                                                   only=baseline_candidates, allow_failure=True, evidence_root=root)
                    details["baseline"] = record
                finally:
                    git(root, "worktree", "remove", "--force", str(checkout))
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            details["baseline_error"] = str(error)
            return inconclusive("isolated hot baseline could not be verified")
        if (not record["supports_case_selection"] or set(baseline) != set(baseline_candidates)
                or any(case.get("status") not in ("passed", "failed") or
                       case.get("fingerprint") != permanent[identity].get("baseline_fingerprint")
                       for identity, case in baseline.items())):
            return inconclusive("isolated hot baseline evidence is incomplete")
        baseline_red = sorted(identity for identity, case in baseline.items() if case["status"] == "failed")
        details["baseline_failed_cases"] = baseline_red
        if baseline_red:
            return HotFailure("baseline_regression", "hot also fails on the accepted baseline; repair it before retrying", details)
        return HotFailure("ticket_regression", "hot fails on the ticket but passes on its baseline", details)

    def run_hot(self, args, result, run):
        root = Path(args.work_dir)
        print(f"\n[HOT_GATE] >>> Starting Hot Acceptance Gate for task: {args.task_id}", flush=True)
        cfg = config(root)
        deadline = time.monotonic() + phase_timeout(cfg, "hot")
        for name in cfg.get("wiring", []):
            if subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--", name]).returncode == 0:
                raise GateError(f"persistent hot wiring must be delivered in Git: {name}")
        existing = ticket_policy.evidence_mode(getattr(args, "title", "")) == "EXISTING"
        declarations = result.get("tdd_cases", [] if existing else None)
        if not isinstance(declarations, list) or (not declarations and not existing):
            raise GateError("development handoff requires nonempty tdd_cases")
        print(f"[HOT_GATE] Discovering permanent test cases (baseline={args.base[:8]})...", flush=True)
        permanent, discovery = self.invoke(root, cfg, "hot", "discover", args.base, run, deadline=deadline)
        pinned = set(ticket_policy.required_cases(args.title)) if existing else set()
        for identity in pinned:
            case = permanent.get(identity, {})
            source = case.get("source", "")
            fingerprint = case.get("fingerprint", "")
            if (not safe_path(source) or not (root / source).is_file() or (root / source).is_symlink()
                    or not (root / source).resolve().is_relative_to(root.resolve())
                    or not isinstance(fingerprint, str) or not re.fullmatch(r"[a-f0-9]{64}", fingerprint)
                    or case.get("baseline_fingerprint") != fingerprint):
                raise GateError(f"pinned existing case requires unchanged baseline source evidence: {identity}")
            if subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--", source]).returncode == 0:
                raise GateError(f"pinned existing case source must be delivered in Git: {identity}")
            if subprocess.run(["git", "-C", str(root), "cat-file", "-e", f"{args.base}:{source}"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
                raise GateError(f"pinned existing case source is absent at baseline: {identity}")
        declared, canonical, dropped, seen = {}, [], [], set()
        original = json.loads(json.dumps(declarations))
        for item in declarations:
            if (not isinstance(item, dict) or not isinstance(item.get("id"), str)
                    or not item["id"] or not isinstance(item.get("source"), str) or not item["source"]):
                raise GateError("tdd_cases requires nonempty IDs and source paths")
            # Resolve only exact discovered identities or extra leading test. wrappers.
            identity, candidates = item["id"], set()
            while True:
                if identity in permanent:
                    candidates.add(identity)
                if not identity.startswith("test."):
                    break
                identity = identity[len("test."):]
            if len(candidates) != 1:
                if "capabilities" in cfg:
                    import evidence_capabilities
                    if not evidence_capabilities.supports(cfg["capabilities"], item["id"]):
                        raise GateError(f"TDD framework/ID namespace unsupported: {item['id']}")
                raise GateError(f"TDD case ID unknown or ambiguous: {item['id']}")
            identity = candidates.pop()
            if identity in seen:
                raise GateError(f"duplicate TDD case after reconciliation: {identity}")
            seen.add(identity)
            submitted = Path(item["source"])
            if ".." in submitted.parts or ".git" in submitted.parts:
                raise GateError(f"unsafe TDD source path: {item['source']}")
            path = submitted if submitted.is_absolute() else root / submitted
            if (not path.resolve().is_relative_to(root.resolve()) or not path.is_file()
                    or path.is_symlink()):
                raise GateError(f"TDD case source not found: {identity}")
            source = path.resolve().relative_to(root.resolve()).as_posix()
            case = permanent[identity]
            if case.get("source") != source or not safe_path(source):
                raise GateError(f"TDD case source mismatch: {identity}")
            fingerprint = case.get("fingerprint", "")
            baseline = case.get("baseline_fingerprint")
            if (not isinstance(fingerprint, str) or not re.fullmatch(r"[a-f0-9]{64}", fingerprint)
                    or (baseline is not None and (not isinstance(baseline, str) or not re.fullmatch(r"[a-f0-9]{64}", baseline)))
                    or "baseline_fingerprint" not in case):
                raise GateError(f"TDD source evidence unsupported: {identity}")
            normalized = {"id": identity, "source": source}
            canonical.append(normalized)
            ignored = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--", source])
            if ignored.returncode == 0:
                raise GateError(f"TDD source must be delivered in Git: {source}")
            if baseline == fingerprint:
                dropped.append(normalized)
                continue
            old = subprocess.run(["git", "-C", str(root), "show", f"{args.base}:{source}"], capture_output=True)
            if old.returncode == 0 and old.stdout == path.read_bytes():
                raise GateError(f"declared TDD source unchanged: {source}")
            declared[identity] = source
        if not declared and not existing:
            raise GateError("TDD handoff contains no new or changed test cases")
        reconciliation = {"original": original, "canonical": canonical, "dropped": dropped}
        result["tdd_cases"] = [{"id": identity, "source": source} for identity, source in declared.items()]
        result["tdd_reconciliation"] = reconciliation
        print("[HOT_GATE] TDD reconciliation: " + json.dumps(reconciliation, sort_keys=True), flush=True)
        required = set(declared) | pinned
        explicit = getattr(args, "required_cases", [])
        if isinstance(explicit, str):
            explicit = [part.strip() for part in explicit.split(",") if part.strip()]
        required.update(explicit)
        print(f"[HOT_GATE] Running hot test suite with {len(required)} required TDD cases...", flush=True)
        executed, execution = self.invoke(root, cfg, "hot", "run", args.base, run, args.task_id, sorted(required),
                                          deadline=deadline, allow_failure=True)
        if execution["exit"] or not executed or any(case.get("status") != "passed" for case in executed.values()):
            raise self.classify_failure(root, cfg, args, run, permanent, executed, execution)
        for identity in required:
            if executed.get(identity, {}).get("status") != "passed":
                raise GateError(f"required case did not execute and pass: {identity}")
            if identity in declared or identity in pinned:
                if any(executed[identity].get(field) != permanent[identity].get(field)
                                            for field in ("source", "fingerprint")):
                    raise GateError(f"case evidence changed between discovery and execution: {identity}")
        evidence = [discovery, execution]
        if args.verify and args.verify.lower() not in ("none", "report_only") and args.verify.strip() != command(cfg, "hot").strip():
            print(f"[HOT_GATE] Running task verify command: {args.verify}...", flush=True)
            budget, started = remaining(deadline), time.monotonic()
            code, output = run(args.verify, str(root), args.worker_port, budget)
            record = {"phase": "task_verify", "command": args.verify, "exit": code,
                      "output": output[-16384:], **verify_evidence(output, budget, started)}
            evidence.append(record)
            if code:
                raise HotFailure("timeout" if record["timed_out"] else "task_verify",
                                 f"task VERIFY exited {code}\n{output[-16384:]}", record)
        print(f"[HOT_GATE] <<< Hot Acceptance Gate PASSED cleanly for {args.task_id}!\n", flush=True)
        return {"cases": sorted(executed), "evidence": evidence, "tdd_reconciliation": reconciliation,
                "evidence_mode": "EXISTING" if existing else "CHANGED", "pinned_cases": sorted(pinned)}

    def run_cold(self, root, run_verify=None, **kwargs):
        runner = run_verify if callable(run_verify) else kwargs.get("run")
        if runner is None or not callable(runner):
            def default_runner(cmd, cwd, port, timeout):
                proc = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout)
                return proc.returncode, proc.stdout + proc.stderr
            runner = default_runner
        # Compatibility for direct project runner callers; lifecycle uses the same executor.
        import acceptance_hooks as hooks
        cfg = config(root)
        head = git(root, "rev-parse", "HEAD")
        run = hooks.make_run(hooks.cold_spec(cfg), "direct", head, "TASK-COLD", head, cfg)
        return hooks.execute(root, run, runner, allow_custom_cold=False)


def get_runner(root, cfg=None):
    """Resolve the acceptance runner for the project.

    A project can customize how hot and cold are executed by:
    1. Specifying 'acceptance.runner' in nightshift/config.json as 'module:Class' or 'module:function'.
    2. Placing nightshift/acceptance_runner.py in the project, exporting 'get_runner()' or 'Runner'.
    """
    if cfg is None:
        try:
            cfg = config(root)
        except Exception:
            cfg = {}
    runner_spec = cfg.get("runner")
    if runner_spec and isinstance(runner_spec, str):
        if ":" in runner_spec:
            mod_name, attr_name = runner_spec.split(":", 1)
        else:
            mod_name, attr_name = runner_spec, "Runner"
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        import importlib
        mod = importlib.import_module(mod_name)
        cls_or_func = getattr(mod, attr_name)
        return cls_or_func() if isinstance(cls_or_func, type) else cls_or_func(root, cfg)

    custom_hook = (Path(root) / "scripts/acceptance_runner.py"
                   if (Path(root) / "scripts/acceptance_runner.py").is_file()
                   else Path(root) / "nightshift/acceptance_runner.py")
    if custom_hook.is_file():
        import importlib.util
        spec = importlib.util.spec_from_file_location("custom_acceptance_runner", str(custom_hook))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        if hasattr(mod, "get_runner"):
            return mod.get_runner(root, cfg)
        if hasattr(mod, "Runner"):
            return mod.Runner() if isinstance(mod.Runner, type) else mod.Runner
    return DefaultAcceptanceRunner()


def invoke(root, cfg, name, phase, base, run, task="", required=()):
    return DefaultAcceptanceRunner().invoke(root, cfg, name, phase, base, run, task, required)


def clean(root, *, external=False):
    """Authorized clean-start policy. Never discard commits or ignored files."""
    import attempt_archive
    attempt_archive.capture(root, state_dir(root) / "retained" / uuid.uuid4().hex)
    if external:
        # External runners own their configuration/state outside product paths;
        # product scripts and generated UID files are not runner state.
        exclusions = []
        selected = Path(os.environ["NIGHTSHIFT_STATE_DIR"]).resolve()
        product = Path(root).resolve()
        if selected == product:
            raise GateError("external clean-start requires separate runner state")
        if selected.is_relative_to(product):
            exclusions = ["-e", "/" + selected.relative_to(product).as_posix() + "/"]
        git(root, "reset", "--hard", "HEAD")
        git(root, "clean", "-fd", *exclusions)
        remaining = git(root, "status", "--porcelain", "--untracked-files=all")
        if remaining:
            raise GateError("external clean-start failed; Worker not launched")
        return
    preserved = {}
    for name in ("tasks.txt", "scripts/tasks.txt", "nightshift/tasks.txt",
                 "tasks.done", "scripts/tasks.done", "nightshift/tasks.done",
                 "progress.log", "scripts/progress.log", "nightshift/progress.log",
                 "scripts/config.json", "nightshift/config.json",
                 "PORTING_GUIDE.md", "scripts/PORTING_GUIDE.md", "nightshift/PORTING_GUIDE.md",
                 "scripts/.ported", "nightshift/.ported"):
        target = Path(root) / name
        if target.is_file():
            preserved[name] = target.read_bytes()
    git(root, "reset", "--hard", "HEAD")
    git(root, "clean", "-fd", "-e", ".scratch", "-e", ".worker*", "-e", "scripts/", "-e", "nightshift/",
        "-e", ".agents/", "-e", ".skills/", "-e", ".gitignore")
    for name, content in preserved.items():
        (Path(root) / name).write_bytes(content)
    status_raw = git(root, "status", "--porcelain", "--untracked-files=all")
    if status_raw:
        lines = [line for line in status_raw.splitlines()
                 if not any(name in line for name in preserved)
                 and not line[3:].startswith("scripts/")
                 and not line[3:].startswith("nightshift/")
                 and not line[3:].startswith(".agents/")
                 and not line[3:].startswith(".skills/")
                 and not line[3:].startswith(".worker")
                 and not line[3:] == ".gitignore"]
        if lines:
            raise GateError("clean-start failed; Worker not launched")


def key(task_id, title):
    return hashlib.sha256(f"{task_id}\n{title}".encode()).hexdigest()


def record_path(args):
    return state_dir(args.work_dir) / "tasks" / (key(args.task_id, args.title) + ".json")


def pause(root, task, detail):
    path = state_dir(root) / "paused.json"
    if not path.exists():
        save(path, {"task": task, "detail": detail})
        print(f"[PLANNER_REQUIRED] {task}: {detail}", flush=True)


def hot(args, result, run):
    root = Path(args.work_dir)
    cfg = config(root)
    runner = get_runner(root, cfg)
    return runner.run_hot(args, result, run)


def cold(root, run):
    root = Path(root)
    cfg = config(root)
    runner = get_runner(root, cfg)
    return runner.run_cold(root, run)
