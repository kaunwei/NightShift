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
import uuid


class GateError(ValueError):
    pass


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
    timeout = value.get("timeout", 180)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
        raise GateError("acceptance timeout must be finite and positive")
    interval = value.get("cold_every")
    if interval is not None and (type(interval) is not int or interval < 1):
        raise GateError("cold_every must be a positive integer or absent")
    wiring = value.get("wiring", [])
    if not isinstance(wiring, list) or any(not safe_path(item) for item in wiring):
        raise GateError("wiring must list exact project-relative files")
    return value


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

    def invoke(self, root, cfg, name, phase, base, run, task="", required=()):
        nonce = uuid.uuid4().hex
        output = state_dir(root) / "evidence" / f"{nonce}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        environment = {"NIGHTSHIFT_PHASE": phase, "NIGHTSHIFT_RESULT": str(output.resolve()),
                       "NIGHTSHIFT_RUN": nonce, "NIGHTSHIFT_BASE": base,
                       "NIGHTSHIFT_TASK": task, "NIGHTSHIFT_REQUIRED": json.dumps(list(required)),
                       "PYTHONDONTWRITEBYTECODE": "1", "PYTHONPYCACHEPREFIX": str(output.with_suffix(".cache")),
                       "NIGHTSHIFT_PROJECT_ROOT": str(root.resolve())}
        # Discover permanent membership with no ticket context.
        if phase == "discover":
            environment.update(NIGHTSHIFT_TASK="", NIGHTSHIFT_REQUIRED="[]")
        prefix = "env " + " ".join(shlex.quote(f"{key}={val}") for key, val in environment.items())
        actual = f"{prefix} bash -c {shlex.quote(command(cfg, name))}"
        code, text = run(actual, str(root), "3001", cfg.get("timeout", 180))
        evidence = {"phase": phase, "command": command(cfg, name), "exit": code,
                    "output": text[-16384:], "run": nonce}
        save(output.with_suffix(".log.json"), evidence)
        if code:
            raise GateError(f"{name}/{phase} exited {code}\n{text[-16384:]}")
        data = load(output)
        if not isinstance(data, dict) or data.get("run") != nonce or not isinstance(data.get("cases"), list):
            raise GateError(f"{name}/{phase}: missing or stale case evidence: {output}")
        cases = {}
        for case in data["cases"]:
            if not isinstance(case, dict) or not isinstance(case.get("id"), str) or not case["id"] or case["id"] in cases:
                raise GateError("case evidence requires unique nonempty IDs")
            cases[case["id"]] = case
        return cases, evidence

    def run_hot(self, args, result, run):
        root = Path(args.work_dir)
        print(f"\n[HOT_GATE] >>> Starting Hot Acceptance Gate for task: {args.task_id}", flush=True)
        cfg = config(root)
        for name in cfg.get("wiring", []):
            if subprocess.run(["git", "-C", str(root), "check-ignore", "-q", "--", name]).returncode == 0:
                raise GateError(f"persistent hot wiring must be delivered in Git: {name}")
        declarations = result.get("tdd_cases")
        if not isinstance(declarations, list) or not declarations:
            raise GateError("development handoff requires nonempty tdd_cases")
        print(f"[HOT_GATE] Discovering permanent test cases (baseline={args.base[:8]})...", flush=True)
        permanent, discovery = self.invoke(root, cfg, "hot", "discover", args.base, run)
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
        if not declared:
            raise GateError("TDD handoff contains no new or changed test cases")
        reconciliation = {"original": original, "canonical": canonical, "dropped": dropped}
        result["tdd_cases"] = [{"id": identity, "source": source} for identity, source in declared.items()]
        result["tdd_reconciliation"] = reconciliation
        print("[HOT_GATE] TDD reconciliation: " + json.dumps(reconciliation, sort_keys=True), flush=True)
        required = set(declared)
        explicit = getattr(args, "required_cases", [])
        if isinstance(explicit, str):
            explicit = [part.strip() for part in explicit.split(",") if part.strip()]
        required.update(explicit)
        print(f"[HOT_GATE] Running hot test suite with {len(required)} required TDD cases...", flush=True)
        executed, execution = self.invoke(root, cfg, "hot", "run", args.base, run, args.task_id, sorted(required))
        if not executed or any(case.get("status") != "passed" for case in executed.values()):
            raise GateError("hot contains failed, skipped or invalid case results")
        for identity in required:
            if executed.get(identity, {}).get("status") != "passed":
                raise GateError(f"required case did not execute and pass: {identity}")
            if identity in declared and any(executed[identity].get(field) != permanent[identity].get(field)
                                            for field in ("source", "fingerprint")):
                raise GateError(f"case evidence changed between discovery and execution: {identity}")
        evidence = [discovery, execution]
        if args.verify and args.verify.lower() not in ("none", "report_only"):
            print(f"[HOT_GATE] Running task verify command: {args.verify}...", flush=True)
            code, output = run(args.verify, str(root), args.worker_port, cfg.get("timeout", 180))
            evidence.append({"phase": "task", "command": args.verify, "exit": code, "output": output[-16384:]})
            if code:
                raise GateError(f"task VERIFY exited {code}\n{output[-16384:]}")
        print(f"[HOT_GATE] <<< Hot Acceptance Gate PASSED cleanly for {args.task_id}!\n", flush=True)
        return {"cases": sorted(executed), "evidence": evidence, "tdd_reconciliation": reconciliation}

    def run_cold(self, root, run_verify=None, **kwargs):
        runner = run_verify if callable(run_verify) else kwargs.get("run")
        if runner is None or not callable(runner):
            def default_runner(cmd, cwd, port, timeout):
                proc = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout)
                return proc.returncode, proc.stdout + proc.stderr
            runner = default_runner
        cfg = config(root)
        head = git(root, "rev-parse", "HEAD")
        path = state_dir(root) / "cold.json"
        state = load(path, {"commits": [], "pending": False})
        if state.get("passed") == head:
            state.update(commits=[], pending=False)
            save(path, state)
            return
        ignored = re.compile(r"(?:^|/)(?:scripts/|nightshift/)?(?:progress\.log|tasks\.txt|tasks\.done|worker\..*\.status|\.preview|\.reports|\.worker.*|\.scratch)")
        def product_status():
            raw = git(root, "status", "--porcelain", "--untracked-files=all")
            return [line for line in raw.splitlines() if line and not ignored.search(line[3:])]

        before = product_status()
        if before:
            raise GateError("cold requires a clean product tree")
        code, output = runner(command(cfg, "cold"), str(root), "3001", cfg.get("timeout", 180))
        after = product_status()
        if code or before != after or git(root, "rev-parse", "HEAD") != head:
            raise GateError(f"cold failed or changed product files (exit {code}) at {head}\n{output[-16384:]}")
        state.update(passed=head, commits=[], pending=False)
        save(path, state)


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


def clean(root):
    """Authorized clean-start policy. Never discard commits or ignored files."""
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


def schedule_cold(root, commit, tasks, insert):
    try:
        cfg = config(root)
    except GateError:
        return
    interval = cfg.get("cold_every")
    if interval is None:
        return
    path = state_dir(root) / "cold.json"
    state = load(path, {"commits": [], "pending": False})
    # A ledger survives completed intervals so replay cannot count a commit twice.
    counted = state.setdefault("counted", [])
    if commit and commit not in counted:
        counted.append(commit)
        state["commits"].append(commit)
    if len(state["commits"]) >= interval or state["pending"]:
        state["pending"] = True
        save(path, state)
        insert(tasks, "TASK-COLD [COLD] | LEVEL: 1 | ACTION: project cold")
    save(path, state)


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
