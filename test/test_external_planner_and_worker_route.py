"""Planner and Worker project context routing tests."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "nightshift"))
import acceptance
import project_config

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "nightshift" / "worker_runtime.py"


class ExternalPlannerAndWorkerRouteTests(unittest.TestCase):
    def test_project_info_reports_canonical_root_skills_and_state(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            installation = workspace / "external-tool" / "nightshift"
            installation.mkdir(parents=True)
            target = workspace / "target-repo"
            target.mkdir()
            subprocess.run(["git", "init", "-q", str(target)], check=True)

            config = {
                "version": 1,
                "default_project": "my-target",
                "projects": {
                    "my-target": {"path": "../../target-repo"}
                }
            }
            config_file = installation / "config.json"
            config_file.write_text(json.dumps(config))

            # Run project-info CLI
            result = subprocess.run([
                sys.executable, str(RUNTIME), "project-info",
                "--root", str(workspace),
                "--config", str(config_file)
            ], capture_output=True, text=True, check=True)

            info = json.loads(result.stdout)
            self.assertEqual(info["name"], "my-target")
            self.assertEqual(Path(info["root"]).resolve(), target.resolve())
            self.assertIsNotNone(info["state"])
            self.assertTrue(Path(info["skills"]).is_dir())

    def test_preexisting_embedded_nightshift_does_not_override_external_config_and_commits_only_project_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            installation = workspace / "tool" / "nightshift"
            installation.mkdir(parents=True)

            # Target repo has pre-existing embedded nightshift
            target = workspace / "embedded-repo"
            target.mkdir()
            subprocess.run(["git", "init", "-q", str(target)], check=True)
            (target / "nightshift").mkdir()
            (target / "nightshift" / "config.json").write_text(json.dumps({
                "version": 1,
                "acceptance": {"hot": "false"}  # Embedded config would fail hot gate
            }))
            (target / ".agents" / "skills" / "local-dummy").mkdir(parents=True)
            (target / ".agents" / "skills" / "local-dummy" / "SKILL.md").write_text("# dummy")
            (target / "app.py").write_text("print('hello')\n")
            (target / "test_app.py").write_text("# initial test\n")
            (target / ".gitignore").write_text("*.pyc\n")
            subprocess.run(["git", "-C", str(target), "add", "."], check=True)
            subprocess.run(["git", "-C", str(target), "commit", "-m", "init with embedded nightshift"], check=True)

            # External configuration with working acceptance
            checks = workspace / "external-checks"
            checks.mkdir()
            hot_runner = checks / "hot_runner.py"
            hot_runner.write_text('''import json, os, pathlib
phase = os.environ.get("NIGHTSHIFT_PHASE")
res = pathlib.Path(os.environ["NIGHTSHIFT_RESULT"])
run_id = os.environ.get("NIGHTSHIFT_RUN", "")
res.write_text(json.dumps({
    "run": run_id,
    "status": "pass",
    "cases": [{
        "id": "test_app",
        "source": "test_app.py",
        "fingerprint": "a" * 64,
        "baseline_fingerprint": None,
        "status": "passed"
    }]
}))
''')
            (checks / "hot.sh").write_text(f"exec {sys.executable} {hot_runner}\n")

            # Fake worker script that modifies app.py and test_app.py and writes valid result
            worker_script = workspace / "fake_worker.py"
            worker_script.write_text('''import json, os, pathlib
target = pathlib.Path(os.environ.get("NIGHTSHIFT_PROJECT_ROOT", "."))
(target / "app.py").write_text("print('updated')\\n")
(target / "test_app.py").write_text("def test_app(): assert True\\n")
result = {
    "outcome": "complete",
    "changed": True,
    "commit_message": "feat: update app",
    "tdd_cases": [{"id": "test_app", "source": "test_app.py"}]
}
pathlib.Path(os.environ["NIGHTSHIFT_RESULT_FILE"]).write_text(json.dumps(result))
''')

            config = {
                "version": 1,
                "default_project": "embedded",
                "projects": {
                    "embedded": {
                        "path": "../../embedded-repo",
                        "acceptance": {"hot_script": "../../external-checks/hot.sh"}
                    }
                },
                "agents": {
                    "fake": {
                        "default": True,
                        "worker": {
                            "task_timeout_seconds": 10,
                            "step_base": {"L1": 60, "L2": 40, "L3": 20}
                        },
                        "agent": {
                            "adapter": "generic",
                            "command": sys.executable,
                            "args": [str(worker_script)]
                        }
                    }
                }
            }
            config_file = installation / "config.json"
            config_file.write_text(json.dumps(config))

            # Put task in external queue
            _, _, state_dir = project_config.resolve_project(config_file, "embedded")
            state_dir.mkdir(parents=True, exist_ok=True)
            queue_file = state_dir / "tasks.txt"
            queue_file.write_text("TASK-001 [CODE: FIX] | LEVEL: 3 | TARGET: app.py,test_app.py | VERIFY: true\n")

            env = {
                **os.environ,
                "RUN_ONCE": "1",
                "POLL_INTERVAL": "0",
                "PYTHONDONTWRITEBYTECODE": "1"
            }

            process = subprocess.run([
                sys.executable, str(RUNTIME), "daemon",
                "--root", str(workspace),
                "--config", str(config_file),
                "--project", "embedded"
            ], env=env, capture_output=True, text=True, timeout=15)

            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

            # Check that commit only touched app.py and test_app.py
            log = subprocess.run([
                "git", "-C", str(target), "log", "-n", "1", "--name-only", "--pretty=format:"
            ], capture_output=True, text=True, check=True)
            changed_files = sorted(f.strip() for f in log.stdout.strip().splitlines() if f.strip())
            self.assertEqual(changed_files, ["app.py", "test_app.py"])

            # Verify no changes were made to embedded nightshift or skills in git
            status = subprocess.run([
                "git", "-C", str(target), "status", "--porcelain"
            ], capture_output=True, text=True, check=True)
            self.assertEqual(status.stdout.strip(), "")

            # Verify embedded config was not overwritten
            embedded_cfg = json.loads((target / "nightshift" / "config.json").read_text())
            self.assertEqual(embedded_cfg.get("acceptance", {}).get("hot"), "false")

    def test_build_task_prompt_injects_canonical_project_and_skills_context(self):
        import worker_runtime
        env = {
            "NIGHTSHIFT_PROJECT_NAME": "demo-proj",
            "NIGHTSHIFT_PROJECT_ROOT": "/path/to/demo-proj"
        }
        with mock.patch.dict(os.environ, env):
            prompt = worker_runtime.build_task_prompt(
                task="implement feature",
                task_id="TASK-99",
                level=2,
                target="src/main.py",
                verify="pytest",
                forbidden="",
                constraints="",
                max_steps=50,
                target_file_count=1,
                step_base=40,
                step_per_file=5,
                progress_file="progress.log"
            )
            self.assertIn("Project: demo-proj", prompt)
            self.assertIn("Project root: /path/to/demo-proj", prompt)
            self.assertIn("NightShift skills: ", prompt)
            self.assertIn("TARGET paths are relative to the project root.", prompt)

