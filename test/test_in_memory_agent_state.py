"""Test that agent runtime state is kept purely in-memory and does not leave disk files or override restarts."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import worker_runtime
import lifecycle

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "scripts" / "worker_runtime.py"


class InMemoryAgentStateTests(unittest.TestCase):
    def test_in_memory_dict_state_updates_without_writing_disk_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt = root / "prompt.txt"
            output = root / "output.json"
            result_file = root / "result.json"

            args = mock.Mock(
                work_dir=str(root),
                title="TASK-01 | ACTION: test",
                task_id="TASK-01",
                level="1",
                target_file_count=1,
                step_per_file=5,
                timeout=10,
                progress_file=str(root / "progress.log"),
                prompt_file=str(prompt),
                output_file=str(output),
                result_file=str(result_file),
                attempt_snapshot_root=str(root / "attempts"),
            )

            agents = [
                {"id": "agent-a", "adapter": "generic", "overrides": {"initial_score": 5}, "command": "cmd-a", "worker": {
                    "task_timeout_seconds": 10, "step_base": {"L1": 20, "L2": 20, "L3": 20}}},
                {"id": "agent-b", "adapter": "generic", "overrides": {"initial_score": 5}, "command": "cmd-b", "worker": {
                    "task_timeout_seconds": 10, "step_base": {"L1": 20, "L2": 20, "L3": 20}}},
            ]

            memory_state = {}
            executed = []

            def fake_execute(attempt):
                executed.append(attempt.agent_id)
                if attempt.agent_id == "agent-a":
                    output.write_text(json.dumps({"status": "execution_timeout"}))
                    result_file.write_text(json.dumps({"outcome": "failure"}))
                    return 1
                output.write_text(json.dumps({"status": "complete"}))
                result_file.write_text(json.dumps({"outcome": "complete"}))
                return 0

            with mock.patch.object(worker_runtime, "capture_attempt_baseline"), \
                 mock.patch.object(worker_runtime, "execute_adapter_task", side_effect=fake_execute):
                code, _ = worker_runtime.execute_registered_agents(args, agents, memory_state, lambda *_: None)

            self.assertEqual(code, 0)
            self.assertEqual(executed, ["agent-a", "agent-b"])
            # In-memory dictionary was updated
            self.assertEqual(memory_state["active_agent_id"], "agent-b")
            self.assertEqual(memory_state["consecutive_no_response"], 0)
            # No .worker-agent-state file created anywhere in root
            state_files = list(root.glob("**/.worker-agent-state*.json"))
            self.assertEqual(state_files, [])

    def test_worker_restart_always_respects_changed_default_agent_without_disk_state(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            installation = workspace / "nightshift"
            installation.mkdir()
            shutil.copytree(ROOT / "scripts" / "adapters", installation / "adapters")
            for name in ("worker.sh", "worker_runtime.py", "lifecycle.py", "acceptance.py", "acceptance_hooks.py", "hook_control.py",
                         "scratch_review.py", "attempt_archive.py", "preflight.py", "environment_probe.py", "verify_process.py", "evidence_capabilities.py", "ticket_policy.py", "outcome_policy.py", "project_config.py", "status.sh", "watch_worker.sh", "reorder_queue.sh"):
                shutil.copy2(ROOT / "scripts" / name, installation / name)

            # Setup git repo
            subprocess.run(["git", "init", "-q", str(workspace)], check=True)
            (workspace / "file.txt").write_text("hello\n")
            (workspace / "test_file.py").write_text("# initial\n")
            (workspace / ".gitignore").write_text("nightshift/\nagent_runner.py\nexecuted_agents.log\nhot_runner.py\n")
            subprocess.run(["git", "-C", str(workspace), "add", "."], check=True)
            subprocess.run(["git", "-C", str(workspace), "commit", "-m", "init"], check=True)

            hot_runner = workspace / "hot_runner.py"
            hot_runner.write_text('''import json, os, pathlib
phase = os.environ.get("NIGHTSHIFT_PHASE")
res = pathlib.Path(os.environ["NIGHTSHIFT_RESULT"])
run_id = os.environ.get("NIGHTSHIFT_RUN", "")
res.write_text(json.dumps({
    "run": run_id,
    "status": "pass",
    "cases": [
        {"id": "test_TASK_1", "source": "test_file.py", "fingerprint": "1" * 64, "baseline_fingerprint": None, "status": "passed"},
        {"id": "test_TASK_2", "source": "test_file.py", "fingerprint": "2" * 64, "baseline_fingerprint": None, "status": "passed"},
    ]
}))
''')

            log_file_path = workspace / "executed_agents.log"
            worker_runner = workspace / "agent_runner.py"
            worker_runner.write_text(f'''import json, os, pathlib
agent_id = os.environ.get("NIGHTSHIFT_AGENT_ID", "unknown")
task = os.environ.get("NIGHTSHIFT_TASK_ID", "TASK-1").replace("-", "_")
with open("{log_file_path}", "a") as f:
    f.write(agent_id + "\\n")
with open("file.txt", "a") as f:
    f.write(f"updated by {{task}}\\n")
with open("test_file.py", "w") as f:
    f.write(f"def test_{{task}}(): pass\\n")
result = {{
    "outcome": "complete",
    "changed": True,
    "commit_message": f"feat: test commit {{task}}",
    "tdd_cases": [{{"id": f"test_{{task}}", "source": "test_file.py"}}]
}}
pathlib.Path(os.environ["NIGHTSHIFT_RESULT_FILE"]).write_text(json.dumps(result))
''')

            # Initial config: agent_alpha is default
            config = {
                "version": 1,
                "acceptance": {"hot": f"{sys.executable} {hot_runner}"},
                "agents": {
                    "agent_alpha": {
                        "default": True,
                        "worker": {"task_timeout_seconds": 10, "step_base": {"L1": 20, "L2": 20, "L3": 20}},
                        "agent": {"adapter": "generic", "config": {"initial_score": 5}, "command": sys.executable, "args": [str(worker_runner)],
                                  "env": {"NIGHTSHIFT_AGENT_ID": "agent_alpha"}}
                    },
                    "agent_beta": {
                        "default": False,
                        "worker": {"task_timeout_seconds": 10, "step_base": {"L1": 20, "L2": 20, "L3": 20}},
                        "agent": {"adapter": "generic", "config": {"initial_score": 5}, "command": sys.executable, "args": [str(worker_runner)],
                                  "env": {"NIGHTSHIFT_AGENT_ID": "agent_beta"}}
                    }
                }
            }
            config_file = installation / "config.json"
            config_file.write_text(json.dumps(config))

            # Queue first task
            tasks = installation / "tasks.txt"
            tasks.write_text("TASK-1 [CODE: FIX] | LEVEL: 1 | TARGET: file.txt,test_file.py | VERIFY: true\n")

            env = {**os.environ, "RUN_ONCE": "1", "POLL_INTERVAL": "0", "PYTHONDONTWRITEBYTECODE": "1"}

            # Launch 1: should use agent_alpha
            run1 = subprocess.run(["bash", str(installation / "worker.sh")], cwd=workspace, env=env,
                                  capture_output=True, text=True, timeout=15)
            self.assertEqual(run1.returncode, 0, run1.stdout + run1.stderr)
            log_content = (workspace / "executed_agents.log").read_text().splitlines()
            self.assertEqual(log_content, ["agent_alpha"])

            # Verify no .worker-agent-state file exists
            state_files = list(workspace.glob("**/.worker-agent-state*.json"))
            self.assertEqual(state_files, [])

            # Now user changes default agent in config to agent_beta!
            config["agents"]["agent_alpha"]["default"] = False
            config["agents"]["agent_beta"]["default"] = True
            config_file.write_text(json.dumps(config))

            # Queue second task
            tasks.write_text("TASK-2 [CODE: FIX] | LEVEL: 1 | TARGET: file.txt,test_file.py | VERIFY: true\n")

            # Launch 2: MUST use agent_beta on restart!
            run2 = subprocess.run(["bash", str(installation / "worker.sh")], cwd=workspace, env=env,
                                  capture_output=True, text=True, timeout=15)
            self.assertEqual(run2.returncode, 0, run2.stdout + run2.stderr)
            log_content = (workspace / "executed_agents.log").read_text().splitlines()
            self.assertEqual(log_content, ["agent_alpha", "agent_beta"])

            # Verify still no .worker-agent-state file on disk
            state_files = list(workspace.glob("**/.worker-agent-state*.json"))
            self.assertEqual(state_files, [])
