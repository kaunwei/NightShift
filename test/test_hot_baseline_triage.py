"""Use a real hot runner and Git worktree to distinguish baseline from ticket failures."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import acceptance
import worker_runtime as runtime


class HotBaselineTests(unittest.TestCase):
    def exercise(self, baseline, candidate):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory).resolve()
            root = parent / "project"
            (root / "test").mkdir(parents=True)
            (root / "scripts").mkdir()
            (root / "scripts/config.json").write_text(json.dumps({"version": 1, "acceptance": {
                "hot": shlex.join([sys.executable, str(SCRIPTS / "unittest_hot.py")]), "hot_timeout": 20}}))
            source = root / "test/test_sample.py"
            source.write_text("import unittest\nfrom pathlib import Path\n"
                              "class Cases(unittest.TestCase):\n"
                              "    def test_existing(self):\n"
                              "        self.assertEqual(Path('value').read_text(), 'green')\n")
            (root / "value").write_text(baseline)
            def git(*argv):
                return subprocess.check_output(["git", "-C", str(root), *argv], text=True).strip()
            git("init", "-q")
            git("config", "user.name", "Fixture")
            git("config", "user.email", "fixture@example.invalid")
            git("add", ".")
            git("commit", "-qm", "base")
            base = git("rev-parse", "HEAD")
            (root / "value").write_text(candidate)
            with source.open("a") as stream:
                stream.write("    def test_new(self):\n        self.assertTrue(Path('value').exists())\n")
            args = argparse.Namespace(work_dir=str(root), base=base, task_id="TASK-X",
                                      verify="", worker_port="3001")
            with patch.dict(os.environ, {"NIGHTSHIFT_STATE_DIR": str(parent / "runner")}, clear=True):
                with self.assertRaises(acceptance.HotFailure) as failure:
                    acceptance.hot(args, {"tdd_cases": [
                        {"id": "test_sample.Cases.test_new", "source": "test/test_sample.py"}]}, runtime.run_verify)
            self.assertEqual(git("rev-parse", "HEAD"), base)
            self.assertEqual((root / "value").read_text(), candidate)
            self.assertEqual(git("worktree", "list", "--porcelain").count("worktree "), 1)
            return failure.exception

    def test_existing_case_passes_baseline(self):
        failure = self.exercise("green", "red")
        self.assertEqual(failure.kind, "ticket_regression")
        self.assertEqual(failure.evidence["baseline_failed_cases"], [])

    def test_existing_case_already_fails_baseline(self):
        failure = self.exercise("red", "red")
        self.assertEqual(failure.kind, "baseline_regression")
        self.assertEqual(failure.evidence["baseline_failed_cases"], ["test_sample.Cases.test_existing"])

    def test_returned_124_and_enforced_deadline_are_distinct(self):
        for command, expected in (("exit 124", False), ("sleep 2", True)):
            code, output = runtime.run_verify(command, ".", 3001, .15)
            self.assertEqual(code, 124)
            self.assertEqual(output.timed_out, expected)


class SharedAgentBudgetTests(unittest.TestCase):
    def exercise(self, elapsed, actions):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            args = argparse.Namespace(work_dir=temp, task_id="TASK-X", title="TASK-X",
                                      timeout=10, output_file=str(root / "out"), result_file=str(root / "result"))
            agents = [{"id": name, "adapter": "generic", "command": "test",
                       "worker": {"task_timeout_seconds": 6}} for name in ("a", "b")]
            clock, budgets, rollbacks = [100], [], []

            def execute(attempt):
                budgets.append(attempt.timeout)
                status = "execution_timeout" if attempt.agent_id == "a" else "complete"
                Path(args.output_file).write_text(json.dumps({"status": status}))
                Path(args.result_file).write_text(json.dumps({"actions_used": actions}))
                if status == "execution_timeout":
                    clock[0] += elapsed
                    return 124
                return 0

            with patch.object(runtime.time, "monotonic", side_effect=lambda: clock[0]), \
                    patch.object(runtime, "capture_attempt_baseline"), \
                    patch.object(runtime, "execute_adapter_task", side_effect=execute):
                code, _ = runtime.execute_registered_agents(args, agents, {},
                                                            lambda *call: rollbacks.append(call))
            self.assertEqual(len(rollbacks), 1)
            return code, budgets

    def test_fallback_receives_only_remaining_time(self):
        self.assertEqual(self.exercise(6, 0), (0, [6, 4]))

    def test_expired_or_productive_ticket_does_not_restart_on_another_adapter(self):
        self.assertEqual(self.exercise(10, 0), (124, [6]))
        self.assertEqual(self.exercise(6, 1), (124, [6]))
