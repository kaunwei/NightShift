import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "nightshift"))
import acceptance
import worker_runtime


class SingleConfigTests(unittest.TestCase):
    def test_worker_restart_reads_only_config_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owned = root / 'nightshift'
            owned.mkdir()
            for name in ('worker.sh', 'worker_runtime.py', 'lifecycle.py', 'acceptance.py', 'scratch_review.py', 'project_config.py'):
                shutil.copy2(ROOT / 'nightshift' / name, owned / name)
            (owned / 'adapters').mkdir()
            agent = {'default': True, 'worker': {'step_base': {'L1': 60, 'L2': 40, 'L3': 20}}, 'agent': {'adapter': 'generic', 'command': 'unused'}}
            (owned / 'adapters/agents.json').write_text(json.dumps({'legacy': agent, 'legacy2': agent}))
            config = owned / 'config.json'
            config.write_text(json.dumps({'version': 1, 'agents': {'one': agent}}))
            env = {**os.environ, 'RUN_ONCE': '1', 'POLL_INTERVAL': '0',
                   'AGENT_CONFIG_FILE': str(owned / 'adapters/agents.json'),
                   'AI_AGENTS_JSON': json.dumps([{'id': 'env', 'adapter': 'generic', 'command': 'unused'}])}
            def start():
                result = subprocess.run(['bash', str(owned / 'worker.sh')], cwd=root, env=env,
                                        capture_output=True, text=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result.stdout
            self.assertIn('Registered adapters: 1', start())
            config.write_text(json.dumps({'version': 1, 'agents': {'one': agent, 'two': agent, 'three': agent}}))
            self.assertIn('Registered adapters: 3', start())

    def test_legacy_files_do_not_override_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            owned = root / "nightshift"
            (owned / "adapters").mkdir(parents=True)
            (owned / "config.json").write_text(json.dumps({"version": 1}))
            (owned / "acceptance.json").write_text(json.dumps({"version": 1, "hot": "true"}))
            (owned / "adapters/agents.json").write_text(json.dumps({"old": {"agent": {"adapter": "generic", "command": "old"}}}))
            self.assertEqual(worker_runtime.load_agent_registry(owned / "config.json"), [])
            with self.assertRaises(acceptance.GateError):
                acceptance.config(root)

    def test_agent_requires_valid_level_budgets(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            agent = {"agent": {"adapter": "generic", "command": "unused"}}
            for ladder in (None, {"L1": 1, "L2": 2}, {"L1": 1, "L2": 2, "L3": 0},
                           {"L1": 1, "L2": 2, "L3": True}):
                agent["worker"] = {"step_base": ladder}
                path.write_text(json.dumps({"version": 1, "agents": {"test": agent}}))
                with self.subTest(ladder=ladder), self.assertRaisesRegex(ValueError, "worker.step_base"):
                    worker_runtime.load_agent_registry(path)

    def test_failover_rebuilds_budget_and_prompt_for_each_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = argparse.Namespace(
                task_id="TASK-1", title="TASK-1 | LEVEL: 2 | TARGET: file", constraints="",
                work_dir=str(root), target="file", level="2", verify="true", timeout=1800,
                target_file_count=2, step_per_file=5, progress_file="progress.log",
                prompt_file=str(root / "prompt"), output_file=str(root / "output"),
                result_file=str(root / "result"), step_budget=0, research_step_budget=100)
            agents = []
            for name, base in (("first", 25), ("second", 45)):
                agents.append({"id": name, "adapter": "generic", "command": "unused", "worker": {
                    "task_timeout_seconds": base, "step_base": {"L1": base, "L2": base, "L3": base}}})
            attempts = []
            def execute(attempt):
                attempts.append((attempt.agent_id, attempt.step_budget, attempt.timeout,
                                 Path(attempt.prompt_file).read_text()))
                return 1 if len(attempts) == 1 else 0
            with mock.patch.object(worker_runtime, "capture_attempt_baseline"), \
                 mock.patch.object(worker_runtime, "execute_adapter_task", side_effect=execute):
                code, _ = worker_runtime.execute_registered_agents(args, agents, root / "state.json", lambda *_: None)
            self.assertEqual(code, 0)
            self.assertEqual([(a, b, t) for a, b, t, _ in attempts],
                             [("first", 35, 25), ("second", 55, 45)])
            self.assertIn("(25+2", attempts[0][3])
            self.assertIn("(45+2", attempts[1][3])
