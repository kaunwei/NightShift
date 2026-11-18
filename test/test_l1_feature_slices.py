"""Complete workflows through real daemon, permanent tests, scope audit and Git."""
import json
import os
import shlex
import sys
from unittest.mock import patch

from test_runtime_hardening import Fixture, SCRIPTS
import test_ticket_granularity as fixtures


class L1FeatureSliceTests(Fixture):
    cli = fixtures.TicketIntegrationTests.cli
    dispatch = fixtures.TicketIntegrationTests.dispatch

    def setUp(self):
        super().setUp()
        environment = patch.dict(os.environ, {"STEP_PER_FILE": "5"})
        environment.start()
        self.addCleanup(environment.stop)
        (self.root / "tests").mkdir()
        (self.root / ".gitignore").write_text("__pycache__/\n")
        self.plan = self.base / "plan.json"
        self.wrapper = self.base / "worker.py"
        self.config_path = self.config(acceptance={
            "hot": shlex.join([sys.executable, str(SCRIPTS / "unittest_hot.py"), "--start", "tests"]),
            "hot_timeout": 10})
        cfg = json.loads(self.config_path.read_text())
        cfg["agents"]["fixture"]["agent"].update(
            args=[str(self.wrapper)], env={"FIXTURE_PLAN": str(self.plan)}, config={"initial_score": 5})
        self.config_path.write_text(json.dumps(cfg))
        source = self.root / "src"
        source.mkdir()
        (source / "__init__.py").write_text("")
        for name, code in {
            "input_event.py": "def normalize(raw): return raw\n",
            "state.py": "def update(amount): return amount\n",
            "workflow.py": "def submit(raw): return raw\n",
        }.items():
            (source / name).write_text(code)
        self.git("add", ".")
        self.git("commit", "-qm", "workflow baseline")
        self.head = self.git("rev-parse", "HEAD").decode().strip()
        self.wrapper.write_text('''import json, os, subprocess, sys
from pathlib import Path
p=json.loads(Path(os.environ['FIXTURE_PLAN']).read_text())
artifact=Path(os.environ['FIXTURE_PLAN']).parent
(artifact/'worker-prompt.txt').write_text(Path(os.environ['NIGHTSHIFT_PROMPT_FILE']).read_text())
if os.environ.get('NIGHTSHIFT_EXECUTION_KIND')=='closeout':
 result={'outcome':'blocked','diagnostic':'fixture closeout'}
else:
 Path('src/input_event.py').write_text('def normalize(raw): return int(raw.strip())\\n')
 Path('src/state.py').write_text('def update(amount): return amount * 2\\n')
 expression='normalize(raw)' if p.get('broken_flow') else 'update(normalize(raw))'
 Path('src/workflow.py').write_text('from src.input_event import normalize\\nfrom src.state import update\\ndef submit(raw): return '+expression+'\\n')
 Path('src/workflow.py.uid').write_text('fixture-generated-uid\\n')
 code='import unittest\\nfrom src.input_event import normalize\\nfrom src.state import update\\nfrom src.workflow import submit\\nclass Workflow(unittest.TestCase):\\n def test_input(self): self.assertEqual(normalize(" 5 "), 5)\\n def test_state(self): self.assertEqual(update(5), 10)\\n'
 names=['test_input','test_state']
 if not p.get('local_only'):
  if p.get('skip_integration'): code+=' @unittest.skip("fixture missing combined check")\\n'
  code+=' def test_combined(self): self.assertEqual(submit(" 5 "), 10)\\n'
  names.append('test_combined')
 Path('tests/test_workflow.py').write_text(code)
 local=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_workflow.py','-k','test_input'],capture_output=True,text=True)
 state=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-p','test_workflow.py','-k','test_state'],capture_output=True,text=True)
 (artifact/'local-checks.json').write_text(json.dumps({'input':local.returncode,'state':state.returncode,'output':local.stderr+state.stderr}))
 if p.get('outside'):
  Path('src_extra').mkdir()
  Path('src_extra/escape.py').write_text('unexpected = True\\n')
 result={'outcome':'complete','commit_message':'feat: normalize and update through complete workflow',
         'tdd_cases':[{'id':'test_workflow.Workflow.'+n,'source':'tests/test_workflow.py'} for n in names]}
Path(os.environ['NIGHTSHIFT_RESULT_FILE']).write_text(json.dumps(result))
''')

    def title(self, *, files=5, target="src,tests", local_only=False, verify="true"):
        cases = "" if local_only else " | CASES: test_workflow.Workflow.test_combined"
        return (f"TASK-WORKFLOW [CODE: FEAT] | LEVEL: 1 | TARGET: {target} | FILES: {files}"
                f" | ACTION: Normalize request, update state and return combined result{cases} | VERIFY: {verify}")

    def assert_local_checks_pass(self):
        checks = json.loads((self.base / "local-checks.json").read_text())
        self.assertEqual(checks["input"], 0, checks["output"])
        self.assertEqual(checks["state"], 0, checks["output"])
        self.assertIn("Ran 1 test", checks["output"])

    def report(self):
        return json.loads(next((self.runner / "lifecycle/reports").glob("*/report.json")).read_text())

    def assert_not_committed(self):
        self.assertEqual(self.git("rev-parse", "HEAD").decode().strip(), self.head)
        self.assertTrue((self.runner / "lifecycle/paused.json").is_file())

    def test_directory_targets_accept_new_files_and_budget_is_not_file_cap(self):
        # Five changed/new files, only two TARGET entries and an estimate of four.
        self.dispatch(self.title(files=4))
        self.assert_local_checks_pass()
        record = json.loads(next((self.runner / "lifecycle/tasks").glob("*.json")).read_text())
        self.assertEqual(record["phase"], "accepted")
        self.assertIn("test_workflow.Workflow.test_combined", record["result"]["hot"]["cases"])
        self.assertNotEqual(self.git("rev-parse", "HEAD").decode().strip(), self.head)
        changed = self.git("diff", "--name-only", self.head, "HEAD").decode().splitlines()
        self.assertEqual(set(changed), {"src/input_event.py", "src/state.py", "src/workflow.py",
                                       "src/workflow.py.uid", "tests/test_workflow.py"})
        prompt = (self.base / "worker-prompt.txt").read_text()
        self.assertTrue(prompt.isascii())
        self.assertIn("10+4*5", prompt)
        self.assertIn("TARGET authorizes listed files and directory descendants", prompt)
        self.assertIn("grants no paths and sets no changed-file cap", prompt)

    def test_local_passes_do_not_hide_broken_combined_result(self):
        self.dispatch(self.title(), broken_flow=True)
        self.assert_local_checks_pass()
        self.assert_not_committed()
        error = self.report()["result"]["runtime_error"]
        self.assertEqual(error["phase"], "hot")
        self.assertIn("test_combined", json.dumps(error))

    def test_skipped_required_integration_case_is_rejected(self):
        self.dispatch(self.title(), skip_integration=True)
        self.assert_local_checks_pass()
        self.assert_not_committed()
        self.assertEqual(self.report()["result"]["runtime_error"]["phase"], "hot")

    def test_generous_files_does_not_authorize_sibling_directory(self):
        self.dispatch(self.title(files=100), outside=True)
        self.assert_local_checks_pass()
        self.assert_not_committed()
        error = self.report()["result"]["runtime_error"]
        self.assertEqual(error["phase"], "pre_commit_audit")
        self.assertIn("src_extra/escape.py", error["message"])
        self.assertIn("Target Whitelist Violation", error["message"])

    def test_generated_sibling_requires_scope_when_only_exact_sources_authorized(self):
        target = "src/input_event.py,src/state.py,src/workflow.py,tests"
        self.dispatch(self.title(target=target))
        self.assert_local_checks_pass()
        self.assert_not_committed()
        error = self.report()["result"]["runtime_error"]
        self.assertEqual(error["phase"], "pre_commit_audit")
        self.assertIn("src/workflow.py.uid", error["message"])

    def test_extra_verify_checks_combined_result_when_hot_has_only_local_checks(self):
        verify = shlex.join([sys.executable, "-c",
                             "from src.workflow import submit; assert submit(' 5 ') == 10"])
        self.dispatch(self.title(local_only=True, verify=verify), broken_flow=True, local_only=True)
        self.assert_local_checks_pass()
        self.assert_not_committed()
        error = self.report()["result"]["runtime_error"]
        self.assertEqual(error["kind"], "task_verify")
        self.assertIn("AssertionError", json.dumps(error))

    def test_extra_verify_accepts_combined_result_and_larger_files_increases_budget(self):
        verify = shlex.join([sys.executable, "-c",
                             "from src.workflow import submit; assert submit(' 5 ') == 10"])
        self.dispatch(self.title(files=8, local_only=True, verify=verify), local_only=True)
        self.assert_local_checks_pass()
        record = json.loads(next((self.runner / "lifecycle/tasks").glob("*.json")).read_text())
        self.assertEqual(record["phase"], "accepted")
        self.assertIn("10+8*5", (self.base / "worker-prompt.txt").read_text())
        self.assertNotEqual(self.git("rev-parse", "HEAD").decode().strip(), self.head)

    def test_missing_explicit_integration_case_is_rejected(self):
        self.dispatch(self.title(), local_only=True)
        self.assert_local_checks_pass()
        self.assert_not_committed()
        self.assertIn("test_workflow.Workflow.test_combined", json.dumps(self.report()["result"]["runtime_error"]))
