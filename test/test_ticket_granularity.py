"""Ticket contracts through real Git, permanent unittest evidence and daemon CLI."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import unittest
from unittest.mock import patch

from test_runtime_hardening import Fixture, SCRIPTS
import acceptance as gate
import outcome_policy
import ticket_policy
import worker_runtime as runtime


class TicketIntegrationTests(Fixture):
    def setUp(self):
        super().setUp()
        (self.root / "calc.py").write_text("def _value(): return 1\ndef value(): return _value()\n")
        (self.root / "tests").mkdir()
        (self.root / "tests/test_behavior.py").write_text(
            "import unittest\nfrom calc import value\nclass Behavior(unittest.TestCase):\n"
            " def test_existing(self): self.assertIsInstance(value(),int)\n")
        (self.root / ".gitignore").write_text("__pycache__/\n")
        self.git("add", "."); self.git("commit", "-qm", "permanent baseline")
        self.plan = self.base / "plan.json"
        self.wrapper = self.base / "worker.py"
        self.wrapper.write_text('''import json,os
from pathlib import Path
p=json.loads(Path(os.environ['FIXTURE_PLAN']).read_text())
kind=p.get('kind','mechanical')
if os.environ.get('NIGHTSHIFT_EXECUTION_KIND')=='closeout':
 result={'outcome':'blocked','diagnostic':'fixture closeout'}
elif kind=='verify':
 result={'outcome':'no_change','no_change_reason':'verification only'}
elif kind=='research':
 target=Path(p['report']);target.parent.mkdir(parents=True,exist_ok=True);target.write_text('# Research\\nBounded inconclusive result.\\n')
 result={'outcome':'complete','commit_message':'docs: bounded report','research_conclusion':'inconclusive'}
else:
 result={'outcome':'complete','commit_message':'refactor: equivalent implementation'}
 if kind=='mechanical':
  Path('calc.py').write_text(Path('calc.py').read_text().replace('_value','_current'))
 elif kind=='unchanged': pass
 else:
  Path('calc.py').write_text("def value(): return 'bad'\\n")
  name='test_'+os.environ['NIGHTSHIFT_TASK_ID'].replace('-','_')
  with Path('tests/test_behavior.py').open('a') as f:f.write(' def '+name+'(self): self.assertTrue(True)\\n')
  result['tdd_cases']=[{'id':'test_behavior.Behavior.'+name,'source':'tests/test_behavior.py'}]
 if p.get('forged_mode'): result['evidence_mode']='EXISTING'
 if p.get('change_case'):
  path=Path('tests/test_behavior.py');path.write_text(path.read_text().replace('self.assertIsInstance(value(),int)','self.assertEqual(value(),1)'))
Path(os.environ['NIGHTSHIFT_RESULT_FILE']).write_text(json.dumps(result))
''')
        self.config_path = self.config(acceptance={"hot": shlex.join([sys.executable, str(SCRIPTS / "unittest_hot.py"), "--start", "tests"]), "hot_timeout": 10})
        cfg = json.loads(self.config_path.read_text())
        cfg["agents"]["fixture"]["agent"].update(args=[str(self.wrapper)], env={"FIXTURE_PLAN": str(self.plan)}, config={"initial_score": 5})
        self.config_path.write_text(json.dumps(cfg))
        self.head = self.git("rev-parse", "HEAD").decode().strip()

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / "worker_runtime.py"), *map(str, args)],
                              capture_output=True, text=True, timeout=30,
                              env={**os.environ, "WORKER_ID": "default", "POLL_INTERVAL": "0.01"})

    def dispatch(self, title, **plan):
        self.plan.write_text(json.dumps(plan))
        (self.runner / "tasks.txt").write_text(title + "\n")
        result = self.cli("daemon", "--root", self.root, "--config", self.config_path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def score(self):
        return json.loads(runtime.registered_agent_score_path(self.runner / ".worker-agent-scores", "fixture").read_text())

    def test_low_initial_capability_keeps_broad_task_queued_then_accepts_narrow_task(self):
        cfg = json.loads(self.config_path.read_text())
        cfg["agents"]["fixture"]["agent"]["config"]["initial_score"] = 1
        self.config_path.write_text(json.dumps(cfg))
        self.plan.write_text('{}')
        title = "TASK-L [CODE: REFACTOR] | LEVEL: 1 | TARGET: calc.py | EVIDENCE: EXISTING | CASES: test_behavior.Behavior.test_existing"
        queue = self.runner / "tasks.txt"; queue.write_text(title + "\n")
        blocked = self.cli("daemon", "--root", self.root, "--config", self.config_path)
        self.assertEqual(blocked.returncode, 2, blocked.stdout + blocked.stderr)
        self.assertIn("exceeds all eligible Worker capabilities", blocked.stdout)
        self.assertEqual(queue.read_text(), title + "\n")
        self.assertFalse((self.runner / ".worker-agent-scores").exists())
        self.assertEqual(self.git("rev-parse", "HEAD").decode().strip(), self.head)
        self.dispatch(title.replace("LEVEL: 1", "LEVEL: 3"))
        self.assertEqual(self.score()["score"], 1)
        self.assertEqual(self.score()["success_window"], ["TASK-L"])

    def test_persisted_low_score_overrides_high_adapter_initial_score(self):
        runtime.initialize_agent_score(self.runner / ".worker-agent-scores", "fixture", 1)
        queue = self.runner / "tasks.txt"
        queue.write_text("TASK-L [CODE: FIX] | LEVEL: 2 | TARGET: calc.py\n")
        before = self.score()
        blocked = self.cli("daemon", "--root", self.root, "--config", self.config_path)
        self.assertEqual(blocked.returncode, 2, blocked.stdout + blocked.stderr)
        self.assertEqual(self.score(), before)
        self.assertIn("TASK-L", queue.read_text())

    def test_direct_task_cli_cannot_bypass_level_guard(self):
        prompt = self.base / "direct-prompt"; prompt.write_text("fixture")
        marker = self.base / "unauthorized-start"
        blocked = self.cli("task-cli", "--adapter", "generic", "--executable", sys.executable,
            "--extra-arg", SCRIPTS / "adapters/generic.py", "--overrides",
            json.dumps({"initial_score": 1, "executable": sys.executable,
                        "args": ["-c", f"from pathlib import Path;Path({str(marker)!r}).touch()"]}),
            "--work-dir", self.root, "--prompt-file", prompt,
            "--output-file", self.base / "direct-output", "--title", "TASK-L | LEVEL: 1", "--level", "3")
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("exceeds Worker", blocked.stdout + blocked.stderr)
        self.assertFalse(marker.exists())

    def test_routing_skips_weak_default_for_capable_registration(self):
        cfg = json.loads(self.config_path.read_text())
        strong = json.loads(json.dumps(cfg["agents"]["fixture"]))
        cfg["agents"]["fixture"]["agent"]["config"]["initial_score"] = 1
        cfg["agents"]["strong"] = strong
        self.config_path.write_text(json.dumps(cfg))
        self.dispatch("TASK-L [CODE: REFACTOR] | LEVEL: 1 | TARGET: calc.py | EVIDENCE: EXISTING | CASES: test_behavior.Behavior.test_existing")
        records = [json.loads(p.read_text()) for p in (self.runner / "lifecycle/tasks").glob("*.json")]
        self.assertEqual(records[0]["result"]["registration_id"], "strong")
        self.assertFalse(runtime.registered_agent_score_path(self.runner / ".worker-agent-scores", "fixture").exists())

    def test_l3_mechanical_ticket_reuses_pinned_cases_and_full_hot(self):
        self.dispatch("TASK-M [CODE: REFACTOR] | LEVEL: 3 | TARGET: calc.py | EVIDENCE: EXISTING | CASES: test_behavior.Behavior.test_existing | VERIFY: true")
        records = [json.loads(p.read_text()) for p in (self.runner / "lifecycle/tasks").glob("*.json")]
        self.assertEqual(records[0]["phase"], "accepted")
        self.assertEqual(records[0]["result"]["hot"]["evidence_mode"], "EXISTING")
        self.assertIn("test_behavior.Behavior.test_existing", records[0]["result"]["hot"]["cases"])
        self.assertEqual((self.root / "tests/test_behavior.py").read_text().count("def test_"), 1)
        self.assertEqual(self.score()["success_window"], ["TASK-M"])

    def test_worker_cannot_forge_existing_mode_for_behavior_ticket(self):
        self.dispatch("TASK-X [CODE: FIX] | LEVEL: 3 | TARGET: calc.py | VERIFY: true", forged_mode=True)
        report = json.loads(next((self.runner / "lifecycle/reports").glob("*/report.json")).read_text())
        self.assertIn("nonempty tdd_cases", report["result"]["runtime_error"]["message"])
        self.assertEqual(report["result"]["score_attribution"]["category"], "evidence_contract")
        self.assertEqual(self.git("rev-parse", "HEAD").decode().strip(), self.head)

    def test_invalid_contract_stays_queued_without_model_or_score(self):
        title = "TASK-X [CODE: FIX] | EVIDENCE: EXISTING | CASES: test_behavior.Behavior.test_existing"
        self.plan.write_text('{}')
        queue = self.runner / "tasks.txt"; queue.write_text(title + "\n")
        result = self.cli("daemon", "--root", self.root, "--config", self.config_path)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(queue.read_text(), title + "\n")
        self.assertEqual(json.loads((self.runner / "worker.status").read_text())["state"], "CONTRACT_BLOCKED")
        self.assertFalse((self.runner / ".worker-agent-scores").exists())

    def test_missing_pinned_case_cannot_accept_mechanical_change(self):
        self.dispatch("TASK-X [CODE: REFACTOR] | TARGET: calc.py | EVIDENCE: EXISTING | CASES: test_unknown.Behavior.missing | VERIFY: true")
        self.assertTrue((self.runner / "lifecycle/paused.json").is_file())
        self.assertEqual(self.git("rev-parse", "HEAD").decode().strip(), self.head)

    def test_changed_pinned_case_cannot_accept_mechanical_change(self):
        self.dispatch("TASK-X [CODE: REFACTOR] | TARGET: calc.py,tests | EVIDENCE: EXISTING | CASES: test_behavior.Behavior.test_existing | VERIFY: true", change_case=True)
        self.assertTrue((self.runner / "lifecycle/paused.json").is_file())
        self.assertEqual(self.git("rev-parse", "HEAD").decode().strip(), self.head)

    def test_skipped_pinned_case_cannot_accept_mechanical_change(self):
        source = self.root / "tests/test_behavior.py"
        source.write_text(source.read_text().replace(" def test_existing", " @unittest.skip('fixture')\n def test_existing"))
        self.git("add", "."); self.git("commit", "-qm", "skipped baseline case")
        self.head = self.git("rev-parse", "HEAD").decode().strip()
        self.dispatch("TASK-X [CODE: REFACTOR] | TARGET: calc.py | EVIDENCE: EXISTING | CASES: test_behavior.Behavior.test_existing | VERIFY: true")
        self.assertTrue((self.runner / "lifecycle/paused.json").is_file())
        self.assertEqual(self.git("rev-parse", "HEAD").decode().strip(), self.head)

    def test_verification_only_executes_actual_command_without_commit_or_credit(self):
        marker = self.runner / "verified"
        verify = shlex.join([sys.executable, "-c", f"from pathlib import Path;Path({str(marker)!r}).write_text('ran')"])
        self.dispatch("TASK-V [VERIFY] | LEVEL: 3 | VERIFY: " + verify, kind="verify")
        self.assertEqual(marker.read_text(), "ran")
        self.assertEqual(self.git("rev-parse", "HEAD").decode().strip(), self.head)
        self.assertEqual(self.score()["success_window"], [])
        self.assertEqual(self.score()["feedback"][-1]["result"], "no_fault")

    def test_failed_verification_only_is_blocked_even_if_worker_says_no_change(self):
        self.dispatch("TASK-V [VERIFY] | VERIFY: exit 7", kind="verify")
        self.assertTrue((self.runner / "lifecycle/paused.json").is_file())
        report = json.loads(next((self.runner / "lifecycle/reports").glob("*/report.json")).read_text())
        self.assertEqual(report["result"]["runtime_verify"]["exit"], 7)
        self.assertEqual(report["result"]["score_attribution"]["category"], "verification")

    def test_verification_command_cannot_edit_product_or_run_zero_tests(self):
        for command in ("echo changed > calc.py", "python3 -m unittest discover -s empty"):
            with self.subTest(command=command):
                if command.endswith("empty"):
                    (self.root / "empty").mkdir()
                self.dispatch("TASK-V [VERIFY] | VERIFY: " + command, kind="verify")
                self.assertTrue((self.runner / "lifecycle/paused.json").is_file())
                self.assertEqual(self.git("rev-parse", "HEAD").decode().strip(), self.head)
                self.assertEqual(self.score()["success_window"], [])
                self.assertEqual(self.cli("restart", "--root", self.root, "--config", self.config_path).returncode, 0)

    def test_distinct_proven_regressions_reduce_score_and_gate_level_change(self):
        for identity in ("TASK-A", "TASK-B"):
            self.dispatch(identity + " [CODE: FIX] | LEVEL: 3 | TARGET: calc.py,tests | VERIFY: true", kind="regression")
            if identity == "TASK-A":
                self.assertEqual(self.score()["score"], 5)
                result = self.cli("restart", "--root", self.root, "--config", self.config_path)
                self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.score()["score"], 4)
        self.assertEqual(self.score()["attributable_failure_streak"], 2)
        self.assertTrue((self.runner / ".worker-dispatch-gate.json").exists())
        for report in (self.runner / "lifecycle/reports").glob("*/report.json"):
            data = json.loads(report.read_text())
            self.assertEqual(data["result"]["score_attribution"]["category"], "ticket_regression")

    def test_research_completion_does_not_inflate_development_score(self):
        report = self.runner / "reports/research/SUMMARY.md"
        self.dispatch("TASK-R [RESEARCH] | LEVEL: 3 | TARGET: " + str(report.parent) + " | VERIFY: REPORT_ONLY", kind="research", report=str(report))
        self.assertEqual(self.score()["success_window"], [])
        self.assertEqual(self.score()["feedback"][-1]["result"], "no_fault")


class BudgetAndScoreTests(Fixture):
    def test_level_permission_matrix_and_missing_level_default(self):
        scores = self.runner / "scores"
        for score in range(1, 6):
            agent = {"id": str(score)}
            runtime.initialize_agent_score(scores, agent["id"], score)
            for level in (1, 2, 3):
                self.assertEqual(runtime.agent_allows_level(agent, f"TASK-X | LEVEL: {level}", scores),
                                 level >= runtime.score_task_level(score))
            self.assertEqual(runtime.agent_allows_level(agent, "TASK-X", scores), score == 5)

    def test_directory_contents_do_not_change_planned_count_and_floor(self):
        (self.root / "src").mkdir()
        for i in range(100): (self.root / "src" / str(i)).write_text("unrelated")
        raw = "TASK-X | LEVEL: 3 | TARGET: src,src/,tests | FILES: 3"
        self.assertEqual(ticket_policy.planned_files(raw), 3)
        worker = {"step_base": {"L1": 60, "L2": 40, "L3": 20}}
        self.assertEqual(ticket_policy.preparation_base(worker, 3), 40)
        self.assertEqual(ticket_policy.preparation_base({**worker, "preparation_steps": 50}, 3), 50)

    def test_parser_preserves_actions_and_validates_contract_fields(self):
        raw = "TASK-X | ACTION: fix x | FILES: 2 | EVIDENCE: CHANGED | VERIFY: true"
        self.assertEqual(runtime.task_field(raw, "ACTION"), "fix x")
        self.assertEqual(ticket_policy.validate(raw)["planned_files"], 2)
        for bad in ("TASK-X | FILES: 0", "TASK-X | EVIDENCE: magical", "TASK-X [VERIFY] | VERIFY: none", "TASK-X [CODE: REFACTOR] | EVIDENCE: EXISTING"):
            with self.subTest(bad=bad), self.assertRaises(ValueError): ticket_policy.validate(bad)

    def test_registration_failures_cross_ids_neutral_replay_and_recovery(self):
        path = self.runner / "score.json"
        for i in range(8):
            result = runtime.record_score_result(path, f"TASK-{i}", "attributable_failure", event_id=str(i))
            self.assertEqual(result["score"], max(1, 5 - (i + 1) // 2))
            runtime.record_score_result(path, f"TASK-{i}", "attributable_failure", event_id=str(i))
            runtime.record_score_result(path, "TASK-ENV", "no_fault")
        self.assertEqual(json.loads(path.read_text())["attributable_failure_streak"], 8)
        for i in range(5): runtime.record_score_result(path, f"TASK-PASS-{i}", "accept")
        state = json.loads(path.read_text())
        self.assertEqual(state["score"], 2)
        self.assertEqual(state["attributable_failure_streak"], 0)

    def test_attribution_does_not_invent_blame_for_unknown_timeouts(self):
        for kind in ("baseline_regression", "timeout", "undetermined", "evidence_contract"):
            self.assertFalse(outcome_policy.classify({"runtime_error": {"phase": "hot", "kind": kind}})["attributable"])
        self.assertTrue(outcome_policy.classify({"runtime_error": {"phase": "hot", "kind": "ticket_regression"}})["attributable"])
        self.assertTrue(outcome_policy.classify({"terminal_status": "step_budget_exceeded"})["attributable"])
        self.assertFalse(outcome_policy.classify({"terminal_status": "step_budget_exceeded"}, research=True)["attributable"])
        self.assertFalse(outcome_policy.classify({"terminal_status": "execution_timeout", "actions_used": 0})["attributable"])

    def test_primary_candidate_traceback_survives_unsupported_isolation(self):
        runner = gate.DefaultAcceptanceRunner()
        case = {"id": "test_case", "status": "failed"}
        permanent = {"test_case": {"baseline_fingerprint": "a" * 64}}
        args = type("Args", (), {"base": self.head})()
        error = runner.classify_failure(self.root, {}, args, None, permanent, {"test_case": case},
            {"supports_case_selection": False, "output": "Traceback: KeyError max_core"})
        self.assertIn("KeyError max_core", str(error))
        self.assertIn("classification_limitation", error.evidence)
        self.assertEqual(error.kind, "undetermined")


if __name__ == "__main__": unittest.main()
