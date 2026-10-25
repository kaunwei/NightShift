"""Behavioral checks for the worker's stable command-line seams."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

from scripts import worker_runtime as runtime_module
from scripts.worker_runtime import build_task_prompt, first_report, publish_research_reports


ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "worker.sh").exists())
RUNTIME = ROOT / "scripts/worker_runtime.py"


def runtime(*args, env=None):
    args = list(args)
    if args and args[0] == "daemon" and env and env.get("AI_AGENTS_JSON"):
        root_index = args.index("--root") + 1
        write_legacy_registry(Path(args[root_index]), env["AI_AGENTS_JSON"])
    return subprocess.run(
        [sys.executable, str(RUNTIME), *map(str, args)],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def write_legacy_registry(root, raw):
    """Translate old integration fixtures to the public registry seam."""
    profiles = json.loads(raw)
    if not isinstance(profiles, list):
        profiles = [profiles]
    registry = {}
    for index, profile in enumerate(profiles):
        if not isinstance(profile, dict):
            profile = {"invalid": profile}
        name = profile.get("id", f"agent-{index}")
        agent_config = dict(profile.get("config", profile.get("overrides", {})))
        agent_config.update({key: profile[key] for key in ("model", "effort") if key in profile})
        command = agent_config.pop("executable", profile.get("command", ""))
        agent_args = agent_config.pop("args", profile.get("args", []))
        agent_env = agent_config.pop("env", profile.get("env", {}))
        entry = {key: value for key, value in profile.items()
                 if key not in {"id", "adapter", "command", "args", "env", "model", "effort", "overrides", "config"}}
        entry.update({
            "default": index == 0,
            "worker": {},
            "agent": {"adapter": profile.get("adapter", ""), "command": command,
                      "args": agent_args, "env": agent_env, "config": agent_config},
        })
        registry[name] = entry
    agent_dir = Path(root) / "scripts/adapters"
    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "agents.json").write_text(json.dumps(registry))


_real_subprocess_run = subprocess.run


def _run_worker_fixture_compat(command, *args, **kwargs):
    """Keep older integration fixtures runnable while their setup is migrated."""
    parts = list(map(str, command)) if isinstance(command, (list, tuple)) else []
    if len(parts) >= 2 and Path(parts[-1]).name == "worker.sh":
        root = Path(kwargs.get("cwd") or Path(parts[-1]).parent)
        legacy = root / ".worker.env"
        child_env = dict(kwargs.get("env") or os.environ)
        if legacy.is_file():
            settings = {}
            for line in legacy.read_text().splitlines():
                if not line.strip() or line.lstrip().startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                value = value.strip()
                if value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]
                elif value.startswith('"') and value.endswith('"'):
                    fallback = re.search(r":-(.*)\}\"?$", value)
                    value = fallback.group(1).rstrip('"') if fallback else value[1:-1]
                settings[key] = value
            if settings.get("AI_AGENTS_JSON"):
                write_legacy_registry(root, settings.pop("AI_AGENTS_JSON"))
                if _real_subprocess_run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
                                        capture_output=True, text=True).returncode == 0:
                    _real_subprocess_run(["git", "-C", str(root), "add", "scripts/adapters/agents.json"], check=True)
                    if _real_subprocess_run(["git", "-C", str(root), "diff", "--cached", "--quiet"]).returncode:
                        _real_subprocess_run(["git", "-C", str(root), "-c", "user.name=Fixture",
                                              "-c", "user.email=fixture@example.invalid",
                                              "commit", "-m", "test: configure agent registry"],
                                             check=True, capture_output=True)
            child_env.update(settings)
            kwargs["env"] = child_env
    return _real_subprocess_run(command, *args, **kwargs)


subprocess.run = _run_worker_fixture_compat


def copy_runtime_fixture(destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RUNTIME, destination)
    adapters = destination.parent / "adapters"
    shutil.copytree(ROOT / "scripts/adapters", adapters, dirs_exist_ok=True)


def codex_registration(registration_id, executable="codex", model="", **settings):
    overrides = {"executable": str(executable), **settings}
    if model:
        overrides["model"] = model
    return {"id": registration_id, "adapter": "codex", "command": sys.executable,
            "args": [str(ROOT / "scripts/adapters/codex.py")], "overrides": overrides}


def generic_registration(registration_id, executable, args=(), env=None, **settings):
    overrides = {"executable": str(executable), "args": list(args), "env": env or {}, **settings}
    return {"id": registration_id, "adapter": "generic", "command": sys.executable,
            "args": [str(ROOT / "scripts/adapters/generic.py")], "overrides": overrides}


def task_cli_adapter(adapter, executable, **settings):
    return ["--adapter", adapter, "--executable", sys.executable,
            "--extra-arg", str(ROOT / "scripts/adapters" / f"{adapter}.py"),
            "--overrides", json.dumps({"executable": str(executable), **settings})]


class WorkerPromptContractTests(unittest.TestCase):
    def test_prompt_preserves_task_scope_budget_verification_and_score_ownership(self):
        prompt = build_task_prompt(
            "[CODE: FIX] Correct the parser", "TASK-9", "2", "src/parser.py",
            "python3 -m unittest", "no thread sleeps", "preserve error messages",
            22, 2, 12, 5, "progress.log",
        )

        for required in (
            "src/parser.py", "Budget: 22 actions (12+2×5)",
            "Per-invocation timeout", "python3 -m unittest", "TASK-9",
            "The Planner owns acceptance and independent review",
            "[EXEC] <brief action>", "closeout_required", "[SCOPE_BLOCKED]", "[DEAD_END]",
            "progress.log",
        ):
            with self.subTest(required=required):
                self.assertIn(required, prompt)
        self.assertIn(str(ROOT / ".skills/universal-build-verify.md"), prompt)
        self.assertIn((ROOT / ".skills/universal-build-verify.md").read_text(), prompt)
        self.assertIn("Preserve unrelated and pre-existing changes", prompt)

    def test_prompt_does_not_request_self_scoring_or_destructive_retry_reset(self):
        prompt = build_task_prompt("task", "TASK-1", "1", "src/a.py", "test",
                                  "", "", 17, 1, 12, 5, "progress.log")
        self.assertIn("Do not self-adjust the shared Worker score", prompt)
        self.assertIn("never clean or reset the checkout", prompt.lower())
        self.assertNotIn("restore the clean tree", prompt)

    def test_prompt_requires_pure_json_and_failure_for_failed_verification(self):
        prompt = build_task_prompt("[CODE: FIX] Repair parser", "TASK-JSON", "1", "parser.py",
                                   "python3 -m unittest", "", "", 12, 1, 12, 0,
                                   "progress.log")
        self.assertIn("Return exactly one JSON object with no text before or after it", prompt)
        self.assertIn("`attempts`=integer; `confidence`=HIGH|MED|LOW", prompt)
        self.assertIn("If verification fails, return blocked or failure", prompt)
        self.assertIn("closeout_required cannot repair failed tests", prompt)
        self.assertNotIn("End diagnostic text: `Attempts:", prompt)


class InPlaceExecutionContractTests(unittest.TestCase):
    def test_legacy_isolation_setting_does_not_create_or_select_worker_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tasks.txt").write_text("")
            env = {**os.environ, "WORKER_ISOLATION": "1", "RUN_ONCE": "1",
                   "POLL_INTERVAL": "0", "AI_AGENTS_JSON":
                   json.dumps([{"id": "unused", "adapter": "opaque", "command": "unused"}])}

            result = runtime("daemon", "--root", root, env=env)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(f"WorkDir: {root.resolve()}", result.stdout)
            self.assertFalse((root / ".worker-tree").exists())
            self.assertFalse((root / ".preview").exists())

    @unittest.skipUnless((ROOT / "install.sh").is_file(), "source checkout only")
    def test_installer_update_preserves_legacy_worker_data_and_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            (root / "worker.sh").write_text("legacy launcher\n")
            (root / ".worker.env").write_text("WORKER_ISOLATION=1\nKEEP_ME=present\n")
            (root / ".worker-tree").mkdir()
            (root / ".worker-tree/unmerged.txt").write_text("unmerged work\n")
            (root / ".preview").mkdir()
            (root / ".preview/version.json").write_text("legacy preview\n")

            result = subprocess.run(["bash", str(ROOT / "install.sh"), str(root)],
                                    capture_output=True, text=True, timeout=30)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((root / ".worker.env").read_text(),
                             "WORKER_ISOLATION=1\nKEEP_ME=present\n")
            self.assertEqual((root / ".worker-tree/unmerged.txt").read_text(), "unmerged work\n")
            self.assertEqual((root / ".preview/version.json").read_text(), "legacy preview\n")


class AgentConfigContractTests(unittest.TestCase):
    def test_agent_config_separates_worker_timeout_from_real_agent_launch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agents.json"
            path.write_text(json.dumps({
                "codex-fast": {
                    "default": True,
                    "worker": {"task_timeout_seconds": 73},
                    "agent": {
                        "adapter": "codex",
                        "command": "/opt/bin/codex",
                        "args": ["--profile", "fast"],
                        "env": {"CODEX_ORG": "nightshift-test"},
                        "config": {"model": "gpt-6-luna", "effort": "low"},
                    },
                },
            }))

            (agent,) = runtime_module.load_agent_registry(path)

            self.assertEqual(agent["worker"]["task_timeout_seconds"], 73)
            self.assertEqual(agent["adapter"], "codex")
            self.assertEqual(agent["command"], "/opt/bin/codex")
            self.assertEqual(agent["args"], ["--profile", "fast"])
            self.assertEqual(agent["env"], {"CODEX_ORG": "nightshift-test"})
            self.assertEqual(agent["overrides"], {
                "model": "gpt-6-luna", "effort": "low",
                "command": "/opt/bin/codex", "args": ["--profile", "fast"],
            })

    def test_registry_orders_every_default_agent_first_and_allows_multiple_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "agents.json"
            path.write_text(json.dumps({
                "backup": {"default": False, "worker": {}, "agent": {"adapter": "opaque", "command": "backup"}},
                "main": {"default": True, "worker": {}, "agent": {"adapter": "opaque", "command": "main"}},
                "secondary-default": {"default": True, "worker": {}, "agent": {"adapter": "opaque", "command": "secondary"}},
            }))

            agents = runtime_module.load_agent_registry(path)

            self.assertEqual({agent["id"] for agent in agents[:2]}, {"main", "secondary-default"})
            self.assertEqual(agents[2]["id"], "backup")

    def test_daemon_scans_single_named_agent_json_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tasks.txt").write_text("")
            config_dir = root / "scripts/adapters"
            config_dir.mkdir(parents=True)
            (config_dir / "agents.json").write_text(json.dumps({
                "backup": {"default": False, "worker": {}, "agent": {"adapter": "opaque", "command": "backup"}},
                "main": {"default": True, "worker": {}, "agent": {"adapter": "opaque", "command": "main"}},
            }))
            env = {**os.environ, "RUN_ONCE": "1", "POLL_INTERVAL": "0"}

            result = runtime("daemon", "--root", root, env=env)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Registered adapters: 2", result.stdout)
            self.assertNotIn("AI_AGENTS_JSON must", result.stderr)

    def test_daemon_accepts_multiple_unrecognized_adapter_registrations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            (root / "tasks.txt").write_text("")
            profiles = [
                {"id": "one", "adapter": "first-party", "command": "unused-first"},
                {"id": "two", "adapter": "second-party", "command": "unused-second"},
            ]
            env = {**os.environ, "AI_AGENTS_JSON": json.dumps(profiles),
                   "WORKER_ISOLATION": "0", "RUN_ONCE": "1", "POLL_INTERVAL": "0"}
            result = runtime("daemon", "--root", root, env=env)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Queue is empty", result.stdout)

    def test_legacy_provider_profile_is_rejected_before_task_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = "TASK-LEGACY | TARGET: output.txt | ACTION: old config | VERIFY: true\n"
            (root / "tasks.txt").write_text(task)
            profile = [{"id": "old", "provider": "codex", "command": "codex"}]
            env = {**os.environ, "AI_AGENTS_JSON": json.dumps(profile),
                   "WORKER_ISOLATION": "0", "RUN_ONCE": "1", "POLL_INTERVAL": "0"}
            result = runtime("daemon", "--root", root, env=env)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unknown fields: provider", result.stderr)
            self.assertEqual((root / "tasks.txt").read_text(), task)


class AgentScoreContractTests(unittest.TestCase):
    def test_get_config_initializes_independent_scores_for_each_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Score Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "score@example.invalid"], check=True)
            (repo / "baseline.txt").write_text("baseline\n")
            subprocess.run(["git", "-C", str(repo), "add", "baseline.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "baseline"], check=True)
            adapter = root / "adapter.py"
            adapter.write_text(
                "import json, pathlib, sys\nrequest=json.load(sys.stdin); op=sys.argv[1]\n"
                "if op == 'get_config': response={'protocol_version':1,'initial_score':3 if request['registration_id']=='low' else 5}\n"
                "elif op == 'start':\n"
                " pathlib.Path(request['result_path']).write_text(json.dumps({'outcome':'no_change','changed':False,'no_change_reason':'already satisfied'}))\n"
                " p=pathlib.Path(request['output_dir']); (p/'status.json').write_text(json.dumps({'status':'complete','result_location':request['result_path']}))\n"
                " response={'execution_id':request['registration_id'],'status_location':str(p/'status.json')}\n"
                "else: response=json.loads(pathlib.Path(request['status_location']).read_text())\n"
                "print(json.dumps(response))\n"
            )
            state_root = root / "agent-scores"
            legacy_state = root / ".worker-score.json"
            legacy_state.write_text(json.dumps({"version":1,"score":2,"success_window":[],"failures":{},"feedback":[]}))
            def execute(registration_id):
                return runtime("task-cli", "--adapter", "shared-adapter", "--agent-id", registration_id,
                               "--executable", sys.executable, "--extra-arg", adapter,
                               "--work-dir", repo, "--prompt-file", root / "prompt.json",
                               "--output-file", root / f"{registration_id}.log",
                               "--result-file", root / f"{registration_id}.json",
                               "--score-state-file", state_root, "--base", "HEAD",
                               "--task-id", f"TASK-{registration_id}")
            low = execute("low")
            high = execute("high")
            self.assertEqual(low.returncode, 0, low.stderr)
            self.assertEqual(high.returncode, 0, high.stderr)
            low_score = runtime("score-read", "--state", state_root, "--agent-id", "low")
            high_score = runtime("score-read", "--state", state_root, "--agent-id", "high")
            self.assertEqual(json.loads(low_score.stdout)["score"], 3)
            self.assertEqual(json.loads(high_score.stdout)["score"], 5)
            self.assertEqual(json.loads(legacy_state.read_text())["score"], 2)
            events = root / "agent-events.jsonl"
            for number in range(5):
                recorded = runtime("score-record", "--state", state_root, "--agent-id", "low",
                                   "--task-id", f"TASK-ACCEPT-{number}", "--result", "accept",
                                   "--events", events, "--mid-batch")
                self.assertEqual(recorded.returncode, 0, recorded.stderr)
            low_after = json.loads(runtime("score-read", "--state", state_root,
                                           "--agent-id", "low").stdout)
            high_after = json.loads(runtime("score-read", "--state", state_root,
                                            "--agent-id", "high").stdout)
            self.assertEqual(low_after["score"], 4)
            self.assertEqual(high_after["score"], 5)
            event = json.loads(events.read_text().splitlines()[-1])
            self.assertEqual(event["registration_id"], "low")
            self.assertEqual(event["cause"], "mid_batch_score_change")
            self.assertEqual((event["previous_score"], event["current_score"]), (3, 4))


class WatcherDispatchGateContractTests(unittest.TestCase):
    def test_watcher_handoffs_each_event_once_and_dispatch_waits_for_planner_ack(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks = root / "tasks.txt"
            events = root / "events.jsonl"
            cursor = root / "cursor.json"
            acknowledgements = root / "acks.jsonl"
            gate = root / "dispatch-gate.json"
            handoff = root / "progress.log"
            tasks.write_text("TASK-WATCH | TARGET: src/a.py | ACTION: continue\n")
            event = {"event_id":"event-1", "registration_id":"agent-a", "cause":"mid_batch_score_change",
                     "task_id":"TASK-WATCH", "previous_registration_id":"agent-a",
                     "current_registration_id":"agent-a", "previous_score":3,
                     "current_score":4, "previous_level":2, "current_level":2}
            events.write_text(json.dumps(event) + "\n")
            first = runtime("agent-events-watch", "--events", events, "--cursor", cursor,
                            "--acknowledgements", acknowledgements, "--gate", gate,
                            "--handoff", handoff)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertIn("event-1", first.stdout)
            self.assertTrue(gate.exists())
            self.assertIn("[PLANNER_REVIEW_REQUIRED]", handoff.read_text())
            resumed = runtime("agent-events-watch", "--events", events, "--cursor", cursor,
                              "--acknowledgements", acknowledgements, "--gate", gate,
                              "--handoff", handoff)
            self.assertEqual(resumed.returncode, 0, resumed.stderr)
            self.assertEqual(resumed.stdout, "")
            self.assertEqual(handoff.read_text().count("event-1"), 1)
            paused = runtime("poll-next", "--tasks", tasks, "--done", root / "tasks.done",
                             "--pause", root / "PAUSE", "--dispatch-gate", gate,
                             "--work-dir", root)
            self.assertEqual(paused.stdout.split("\0")[0], "paused")
            self.assertIn("TASK-WATCH", tasks.read_text())
            acknowledged = runtime("agent-event-ack", "--events", events,
                                   "--acknowledgements", acknowledgements,
                                   "--event-id", "event-1", "--resolution", "revised")
            self.assertEqual(acknowledged.returncode, 0, acknowledged.stderr)
            released = runtime("agent-events-watch", "--events", events, "--cursor", cursor,
                               "--acknowledgements", acknowledgements, "--gate", gate,
                               "--handoff", handoff)
            self.assertEqual(released.returncode, 0, released.stderr)
            self.assertFalse(gate.exists())
            dispatched = runtime("poll-next", "--tasks", tasks, "--done", root / "tasks.done",
                                 "--pause", root / "PAUSE", "--dispatch-gate", gate,
                                 "--work-dir", root)
            self.assertEqual(dispatched.stdout.split("\0")[0], "task")
            self.assertEqual(dispatched.stdout.split("\0")[1], "TASK-WATCH | TARGET: src/a.py | ACTION: continue")


class RegisteredAgentFailoverContractTests(unittest.TestCase):
    def test_timeout_is_task_local_failover_but_budget_and_cancellation_failure_are_not(self):
        self.assertTrue(runtime_module.should_failover_agent(124, '{"status":"execution_timeout"}'))
        self.assertTrue(runtime_module.should_failover_agent(124, '{"status":"callback_timeout"}'))
        self.assertFalse(runtime_module.should_failover_agent(125, '{"status":"step_budget_exceeded"}'))
        self.assertFalse(runtime_module.should_failover_agent(124, '{"status":"cancellation_failed"}'))
        self.assertFalse(runtime_module.should_failover_agent(1, '{"status":"error"}'))


class BuiltinAdapterContractTests(unittest.TestCase):
    def test_task_cli_treats_adapter_name_as_opaque_and_uses_registered_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Adapter Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "adapter@example.invalid"], check=True)
            (root / "baseline.txt").write_text("baseline\n")
            subprocess.run(["git", "-C", str(root), "add", "baseline.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "baseline"], check=True)
            executable = Path(directory) / "adapter.py"
            executable.write_text(
                "import json,pathlib,sys\nrequest=json.load(sys.stdin); op=sys.argv[1]\n"
                "if op == 'get_config': response={'protocol_version':1,'initial_score':5,"
                "'limits':{'poll_interval_seconds':0.01}}\n"
                "elif op == 'start':\n"
                " pathlib.Path(request['result_path']).write_text(json.dumps({'outcome':'no_change',"
                "'changed':False,'no_change_reason':'adapter contract check'}))\n"
                " p=pathlib.Path(request['output_dir']); p.mkdir(parents=True,exist_ok=True)\n"
                " (p/'status.json').write_text(json.dumps({'status':'complete',"
                "'result_location':request['result_path']}))\n"
                " response={'execution_id':'test','status_location':str(p/'status.json')}\n"
                "else: response=json.loads(pathlib.Path(request['status_location']).read_text())\n"
                "print(json.dumps(response))\n")
            prompt, output, result = Path(directory) / "prompt.txt", Path(directory) / "runtime.log", Path(directory) / "result.json"
            prompt.write_text("same common task prompt")

            completed = runtime("task-cli", "--adapter", "codex", "--executable", sys.executable,
                                "--extra-arg", executable,
                                "--work-dir", root, "--prompt-file", prompt,
                                "--output-file", output, "--result-file", result,
                                "--task-id", "TASK-ADAPTER", "--base", "HEAD")

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertEqual(json.loads(output.read_text())["status"], "complete")
            self.assertEqual(json.loads(result.read_text())["no_change_reason"],
                             "adapter contract check")

    def test_execute_adapter_protocol_streams_live_logs_to_stderr(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Adapter Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "adapter@example.invalid"], check=True)
            (root / "baseline.txt").write_text("baseline\n")
            subprocess.run(["git", "-C", str(root), "add", "baseline.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "baseline"], check=True)
            executable = Path(directory) / "stream_adapter.py"
            executable.write_text(
                "import json, pathlib, sys\n"
                "request = json.load(sys.stdin); op = sys.argv[1]\n"
                "if op == 'get_config':\n"
                "    response = {'protocol_version': 1, 'initial_score': 5, 'limits': {'poll_interval_seconds': 0.05}}\n"
                "elif op == 'start':\n"
                "    p = pathlib.Path(request['output_dir'])\n"
                "    p.mkdir(parents=True, exist_ok=True)\n"
                "    (p / 'adapter.log').write_text('[STREAM_OUTPUT] Step 1: reading file\\n[STREAM_OUTPUT] Step 2: compiling\\n')\n"
                "    pathlib.Path(request['result_path']).write_text(json.dumps({'outcome': 'no_change', 'changed': False, 'no_change_reason': 'already done'}))\n"
                "    (p / 'status.json').write_text(json.dumps({'status': 'complete', 'result_location': request['result_path']}))\n"
                "    response = {'execution_id': 'stream-test', 'status_location': str(p / 'status.json')}\n"
                "else:\n"
                "    response = json.loads(pathlib.Path(request['status_location']).read_text())\n"
                "print(json.dumps(response))\n"
            )
            prompt, output, result = Path(directory) / "prompt.txt", Path(directory) / "runtime.log", Path(directory) / "result.json"
            prompt.write_text("task prompt")
            completed = runtime("task-cli", "--adapter", "custom", "--executable", sys.executable,
                                "--extra-arg", executable, "--work-dir", root,
                                "--prompt-file", prompt, "--output-file", output,
                                "--result-file", result, "--task-id", "TASK-STREAM", "--base", "HEAD")
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertIn("[STREAM_OUTPUT] Step 1: reading file", completed.stderr)
            self.assertIn("[STREAM_OUTPUT] Step 2: compiling", completed.stderr)

    def test_codex_adapter_uses_final_outcome_instead_of_zero_exit(self):
        cases = (("[BLOCKED] unavailable", "blocked", "failed"),
                 ("[SCOPE_BLOCKED] need target", "scope_blocked", "failed"),
                 ("[NEED_GUIDANCE] clarify", "guidance", "failed"),
                 ("", "failure", "failed"),
                 ("Done.", "failure", "failed"),
                 ('{"changed":true}', "failure", "failed"),
                 ('{"outcome":[]}', "failure", "failed"),
                 ('{"outcome":{}}', "failure", "failed"),
                 ('{"outcome":"complete","commit_message":"docs: finish"}', "complete", "complete"))
        for reply, outcome, status in cases:
            with self.subTest(reply=reply), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                fake = root / "codex"
                fake.write_text(
                    "#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\n"
                    "Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(os.environ['FINAL_REPLY'])\n"
                    "print('tool output quoted [BLOCKED]; not the final reply')\n")
                fake.chmod(0o755)
                (root / "prompt.txt").write_text("task")
                request = {"protocol_version":1,"registration_id":"codex-test",
                           "overrides":{"command":str(fake),"effort":"none"},
                           "task_id":"TASK-RESULT","working_directory":str(root),
                           "prompt_path":str(root/"prompt.txt"),"output_dir":str(root/"run"),
                           "result_path":str(root/"result.json"),
                           "environment":{"FINAL_REPLY":reply},"limits":{"action_limit":3}}
                (root / "request.json").write_text(json.dumps(request))
                executed = runtime("adapter-exec", "--command", sys.executable,
                                   "--adapter-arg", ROOT/"scripts/adapters/codex.py",
                                   "--request", root/"request.json", "--execution-timeout", "2", "--callback-timeout", "0.5")
                self.assertEqual(executed.returncode, 0, executed.stderr)
                self.assertEqual(json.loads(executed.stdout)["status"], status)
                self.assertEqual(json.loads((root/"result.json").read_text())["outcome"], outcome)

    def test_codex_adapter_runs_fake_cli_and_returns_structured_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "fake-codex"
            executable.write_text(
                "#!/usr/bin/env python3\nimport json,os,sys\n"
                "json.dump(sys.argv[1:],open(os.environ['ARGS_LOG'],'w'))\n"
                "a=sys.argv; out=a[a.index('--output-last-message')+1]\n"
                "open(out,'w').write(json.dumps({'outcome':'complete','changed':False,"
                "'no_change_reason':'fixture','commit_message':'docs: no changes'}))\n"
                "print(json.dumps({'type':'item.completed','item':{'type':'command_execution'}}))\n")
            executable.chmod(0o755)
            adapter = ROOT / "scripts/adapters/codex.py"
            args_log = root / "codex-args.json"
            request = {"protocol_version":1,"registration_id":"codex-test","overrides":{
                "executable":str(executable),"model":"gpt-6-luna","effort":"none",
                "approval_mode":"auto","ephemeral":"1","additional_dirs":str(root)},
                "task_id":"TASK-CODEX","environment":{"ARGS_LOG":str(args_log)},
                "working_directory":str(root),"prompt_path":str(root/'prompt.txt'),
                "output_dir":str(root/'run'),"result_path":str(root/'result.json'),
                "limits":{"action_limit":3}}
            (root / "prompt.txt").write_text("implement nothing")
            def callback(name, payload):
                return subprocess.run([sys.executable,str(adapter),name],
                    input=json.dumps(payload),text=True,capture_output=True,timeout=10)
            config = callback("get_config", {"protocol_version":1,"registration_id":"codex-test",
                                               "overrides":request["overrides"]})
            self.assertEqual(json.loads(config.stdout)["initial_score"],5)
            started = callback("start", {**request,"configuration":json.loads(config.stdout)["configuration"]})
            self.assertEqual(started.returncode,0,started.stderr)
            handle = json.loads(started.stdout)
            deadline=time.monotonic()+5
            result=None
            while time.monotonic()<deadline:
                checked=callback("status", {"protocol_version":1,**handle})
                result=json.loads(checked.stdout)
                if result["status"]!="running": break
                time.sleep(.02)
            self.assertEqual(result["status"],"complete", str(handle) + " " + str(list((root/"run").iterdir())))
            self.assertEqual(json.loads(Path(result["result_location"]).read_text())["commit_message"],
                             "docs: no changes")
            argv=json.loads(args_log.read_text())
            self.assertIn("--approve-for-me",argv)
            self.assertIn("gpt-6-luna",argv)
            self.assertIn("model_reasoning_effort=none",argv)
            self.assertEqual(argv[argv.index("--add-dir")+1],str(root))
            invalid=callback("get_config",{"protocol_version":1,"registration_id":"codex-test",
                "overrides":{"executable":str(executable),"approval_mode":"unknown"}})
            self.assertNotEqual(invalid.returncode,0)

    def test_codex_adapter_does_not_treat_successful_test_output_429_as_quota(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "fake-codex"
            fake.write_text(
                "#!/usr/bin/env python3\nimport json,sys\n"
                "open(sys.argv[sys.argv.index('--output-last-message')+1],'w').write('{\"outcome\":\"complete\",\"changed\":false}')\n"
                "print('expected uint32 value 4294967168 (429 is not an API error)')\n")
            fake.chmod(0o755)
            (root / "prompt.txt").write_text("task")
            request = {"protocol_version": 1, "overrides": {"command": str(fake)},
                       "task_id": "TASK-429", "working_directory": str(root),
                       "prompt_path": str(root / "prompt.txt"), "output_dir": str(root / "run"),
                       "result_path": str(root / "result.json"), "limits": {"action_limit": 3}}
            (root / "request.json").write_text(json.dumps(request))
            executed = runtime("adapter-exec", "--command", sys.executable,
                               "--adapter-arg", ROOT / "scripts/adapters/codex.py",
                               "--request", root / "request.json", "--execution-timeout", "2",
                               "--callback-timeout", "0.5")
            self.assertEqual(executed.returncode, 0, executed.stderr)
            self.assertEqual(json.loads(executed.stdout)["status"], "complete")
            self.assertEqual(json.loads((root / "result.json").read_text())["outcome"], "complete")

    def test_codex_adapter_ignores_quota_words_in_command_output_after_cli_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "fake-codex"
            fake.write_text(
                "#!/usr/bin/env python3\nimport json,sys\n"
                "print(json.dumps({'type':'item.completed','item':{'type':'command_execution',"
                "'aggregated_output':'Error: insufficient_quota'}}), flush=True)\n"
                "sys.exit(1)\n")
            fake.chmod(0o755)
            (root / "prompt.txt").write_text("task")
            request = {"protocol_version": 1, "overrides": {"command": str(fake)},
                       "task_id": "TASK-QUOTED-ERROR", "working_directory": str(root),
                       "prompt_path": str(root / "prompt.txt"), "output_dir": str(root / "run"),
                       "result_path": str(root / "result.json"), "limits": {"action_limit": 3}}
            (root / "request.json").write_text(json.dumps(request))
            executed = runtime("adapter-exec", "--command", sys.executable,
                               "--adapter-arg", ROOT / "scripts/adapters/codex.py",
                               "--request", root / "request.json", "--execution-timeout", "2",
                               "--callback-timeout", "0.5")
            self.assertEqual(executed.returncode, 0, executed.stderr)
            self.assertEqual(json.loads(executed.stdout)["status"], "failed")
            self.assertEqual(json.loads((root / "result.json").read_text())["outcome"], "failure")

    def test_codex_adapter_recognizes_quota_from_codex_error_event(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "fake-codex"
            fake.write_text(
                "#!/usr/bin/env python3\nimport json,sys\n"
                "print(json.dumps({'type':'turn.failed','error':"
                "{'message':'insufficient_quota'}}), flush=True)\n"
                "sys.exit(1)\n")
            fake.chmod(0o755)
            (root / "prompt.txt").write_text("task")
            request = {"protocol_version": 1, "overrides": {"command": str(fake)},
                       "task_id": "TASK-CODEX-QUOTA", "working_directory": str(root),
                       "prompt_path": str(root / "prompt.txt"), "output_dir": str(root / "run"),
                       "result_path": str(root / "result.json"), "limits": {"action_limit": 3}}
            (root / "request.json").write_text(json.dumps(request))
            executed = runtime("adapter-exec", "--command", sys.executable,
                               "--adapter-arg", ROOT / "scripts/adapters/codex.py",
                               "--request", root / "request.json", "--execution-timeout", "2",
                               "--callback-timeout", "0.5")
            self.assertEqual(executed.returncode, 0, executed.stderr)
            self.assertEqual(json.loads(executed.stdout)["status"], "quota_exhausted")
            self.assertEqual(json.loads((root / "result.json").read_text())["outcome"], "quota_exhausted")

    def test_codex_adapter_preserves_json_result_with_legacy_attempts_line(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "fake-codex"
            fake.write_text(
                "#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\n"
                "message = Path(sys.argv[sys.argv.index('--output-last-message')+1])\n"
                "message.write_text('{\"outcome\":\"closeout_required\",\"changed\":true}'"
                " + '\\n\\nAttempts: 1 | Confidence: MED')\n")
            fake.chmod(0o755)
            (root / "prompt.txt").write_text("task")
            request = {"protocol_version": 1, "overrides": {"command": str(fake)},
                       "task_id": "TASK-LEGACY-RESULT", "working_directory": str(root),
                       "prompt_path": str(root / "prompt.txt"), "output_dir": str(root / "run"),
                       "result_path": str(root / "result.json"), "limits": {"action_limit": 3}}
            (root / "request.json").write_text(json.dumps(request))
            executed = runtime("adapter-exec", "--command", sys.executable,
                               "--adapter-arg", ROOT / "scripts/adapters/codex.py",
                               "--request", root / "request.json", "--execution-timeout", "2",
                               "--callback-timeout", "0.5")
            self.assertEqual(executed.returncode, 0, executed.stderr)
            self.assertEqual(json.loads(executed.stdout)["status"], "closeout_required")
            payload = json.loads((root / "result.json").read_text())
            self.assertEqual((payload["outcome"], payload["attempts"], payload["confidence"]),
                             ("closeout_required", 1, "MED"))

    def test_agy_adapter_probes_fake_cli_and_extracts_structured_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); executable=root/"fake-agy"
            executable.write_text(
                "#!/usr/bin/env python3\nimport json,sys\n"
                "if '--help' in sys.argv: print('--max-steps'); raise SystemExit(0)\n"
                "import os; json.dump(sys.argv[1:],open(os.environ['ARGS_LOG'],'w'))\n"
                "print(json.dumps({'outcome':'complete','changed':False,"
                "'no_change_reason':'fixture','commit_message':'docs: no changes'}))\n")
            executable.chmod(0o755)
            adapter=ROOT/"scripts/adapters/agy.py"
            args_log=root/"agy-args.json"; extra=root/"extra"; extra.mkdir()
            request={"protocol_version":1,"registration_id":"agy-test","overrides":{
                "executable":str(executable),"model":"model-low","effort":"high",
                "mode":"accept-edits","sandbox":"true","additional_dirs":str(extra),
                "extra_args":["--custom-flag"]},"task_id":"TASK-AGY",
                "environment":{"ARGS_LOG":str(args_log)},
                "working_directory":str(root),"prompt_path":str(root/"prompt.txt"),
                "output_dir":str(root/"run"),"result_path":str(root/"result.json"),
                "limits":{"action_limit":23,"execution_timeout_seconds":90}}
            (root/"prompt.txt").write_text("implement nothing")
            def callback(name,payload):
                return subprocess.run([sys.executable,str(adapter),name],input=json.dumps(payload),
                    text=True,capture_output=True,timeout=10)
            configuration=json.loads(callback("get_config",{"protocol_version":1,
                "registration_id":"agy-test","overrides":request["overrides"]}).stdout)
            self.assertEqual(configuration["initial_score"],5)
            started=callback("start",{**request,"configuration":configuration["configuration"]})
            self.assertEqual(started.returncode,0,started.stderr)
            handle=json.loads(started.stdout); deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                checked=callback("status",{"protocol_version":1,**handle})
                result=json.loads(checked.stdout)
                if result["status"]!="running": break
                time.sleep(.02)
            self.assertEqual(result["status"],"complete")
            self.assertEqual(json.loads(Path(result["result_location"]).read_text())["outcome"],"complete")
            argv=json.loads(args_log.read_text())
            self.assertIn("--sandbox",argv); self.assertIn("--mode",argv)
            self.assertIn("model-low",argv); self.assertIn("--effort",argv)
            self.assertEqual(argv[argv.index("--add-dir")+1],str(extra))
            self.assertIn("--max-steps",argv); self.assertIn("23",argv)
            self.assertIn("--custom-flag",argv)

    def test_agy_adapter_ignores_quota_words_and_status_codes_in_command_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "fake-agy"
            fake.write_text(
                "#!/usr/bin/env python3\nimport json,sys\n"
                "if '--help' in sys.argv: sys.exit(0)\n"
                "print(json.dumps({'type':'item.completed','item':{'type':'command_execution',"
                "'aggregated_output':'HTTP 429: insufficient_quota'}}), flush=True)\n"
                "print('tool output line containing 429 and rate limit', flush=True)\n"
                "sys.exit(1)\n")
            fake.chmod(0o755)
            (root / "prompt.txt").write_text("task")
            request = {"protocol_version": 1, "overrides": {"command": str(fake)},
                       "task_id": "TASK-AGY-QUOTED-ERROR", "working_directory": str(root),
                       "prompt_path": str(root / "prompt.txt"), "output_dir": str(root / "run"),
                       "result_path": str(root / "result.json"), "limits": {"action_limit": 3}}
            (root / "request.json").write_text(json.dumps(request))
            executed = runtime("adapter-exec", "--command", sys.executable,
                               "--adapter-arg", ROOT / "scripts/adapters/agy.py",
                               "--request", root / "request.json", "--execution-timeout", "2",
                               "--callback-timeout", "0.5")
            self.assertEqual(executed.returncode, 0, executed.stderr)
            self.assertEqual(json.loads(executed.stdout)["status"], "failed")
            self.assertEqual(json.loads((root / "result.json").read_text())["outcome"], "failure")

    def test_agy_adapter_recognizes_quota_from_error_event(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "fake-agy"
            fake.write_text(
                "#!/usr/bin/env python3\nimport json,sys\n"
                "if '--help' in sys.argv: sys.exit(0)\n"
                "print(json.dumps({'type':'turn.failed','error':"
                "{'message':'insufficient_quota'}}), flush=True)\n"
                "sys.exit(1)\n")
            fake.chmod(0o755)
            (root / "prompt.txt").write_text("task")
            request = {"protocol_version": 1, "overrides": {"command": str(fake)},
                       "task_id": "TASK-AGY-QUOTA", "working_directory": str(root),
                       "prompt_path": str(root / "prompt.txt"), "output_dir": str(root / "run"),
                       "result_path": str(root / "result.json"), "limits": {"action_limit": 3}}
            (root / "request.json").write_text(json.dumps(request))
            executed = runtime("adapter-exec", "--command", sys.executable,
                               "--adapter-arg", ROOT / "scripts/adapters/agy.py",
                               "--request", root / "request.json", "--execution-timeout", "2",
                               "--callback-timeout", "0.5")
            self.assertEqual(executed.returncode, 0, executed.stderr)
            self.assertEqual(json.loads(executed.stdout)["status"], "quota_exhausted")
            self.assertEqual(json.loads((root / "result.json").read_text())["outcome"], "quota_exhausted")

    def test_generic_compatibility_adapter_passes_paths_environment_and_structured_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); wrapper=root/"legacy-wrapper.py"; marker=root/"marker.json"
            wrapper.write_text(
                "import json,os,pathlib,sys\n"
                "prompt=pathlib.Path(os.environ['NIGHTSHIFT_PROMPT_FILE']).read_text()\n"
                "json.dump({'prompt':prompt,'model':os.environ['NIGHTSHIFT_MODEL'],"
                "'effort':os.environ['NIGHTSHIFT_EFFORT'],'kind':os.environ['NIGHTSHIFT_EXECUTION_KIND']},"
                "open("+repr(str(marker))+",'w'))\n"
                "json.dump({'outcome':'complete','changed':False,'no_change_reason':'fixture',"
                "'commit_message':'docs: no changes'},open(os.environ['NIGHTSHIFT_RESULT_FILE'],'w'))\n")
            adapter=ROOT/"scripts/adapters/generic.py"
            request={"protocol_version":1,"registration_id":"custom","overrides":{
                "executable":sys.executable,"args":[str(wrapper)],"model":"model-x","effort":"high"},
                "task_id":"TASK-GENERIC","working_directory":str(root),
                "prompt_path":str(root/"prompt.txt"),"output_dir":str(root/"run"),
                "result_path":str(root/"result.json"),"limits":{"action_limit":2}}
            (root/"prompt.txt").write_text("common prompt")
            def callback(name,payload):
                return subprocess.run([sys.executable,str(adapter),name],input=json.dumps(payload),
                    text=True,capture_output=True,timeout=10)
            config=json.loads(callback("get_config",{"protocol_version":1,"registration_id":"custom",
                "overrides":request["overrides"]}).stdout)
            self.assertEqual(config["initial_score"],3)
            started=callback("start",{**request,"configuration":config["configuration"]})
            self.assertEqual(started.returncode,0,started.stderr)
            handle=json.loads(started.stdout); deadline=time.monotonic()+5
            while time.monotonic()<deadline:
                checked=callback("status",{"protocol_version":1,**handle})
                result=json.loads(checked.stdout)
                if result["status"]!="running": break
                time.sleep(.02)
            self.assertEqual(result["status"],"complete")
            self.assertEqual(json.loads(marker.read_text()),{"prompt":"common prompt","model":"model-x",
                "effort":"high","kind":"main"})


class AdapterDeadlineContractTests(unittest.TestCase):
    def run_adapter(self, status_body, cancel_response, callback_timeout="0.1", execution_timeout="2"):
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        adapter = root / "adapter.py"
        adapter.write_text(
            "import json, pathlib, subprocess, sys, time\nrequest=json.load(sys.stdin); op=sys.argv[1]\n"
            "if op == 'get_config': response={'protocol_version':1,'initial_score':5,'limits':{'poll_interval_seconds':0.01}}\n"
            "elif op == 'start':\n"
            " p=pathlib.Path(request['output_dir']); p.mkdir(parents=True,exist_ok=True)\n"
            " (p/'status.json').write_text(json.dumps({'status':'running'}))\n"
            " response={'execution_id':'exec-deadline','status_location':str(p/'status.json')}\n"
            f"elif op == 'status':\n{status_body}\n"
            f"elif op == 'cancel': response={cancel_response}\n"
            "else: response={'error':{'code':'unsupported','message':op}}\n"
            "print(json.dumps(response))\n"
        )
        result = runtime("adapter-exec", "--command", sys.executable,
                         "--adapter-arg", adapter, "--request", root / "request.json",
                         "--callback-timeout", callback_timeout,
                         "--execution-timeout", execution_timeout)
        return directory, result

    def test_blocked_status_callback_is_bounded_and_cancel_is_confirmed(self):
        directory, result = self.run_adapter(
            " time.sleep(5); response={'status':'running'}", "{'stopped':True}")
        try:
            self.assertEqual(result.returncode, 0, result.stderr)
            status = json.loads(result.stdout)
            self.assertEqual(status["status"], "callback_timeout")
            self.assertTrue(status["stopped"])
        finally:
            directory.cleanup()

    def test_responsive_running_status_does_not_bypass_execution_deadline(self):
        directory, result = self.run_adapter(
            " response={'status':'running'}", "{'stopped':True}", execution_timeout="0.08")
        try:
            self.assertEqual(result.returncode, 0, result.stderr)
            status = json.loads(result.stdout)
            self.assertEqual(status["status"], "execution_timeout")
            self.assertTrue(status["stopped"])
        finally:
            directory.cleanup()

    def test_cancel_acknowledgement_without_termination_is_not_stopped(self):
        directory, result = self.run_adapter(
            " time.sleep(5); response={'status':'running'}", "{'accepted':True,'stopped':False}")
        try:
            self.assertEqual(result.returncode, 0, result.stderr)
            status = json.loads(result.stdout)
            self.assertEqual(status["status"], "cancellation_failed")
            self.assertFalse(status["stopped"])
        finally:
            directory.cleanup()

    def test_timeout_terminates_children_left_by_a_callback(self):
        with tempfile.TemporaryDirectory() as directory:
            pid_file = Path(directory) / "child.pid"
            status_body = (
                " child=subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'])\n"
                f" pathlib.Path({str(pid_file)!r}).write_text(str(child.pid))\n"
                " time.sleep(5); response={'status':'running'}"
            )
            directory_handle, result = self.run_adapter(
                status_body, "{'stopped':True}", callback_timeout="0.15")
            try:
                self.assertEqual(result.returncode, 0, result.stderr)
                child_pid = int(pid_file.read_text())
                with self.assertRaises(ProcessLookupError):
                    os.kill(child_pid, 0)
            finally:
                directory_handle.cleanup()


class AdapterGhostCloseoutContractTests(unittest.TestCase):
    def test_missing_closeout_is_rescued_once_on_same_registration_and_committed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "worker@example.invalid"], check=True)
            (repo / "output.txt").write_text("before\n")
            subprocess.run(["git", "-C", str(repo), "add", "output.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "baseline"], check=True)
            adapter = root / "adapter.py"
            trace = root / "trace.jsonl"
            adapter.write_text(
                "import json, pathlib, sys\nrequest=json.load(sys.stdin); op=sys.argv[1]\n"
                f"with open({str(trace)!r}, 'a') as f: f.write(json.dumps({{'op':op,'request':request}})+'\\n')\n"
                "if op == 'get_config': response={'protocol_version':1,'initial_score':5,'limits':{'poll_interval_seconds':0.01}}\n"
                "elif op == 'start':\n"
                " pathlib.Path(request['working_directory'],'output.txt').write_text('after\\n')\n"
                " pathlib.Path(request['result_path']).write_text(json.dumps({'outcome':'closeout_required','changed':True}))\n"
                " p=pathlib.Path(request['output_dir']); (p/'main-status.json').write_text(json.dumps({'status':'complete','result_location':request['result_path']}))\n"
                " response={'execution_id':'main-exec','status_location':str(p/'main-status.json')}\n"
                "elif op == 'closeout':\n"
                " assert request['execution_id'] == 'main-exec'\n"
                " pathlib.Path(request['result_path']).write_text(json.dumps({'outcome':'complete','changed':True,'commit_message':'fix(parser): close out task'}))\n"
                " p=pathlib.Path(request['output_dir']); (p/'ghost-status.json').write_text(json.dumps({'status':'complete','result_location':request['result_path']}))\n"
                " response={'execution_id':'ghost-exec','status_location':str(p/'ghost-status.json')}\n"
                "else: response=json.loads(pathlib.Path(request['status_location']).read_text())\n"
                "print(json.dumps(response))\n"
            )
            result = runtime("task-cli", "--adapter", "mystery", "--executable", sys.executable,
                             "--extra-arg", adapter, "--work-dir", repo, "--prompt-file", root / "worker-prompt.txt",
                             "--output-file", root / "main.log", "--result-file", root / "main-result.json",
                             "--task-id", "TASK-GHOST", "--target", "output.txt", "--base", "HEAD")
            self.assertEqual(result.returncode, 0, result.stderr)
            calls = [json.loads(line) for line in trace.read_text().splitlines()]
            self.assertEqual([call['op'] for call in calls],
                             ["get_config", "start", "status", "get_config", "closeout", "status"])
            main_request = next(call['request'] for call in calls if call['op'] == 'start')
            ghost_request = next(call['request'] for call in calls if call['op'] == 'closeout')
            self.assertEqual(ghost_request["registration_id"], "mystery")
            self.assertEqual(ghost_request["task_id"], "TASK-GHOST")
            self.assertNotEqual(ghost_request["prompt_path"], main_request["prompt_path"])
            self.assertNotEqual(ghost_request["result_path"], main_request["result_path"])
            ghost_prompt = Path(ghost_request["prompt_path"]).read_text()
            self.assertIn("for original task TASK-GHOST", ghost_prompt)
            self.assertIn("Never modify, create, or delete source", ghost_prompt)
            self.assertIn('"commit_message"', ghost_prompt)
            self.assertIn('"outcome"', ghost_prompt)
            self.assertNotIn("[CLOSEOUT_VERIFIED]", ghost_prompt)
            self.assertTrue(Path(ghost_request["output_dir"]).is_dir())
            self.assertEqual(json.loads(Path(ghost_request["result_path"]).read_text())["commit_message"],
                             "fix(parser): close out task")
            self.assertIn("TASK-GHOST", json.loads((repo / ".worker-ghost-state.json").read_text())["issued"])
            self.assertEqual(subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%s"],
                                            check=True, capture_output=True, text=True).stdout.strip(),
                             "fix(parser): close out task")
            retry = runtime("task-cli", "--adapter", "mystery", "--executable", sys.executable,
                            "--extra-arg", adapter, "--work-dir", repo,
                            "--prompt-file", root / "worker-prompt.txt",
                            "--output-file", root / "main.log", "--result-file", root / "main-result.json",
                            "--task-id", "TASK-GHOST", "--target", "output.txt", "--base", "HEAD")
            self.assertEqual(retry.returncode, 126)
            retried_calls = [json.loads(line) for line in trace.read_text().splitlines()]
            self.assertEqual(sum(call["op"] == "closeout" for call in retried_calls), 1)

    def test_fake_adapter_completes_through_versioned_callbacks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "worker@example.invalid"], check=True)
            (repo / "baseline.txt").write_text("baseline\n")
            subprocess.run(["git", "-C", str(repo), "add", "baseline.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "baseline"], check=True)
            adapter = root / "adapter.py"
            adapter.write_text(
                "import json, pathlib, sys\n"
                "request=json.load(sys.stdin); op=sys.argv[1]\n"
                "with open(request['trace'], 'a') as f: f.write(op + '\\n')\n"
                "if op == 'get_config': response={'protocol_version':1,'initial_score':4,'limits':{'poll_interval_seconds':0.01},'configuration':request['overrides']}\n"
                "elif op == 'start':\n"
                " p=pathlib.Path(request['output_dir']); p.mkdir(parents=True,exist_ok=True)\n"
                " (p/'result.json').write_text(json.dumps({'outcome':'complete','commit_message':'finish task'}))\n"
                " response={'execution_id':'exec-1','status_location':str(p/'status.json')}\n"
                " (p/'status.json').write_text(json.dumps({'execution_id':'exec-1','status':'complete','result_location':str(p/'result.json')}))\n"
                "elif op == 'status': response=json.loads(pathlib.Path(request['status_location']).read_text())\n"
                "else: response={'error':{'code':'unsupported','message':op}}\n"
                "print(json.dumps(response))\n"
            )
            result = runtime("adapter-exec", "--command", sys.executable,
                             "--adapter-arg", adapter, "--request", root / "request.json",
                             "--trace", root / "trace.log")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / "trace.log").read_text().splitlines(),
                             ["get_config", "start", "status"])
            response = json.loads(result.stdout)
            self.assertEqual(response["status"], "complete")
            self.assertEqual(json.loads(Path(response["result_location"]).read_text())["commit_message"],
                             "finish task")

    def test_invalid_profile_is_rejected_before_claiming_a_task(self):
        for override, expected in (({"arguments": []}, "unknown fields"),
                                   ({"model": None}, "must be a string"),
                                   ({"args": "--flag"}, "array of strings"),
                                   ({"env": []}, "map valid names")):
            with self.subTest(override=override), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                task = "TASK-CFG | TARGET: output.txt | ACTION: configuration check\n"
                (root / "tasks.txt").write_text(task)
                profile = {"id": "api", "adapter": "generic", "command": "unused", **override}
                env = {**os.environ, "AI_AGENTS_JSON": json.dumps([profile]), "WORKER_ISOLATION": "0", "RUN_ONCE": "1", "TASK_TIMEOUT": "1"}
                result = runtime("daemon", "--root", root, env=env)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected, result.stderr)
                self.assertEqual((root / "tasks.txt").read_text(), task)


class QueueInsertContractTests(unittest.TestCase):
    def test_inserts_trial_task_before_pending_work_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            tasks = Path(directory) / "tasks.txt"
            original = "# task queue\nTASK-A | TARGET: a.py | ACTION: existing A\nTASK-B | TARGET: b.py | ACTION: existing B\n"
            tasks.write_text(original)
            trial = "TASK-TRIAL-1 | TARGET: app | ACTION: build trial\n"

            inserted = runtime("queue-insert", "--tasks", tasks, "--task", trial)
            repeated = runtime("queue-insert", "--tasks", tasks, "--task", trial)

            self.assertEqual(inserted.returncode, 0, inserted.stderr)
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            self.assertEqual(tasks.read_text(),
                             "# task queue\n" + trial + "TASK-A | TARGET: a.py | ACTION: existing A\n"
                             "TASK-B | TARGET: b.py | ACTION: existing B\n")
            self.assertIn('"inserted": false', repeated.stdout)

    def test_insert_racing_with_claim_preserves_every_unclaimed_task(self):
        with tempfile.TemporaryDirectory() as directory:
            tasks = Path(directory) / "tasks.txt"
            tasks.write_text("TASK-A | ACTION: A\nTASK-B | ACTION: B\n")
            trial = "TRIAL-RACE | ACTION: trial\n"
            with ThreadPoolExecutor(max_workers=2) as executor:
                claim_future = executor.submit(runtime, "queue-pop", tasks)
                insert_future = executor.submit(runtime, "queue-insert", "--tasks", tasks,
                                                "--task", trial)
                claimed, inserted = claim_future.result(), insert_future.result()

            self.assertEqual(claimed.returncode, 0, claimed.stderr)
            self.assertEqual(inserted.returncode, 0, inserted.stderr)
            claimed_id = claimed.stdout.strip().split("|", 1)[0].strip()
            pending_ids = [line.split("|", 1)[0].strip() for line in tasks.read_text().splitlines()
                           if line.strip() and not line.lstrip().startswith("#")]
            self.assertCountEqual([claimed_id, *pending_ids], ["TASK-A", "TASK-B", "TRIAL-RACE"])


class QueueContractTests(unittest.TestCase):
    def test_pop_preserves_comments_and_only_removes_first_task(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = Path(directory) / "tasks.txt"
            queue.write_text("# heading\n\nTASK-1 | TARGET: a.py\nTASK-2 | TARGET: b.py\n")

            result = runtime("queue-pop", queue)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "TASK-1 | TARGET: a.py")
            self.assertEqual(queue.read_text(), "# heading\n\nTASK-2 | TARGET: b.py\n")

    def test_pop_empty_queue_leaves_file_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = Path(directory) / "tasks.txt"
            queue.write_text("# heading\n\n")
            result = runtime("queue-pop", queue)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertEqual(queue.read_text(), "# heading\n\n")

    def test_parallel_claims_do_not_duplicate_a_task(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = Path(directory) / "tasks.txt"
            queue.write_text("".join(f"TASK-{i}\n" for i in range(8)))
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: runtime("queue-pop", queue), range(8)))
            self.assertTrue(all(result.returncode == 0 for result in results))
            self.assertEqual({result.stdout.strip() for result in results},
                             {f"TASK-{i}" for i in range(8)})
            self.assertEqual(queue.read_text(), "")

    def test_field_allows_pipe_inside_value(self):
        result = runtime(
            "task-field",
            "TASK-1 | TARGET: src/a.py | VERIFY: python -c 'print(1 | 2)' | CONSTRAINTS: safe",
            "VERIFY",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "python -c 'print(1 | 2)'")


class PollContractTests(unittest.TestCase):
    def test_empty_queue_reports_idle_without_modification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks, done = root / "tasks.txt", root / "tasks.done"
            tasks.write_text("# no work\n")
            done.write_text("[DONE] TASK-1\n")
            result = runtime("poll-next", "--tasks", tasks, "--done", done,
                             "--pause", root / "PAUSE", "--work-dir", root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.split("\0")[:5], ["idle", "", "1", "0", "1"])
            self.assertEqual(tasks.read_text(), "# no work\n")

    def test_pause_does_not_claim_task(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks, done, pause = root / "tasks.txt", root / "tasks.done", root / "PAUSE"
            tasks.write_text("TASK-1 | TARGET: src/a.py\n")
            done.write_text("")
            pause.touch()
            result = runtime("poll-next", "--tasks", tasks, "--done", done,
                             "--pause", pause, "--work-dir", root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.split("\0")[0], "paused")
            self.assertIn("TASK-1", tasks.read_text())

    def test_claim_calculates_progress_and_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks, done = root / "tasks.txt", root / "tasks.done"
            tasks.write_text("# queued\nTASK-2 | LEVEL: 2 | TARGET: a.py,b.py | VERIFY: true\n")
            done.write_text("[DONE] TASK-1\n")
            result = runtime("poll-next", "--tasks", tasks, "--done", done,
                             "--pause", root / "PAUSE", "--work-dir", root,
                             "--step-base", "12", "--step-per-file", "5")
            self.assertEqual(result.returncode, 0, result.stderr)
            fields = result.stdout.split("\0")
            self.assertEqual(fields[:7], ["task", "TASK-2 | LEVEL: 2 | TARGET: a.py,b.py | VERIFY: true",
                                          "1", "1", "2", "2", "50"])
            self.assertEqual(fields[8], "TASK-2")
            self.assertEqual(fields[15], "22")
            self.assertEqual(tasks.read_text(), "# queued\n")


class WorkerScoreTests(unittest.TestCase):
    def test_planner_review_updates_only_matching_audit_and_preserves_history(self):
        with tempfile.TemporaryDirectory() as directory:
            progress = Path(directory) / "progress.log"
            progress.write_text(
                "[MECHANICAL_AUDIT] Status: PASS | Task: T | Audit_NS: 11 | Planner_Review: pending\n"
                "[MECHANICAL_AUDIT] Status: PASS | Task: T | Audit_NS: 12 | Planner_Review: pending\n"
                "unrelated history\n", encoding="utf-8")
            result = runtime("score-record", "--state", Path(directory) / "score.json",
                             "--task-id", "T", "--result", "accept",
                             "--progress-file", progress, "--audit-ns", "11")
            self.assertEqual(result.returncode, 0, result.stderr)
            content = progress.read_text(encoding="utf-8")
            self.assertIn("Audit_NS: 11 | Planner_Review: accept", content)
            self.assertIn("Audit_NS: 12 | Planner_Review: pending", content)
            self.assertTrue(content.endswith("unrelated history\n"))

    def test_planner_review_rejects_legacy_and_conflicting_records(self):
        with tempfile.TemporaryDirectory() as directory:
            progress = Path(directory) / "progress.log"
            progress.write_text("[MECHANICAL_AUDIT] Status: PASS | Task: T | Audit_NS: 11\n")
            legacy = runtime("score-record", "--state", Path(directory) / "score.json",
                             "--task-id", "T", "--result", "accept",
                             "--progress-file", progress, "--audit-ns", "11")
            self.assertNotEqual(legacy.returncode, 0)
            self.assertIn("confirmation", legacy.stderr)
            progress.write_text("[MECHANICAL_AUDIT] Status: PASS | Task: T | Audit_NS: 11 | Planner_Review: reject\n")
            conflict = runtime("score-record", "--state", Path(directory) / "score.json",
                               "--task-id", "T", "--result", "accept",
                               "--progress-file", progress, "--audit-ns", "11")
            self.assertNotEqual(conflict.returncode, 0)
            self.assertIn("conflict", conflict.stderr)

    def test_score_record_reviews_one_audit_once_and_leaves_another_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            progress, state = root / "progress.log", root / "score.json"
            progress.write_text(
                "[MECHANICAL_AUDIT] Status: PASS | Task: T | Audit_NS: 11 | Planner_Review: pending\n"
                "[MECHANICAL_AUDIT] Status: PASS | Task: T | Audit_NS: 12 | Planner_Review: pending\n",
                encoding="utf-8")
            state.write_text(json.dumps({"version": 1, "score": 3,
                                         "success_window": ["A", "B", "C", "D"],
                                         "failures": {}, "feedback": []}), encoding="utf-8")
            args = ("score-record", "--state", state, "--task-id", "T", "--result", "accept",
                    "--progress-file", progress, "--audit-ns", "11")
            first = runtime(*args)
            duplicate = runtime(*args)
            self.assertEqual(json.loads(first.stdout)["score"], 4)
            self.assertTrue(json.loads(duplicate.stdout)["duplicate"])
            self.assertEqual(json.loads(state.read_text())["score"], 4)
            content = progress.read_text(encoding="utf-8")
            self.assertIn("Audit_NS: 11 | Planner_Review: accept", content)
            self.assertIn("Audit_NS: 12 | Planner_Review: pending", content)

    def test_new_worker_starts_at_five_and_maps_to_coarsest_task_level(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "score.json"
            result = runtime("score-read", "--state", state)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data["score"], 5)
            self.assertEqual(data["task_level"], 1)
            self.assertTrue(state.exists())

    def test_only_five_accepted_real_tasks_increase_score(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "score.json"
            state.write_text(json.dumps({"version": 1, "score": 3,
                                         "success_window": [], "failures": {}}))
            for index in range(4):
                result = runtime("score-record", "--state", state,
                                 "--task-id", f"TASK-{index}", "--result", "accept")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["score"], 3)
            result = runtime("score-record", "--state", state,
                             "--task-id", "TASK-4", "--result", "accept")
            self.assertEqual(json.loads(result.stdout)["score"], 4)
            self.assertEqual(json.loads(result.stdout)["successes_in_window"], 0)

    def test_reject_resets_success_window_while_no_fault_is_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "score.json"
            state.write_text(json.dumps({"version": 1, "score": 4,
                                         "success_window": ["A", "B"], "failures": {}}))
            result = runtime("score-record", "--state", state, "--task-id", "C",
                             "--result", "no_fault", "--evidence", "progress.log#L1")
            persisted = json.loads(state.read_text())
            self.assertEqual(persisted["success_window"], ["A", "B"])
            self.assertEqual(persisted["feedback"][-1]["evidence"], "progress.log#L1")
            result = runtime("score-record", "--state", state, "--task-id", "D",
                             "--result", "reject", "--evidence", "tasks.done#L2")
            self.assertEqual(json.loads(state.read_text())["success_window"], [])

    def test_concurrent_feedback_updates_do_not_lose_score_records(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "score.json"
            state.write_text(json.dumps({"version": 1, "score": 3,
                                         "success_window": [], "failures": {}}))
            with ThreadPoolExecutor(max_workers=5) as pool:
                results = list(pool.map(
                    lambda index: runtime("score-record", "--state", state,
                                           "--task-id", f"TASK-{index}",
                                           "--result", "accept"), range(5)))
            self.assertTrue(all(result.returncode == 0 for result in results))
            persisted = json.loads(state.read_text())
            self.assertEqual(persisted["score"], 4)
            self.assertEqual(len(persisted["feedback"]), 5)

    def test_hard_failures_lower_original_task_score_on_second_and_third_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "score.json"
            for expected in (5, 4, 3):
                result = runtime("score-record", "--state", state,
                                 "--task-id", "TASK-X", "--result", "hard_failure")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["score"], expected)
            result = runtime("score-record", "--state", state,
                             "--task-id", "TASK-X", "--result", "hard_failure")
            self.assertEqual(json.loads(result.stdout)["score"], 3)
            result = runtime("score-record", "--state", state,
                             "--task-id", "TASK-X", "--result", "success")
            self.assertEqual(json.loads(state.read_text())["failures"], {})

    def test_ghost_closeout_prompt_forbids_implementation_and_names_original_task(self):
        with tempfile.TemporaryDirectory() as directory:
            prompt = Path(directory) / "closeout.txt"
            result = runtime("ghost-prompt", "--output", prompt,
                             "--task-id", "TASK-7", "--verify", "python3 -m unittest")
            self.assertEqual(result.returncode, 0, result.stderr)
            text = prompt.read_text()
            self.assertIn("TASK-7", text)
            self.assertIn("Never modify, create, or delete source", text)
            self.assertIn("python3 -m unittest", text)
            self.assertIn("their changes do not block closeout", text)

    def test_codex_jsonl_command_execution_events_are_counted_against_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt, output, last_message = root / "prompt", root / "output", root / "message"
            prompt.write_text("task")
            executable = root / "codex"
            executable.write_text(
                "#!/bin/sh\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = --output-last-message ]; then shift; printf 'done\\n' > \"$1\"; fi\n"
                "  shift\n"
                "done\n"
                "printf '%s\\n' '{\"type\":\"item.completed\",\"item\":{\"type\":\"command_execution\"}}'\n"
                "sleep 0.3\n"
                "touch \"$BUDGET_MARKER\"\n"
            )
            executable.chmod(0o755)
            marker = Path(directory) / "continued-after-budget"
            env = os.environ.copy()
            env["BUDGET_MARKER"] = str(marker)
            result = runtime("task-cli", *task_cli_adapter("codex", executable,
                             model="gpt-6-luna", effort="none", approval_mode="auto",
                             sandbox="workspace-write", ephemeral="1", additional_dirs=""),
                             "--work-dir", root, "--prompt-file", prompt, "--output-file", output,
                             "--result-file", last_message, "--timeout", "10", "--step-budget", "0",
                             "--worker-port", "3001", "--target", "", "--task-id", "TASK-C", "--title", "test",
                             "--level", "1", "--verify", "", "--base", "HEAD", "--progress-file", "progress.log",
                             env=env)
            self.assertEqual(result.returncode, 125, result.stdout + result.stderr + output.read_text())
            self.assertFalse(marker.exists())

    def test_codex_hands_closeout_marker_to_ghost_without_editing_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "Codex Test")
            git("config", "user.email", "codex@example.invalid")
            (root / ".gitignore").write_text(".worker-ghost-state.json\n.worker-ghosts/\n")
            (root / "output.txt").write_text("before\n")
            git("add", "output.txt", ".gitignore")
            git("commit", "-qm", "baseline")
            base = git("rev-parse", "HEAD")
            prompt = Path(directory) / "prompt.txt"
            prompt.write_text("implement")
            output, result_path = Path(directory) / "cli.log", Path(directory) / "result.json"
            executable = Path(directory) / "fake-codex"
            executable.write_text(
                "#!/usr/bin/env python3\nimport json,os,sys\n"
                "args=sys.argv[1:]; result=args[args.index('--output-last-message')+1]\n"
                "kind=os.environ.get('NIGHTSHIFT_EXECUTION_KIND','main')\n"
                "open(os.environ['KIND_LOG'],'a').write(kind+'\\n')\n"
                "if kind == 'closeout': payload={'outcome':os.environ.get('CLOSEOUT_OUTCOME','complete'),"
                "'changed':False,'commit_message':'fix: complete TASK-CLOSE'}\n"
                "else:\n"
                " open('output.txt','w').write('after\\n')\n"
                " payload={'outcome':os.environ.get('INITIAL_OUTCOME','closeout_required'),'changed':True}\n"
                "if kind=='closeout' and os.environ.get('MISSING_CLOSEOUT_MESSAGE')=='1': payload.pop('commit_message',None)\n"
                "json.dump(payload,open(result,'w'))\n"
                "print(json.dumps({'type':'item.completed','item':{'type':'command_execution'}}))\n")
            executable.chmod(0o755)

            def invoke(initial="closeout_required", closeout="complete", mode="auto", missing_message=False):
                env={**os.environ,"INITIAL_OUTCOME":initial,"CLOSEOUT_OUTCOME":closeout,
                     "KIND_LOG":str(Path(directory)/"kind.log"),
                     "MISSING_CLOSEOUT_MESSAGE":"1" if missing_message else "0"}
                return runtime("task-cli",*task_cli_adapter("codex",executable,model="gpt-6-luna",
                    effort="none",approval_mode=mode),
                    "--work-dir",root,"--prompt-file",prompt,"--output-file",output,
                    "--result-file",result_path,"--timeout","10","--target","output.txt",
                    "--task-id","TASK-CLOSE","--title","[CODE: FIX] change output",
                    "--base",base,"--step-budget","2",env=env)

            completed=invoke()
            self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr+(Path(directory)/"kind.log").read_text())
            self.assertEqual(git("log","-1","--pretty=%s"),"fix: complete TASK-CLOSE")
            self.assertEqual(git("show","HEAD:output.txt"),"after")
            self.assertEqual(git("status","--porcelain"),"")
            def reset_task_state():
                git("reset","--hard",base)
                (root/".worker-ghost-state.json").unlink(missing_ok=True)
                shutil.rmtree(root/".worker-ghosts",ignore_errors=True)
            for mode in ("auto","approve-for-me","prompt","default","","bypass"):
                with self.subTest(mode=mode):
                    reset_task_state()
                    completed=invoke(mode=mode)
                    self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr+(Path(directory)/"kind.log").read_text())
                    self.assertEqual(git("show","HEAD:output.txt"),"after")
                    self.assertEqual(git("status","--porcelain"),"")
            reset_task_state()
            (Path(directory)/"kind.log").write_text("")
            rejected = invoke(missing_message=True)
            self.assertEqual(rejected.returncode, 126)
            self.assertEqual(git("rev-parse", "HEAD"), base)
            self.assertEqual((Path(directory)/"kind.log").read_text().splitlines(), ["main", "closeout"])
            rejected_again = invoke(missing_message=True)
            self.assertEqual(rejected_again.returncode, 126)
            self.assertEqual((Path(directory)/"kind.log").read_text().splitlines(), ["main", "closeout", "main"])
            for outcome in ("blocked","scope_blocked","guidance","failure"):
                with self.subTest(outcome=outcome):
                    reset_task_state()
                    completed=invoke("closeout_required",outcome)
                    self.assertNotEqual(completed.returncode,0,completed.stdout+completed.stderr+(Path(directory)/"kind.log").read_text())
                    self.assertEqual(json.loads(result_path.read_text())["outcome"], outcome)
                    self.assertEqual(git("rev-parse","HEAD"),base,
                                     "an incomplete ghost must never commit")

    def test_status_is_valid_json_for_quoted_task_and_path(self):
        with tempfile.TemporaryDirectory() as directory:
            status = Path(directory) / "worker.status"
            task = 'TASK-1 | GOAL: write "a\\b"\nthen test'
            result = runtime(
                "status-write", status, "default", "mac", "macOS",
                Path(directory) / 'folder "quoted"', "RUNNING", task,
                "3", "1", "2", "1", "50%", "[###---]", "42",
                "gpt-6-luna", "codex", "1800",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(status.read_text())
            self.assertEqual(data["current_task"], task)
            self.assertEqual(data["work_dir"], str(Path(directory) / 'folder "quoted"'))
            self.assertNotIn("isolation", data)
            self.assertEqual(data["model"], "gpt-6-luna")
            self.assertEqual(data["progress"]["remaining"], 1)
            display = runtime("status-display", status)
            self.assertEqual(display.returncode, 0, display.stderr)
            self.assertIn(task, display.stdout)
            self.assertIn("Worker Score   : 5/5", display.stdout)

    def test_progress_prepend_keeps_new_record_before_existing_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "progress.log"
            path.write_text("older result\n")
            result = runtime("progress-prepend", "--path", path,
                             "--entry", "new result\nsecond detail")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(path.read_text(), "new result\nsecond detail\nolder result\n")


class CliContractTests(unittest.TestCase):
    def test_external_adapter_commit_uses_structured_message_after_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "worker@example.invalid"], check=True)
            (repo / "output.txt").write_text("before\n")
            subprocess.run(["git", "-C", str(repo), "add", "output.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "baseline"], check=True)
            adapter = root / "adapter.py"
            adapter.write_text(
                "import json, pathlib, sys\nrequest=json.load(sys.stdin); op=sys.argv[1]\n"
                "if op == 'get_config': response={'protocol_version':1,'initial_score':5,'limits':{'poll_interval_seconds':0.01}}\n"
                "elif op == 'start':\n"
                " pathlib.Path(request['working_directory'],'output.txt').write_text('after\\n')\n"
                " pathlib.Path(request['result_path']).write_text(json.dumps({'outcome':'complete','changed':True,'commit_message':'fix(parser): honor exact structured message'}))\n"
                " p=pathlib.Path(request['output_dir']); (p/'status.json').write_text(json.dumps({'status':'complete','result_location':request['result_path']}))\n"
                " response={'execution_id':'commit-1','status_location':str(p/'status.json')}\n"
                "else: response=json.loads(pathlib.Path(request['status_location']).read_text())\n"
                "print(json.dumps(response))\n"
            )
            result = runtime(
                "task-cli", "--adapter", "unknown-adapter", "--executable", sys.executable,
                "--extra-arg", adapter, "--work-dir", repo, "--prompt-file", root / "prompt.txt",
                "--output-file", root / "adapter.log", "--result-file", root / "result.json",
                "--task-id", "TASK-COMMIT", "--target", "output.txt", "--base", "HEAD",
                "--verify", "python3 -c 'print(\"verified\")'",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            subject = subprocess.run(["git", "-C", str(repo), "log", "-1", "--format=%s"],
                                     check=True, capture_output=True, text=True).stdout.strip()
            self.assertEqual(subject, "fix(parser): honor exact structured message")

    def test_prompt_is_provider_invariant_and_requires_structured_script_owned_closeout(self):
        prompt = build_task_prompt("task", "TASK-9", "2", "src/a.py", "python -m unittest",
                                   "", "", 15, 1, 10, 5, "progress.log")
        self.assertNotRegex(prompt, r"(?i)codex|agy|generic adapter|selected adapter policy")
        self.assertIn("commit_message", prompt)
        self.assertIn("Do not stage or commit", prompt)

    def test_structured_no_change_finishes_without_a_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "worker@example.invalid"], check=True)
            (repo / "baseline.txt").write_text("baseline\n")
            subprocess.run(["git", "-C", str(repo), "add", "baseline.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "baseline"], check=True)
            base = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                                  check=True, capture_output=True, text=True).stdout.strip()
            adapter = root / "adapter.py"
            adapter.write_text(
                "import json, pathlib, sys\nrequest=json.load(sys.stdin); op=sys.argv[1]\n"
                "if op == 'get_config': response={'protocol_version':1,'initial_score':5}\n"
                "elif op == 'start':\n"
                " pathlib.Path(request['result_path']).write_text(json.dumps({'outcome':'no_change','changed':False,'no_change_reason':'The requested state already holds.'}))\n"
                " p=pathlib.Path(request['output_dir']); (p/'status.json').write_text(json.dumps({'status':'complete','result_location':request['result_path']}))\n"
                " response={'execution_id':'no-change-1','status_location':str(p/'status.json')}\n"
                "else: response=json.loads(pathlib.Path(request['status_location']).read_text())\n"
                "print(json.dumps(response))\n"
            )
            result = runtime("task-cli", "--adapter", "new-adapter", "--executable", sys.executable,
                             "--extra-arg", adapter, "--work-dir", repo, "--prompt-file", root / "prompt",
                             "--output-file", root / "adapter.log", "--result-file", root / "result.json",
                             "--task-id", "TASK-NO-CHANGE", "--base", base)
            self.assertEqual(result.returncode, 0, result.stderr)
            current = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"],
                                     check=True, capture_output=True, text=True).stdout.strip()
            self.assertEqual(current, base)

    def test_task_cli_executes_an_unrecognized_adapter_with_protocol(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "worker@example.invalid"], check=True)
            (repo / "baseline.txt").write_text("baseline\n")
            subprocess.run(["git", "-C", str(repo), "add", "baseline.txt"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "baseline"], check=True)
            adapter = root / "adapter.py"
            adapter.write_text(
                "import json, pathlib, sys\nrequest=json.load(sys.stdin); op=sys.argv[1]\n"
                "if op == 'get_config': response={'protocol_version':1,'initial_score':5,'configuration':{'normalized':True},'limits':{'poll_interval_seconds':0.01}}\n"
                "elif op == 'start':\n"
                " p=pathlib.Path(request['output_dir']); p.mkdir(parents=True,exist_ok=True)\n"
                " (p/'result.json').write_text(json.dumps({'outcome':'complete','commit_message':'adapter result'}))\n"
                " (p/'status.json').write_text(json.dumps({'status':'complete','result_location':str(p/'result.json')}))\n"
                " response={'execution_id':'run-1','status_location':str(p/'status.json')}\n"
                "else: response=json.loads(pathlib.Path(request['status_location']).read_text())\n"
                "print(json.dumps(response))\n"
            )
            prompt, output, result_file = root / "prompt", root / "output.log", root / "result.json"
            prompt.write_text("same shared task prompt")
            result = runtime(
                "task-cli", "--adapter", "unlisted-adapter", "--executable", sys.executable,
                "--extra-arg", adapter, "--work-dir", repo, "--prompt-file", prompt,
                "--output-file", output, "--result-file", result_file,
                "--task-id", "TASK-UNKNOWN", "--worker-port", "4100", "--base", "HEAD",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result_file.read_text())["commit_message"], "adapter result")
            self.assertIn('"status": "complete"', output.read_text())

    def test_task_cli_streams_output_selects_last_message_and_commits_only_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "CLI Test")
            git("config", "user.email", "cli@example.invalid")
            (root / "output.txt").write_text("before\n")
            (root / ".gitignore").write_text("cli.log\ncodex\nmessage.txt\nprompt.txt\n")
            git("add", "output.txt", ".gitignore")
            git("commit", "-qm", "baseline")
            base = git("rev-parse", "HEAD")
            prompt = root / "prompt.txt"
            prompt.write_text("perform the task")
            output, last_message = Path(directory) / "cli.log", Path(directory) / "message.txt"
            executable = root / "codex"
            executable.write_text(
                "#!/bin/sh\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = --output-last-message ]; then shift; printf '%s' '{\"outcome\":\"complete\",\"changed\":true,\"commit_message\":\"fix: update output\"}' > \"$1\"; fi\n"
                "  shift\n"
                "done\n"
                "printf 'finished\\n'\n"
                "printf 'after\\n' > output.txt\n"
            )
            executable.chmod(0o755)

            result = runtime(
                "task-cli", *task_cli_adapter("codex", executable, model="gpt-6-luna",
                    effort="none", approval_mode="auto"),
                "--work-dir", root, "--prompt-file", prompt, "--output-file", output,
                "--result-file", last_message, "--timeout", "15", "--target", "output.txt",
                "--task-id", "TASK-1", "--title", "[CODE: FIX] update output",
                "--base", base,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(output.read_text())["status"], "complete")
            artifacts=Path(directory)
            self.assertTrue(any("finished" in path.read_text()
                                for path in artifacts.rglob("codex.jsonl")),
                            str([(path, path.read_text(errors="replace"))
                                 for path in artifacts.rglob("codex.jsonl")]))
            self.assertEqual(json.loads(last_message.read_text())["commit_message"], "fix: update output")
            self.assertEqual(git("show", "HEAD:output.txt"), "after")
            self.assertEqual(git("status", "--porcelain"), "")

    def test_agy_task_cli_uses_one_restricted_closeout_for_dirty_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "agy Test")
            git("config", "user.email", "agy@example.invalid")
            (root / "output.txt").write_text("before\n")
            git("add", "output.txt")
            git("commit", "-qm", "baseline")
            base = git("rev-parse", "HEAD")
            prompt = Path(directory) / "prompt.txt"
            prompt.write_text("perform the task")
            output, calls = Path(directory) / "cli.log", Path(directory) / "calls.log"
            executable = root / "agy"
            executable.write_text(
                "#!/bin/sh\n"
                "if [ \"${1:-}\" = --help ]; then echo --max-turns; exit 0; fi\n"
                "printf '%s %s\\n' \"$MAX_STEPS\" \"$*\" >> \"$CALLS_LOG\"\n"
                "printf '[EXEC] step\\n'\n"
                "printf 'after\\n' > output.txt\n"
                "case \"$*\" in *'for original task TASK-2'*) printf '%s\\n' '{\"outcome\":\"complete\",\"changed\":false,\"commit_message\":\"fix: complete TASK-2\"}' ;; *) printf '%s\\n' '{\"outcome\":\"closeout_required\",\"changed\":true}' ;; esac\n"
            )
            executable.chmod(0o755)
            env = os.environ.copy()
            env["CALLS_LOG"] = str(calls)

            result = runtime(
                "task-cli", *task_cli_adapter("agy", executable, model="gemini-3.8-flash-low",
                    effort="low", mode="accept-edits"),
                "--work-dir", root, "--prompt-file", prompt, "--output-file", output,
                "--timeout", "15", "--step-budget", "2", "--task-id", "TASK-2",
                "--base", base, env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            call_lines = [line for line in calls.read_text().splitlines()
                          if line.startswith(("2 -p", "25 -p"))]
            self.assertEqual(len(call_lines), 2)
            self.assertTrue(call_lines[0].startswith("2 "))
            self.assertTrue(call_lines[1].startswith("25 "))
            self.assertIn("for original task TASK-2", calls.read_text())
            self.assertIn("Never modify, create, or delete source", calls.read_text())
            self.assertEqual(json.loads(output.read_text())["status"], "complete")

    def test_task_cli_converts_provider_print_timeout_to_timeout_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt, output = root / "prompt", root / "output"
            prompt.write_text("task")
            executable = root / "fake-cli"
            executable.write_text("#!/bin/sh\necho 'print timeout after 90s'\n")
            executable.chmod(0o755)
            result = runtime("task-cli", *task_cli_adapter("generic", executable),
                             "--work-dir", root, "--prompt-file", prompt,
                             "--output-file", output, "--timeout", "10")
            self.assertEqual(result.returncode, 124)

    def test_task_cli_stream_timeout_stops_provider_and_preserves_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            prompt, output = Path(directory) / "prompt", Path(directory) / "output"
            prompt.write_text("task")
            executable = root / "fake-cli"
            executable.write_text("#!/bin/sh\necho started\nsleep 10\n")
            executable.chmod(0o755)
            result = runtime("task-cli", *task_cli_adapter("generic", executable),
                             "--work-dir", root, "--prompt-file", prompt,
                             "--output-file", output, "--timeout", "0.5")
            self.assertEqual(result.returncode, 124)
            self.assertEqual(json.loads(output.read_text())["status"], "execution_timeout")
            logs = list(Path(directory).rglob("wrapper.log"))
            self.assertEqual(len(logs), 1)
            self.assertIn("started", logs[0].read_text())


class TimeoutContractTests(unittest.TestCase):
    def test_run_timeout_preserves_exit_code_and_streamed_output(self):
        result = runtime("run-timeout", "5", "--", sys.executable, "-c",
                         "import sys; print('started', flush=True); sys.exit(7)")
        self.assertEqual(result.returncode, 7)
        self.assertIn("started", result.stdout)

    def test_run_timeout_returns_124_and_terminates_child(self):
        result = runtime("run-timeout", "0.1", "--", sys.executable, "-c",
                         "import time; print('started', flush=True); time.sleep(10)")
        self.assertEqual(result.returncode, 124)
        self.assertIn("started", result.stdout)


class GitAuditContractTests(unittest.TestCase):
    def audit_case(self, files, *, target="src/a.py", title="[CODE: EXPAND]", level="1", constraints="", untracked=None, baseline_source="first\nsecond\n"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args],
                                      check=True, capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "Audit Test")
            git("config", "user.email", "audit@example.invalid")
            (root / "src").mkdir()
            (root / "src/a.py").write_text(baseline_source)
            (root / "tests").mkdir()
            (root / "tests/test_a.py").write_text("assert True\n")
            git("add", ".")
            git("commit", "-qm", "baseline")
            base = git("rev-parse", "HEAD")
            for path, content in files.items():
                destination = root / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(content)
            git("add", ".")
            git("commit", "-qm", "change")
            if untracked:
                (root / untracked).write_text("ghost\n")
            return runtime("git-audit", "--work-dir", root, "--base", base,
                           "--target", target, "--constraints", constraints,
                           "--title", title, "--level", level)

    def test_accepts_declared_target(self):
        self.assertEqual(self.audit_case({"src/a.py": "updated\n"}).returncode, 0)

    def test_rejects_file_outside_target(self):
        result = self.audit_case({"src/other.py": "new\n"})
        self.assertEqual(result.returncode, 2)
        self.assertIn("Target Whitelist", result.stdout)

    def test_diagnostic_cannot_commit_product_code(self):
        result = self.audit_case({"src/a.py": "updated\n"}, title="[DIAGNOSTIC]")
        self.assertEqual(result.returncode, 4)

    def test_fix_cannot_modify_tests(self):
        result = self.audit_case({"tests/test_a.py": "assert False\n"},
                                 target="tests/test_a.py", title="[CODE: FIX]")
        self.assertEqual(result.returncode, 5)

    def test_rejects_decreased_assertions(self):
        result = self.audit_case({"tests/test_a.py": "pass\n"},
                                 target="tests/test_a.py", title="[CODE: REFACTOR]")
        self.assertEqual(result.returncode, 7)

    def test_rejects_untracked_file(self):
        result = self.audit_case({"src/a.py": "updated\n"}, untracked="ghost.txt")
        self.assertEqual(result.returncode, 1)

    def test_rejects_micro_task_large_deletion(self):
        result = self.audit_case({"src/a.py": "kept\n"}, level="3",
                                 baseline_source="".join(f"line {i}\n" for i in range(50)))
        self.assertEqual(result.returncode, 8)


class MechanicalAuditContractTests(unittest.TestCase):
    def test_research_audit_adds_metadata_and_rejects_invalid_pointers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "Audit Test")
            git("config", "user.email", "audit@example.invalid")
            (root / ".gitignore").write_text(".reports/\n")
            (root / "src.py").write_text("one\ntwo\n")
            git("add", ".gitignore", "src.py")
            git("commit", "-qm", "baseline")
            base = git("rev-parse", "HEAD")
            report = root / ".reports" / "SUMMARY.md"
            report.parent.mkdir()
            report.write_text("# Findings\nInvalid location: src.py#L9\n")

            result = runtime("mechanical-audit", "--work-dir", root, "--base", base,
                             "--target", ".reports/SUMMARY.md", "--title", "[RESEARCH] inspect",
                             "--task-id", "TASK-R1", "--verify", "REPORT_ONLY")

            self.assertEqual(result.returncode, 0, result.stderr)
            audit = json.loads(result.stdout)
            self.assertEqual(audit["status"], 13)
            self.assertIn("Pointer Validity", audit["error"])
            self.assertIn("REPORT_META:", report.read_text().splitlines()[0])

    def test_research_audit_ignores_archived_reports_and_requires_current_task_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "Audit Test")
            git("config", "user.email", "audit@example.invalid")
            (root / ".gitignore").write_text(".reports/\n")
            (root / "source.py").write_text("one\n")
            git("add", ".gitignore", "source.py")
            git("commit", "-qm", "baseline")
            base = git("rev-parse", "HEAD")
            archived = root / ".reports/.archive/old/SUMMARY.md"
            archived.parent.mkdir(parents=True)
            archived.write_text("# Old report\n")

            result = runtime("mechanical-audit", "--work-dir", root, "--base", base,
                             "--target", ".reports/current/SUMMARY.md", "--title", "[RESEARCH] inspect",
                             "--task-id", "TASK-NEW", "--verify", "REPORT_ONLY")
            self.assertEqual(json.loads(result.stdout)["status"], 11)

            report = root / ".reports/current/SUMMARY.md"
            report.parent.mkdir()
            report.write_text("<!-- REPORT_META: Task=TASK-OLD | Commit=abc | Time=now -->\n# Old report\n")
            result = runtime("mechanical-audit", "--work-dir", root, "--base", base,
                             "--target", ".reports/current/SUMMARY.md", "--title", "[RESEARCH] inspect",
                             "--task-id", "TASK-NEW", "--verify", "REPORT_ONLY")
            audit = json.loads(result.stdout)
            self.assertEqual(audit["status"], 11)
            self.assertIn("Stale", audit["error"])

    def test_research_report_discovery_only_uses_declared_reports_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / ".reports/.archive/old/SUMMARY.md"
            old.parent.mkdir(parents=True)
            old.write_text("# Archived\n")
            tree = root / ".worker-tree"
            current = tree / ".reports/current/SUMMARY.md"
            current.parent.mkdir(parents=True)
            current.write_text("# Current\n")

            self.assertEqual(first_report(tree, ".reports/current/SUMMARY.md"), current.resolve())
            self.assertIsNone(first_report(tree, "docs/research/"))
            publish_research_reports(root, tree, ".reports/current/SUMMARY.md")
            self.assertEqual((root / ".reports/current/SUMMARY.md").read_text(), "# Current\n")

    def test_code_verification_timeout_is_a_guard_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "Audit Test")
            git("config", "user.email", "audit@example.invalid")
            (root / "source.txt").write_text("baseline\n")
            git("add", "source.txt")
            git("commit", "-qm", "baseline")
            base = git("rev-parse", "HEAD")

            result = runtime("mechanical-audit", "--work-dir", root, "--base", base,
                             "--target", "source.txt", "--title", "[CODE: FIX] verify",
                             "--task-id", "TASK-C1", "--verify", "sleep 10",
                             "--verify-timeout", "0.1")

            self.assertEqual(result.returncode, 0, result.stderr)
            audit = json.loads(result.stdout)
            self.assertEqual(audit["status"], 6)
            self.assertEqual(audit["verify_exit"], 124)


class ReportArchiveContractTests(unittest.TestCase):
    def test_research_archive_moves_active_reports_but_keeps_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / ".reports"
            (reports / "one").mkdir(parents=True)
            (reports / ".archive").mkdir()
            (reports / "one" / "SUMMARY.md").write_text("research")
            (reports / ".archive" / "old").write_text("old")

            result = runtime("archive-reports", "--root", root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((reports / "one").exists())
            self.assertEqual(len(list((reports / ".archive").iterdir())), 2)

    def test_changed_report_reference_is_archived_without_moving_unrelated_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "Archive Test")
            git("config", "user.email", "archive@example.invalid")
            (root / "src").mkdir()
            (root / "src/a.py").write_text("before\n")
            (root / "src/b.py").write_text("unchanged\n")
            git("add", "src/a.py", "src/b.py")
            git("commit", "-qm", "baseline")
            base = git("rev-parse", "HEAD")
            (root / "src/a.py").write_text("after\n")
            git("commit", "-qam", "change")
            reports = root / ".reports"
            (reports / "related").mkdir(parents=True)
            (reports / "unrelated").mkdir()
            (reports / "related" / "SUMMARY.md").write_text(
                f"<!-- REPORT_META: Task=R1 | Commit={base} -->\nFindings in src/a.py#L1\n")
            (reports / "unrelated" / "SUMMARY.md").write_text(
                f"<!-- REPORT_META: Task=R2 | Commit={base} -->\nFindings in src/b.py#L1\n")

            result = runtime("archive-overlapping-reports", "--root", root,
                             "--work-dir", root, "--base", base)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((reports / "related").exists())
            self.assertTrue((reports / "unrelated").exists())


class RollbackContractTests(unittest.TestCase):
    def test_attempt_recovery_restores_head_index_dirty_and_untracked_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("init", "-q")
            git("config", "user.name", "Recovery Test")
            git("config", "user.email", "recovery@example.invalid")
            (root / "tracked.txt").write_text("committed\n")
            git("add", "tracked.txt")
            git("commit", "-qm", "baseline")
            baseline_head = git("rev-parse", "HEAD")
            snapshot = Path(directory) / "snapshot"
            archived = Path(directory) / "archived"
            captured = runtime("attempt-snapshot", "--work-dir", root, "--task-id", "TASK-R",
                               "--attempt-id", "attempt-A", "--snapshot", snapshot)
            self.assertEqual(captured.returncode, 0, captured.stderr)
            (root / "tracked.txt").write_text("failed attempt\n")
            (root / "attempt-commit.txt").write_text("committed by failed attempt\n")
            git("add", "tracked.txt", "attempt-commit.txt")
            git("commit", "-qm", "failed attempt commit")
            (root / "attempt-untracked.txt").write_text("failed attempt untracked\n")

            recovered = runtime("attempt-recover", "--work-dir", root, "--snapshot", snapshot,
                                "--archive", archived)

            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            self.assertEqual(git("rev-parse", "HEAD"), baseline_head)
            self.assertEqual((root / "tracked.txt").read_text(), "committed\n")
            self.assertFalse((root / "attempt-commit.txt").exists())
            self.assertFalse((root / "attempt-untracked.txt").exists())
            self.assertTrue((archived / "changes.diff").is_file())
            self.assertIn("failed attempt commit", (archived / "commits.txt").read_text())
            self.assertIn("failed attempt", (archived / "changes.diff").read_text())
            self.assertFalse((snapshot / "files").exists())
            self.assertFalse((archived / "failed-files").exists())

    def test_attempt_baseline_excludes_ignored_files_and_scratch_from_snapshot_and_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("init", "-q")
            git("config", "user.name", "Recovery Test")
            git("config", "user.email", "recovery@example.invalid")
            (root / ".gitignore").write_text(".scratch/\nbuild/\n*.log\n")
            (root / "tracked.txt").write_text("committed\n")
            git("add", ".gitignore", "tracked.txt")
            git("commit", "-qm", "baseline")

            (root / ".scratch/attempts/old").mkdir(parents=True)
            (root / ".scratch/attempts/old/data.json").write_text("{\"old\": 1}\n")
            (root / "build").mkdir()
            (root / "build/app.o").write_text("binary blob\n")
            (root / "debug.log").write_text("log line\n")

            snapshot = Path(directory) / "snapshot"
            archived = Path(directory) / "archived"
            captured = runtime("attempt-snapshot", "--work-dir", root, "--task-id", "TASK-R",
                               "--attempt-id", "attempt-A", "--snapshot", snapshot)
            self.assertEqual(captured.returncode, 0, captured.stderr)

            metadata = json.loads((snapshot / "snapshot.json").read_text())
            self.assertFalse((snapshot / "files").exists())

            (root / "tracked.txt").write_text("failed attempt edit\n")
            (root / "attempt-untracked.txt").write_text("failed attempt untracked\n")
            (root / "build/new.o").write_text("new binary\n")
            (root / ".scratch/failed_tasks/previous").mkdir(parents=True)
            (root / ".scratch/failed_tasks/previous/info.txt").write_text("fail\n")

            recovered = runtime("attempt-recover", "--work-dir", root, "--snapshot", snapshot,
                                "--archive", archived)
            self.assertEqual(recovered.returncode, 0, recovered.stderr)

            self.assertTrue((archived / "changes.diff").is_file())
            self.assertIn("failed attempt edit", (archived / "changes.diff").read_text())
            self.assertFalse((archived / "failed-files").exists())

            self.assertEqual((root / "tracked.txt").read_text(), "committed\n")
            self.assertFalse((root / "attempt-untracked.txt").exists())
            self.assertTrue((root / ".scratch/attempts/old/data.json").is_file())
            self.assertTrue((root / "build/app.o").is_file())

    def test_invalid_attempt_baseline_stops_recovery_without_resetting_workspace(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Recovery Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "recovery@example.invalid"], check=True)
            (root / "tracked.txt").write_text("baseline\n")
            subprocess.run(["git", "-C", str(root), "add", "tracked.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "baseline"], check=True)
            snapshot = Path(directory) / "snapshot"
            self.assertEqual(runtime("attempt-snapshot", "--work-dir", root, "--task-id", "TASK-R",
                                     "--attempt-id", "attempt-A", "--snapshot", snapshot).returncode, 0)
            metadata_path = snapshot / "snapshot.json"
            metadata = json.loads(metadata_path.read_text())
            metadata["head"] = "not-a-commit"
            metadata_path.write_text(json.dumps(metadata))
            (root / "tracked.txt").write_text("do not destroy\n")

            recovered = runtime("attempt-recover", "--work-dir", root, "--snapshot", snapshot,
                                "--archive", Path(directory) / "archive")

            self.assertNotEqual(recovered.returncode, 0)
            self.assertEqual((root / "tracked.txt").read_text(), "do not destroy\n")

    def test_failed_workspace_changes_are_saved_and_runtime_files_survive_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "Rollback Test")
            git("config", "user.email", "rollback@example.invalid")
            (root / "source.txt").write_text("baseline\n")
            (root / "tasks.txt").write_text("baseline queue\n")
            git("add", "source.txt", "tasks.txt")
            git("commit", "-qm", "baseline")
            (root / "source.txt").write_text("failed edit\n")
            (root / "tasks.txt").write_text("remaining task\n")
            (root / "new.txt").write_text("untracked work\n")

            result = runtime("rollback-failed-task", "--root", root,
                             "--work-dir", root, "--task-id", "TASK-9",
                             "--tasks", root / "tasks.txt")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / "source.txt").read_text(), "baseline\n")
            self.assertEqual((root / "tasks.txt").read_text(), "remaining task\n")
            self.assertFalse((root / "new.txt").exists())
            backup = Path(result.stdout.strip())
            self.assertIn("source.txt", (backup / "changes.diff").read_text())
            self.assertIn("new.txt", (backup / "status.txt").read_text())
            self.assertFalse((backup / "untracked").exists())


class WorkerIntegrationTests(unittest.TestCase):
    def test_worker_halts_before_backup_agent_when_baseline_restore_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            copy_runtime_fixture(root / "scripts/worker_runtime.py")
            profiles = [codex_registration("first", "codex", "first-model"),
                        codex_registration("second", "codex", "second-model")]
            (root / ".worker.env").write_text(
                "WORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0\n"
                "AI_AGENTS_JSON='" + json.dumps(profiles) + "'\n"
            )
            task = "TASK-RECOVER | LEVEL: 1 | TARGET: output.txt | ACTION: write | VERIFY: true\n"
            (root / "tasks.txt").write_text(task)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "worker@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "worker.sh", "scripts", ".gitignore", "tasks.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "codex"
            fake.write_text(
                "#!/bin/sh\nmodel=\nwhile [ \"$#\" -gt 0 ]; do\n"
                " if [ \"$1\" = --model ]; then shift; model=$1; fi\n"
                " if [ \"$1\" = --output-last-message ]; then shift; result=$1; fi\n"
                " shift\ndone\n"
                "printf '%s\\n' \"$model\" >> \"$AGENT_CALLS\"\n"
                "if [ \"$model\" = first-model ]; then touch .git/index.lock; echo '{\"type\":\"turn.failed\",\"error\":{\"message\":\"insufficient_quota\"}}'; exit 1; fi\n"
                "printf 'Attempts: 1 | Confidence: HIGH\\n' > \"$result\"\n"
            )
            fake.chmod(0o755)
            calls = Path(directory) / "calls.log"
            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                    env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                                         "AGENT_CALLS": str(calls)},
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(calls.read_text().splitlines(), ["first-model"])
            self.assertIn(task, (root / "tasks.txt").read_text())
            self.assertEqual(json.loads((root / "worker.status").read_text())["state"],
                             "RECOVERY_FAILED")

    def test_worker_rejects_zero_exit_when_final_response_says_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            copy_runtime_fixture(root / "scripts/worker_runtime.py")
            (root / ".worker.env").write_text(
                "WORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0\n"
            )
            task = "TASK-BLOCKED | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: FIX] Stop blocked | VERIFY: true\n"
            (root / "tasks.txt").write_text(task)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "worker@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "worker.sh", "scripts", ".gitignore", "tasks.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "codex"
            fake.write_text(
                "#!/bin/sh\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = --output-last-message ]; then shift; result=$1; fi\n"
                "  shift\n"
                "done\n"
                "printf '[BLOCKED] reports-not-writable\\n' > \"$result\"\n"
            )
            fake.chmod(0o755)
            (root / ".worker.env").write_text(
                "WORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0\nAI_AGENTS_JSON='" +
                json.dumps([codex_registration("test", fake)]) + "'\n")

            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                    env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
                                    capture_output=True, text=True, timeout=30)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("[WORKER_BLOCKED]", (root / "tasks.done").read_text())
            self.assertNotIn("[DONE]", (root / "tasks.done").read_text())
            self.assertNotIn("CLOSEOUT_FAILED", (root / "tasks.done").read_text())
            self.assertFalse((root / ".worker-ghost-state.json").exists())
            self.assertIn("[BLOCKED] reports-not-writable", (root / "progress.log").read_text())
            self.assertEqual(json.loads((root / "worker.status").read_text())["state"], "BLOCKED")

    def test_worker_reports_invalid_codex_result_without_calling_cli_exit_one(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            copy_runtime_fixture(root / "scripts/worker_runtime.py")
            (root / "tasks.txt").write_text(
                "TASK-BAD-JSON | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: FIX] Write output "
                "| VERIFY: test -f output.txt\n")
            fake = Path(directory) / "fake-codex"
            fake.write_text(
                "#!/usr/bin/env python3\nimport sys\nfrom pathlib import Path\n"
                "Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text('not JSON')\n")
            fake.chmod(0o755)
            write_legacy_registry(root, json.dumps([codex_registration("codex-main", fake)]))
            for args in (("init", "-q"), ("config", "user.name", "Worker Test"),
                         ("config", "user.email", "worker@example.invalid"),
                         ("add", "worker.sh", "scripts", ".gitignore", "tasks.txt"),
                         ("commit", "-qm", "fixture")):
                subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
            env = {**os.environ, "RUN_ONCE": "1", "POLL_INTERVAL": "0"}
            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            progress = (root / "progress.log").read_text()
            self.assertIn("CLI Exit Code: 0", progress)
            self.assertIn("Verification: not run", progress)
            self.assertIn("Result Error: invalid_result", progress)
            self.assertIn("Task Status: FAILED", progress)
            self.assertNotIn("Worker CLI returned non-zero exit status 1", progress)

    def test_worker_records_codex_attempts_from_json_result(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            copy_runtime_fixture(root / "scripts/worker_runtime.py")
            (root / "tasks.txt").write_text(
                "TASK-ATTEMPTS | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: EXPAND] Write output "
                "| VERIFY: test -f output.txt\n")
            fake = Path(directory) / "fake-codex"
            fake.write_text(
                "#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\n"
                "Path('output.txt').write_text('done\\n')\n"
                "Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(json.dumps("
                "{'outcome':'complete','changed':True,'commit_message':'test: finish task',"
                "'attempts':2,'confidence':'MED'}))\n")
            fake.chmod(0o755)
            write_legacy_registry(root, json.dumps([codex_registration("codex-main", fake)]))
            for args in (("init", "-q"), ("config", "user.name", "Worker Test"),
                         ("config", "user.email", "worker@example.invalid"),
                         ("add", "worker.sh", "scripts", ".gitignore", "tasks.txt"),
                         ("commit", "-qm", "fixture")):
                subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
            env = {**os.environ, "RUN_ONCE": "1", "POLL_INTERVAL": "0"}
            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("[DONE] TASK-ATTEMPTS", (root / "tasks.done").read_text())
            self.assertIn("Attempts: 2", (root / "progress.log").read_text())

    def test_in_place_research_task_keeps_its_new_report_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            copy_runtime_fixture(root / "scripts/worker_runtime.py")
            (root / ".worker.env").write_text(
                "WORKER_ISOLATION=1\nRUN_ONCE=1\nPOLL_INTERVAL=0\n"
            )
            (root / "tasks.txt").write_text(
                "TASK-REPORT | LEVEL: 1 | TARGET: .reports/fake/SUMMARY.md,.reports/fake/03-micro.md | "
                "ACTION: [RESEARCH] Produce fake report | VERIFY: REPORT_ONLY\n"
            )
            (root / ".reports/.archive/old").mkdir(parents=True)
            (root / ".reports/.archive/old/SUMMARY.md").write_text("# Archived\n")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "worker@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "worker.sh", "scripts", ".gitignore", "tasks.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "codex"
            fake.write_text(
                "#!/bin/sh\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = --output-last-message ]; then shift; result=$1; fi\n"
                "  shift\n"
                "done\n"
                "mkdir -p .reports/fake\n"
                "printf '# Fresh summary\\n\\nEvidence: scripts/worker_runtime.py#L1\\n' > .reports/fake/SUMMARY.md\n"
                "printf '# Fresh details\\n' > .reports/fake/03-micro.md\n"
                "printf '{\"outcome\":\"complete\",\"changed\":true,\"commit_message\":\"docs: add fake report\"}\\n' > \"$result\"\n"
            )
            fake.chmod(0o755)
            (root / ".worker.env").write_text(
                "WORKER_ISOLATION=1\nRUN_ONCE=1\nPOLL_INTERVAL=0\nAI_AGENTS_JSON='" +
                json.dumps([codex_registration("research", fake)]) + "'\n")

            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                    env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
                                    capture_output=True, text=True, timeout=45)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("[DONE] TASK-REPORT", (root / "tasks.done").read_text(), result.stdout)
            self.assertIn("[MECHANICAL_AUDIT] Status: PASS | Task: TASK-REPORT",
                          (root / "progress.log").read_text())
            summary = root / ".reports/fake/SUMMARY.md"
            self.assertIn("Task=TASK-REPORT", summary.read_text().splitlines()[0])
            self.assertEqual((root / ".reports/fake/03-micro.md").read_text(), "# Fresh details\n")
            self.assertFalse((root / ".worker-tree").exists())
            self.assertTrue(list((root / ".reports/.archive").iterdir()))

    def test_worker_rechecks_quota_agent_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            copy_runtime_fixture(root / "scripts/worker_runtime.py")
            profiles = [codex_registration("primary", "codex", "gpt-6-luna"),
                        codex_registration("backup", "codex", "gpt-6.1-sol")]
            (root / ".worker.env").write_text(
                "WORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0\n"
                "AI_AGENTS_JSON='" + json.dumps(profiles) + "'\n"
            )
            (root / "tasks.txt").write_text(
                "TASK-Q | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: EXPAND] "
                "Write output | VERIFY: test -f output.txt\n"
            )
            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "codex"
            fake.write_text(
                "#!/bin/sh\n"
                "model=\nwhile [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = --model ]; then shift; model=$1; fi\n"
                "  if [ \"$1\" = --output-last-message ]; then shift; result=$1; fi\n"
                "  shift\ndone\n"
                "printf '%s\\n' \"$model\" >> \"$AGENT_CALLS\"\n"
                "if [ \"$model\" = gpt-6-luna ]; then echo '{\"type\":\"turn.failed\",\"error\":{\"message\":\"insufficient_quota\"}}'; exit 1; fi\n"
                "printf '{\"outcome\":\"complete\",\"changed\":true,\"commit_message\":\"feat: complete TASK-Q\"}\\n' > \"$result\"\n"
                "printf 'hello\\n' > output.txt\n"
            )
            fake.chmod(0o755)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "worker@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "worker.sh", "scripts", ".gitignore", "tasks.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            calls = Path(directory) / "agent-calls.log"
            env = os.environ.copy()
            env.update(PATH=f"{bin_dir}{os.pathsep}{env['PATH']}", AGENT_CALLS=str(calls))

            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=45)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(calls.read_text().splitlines(), ["gpt-6-luna"])
            self.assertEqual((root / "tasks.txt").read_text().count("TASK-Q"), 1)
            self.assertEqual((root / "tasks.done").read_text(), "")
            events = root / ".worker-agent-events.jsonl"
            self.assertTrue(events.is_file())
            event = json.loads(events.read_text().splitlines()[-1])
            self.assertEqual(event["cause"], "main_task_failover")
            self.assertEqual((event["previous_registration_id"],
                              event["current_registration_id"]), ("primary", "backup"))
            gate = root / ".worker-dispatch-gate.json"
            self.assertTrue(gate.exists())

            watch = runtime("agent-events-watch", "--events", events,
                            "--cursor", root / ".worker-agent-events.cursor.json",
                            "--acknowledgements", root / ".worker-agent-events.acks.jsonl",
                            "--gate", gate, "--handoff", root / "progress.log")
            self.assertEqual(watch.returncode, 0, watch.stderr)
            self.assertIn("[PLANNER_REVIEW_REQUIRED]", (root / "progress.log").read_text())
            ack = runtime("agent-event-ack", "--events", events,
                          "--acknowledgements", root / ".worker-agent-events.acks.jsonl",
                          "--event-id", event["event_id"], "--resolution", "revised")
            self.assertEqual(ack.returncode, 0, ack.stderr)
            release = runtime("agent-events-watch", "--events", events,
                              "--cursor", root / ".worker-agent-events.cursor.json",
                              "--acknowledgements", root / ".worker-agent-events.acks.jsonl",
                              "--gate", gate, "--handoff", root / "progress.log")
            self.assertEqual(release.returncode, 0, release.stderr)
            self.assertFalse(gate.exists())

            resumed = subprocess.run(["bash", str(root / "worker.sh")], cwd=root, env=env,
                                      capture_output=True, text=True, timeout=45)
            self.assertEqual(resumed.returncode, 0, resumed.stdout + resumed.stderr)
            latest_event = json.loads(events.read_text().splitlines()[-1])
            self.assertEqual(latest_event["previous_registration_id"], "primary")
            self.assertEqual(calls.read_text().splitlines(), ["gpt-6-luna", "gpt-6-luna"])
            watch = runtime("agent-events-watch", "--events", events,
                            "--cursor", root / ".worker-agent-events.cursor.json",
                            "--acknowledgements", root / ".worker-agent-events.acks.jsonl",
                            "--gate", gate, "--handoff", root / "progress.log")
            self.assertEqual(watch.returncode, 0, watch.stderr)
            ack = runtime("agent-event-ack", "--events", events,
                          "--acknowledgements", root / ".worker-agent-events.acks.jsonl",
                          "--event-id", latest_event["event_id"], "--resolution", "revised")
            self.assertEqual(ack.returncode, 0, ack.stderr)
            release = runtime("agent-events-watch", "--events", events,
                              "--cursor", root / ".worker-agent-events.cursor.json",
                              "--acknowledgements", root / ".worker-agent-events.acks.jsonl",
                              "--gate", gate, "--handoff", root / "progress.log")
            self.assertEqual(release.returncode, 0, release.stderr)
            self.assertEqual([line for line in calls.read_text().splitlines() if line],
                             ["gpt-6-luna", "gpt-6-luna"])
            self.assertFalse((root / "tasks.done").read_text())
            state = json.loads((root / ".worker-agent-state.default.json").read_text())
            self.assertEqual(state["exhausted"]["primary"]["reason"], "quota")

    def test_generic_registry_receives_model_arguments_environment_and_result_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            (root / "scripts").mkdir(parents=True)
            shutil.copy2(ROOT / "worker.sh", root / "worker.sh")
            copy_runtime_fixture(root / "scripts/worker_runtime.py")
            shutil.copy2(ROOT / ".gitignore", root / ".gitignore")
            wrapper = Path(directory) / "API wrapper.py"
            wrapper.write_text(
                "import os, sys, json\nfrom pathlib import Path\n"
                "assert sys.argv[1] == '--api-mode'\n"
                "assert os.environ['NIGHTSHIFT_MODEL'] == 'vendor/model-x'\n"
                "assert os.environ['NIGHTSHIFT_EFFORT'] == 'medium'\n"
                "assert os.environ['API_BASE_URL'] == 'https://api.invalid/v2'\n"
                "assert Path(os.environ['NIGHTSHIFT_PROMPT_FILE']).read_text() == sys.argv[-1]\n"
                "assert os.environ['NIGHTSHIFT_TASK_ID'] == 'TASK-API'\n"
                "Path('output.txt').write_text('api adapter worked\\n')\n"
                "Path(os.environ['NIGHTSHIFT_RESULT_FILE']).write_text(json.dumps({'outcome':'complete',"
                "'changed':True,'commit_message':'feat: add wrapper output'}))\n"
                "print('[BLOCKED] quoted tool output; not the final result')\n"
            )
            profiles = [generic_registration("api", sys.executable,
                         [str(wrapper), "--api-mode"], {"API_BASE_URL": "https://api.invalid/v2"},
                         model="vendor/model-x", effort="medium")]
            (root / ".worker.env").write_text(
                "WORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0\nAI_AGENTS_JSON='" + json.dumps(profiles) + "'\n")
            (root / "tasks.txt").write_text(
                "TASK-API | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: EXPAND] "
                "Write artifact | VERIFY: test -f output.txt\n")
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("init", "-q")
            git("config", "user.name", "API Test")
            git("config", "user.email", "api@example.invalid")
            git("add", "worker.sh", "scripts", ".gitignore", "tasks.txt")
            git("commit", "-qm", "fixture")
            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                    capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("[DONE] TASK-API", (root / "tasks.done").read_text(),
                          result.stdout + (root / ".worker.log").read_text())
            self.assertEqual(git("show", "HEAD:output.txt"), "api adapter worked")

    def test_worker_holds_replacement_until_planner_resolves_failover(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            copy_runtime_fixture(root / "scripts/worker_runtime.py")
            task = ("TASK-Q | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: EXPAND] "
                    "Write output | VERIFY: test -f output.txt\n")
            profiles = [codex_registration("one"), codex_registration("two")]
            (root / ".worker.env").write_text(
                "WORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0\n"
                "AI_AGENTS_JSON='" + json.dumps(profiles) + "'\n"
            )
            (root / "tasks.txt").write_text(task)
            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "codex"
            fake.write_text("#!/bin/sh\necho '{\"type\":\"turn.failed\",\"error\":{\"message\":\"rate limit exceeded\"}}'; exit 1\n")
            fake.chmod(0o755)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "worker@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "worker.sh", "scripts", ".gitignore", "tasks.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                    env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
                                    capture_output=True, text=True, timeout=45)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((root / "tasks.txt").read_text(), task)
            self.assertEqual((root / "tasks.done").read_text(), "")
            self.assertIn("PLANNER_REVIEW_REQUIRED", result.stdout)
            self.assertEqual(json.loads((root / "worker.status").read_text())["state"], "PAUSED_FOR_PLANNER")
            state = json.loads((root / ".worker-agent-state.default.json").read_text())
            self.assertEqual(set(state["exhausted"]), {"one"})
            self.assertEqual((root / ".worker-dispatch-gate.json").is_file(), True)

    def test_worker_does_not_switch_agents_for_non_quota_cli_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            copy_runtime_fixture(root / "scripts/worker_runtime.py")
            wrapper = Path(directory) / "wrapper.py"
            wrapper.write_text(
                "import json, os\n"
                "with open(os.environ['AGENT_CALLS'], 'a') as calls: calls.write('called\\n')\n"
                "print('rate limit mentioned in unrelated diagnostic context')\n"
                "json.dump({'outcome': 'failure', 'diagnostic': 'ordinary failure; rate limit text is incidental'}, "
                "open(os.environ['NIGHTSHIFT_RESULT_FILE'], 'w'))\n"
                "raise SystemExit(1)\n"
            )
            profiles = [generic_registration("primary", sys.executable, [str(wrapper)]),
                        generic_registration("backup", sys.executable, [str(wrapper)])]
            (root / ".worker.env").write_text(
                "WORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0\n"
                "AI_AGENTS_JSON='" + json.dumps(profiles) + "'\n"
            )
            (root / "tasks.txt").write_text("TASK-E | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: EXPAND] Fail | VERIFY: true\n")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "worker@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "worker.sh", "scripts", ".gitignore", "tasks.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            calls = Path(directory) / "calls.log"
            env = {**os.environ, "AGENT_CALLS": str(calls)}

            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=45)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(calls.read_text().splitlines(), ["called"])
            self.assertFalse((root / ".worker-agent-state.default.json").exists())

    def test_trial_artifact_is_delivered_before_the_next_normal_task_continues(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            copy_runtime_fixture(root / "scripts/worker_runtime.py")
            trial_dir = ".trials/TRIAL-1"
            trial_task = (
                f"TRIAL-1 | LEVEL: 1 | TARGET: {trial_dir} | ACTION: build and deliver trial | "
                f"VERIFY: test -x {trial_dir}/bin/app\n"
            )
            next_task = (
                f"TASK-NEXT | LEVEL: 1 | TARGET: {trial_dir}/manifest.json | "
                f"ACTION: verify trial delivery and continue | VERIFY: test -x {trial_dir}/bin/app\n"
            )
            (root / "tasks.txt").write_text(trial_task + next_task)
            calls = Path(directory) / "calls"
            fake = Path(directory) / "codex"
            fake.write_text(
                "#!/bin/sh\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = --output-last-message ]; then result=$2; shift; fi\n"
                "  shift\n"
                "done\n"
                f"count=0; [ -f {str(calls)!r} ] && count=$(cat {str(calls)!r}); count=$((count + 1)); echo $count > {str(calls)!r}\n"
                "if [ \"$count\" = 1 ]; then\n"
                f"  mkdir -p {trial_dir}/bin\n"
                f"  printf '#!/bin/sh\\necho runnable\\n' > {trial_dir}/bin/app; chmod +x {trial_dir}/bin/app\n"
                f"  printf '{{\"task_id\":\"TRIAL-1\",\"source_revision\":\"fixture\",\"launch_command\":\"{trial_dir}/bin/app\"}}\\n' > {trial_dir}/manifest.json\n"
                "fi\n"
                "printf '{\"outcome\":\"no_change\",\"changed\":false,\"no_change_reason\":\"trial artifact only\"}\\n' > \"$result\"\n"
            )
            fake.chmod(0o755)
            (root / ".worker.env").write_text(
                "RUN_ONCE=1\nPOLL_INTERVAL=0\nTASK_TIMEOUT=30\n"
                "AI_AGENTS_JSON='" + json.dumps([codex_registration("trial", fake)]) + "'\n"
            )
            subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Trial Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "trial@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "worker.sh", "scripts", ".gitignore", "tasks.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)

            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                    env={**os.environ, "PATH": f"{fake.parent}{os.pathsep}{os.environ['PATH']}"},
                                    capture_output=True, text=True, timeout=45)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((root / f"{trial_dir}/bin/app").read_text(), "#!/bin/sh\necho runnable\n")
            manifest = json.loads((root / f"{trial_dir}/manifest.json").read_text())
            self.assertEqual(manifest["task_id"], "TRIAL-1")
            self.assertEqual(manifest["launch_command"], f"{trial_dir}/bin/app")
            self.assertIn("[DONE] TRIAL-1", (root / "tasks.done").read_text())
            self.assertIn("[DONE] TASK-NEXT", (root / "tasks.done").read_text())
            self.assertEqual((root / "tasks.txt").read_text(), "")
            self.assertFalse((root / "PAUSE").exists(), "trial delivery must not pause the Worker")
            self.assertEqual((root / ".git" / "HEAD").exists(), True)

    def test_status_dashboard_uses_project_paths_from_an_external_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            external = Path(directory)
            root = external / "repo"
            (root / "scripts").mkdir(parents=True)
            shutil.copy2(ROOT / "scripts/status.sh", root / "scripts/status.sh")
            (root / "scripts").mkdir(exist_ok=True)
            copy_runtime_fixture(root / "scripts/worker_runtime.py")
            (root / ".worker.env").write_text(
                "STATUS_FILE=state/worker.json\nTASKS_FILE=queue/tasks.txt\n"
                "TASKS_DONE_FILE=queue/tasks.done\nPROGRESS_FILE=queue/progress.log\n"
            )
            (root / "state").mkdir()
            (root / "queue").mkdir()
            (root / "state/worker.json").write_text(json.dumps({
                "state": "IDLE", "pid": -1, "elapsed_seconds": 0,
                "progress": {"bar": "[###]"}, "isolation": False,
            }))
            (root / "queue/tasks.txt").write_text("TASK-1\n")
            (root / "queue/tasks.done").write_text("[DONE] TASK-0\n[DONE] TASK-9\n")
            (root / "queue/progress.log").write_text("latest verified entry\n")
            (root / ".preview").mkdir()
            (root / ".preview/version.json").write_text(json.dumps({
                "task_id": "TASK-0", "commit": "abc123", "updated_at": "now",
            }))
            subprocess.run(["git", "init", "-q", str(root)], check=True)

            result = subprocess.run(["bash", str(root / "scripts/status.sh")], cwd=external,
                                    env={**os.environ, "STATUS_FILE": "state/worker.json",
                                         "TASKS_FILE": "queue/tasks.txt",
                                         "TASKS_DONE_FILE": "queue/tasks.done",
                                         "PROGRESS_FILE": "queue/progress.log"},
                                    capture_output=True, text=True, timeout=10)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Worker State   : IDLE", result.stdout)
            self.assertIn("Completed: 2 | Remaining in Queue: 1", result.stdout)
            self.assertNotIn("Preview Ready", result.stdout)
            self.assertNotIn("TASK-0 (abc123)", result.stdout)

    def test_sentinel_does_not_treat_historical_pass_as_new_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            external = Path(directory)
            root = external / "repo"
            (root / "scripts").mkdir(parents=True)
            shutil.copy2(ROOT / "scripts/watch_worker.sh", root / "scripts/watch_worker.sh")
            (root / ".worker.env").write_text(
                "TASKS_FILE=queue/tasks.txt\n"
                "TASKS_DONE_FILE=queue/tasks.done\n"
                "STATUS_FILE=queue/worker.json\nPROGRESS_FILE=queue/progress.log\n"
            )
            (root / "queue").mkdir()
            (root / "queue/tasks.txt").write_text("")
            (root / "queue/tasks.done").write_text("[DONE] TASK-0\n")
            (root / "queue/progress.log").write_text("[MECHANICAL_AUDIT] Status: PASS\n")
            (root / "queue/worker.json").write_text(json.dumps({"state": "STOPPED"}))

            result = subprocess.run(["bash", str(root / "scripts/watch_worker.sh"), "1", "0.01"],
                                    cwd=external, capture_output=True, text=True, timeout=5)

            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("[SENTINEL_TIMEOUT]", result.stdout)
            self.assertNotIn("[SENTINEL_COMPLETED]", result.stdout)

    def test_sentinel_requires_a_fresh_task_scoped_audit_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            (root / "scripts").mkdir(parents=True)
            (root / "queue").mkdir()
            shutil.copy2(ROOT / "scripts/watch_worker.sh", root / "scripts/watch_worker.sh")
            (root / "queue/tasks.txt").write_text("")
            (root / "queue/tasks.done").write_text("[DONE] TASK-OLD\n")
            (root / "queue/progress.log").write_text(
                "[MECHANICAL_AUDIT] Status: PASS | Task: TASK-OLD |\n"
            )
            (root / "queue/worker.json").write_text(json.dumps({"state": "STOPPED"}))
            completion = (
                "sleep 0.05; printf 'TASK-NEW | LEVEL: 1\\n' > queue/tasks.txt; "
                "sleep 0.10; : > queue/tasks.txt; "
                "printf '[2026-01-01] [DONE] TASK-NEW\\n' >> queue/tasks.done; "
                "printf '[MECHANICAL_AUDIT] Status: PASS | Task: TASK-NEW | Verify_Exit: 0\\n' >> queue/progress.log; "
                "printf '{\\\"state\\\":\\\"IDLE\\\"}\\n' > queue/worker.json"
            )
            completer = subprocess.Popen(["bash", "-c", completion], cwd=root,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            result = subprocess.run(
                ["bash", str(root / "scripts/watch_worker.sh"), "1", "0.01"],
                cwd=root, env={**os.environ, "TASKS_FILE": "queue/tasks.txt",
                               "TASKS_DONE_FILE": "queue/tasks.done",
                               "STATUS_FILE": "queue/worker.json",
                               "PROGRESS_FILE": "queue/progress.log"},
                capture_output=True, text=True, timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("TASK-NEW", result.stdout)
            self.assertIn("[SENTINEL_COMPLETED]", result.stdout)
            completer.wait(timeout=5)

    def test_sentinel_reports_fresh_task_failure_even_when_old_pass_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            (root / "scripts").mkdir(parents=True)
            (root / "queue").mkdir()
            shutil.copy2(ROOT / "scripts/watch_worker.sh", root / "scripts/watch_worker.sh")
            (root / "queue/tasks.txt").write_text("")
            (root / "queue/tasks.done").write_text("[DONE] TASK-RETRY\n")
            (root / "queue/progress.log").write_text(
                "[MECHANICAL_AUDIT] Status: PASS | Task: TASK-RETRY | Verify_Exit: 0 | Attempts: 1\n"
            )
            (root / "queue/worker.json").write_text(json.dumps({"state": "STOPPED"}))
            completion = (
                "sleep 0.05; printf '[2026-01-01] [FAILED] TASK-RETRY [EXIT_1]\\n' >> queue/tasks.done"
            )
            completer = subprocess.Popen(["bash", "-c", completion], cwd=root,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            result = subprocess.run(
                ["bash", str(root / "scripts/watch_worker.sh"), "1", "0.01", "TASK-RETRY"],
                cwd=root, env={**os.environ, "TASKS_FILE": "queue/tasks.txt",
                               "TASKS_DONE_FILE": "queue/tasks.done",
                               "STATUS_FILE": "queue/worker.json",
                               "PROGRESS_FILE": "queue/progress.log"},
                capture_output=True, text=True, timeout=10,
            )

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("[SENTINEL_FAILED] Task TASK-RETRY", result.stdout)
            completer.wait(timeout=5)

    def test_sentinel_rejects_old_same_task_audit_for_a_new_done_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            (root / "scripts").mkdir(parents=True)
            (root / "queue").mkdir()
            shutil.copy2(ROOT / "scripts/watch_worker.sh", root / "scripts/watch_worker.sh")
            (root / "queue/tasks.txt").write_text("TASK-RETRY | LEVEL: 1\n")
            (root / "queue/tasks.done").write_text("[FAILED] TASK-RETRY [EXIT_1]\n")
            (root / "queue/progress.log").write_text(
                "[MECHANICAL_AUDIT] Status: PASS | Task: TASK-RETRY | Verify_Exit: 0 | Attempts: 1\n"
            )
            (root / "queue/worker.json").write_text(json.dumps({"state": "IDLE"}))
            completion = (
                "sleep 0.05; : > queue/tasks.txt; "
                "printf '[2026-01-01] [DONE] TASK-RETRY\\n' >> queue/tasks.done; "
                "printf '{\\\"state\\\":\\\"IDLE\\\"}\\n' > queue/worker.json"
            )
            completer = subprocess.Popen(["bash", "-c", completion], cwd=root,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            result = subprocess.run(
                ["bash", str(root / "scripts/watch_worker.sh"), "1", "0.01", "TASK-RETRY"],
                cwd=root, env={**os.environ, "TASKS_FILE": "queue/tasks.txt",
                               "TASKS_DONE_FILE": "queue/tasks.done",
                               "STATUS_FILE": "queue/worker.json",
                               "PROGRESS_FILE": "queue/progress.log"},
                capture_output=True, text=True, timeout=5,
            )

            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("[SENTINEL_TIMEOUT]", result.stdout)
            self.assertNotIn("[SENTINEL_COMPLETED]", result.stdout)
            completer.wait(timeout=5)

    def test_launcher_runs_python_daemon_and_cleans_pid_when_run_once_queue_is_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            copy_runtime_fixture(root / "scripts/worker_runtime.py")
            (root / "scripts/adapters").mkdir(parents=True, exist_ok=True)
            (root / "scripts/adapters/agents.json").write_text(json.dumps({
                "primary": {"default": True, "worker": {},
                            "agent": {"adapter": "opaque", "command": "unused"}}
            }))
            (root / "tasks.txt").write_text("# no tasks\n")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "worker@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "worker.sh", "scripts", ".gitignore", "tasks.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)

            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                    env={**os.environ, "RUN_ONCE": "1", "POLL_INTERVAL": "0.01"},
                                    capture_output=True, text=True, timeout=30)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("RUN_ONCE", result.stdout)
            self.assertIn("Registered adapters: 1", result.stdout)
            self.assertEqual(json.loads((root / "worker.status").read_text())["state"], "STOPPED")
            self.assertFalse((root / ".worker.pid").exists())

    def test_launcher_refuses_a_live_pid_without_touching_runtime_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            copy_runtime_fixture(root / "scripts/worker_runtime.py")
            pid_file = root / ".worker.pid"
            pid_file.write_text(f"{os.getpid()}\n")

            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                    capture_output=True, text=True, timeout=10)

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("already running", result.stderr)
            self.assertEqual(pid_file.read_text(), f"{os.getpid()}\n")
            self.assertFalse((root / "tasks.txt").exists())

    def test_timed_out_task_is_requeued_and_dirty_workspace_is_preserved_then_rolled_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            copy_runtime_fixture(root / "scripts/worker_runtime.py")
            (root / "output.txt").write_text("baseline\n")
            (root / "tasks.txt").write_text(
                "TASK-T | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: FIX] Timeout test | VERIFY: true\n"
            )
            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "codex"
            fake.write_text(
                "#!/bin/sh\nprintf 'partial\\n' > output.txt\n"
                "printf 'started\\n'\n"
                "sleep 10\n"
            )
            fake.chmod(0o755)
            (root / ".worker.env").write_text(
                "WORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0\nTASK_TIMEOUT=0.5\n"
                "WORKER_SCORE_FILE=.worker-score-test.json\nAI_AGENTS_JSON='" +
                json.dumps([codex_registration("timeout", fake)]) + "'\n")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "worker@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "worker.sh", "scripts", ".gitignore", "output.txt", "tasks.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"

            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                    env=env, capture_output=True, text=True, timeout=20)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((root / "output.txt").read_text(), "baseline\n")
            self.assertIn("TASK-T", (root / "tasks.txt").read_text())
            self.assertEqual((root / "tasks.done").read_text(), "")
            self.assertEqual(json.loads((root / ".worker-agent-state.default.json").read_text())
                             ["task_exclusions"], {"TASK-T": ["timeout"]})
            self.assertIn("remove this task from task_exclusions", (root / "progress.log").read_text())
            backups = list((root / ".scratch/failed_tasks").glob("TASK-T_*/changes.diff"))
            self.assertEqual(len(backups), 1)
            self.assertIn("partial", backups[0].read_text())
            self.assertFalse((root / ".worker.pid").exists())
            score = json.loads((root / ".worker-score-test.json").read_text())
            self.assertNotIn("TASK-T", score["failures"])
            self.assertEqual(score["score"], 5)

    def test_worker_task_failure_with_ignored_scratch_and_build_files_avoids_recursive_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            with open(root / ".gitignore", "a") as f:
                f.write("build/\n")
            (root / "scripts").mkdir()
            copy_runtime_fixture(root / "scripts/worker_runtime.py")
            (root / "output.txt").write_text("baseline\n")
            (root / "tasks.txt").write_text(
                "TASK-F | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: FIX] Failure test | VERIFY: true\n"
            )
            (root / ".scratch/attempts/PREV/baseline").mkdir(parents=True)
            (root / ".scratch/attempts/PREV/baseline/snapshot.json").write_text('{"paths":{}}\n')
            (root / "build").mkdir()
            (root / "build/app.o").write_text("binary blob\n")

            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "codex"
            fake.write_text(
                "#!/bin/sh\n"
                "printf 'failed partial\\n' > output.txt\n"
                "mkdir -p build\n"
                "printf 'new build artifact\\n' > build/failed.o\n"
                "exit 1\n"
            )
            fake.chmod(0o755)
            (root / ".worker.env").write_text(
                "WORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0\nTASK_TIMEOUT=5\n"
                "WORKER_SCORE_FILE=.worker-score-test.json\nAI_AGENTS_JSON='" +
                json.dumps([codex_registration("failagent", fake)]) + "'\n")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "worker@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "worker.sh", "scripts", ".gitignore", "output.txt", "tasks.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"

            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                    env=env, capture_output=True, text=True, timeout=20)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((root / "output.txt").read_text(), "baseline\n")
            snapshots = list((root / ".scratch/attempts/TASK-F").glob("*/baseline/snapshot.json"))
            self.assertEqual(len(snapshots), 1)
            snapshot_meta = json.loads(snapshots[0].read_text())
            for path_key in snapshot_meta.get("paths", {}):
                self.assertFalse(path_key.startswith(".scratch/"), f"Unexpected .scratch path in snapshot: {path_key}")
                self.assertFalse(path_key.startswith("build/"), f"Unexpected build path in snapshot: {path_key}")
            backups = list((root / ".scratch/failed_tasks").glob("TASK-F_*"))
            self.assertTrue(len(backups) >= 1)
            backup_dir = backups[0]
            self.assertFalse((backup_dir / "failed-files").exists())
            self.assertTrue((root / ".scratch/attempts/PREV/baseline/snapshot.json").is_file())
            self.assertTrue((root / "build/app.o").is_file())

    def test_codex_task_keeps_queue_status_commit_and_guard_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            copy_runtime_fixture(root / "scripts/worker_runtime.py")
            (root / "tasks.txt").write_text(
                "TASK-1 | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: EXPAND] "
                "Write output | VERIFY: test -f output.txt\n"
            )
            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "codex"
            fake.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$@\" > \"$FAKE_ARGS_LOG\"\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = --output-last-message ]; then\n"
                "    shift; printf '{\"outcome\":\"complete\",\"changed\":true,\"commit_message\":\"feat: complete TASK-1\"}\\n' > \"$1\"\n"
                "  fi\n"
                "  shift\n"
                "done\n"
                "printf 'hello\\n' > output.txt\n"
                "if [ \"${FAKE_OUTSIDE:-0}\" = 1 ]; then printf 'bad\\n' > outside.txt; fi\n"
            )
            fake.chmod(0o755)
            (root / ".worker.env").write_text(
                "WORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0\nTASK_TIMEOUT=30\nAI_AGENTS_JSON='" +
                json.dumps([codex_registration("codex", fake, "gpt-6-luna", effort="none")]) + "'\n")
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args],
                                      capture_output=True, text=True, check=True).stdout.strip()
            git("init", "-q")
            git("config", "user.name", "Worker Test")
            git("config", "user.email", "worker@example.invalid")
            git("add", "worker.sh", "scripts", ".gitignore", "tasks.txt")
            git("commit", "-qm", "fixture")
            args_log = Path(directory) / "args.txt"
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
            env["FAKE_ARGS_LOG"] = str(args_log)

            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                    env=env, capture_output=True, text=True, timeout=45)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((root / "tasks.txt").read_text(), "")
            self.assertIn("[DONE]", (root / "tasks.done").read_text(),
                          result.stdout + result.stderr)
            self.assertEqual((root / "output.txt").read_text(), "hello\n")
            self.assertEqual(git("show", "HEAD:output.txt"), "hello")
            self.assertIn("--model\ngpt-6-luna", args_log.read_text())
            self.assertIn("model_reasoning_effort=none", args_log.read_text())
            self.assertIn("--approve-for-me", args_log.read_text())
            self.assertEqual(json.loads((root / "worker.status").read_text())["state"], "STOPPED")
            self.assertIn("[MECHANICAL_AUDIT] Status: PASS", (root / "progress.log").read_text())

            # The same public worker entry point must reject an undeclared edit.
            (root / "tasks.txt").write_text(
                "TASK-2 | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: EXPAND] "
                "Try an out-of-scope edit | VERIFY: test -f output.txt\n"
            )
            env["FAKE_OUTSIDE"] = "1"
            rejected = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                      env=env, capture_output=True, text=True, timeout=45)
            self.assertEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
            self.assertIn("[FAILED]", (root / "tasks.done").read_text())
            self.assertIn("Pre-commit audit failed", rejected.stderr)
            self.assertFalse((root / "outside.txt").exists())
            self.assertEqual(git("show", "HEAD:output.txt"), "hello")


class DaemonLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "repo"
        (self.root / "scripts").mkdir(parents=True)
        shutil.copy2(ROOT / "worker.sh", self.root / "worker.sh")
        copy_runtime_fixture(self.root / "scripts/worker_runtime.py")
        shutil.copy2(ROOT / ".gitignore", self.root / ".gitignore")
        (self.root / ".worker.env").write_text(
            "WORKER_ISOLATION=0\nRUN_ONCE=0\nPOLL_INTERVAL=0.05\nSTEP_BASE=1\nSTEP_PER_FILE=0\n")
        self.fake = Path(self.directory.name) / "codex"
        self.flag = Path(self.directory.name) / "quota"
        self.fake.write_text(
            "#!/usr/bin/env python3\nimport os,sys,json,time\nfrom pathlib import Path\n"
            "if os.environ.get('AGENT_DELAY'): time.sleep(float(os.environ['AGENT_DELAY']))\n"
            "if Path(os.environ['QUOTA_FLAG']).exists():\n print(json.dumps({'type':'turn.failed','error':{'message':'RESOURCE_EXHAUSTED code 429'}}),flush=True);sys.exit(1)\n"
            "prompt=sys.stdin.read()\n"
            "if 'TASK-BUDGET' in prompt:\n"
            " Path('output.txt').write_text('partial')\n"
            " for _ in range(2): print(json.dumps({'type':'item.completed','item':{'type':'command_execution'}}),flush=True)\n"
            "else:\n"
            " Path('output.txt').write_text('recovered')\n"
            " Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(json.dumps({'outcome':'complete','changed':True,'commit_message':'feat: recover output'}))\n")
        self.fake.chmod(0o755)
        write_legacy_registry(self.root, json.dumps([codex_registration("test", self.fake)]))
        for args in (("init", "-q"), ("config", "user.name", "Lifecycle Test"),
                     ("config", "user.email", "lifecycle@example.invalid"),
                     ("add", "."), ("commit", "-qm", "fixture")):
            subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)
        self.env = {**os.environ, "RUN_ONCE": "0", "POLL_INTERVAL": "0.05",
                    "STEP_BASE": "1", "STEP_PER_FILE": "0",
                    "PATH": f"{self.fake.parent}{os.pathsep}{os.environ['PATH']}",
                    "QUOTA_FLAG": str(self.flag)}

    def enqueue(self, task):
        (self.root / "tasks.txt").write_text(
            f"{task} | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: EXPAND] Write output | VERIFY: test -f output.txt\n")

    def start(self):
        self.log = (Path(self.directory.name) / "daemon.log").open("w+")
        self.addCleanup(self.log.close)
        self.process = subprocess.Popen(["bash", "worker.sh"], cwd=self.root, env=self.env,
                                        stdout=self.log, stderr=subprocess.STDOUT)
        def stop():
            if self.process.poll() is None:
                self.process.terminate()
                self.process.wait(timeout=5)
        self.addCleanup(stop)

    def wait_for(self, predicate):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            self.log.seek(0)
            self.assertIsNone(self.process.poll(), "daemon unexpectedly exited:\n" + self.log.read())
            if predicate():
                return
            time.sleep(0.02)
        self.log.seek(0)
        self.fail("daemon condition timed out: " + self.log.read())

    def state(self):
        p = self.root / "worker.status"
        return json.loads(p.read_text())["state"] if p.exists() else None

    def test_task_audit_and_commit_preserve_preexisting_user_work(self):
        def git(*args):
            return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                                  capture_output=True, text=True).stdout
        (self.root / "docs/agents").mkdir(parents=True)
        (self.root / "docs/agents/granularity-profile.json").write_text("original\n")
        (self.root / "staged.txt").write_text("original\n")
        (self.root / "deleted.txt").write_text("original\n")
        (self.root / "tests").mkdir()
        (self.root / "tests/test_user.py").write_text("assert True\n" * 60)
        git("add", "docs", "staged.txt", "deleted.txt", "tests")
        git("commit", "-qm", "user baseline")
        (self.root / "docs/agents/granularity-profile.json").write_text("user configuration\n")
        (self.root / "staged.txt").write_text("user staged work\n")
        git("add", "staged.txt")
        (self.root / "staged.txt").write_text("user unstaged work after staging\n")
        (self.root / "deleted.txt").unlink()
        (self.root / "tests/test_user.py").write_text("assert True\n")
        (self.root / "user-notes.txt").write_text("untracked user work\n")
        (self.root / "user-link").symlink_to("user-notes.txt")
        index_before = git("diff", "--cached", "--binary")
        self.enqueue("TASK-USER-BASELINE")
        queue = self.root / "tasks.txt"
        queue.write_text(queue.read_text().replace("LEVEL: 1", "LEVEL: 3"))
        self.start()
        self.wait_for(lambda: (self.root / "tasks.done").exists() and
                      "[DONE] TASK-USER-BASELINE" in (self.root / "tasks.done").read_text())
        self.wait_for(lambda: self.state() == "IDLE")
        self.assertEqual(git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").strip(), "output.txt")
        self.assertEqual(git("diff", "--cached", "--binary"), index_before)
        self.assertEqual((self.root / "docs/agents/granularity-profile.json").read_text(), "user configuration\n")
        self.assertEqual((self.root / "staged.txt").read_text(), "user unstaged work after staging\n")
        self.assertFalse((self.root / "deleted.txt").exists())
        self.assertEqual((self.root / "tests/test_user.py").read_text(), "assert True\n")
        self.assertEqual((self.root / "user-link").readlink(), Path("user-notes.txt"))
        self.assertIn("user-notes.txt", git("ls-files", "--others", "--exclude-standard"))

    def test_worker_modification_to_preexisting_out_of_scope_file_is_rejected(self):
        user_file = self.root / "user-notes.txt"
        user_file.write_text("user baseline\n")
        subprocess.run(["git", "-C", str(self.root), "add", "user-notes.txt"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "baseline notes"], check=True)
        self.fake.write_text(self.fake.read_text().replace(
            "Path('output.txt').write_text('recovered')",
            "Path('user-notes.txt').write_text('worker overwrite');Path('output.txt').write_text('recovered')"))
        self.enqueue("TASK-OUTSIDE")
        self.start()
        self.wait_for(lambda: (self.root / "tasks.done").exists() and
                      "[FAILED] TASK-OUTSIDE" in (self.root / "tasks.done").read_text())
        self.assertEqual(user_file.read_text(), "user baseline\n")
        self.assertFalse((self.root / "output.txt").exists())
        for path in ("progress.log", ".worker.log"):
            details = (self.root / path).read_text()
            self.assertIn("Target Whitelist Violation", details)
            self.assertIn("user-notes.txt", details)

    def test_preexisting_dirty_target_is_not_silently_committed(self):
        target = self.root / "output.txt"
        target.write_text("original\n")
        subprocess.run(["git", "-C", str(self.root), "add", "output.txt"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "baseline target"], check=True)
        target.write_text("user work\n")
        self.enqueue("TASK-OVERLAP")
        self.start()
        self.wait_for(lambda: (self.root / "tasks.done").exists() and
                      "[FAILED] TASK-OVERLAP" in (self.root / "tasks.done").read_text())
        self.assertEqual(target.read_text(), "user work\n")

    def test_staged_target_is_preserved_when_worktree_matches_head(self):
        def git(*args):
            return subprocess.run(["git", "-C", str(self.root), *args], check=True,
                                  capture_output=True, text=True).stdout
        target = self.root / "output.txt"
        target.write_text("original\n")
        git("add", "output.txt")
        git("commit", "-qm", "baseline target")
        target.write_text("user staged\n")
        git("add", "output.txt")
        target.write_text("original\n")
        staged_before = git("diff", "--cached", "--binary")
        self.enqueue("TASK-STAGED-TARGET")
        self.start()
        self.wait_for(lambda: (self.root / "tasks.done").exists() and
                      "[FAILED] TASK-STAGED-TARGET" in (self.root / "tasks.done").read_text())
        self.assertEqual(git("diff", "--cached", "--binary"), staged_before)
        self.assertEqual(target.read_text(), "original\n")

    def test_running_task_refreshes_elapsed_time_and_heartbeat(self):
        self.env["AGENT_DELAY"] = "2.5"
        self.enqueue("TASK-HEARTBEAT")
        self.start()
        self.wait_for(lambda: self.state() == "RUNNING")
        status = self.root / "worker.status"
        initial = json.loads(status.read_text())
        self.wait_for(lambda: self.state() == "RUNNING" and
                      json.loads(status.read_text())["elapsed_seconds"] >= 1 and
                      json.loads(status.read_text())["last_heartbeat"] != initial["last_heartbeat"])
        self.wait_for(lambda: "[DONE] TASK-HEARTBEAT" in (self.root / "tasks.done").read_text())
        self.wait_for(lambda: self.state() == "IDLE")
        time.sleep(0.15)
        self.assertEqual(self.state(), "IDLE", "late heartbeat must not overwrite terminal state")

    def test_budget_failure_hands_back_to_planner_and_resumes_after_pause(self):
        self.enqueue("TASK-BUDGET")
        self.start()
        self.wait_for(lambda: (self.root / "tasks.done").exists() and
                      "[FAILED] TASK-BUDGET" in (self.root / "tasks.done").read_text())
        self.wait_for(lambda: self.state() == "BLOCKED")
        self.assertIn("[NEED_DECOMPOSITION] TASK-BUDGET", (self.root / "progress.log").read_text())
        self.assertFalse((self.root / "output.txt").exists())
        (self.root / "PAUSE").touch()
        self.wait_for(lambda: self.state() == "PAUSED")
        self.enqueue("TASK-RECOVER")
        time.sleep(0.15)
        self.assertIn("TASK-RECOVER", (self.root / "tasks.txt").read_text())
        (self.root / "PAUSE").unlink()
        self.wait_for(lambda: "[DONE] TASK-RECOVER" in (self.root / "tasks.done").read_text())
        self.wait_for(lambda: self.state() == "IDLE")
        self.assertTrue((self.root / ".worker.pid").exists())

    def test_failed_verification_keeps_planner_handoff_instead_of_idle(self):
        self.enqueue("TASK-AUDIT")
        queue = self.root / "tasks.txt"
        queue.write_text(queue.read_text().replace("VERIFY: test -f output.txt", "VERIFY: false"))
        self.start()
        self.wait_for(lambda: (self.root / "tasks.done").exists() and
                      "[FAILED] TASK-AUDIT" in (self.root / "tasks.done").read_text())
        time.sleep(0.15)
        self.assertEqual(self.state(), "BLOCKED")
        self.assertIn("awaiting Planner", json.loads((self.root / "worker.status").read_text())["current_task"])

    def test_all_quotas_exhausted_waits_then_recovers_without_daemon_restart(self):
        self.flag.touch()
        self.enqueue("TASK-QUOTA")
        self.start()
        self.wait_for(lambda: self.state() == "QUOTA_EXHAUSTED")
        time.sleep(0.15)
        self.assertIn("TASK-QUOTA", (self.root / "tasks.txt").read_text())
        self.assertEqual((self.root / "tasks.done").read_text(), "")
        self.flag.unlink()
        (self.root / ".worker-agent-state.default.json").unlink()
        self.wait_for(lambda: "[DONE] TASK-QUOTA" in (self.root / "tasks.done").read_text())
        self.wait_for(lambda: self.state() == "IDLE")

    def test_worker_restart_rechecks_previously_exhausted_agent(self):
        self.flag.touch()
        self.enqueue("TASK-RECHECK")
        self.start()
        self.wait_for(lambda: self.state() == "QUOTA_EXHAUSTED")
        self.process.terminate()
        self.process.wait(timeout=5)
        (self.root / ".worker.pid").unlink(missing_ok=True)
        self.flag.unlink()
        self.start()
        self.wait_for(lambda: "[DONE] TASK-RECHECK" in (self.root / "tasks.done").read_text())

    def test_last_timed_out_registration_requeues_task_without_marking_failure(self):
        wrapper = Path(self.directory.name) / "slow-wrapper.py"
        wrapper.write_text(
            "import json,os,time\ntime.sleep(float(os.environ['AGENT_DELAY']))\n"
            "json.dump({'outcome':'failure'}, open(os.environ['NIGHTSHIFT_RESULT_FILE'],'w'))\n"
        )
        write_legacy_registry(self.root, json.dumps([
            generic_registration("test", sys.executable, [str(wrapper)], {"AGENT_DELAY": "1"})
        ]))
        subprocess.run(["git", "-C", str(self.root), "add", "scripts/adapters/agents.json"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "test: configure timeout agent"], check=True)
        self.env["TASK_TIMEOUT"] = "0.1"
        self.env["POLL_INTERVAL"] = "0.05"
        self.env["RUN_ONCE"] = "1"
        self.enqueue("TASK-TIMEOUT")
        (self.root / ".worker.env").write_text(
            "WORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0.05\n"
            "TASK_TIMEOUT=0.1\nSTEP_BASE=1\nSTEP_PER_FILE=0\n")
        self.start()
        self.assertEqual(self.process.wait(timeout=10), 0)
        self.assertEqual(self.state(), "WAITING_FOR_AGENT")
        self.assertIn("TASK-TIMEOUT", (self.root / "tasks.txt").read_text())
        self.assertEqual((self.root / "tasks.done").read_text(), "")
        state = json.loads((self.root / ".worker-agent-state.default.json").read_text())
        self.assertEqual(state["task_exclusions"], {"TASK-TIMEOUT": ["test"]})


class TrialDemoIntegrationTests(unittest.TestCase):
    @unittest.skipUnless((ROOT / "install.sh").is_file(), "source checkout only")
    def test_installed_trial_demo_covers_binary_bundle_shared_file_and_custom_pause(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            fixture = ROOT / "test/fixtures/trial-demo"
            shutil.copytree(fixture, target)
            subprocess.run(["git", "-C", str(target), "init", "-q"], check=True)
            install = subprocess.run(["bash", str(ROOT / "install.sh"), str(target)],
                                     capture_output=True, text=True, timeout=30)
            self.assertEqual(install.returncode, 0, install.stdout + install.stderr)

            single = subprocess.run([str(target / "bin/standalone")], cwd=target,
                                    capture_output=True, text=True, check=True)
            self.assertEqual(single.stdout.strip(), "standalone trial v1")
            trial = target / ".trials/TRIAL-BUNDLED"
            shutil.copytree(target / "bundled", trial)
            bundled = subprocess.run([str(trial / "bin/show-message")], cwd=target,
                                     capture_output=True, text=True, check=True)
            self.assertEqual(bundled.stdout.strip(), "bundled message v1")
            shared = subprocess.run([str(target / "scripts/read-shared.sh")], cwd=target,
                                    capture_output=True, text=True, check=True)
            self.assertEqual(shared.stdout.strip(), "shared project data")
            ignored = subprocess.run(["git", "-C", str(target), "check-ignore", "-q",
                                      str(trial / "bin/show-message")], check=False)
            self.assertEqual(ignored.returncode, 0)

            tasks = target / "tasks.txt"
            tasks.write_text("TASK-WAIT | ACTION: remain pending\n")
            pause = target / "ops/worker.hold"
            pause.parent.mkdir(parents=True, exist_ok=True)
            pause.touch()
            status = subprocess.run(["bash", str(target / "scripts/status.sh")], cwd=target,
                                    env={**os.environ, "PAUSE_FILE": str(pause)},
                                    capture_output=True, text=True, check=True)
            self.assertIn("Pause Flag     : [PAUSED]", status.stdout)
            poll = subprocess.run([sys.executable, str(target / "scripts/worker_runtime.py"),
                                   "poll-next", "--tasks", str(tasks), "--done", str(target / "tasks.done"),
                                   "--pause", str(pause), "--work-dir", str(target)],
                                  capture_output=True, text=True, check=True)
            self.assertEqual(poll.stdout.split("\0", 1)[0], "paused")
            self.assertIn("TASK-WAIT", tasks.read_text())


class InstallerIntegrationTests(unittest.TestCase):
    @unittest.skipUnless((ROOT / "install.sh").exists(), "source checkout only")
    def test_installer_deploys_python_runtime_and_regression_pattern(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            subprocess.run(["git", "init", "-q", str(target)], check=True)
            (target / ".agents").mkdir()
            skills_manifest = target / ".agents/skills.json"
            skills_manifest.write_text('{"entries":[{"path":"custom/skills"}]}\n')
            result = subprocess.run(["bash", str(ROOT / "install.sh"), str(target)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(skills_manifest.read_text(), '{"entries":[{"path":"custom/skills"}]}\n')
            self.assertEqual((target / "update.sh").read_bytes(), (ROOT / "update.sh").read_bytes())
            deployed_runtime = target / "scripts/worker_runtime.py"
            self.assertEqual(deployed_runtime.read_bytes(), (ROOT / "scripts/worker_runtime.py").read_bytes())
            for adapter in ("codex.py", "agy.py", "generic.py", "aider.py",
                            "aider_explore.py", "explore_evidence.py"):
                self.assertEqual((target / "scripts/adapters" / adapter).read_bytes(),
                                 (ROOT / "scripts/adapters" / adapter).read_bytes())
            self.assertEqual((target / "docs/PORTING_GUIDE.md").read_bytes(),
                             (ROOT / "docs/PORTING_GUIDE.md").read_bytes())
            operations = target / ".agents/skills/nightshift/planner/OPERATIONS.md"
            self.assertFalse(operations.exists())
            operations.parent.mkdir(parents=True, exist_ok=True)
            operations.write_text("stale planner instructions\n")
            self.assertFalse((target / "worker_runtime.py").exists())
            self.assertTrue((target / "test/nightshift_worker/test_worker_runtime.py").is_file())
            self.assertTrue((target / "test/nightshift_worker/test_explore_evidence.py").is_file())
            self.assertTrue((target / "test/nightshift_worker/README.md").is_file())
            self.assertFalse((target / ".worker.env").exists())
            self.assertTrue((target / "scripts/adapters/agents.json").is_file())
            self.assertEqual((target / "scripts/adapters/agents.json").read_bytes(),
                             (ROOT / "scripts/adapters/agents.json").read_bytes())
            self.assertFalse((target / "agents/agents.json").exists())
            self.assertIn(".worker-agent-state*.json", (target / ".gitignore").read_text())
            self.assertIn(".worker-score*.json", (target / ".gitignore").read_text())
            self.assertIn(".worker-score*.json.lock/", (target / ".gitignore").read_text())
            self.assertIn(".worker-agent-scores/", (target / ".gitignore").read_text())
            self.assertIn(".worker-agent-events.jsonl", (target / ".gitignore").read_text())
            self.assertIn(".trials/", (target / ".gitignore").read_text())
            agent_registry = target / "scripts/adapters/agents.json"
            custom_registry = json.dumps({"custom": {
                "default": True, "adapter": "codex", "command": "python3",
                "args": ["scripts/adapters/codex.py"],
                "config": {"executable": "/opt/bin/codex", "model": "custom-model", "effort": "low"},
            }}) + "\n"
            legacy_registry = target / "agents/agents.json"
            legacy_registry.parent.mkdir()
            legacy_registry.write_text(custom_registry)
            agent_registry.unlink()
            (target / ".worker.env.example").write_text("stale environment example\n")
            (target / "update.sh").write_text("stale updater\n")
            deployed_runtime.write_text("stale runtime\n")
            update = subprocess.run(["bash", str(ROOT / "install.sh"), str(target)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(update.returncode, 0, update.stdout + update.stderr)
            self.assertIn("Deployed scripts/worker_runtime.py", update.stdout)
            self.assertEqual(deployed_runtime.read_bytes(), (ROOT / "scripts/worker_runtime.py").read_bytes())
            self.assertIn("Migrated agents/agents.json to scripts/adapters/agents.json", update.stdout)
            self.assertFalse(operations.exists(), "updates must remove retired skill sidecars")
            planner_skill = (target / ".agents/skills/nightshift/planner/SKILL.md").read_text()
            worker_contract = (target / ".skills/universal-build-verify.md").read_text()
            self.assertNotIn("OPERATIONS.md", planner_skill + worker_contract)
            self.assertIn("entire graph without repeated approval", planner_skill)
            migrated_registry = json.loads(agent_registry.read_text())
            self.assertEqual(migrated_registry["custom"], {
                "default": True,
                "worker": {"task_timeout_seconds": 1800},
                "agent": {"adapter": "codex", "command": "/opt/bin/codex", "args": [],
                          "env": {}, "config": {"model": "custom-model", "effort": "low"}},
            })
            self.assertFalse(legacy_registry.exists())
            self.assertFalse((target / ".worker.env.example").exists())
            self.assertEqual((target / "update.sh").read_bytes(), (ROOT / "update.sh").read_bytes())
            self.assertEqual(deployed_runtime.read_bytes(), (ROOT / "scripts/worker_runtime.py").read_bytes())
            # Once migrated, updates preserve the current config exactly.
            preserved_registry = json.dumps({"custom": {
                "default": True, "worker": {"task_timeout_seconds": 91},
                "agent": {"adapter": "opaque", "command": "changed", "args": [],
                          "env": {}, "config": {"model": "retained"}},
            }}) + "\n"
            agent_registry.write_text(preserved_registry)
            second_update = subprocess.run(["bash", str(ROOT / "install.sh"), str(target)],
                                           cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(second_update.returncode, 0, second_update.stdout + second_update.stderr)
            self.assertEqual(agent_registry.read_text(), preserved_registry)
            installed = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "test", "-v"],
                cwd=target, capture_output=True, text=True, timeout=90,
            )
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)

    @unittest.skipUnless((ROOT / "install.sh").exists(), "source checkout only")
    def test_installed_runtime_executes_unknown_protocol_adapter_without_source_checkout(self):
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)/"project"; target.mkdir()
            installed=subprocess.run(["bash",str(ROOT/"install.sh"),str(target)],
                cwd=ROOT,capture_output=True,text=True,timeout=30)
            self.assertEqual(installed.returncode,0,installed.stdout+installed.stderr)
            repo=Path(directory)/"work"; repo.mkdir()
            subprocess.run(["git","init","-q",str(repo)],check=True)
            for args in (("config","user.name","Installed Test"),
                         ("config","user.email","installed@example.invalid"),
                         ("add","."),):
                subprocess.run(["git","-C",str(repo),*args],check=True)
            subprocess.run(["git","-C",str(repo),"commit","--allow-empty","-qm","baseline"],check=True)
            adapter=Path(directory)/"unregistered.py"
            adapter.write_text(
                "import json,pathlib,sys\nr=json.load(sys.stdin); op=sys.argv[-1]\n"
                "if op=='get_config': x={'protocol_version':1,'initial_score':4,'limits':{'poll_interval_seconds':0.01}}\n"
                "elif op=='start':\n"
                " p=pathlib.Path(r['output_dir']);p.mkdir(parents=True,exist_ok=True)\n"
                " q=pathlib.Path(r['result_path']);q.write_text(json.dumps({'outcome':'no_change','changed':False,'no_change_reason':'verified fixture'}))\n"
                " (p/'status.json').write_text(json.dumps({'status':'complete','result_location':str(q)}))\n"
                " x={'execution_id':'installed-run','status_location':str(p/'status.json')}\n"
                "else:x=json.loads(pathlib.Path(r['status_location']).read_text())\n"
                "print(json.dumps(x))\n")
            (Path(directory)/"prompt.txt").write_text("common task prompt")
            runtime_path=target/"scripts/worker_runtime.py"
            result=subprocess.run([sys.executable,str(runtime_path),"task-cli","--adapter","unknown-extension",
                "--executable",sys.executable,"--extra-arg",str(adapter),"--work-dir",str(repo),
                "--prompt-file",str(Path(directory)/"prompt.txt"),"--output-file",str(Path(directory)/"run.log"),
                "--result-file",str(Path(directory)/"result.json"),"--task-id","TASK-INSTALLED",
                "--target",".","--base","HEAD"],cwd=target,capture_output=True,text=True,timeout=15)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(json.loads((Path(directory)/"result.json").read_text())["outcome"],"no_change")

    @unittest.skipUnless((ROOT / "install.sh").exists(), "source checkout only")
    def test_installer_resolves_symlink_target_before_self_install_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            alias = Path(directory) / "nightshift-alias"
            alias.symlink_to(ROOT, target_is_directory=True)
            result = subprocess.run(["bash", str(ROOT / "install.sh"), str(alias)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Cannot install/update NightShift into its own source directory.", result.stdout)


if __name__ == "__main__":
    unittest.main()
