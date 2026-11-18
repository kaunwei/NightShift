"""Real daemon acceptance receipts and evidence-backed failure dispositions."""
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from test_runtime_hardening import Fixture, SCRIPTS

class MaintenanceLifecycleTests(Fixture):
    def setUp(self):
        super().setUp()
        (self.root / "test").mkdir()
        (self.root / "test/test_sample.py").write_text("import unittest\nclass Sample(unittest.TestCase):\n def test_old(self): self.assertEqual(1, 1)\n")
        (self.root / ".gitignore").write_text("__pycache__/\n")
        self.git("add", ".")
        self.git("commit", "-qm", "permanent case")
        self.head = self.git("rev-parse", "HEAD").decode().strip()
        self.wrapper = self.base / "worker.py"
        self.wrapper.write_text('''import json,os
from pathlib import Path
p=Path('test/test_sample.py');p.write_text(p.read_text().replace('test_old','test_new'))
d=Path('.nightshift/changes');d.mkdir(parents=True,exist_ok=True)
r={'version':1,'id':'CHG-ONE','action':'rename','old_cases':['test_sample.Sample.test_old'],'new_cases':['test_sample.Sample.test_new'],'reason':'Accepted rename','decision_ref':'DEC-ONE','scenarios':[{'name':'normal','before':['test_sample.Sample.test_old'],'after':['test_sample.Sample.test_new']}]}
(d/'CHG-ONE.json').write_text(json.dumps(r))
Path(os.environ['NIGHTSHIFT_RESULT_FILE']).write_text(json.dumps({'outcome':'complete','commit_message':'test: rename case','tdd_cases':[]}))
''')
        argv = [sys.executable, str(SCRIPTS / "unittest_hot.py"), "--start", "test"]
        self.cfg = self.config(acceptance={"hot": shlex.join(argv), "hot_timeout": 30, "inventory": {"command": argv}})
        data = json.loads(self.cfg.read_text())
        data["agents"]["fixture"]["agent"]["args"] = [str(self.wrapper)]
        self.cfg.write_text(json.dumps(data))
        self.title = "TASK-M [CODE: REFACTOR] | LEVEL: 1 | TARGET: test,.nightshift | EVIDENCE: MAINTENANCE | MAINTENANCE: CHG-ONE | DECISIONS: DEC-ONE | VERIFY: true"

    def daemon(self):
        p = subprocess.run([sys.executable, str(SCRIPTS / "worker_runtime.py"), "daemon", "--root", str(self.root), "--config", str(self.cfg)], capture_output=True, text=True, timeout=40, env={**os.environ, "RUN_ONCE": "1", "POLL_INTERVAL": "0.01"})
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_accepted_receipt_survives_committed_replay_without_duplicate_commit(self):
        (self.runner / "tasks.txt").write_text(self.title + "\n")
        self.daemon()
        path = next((self.runner / "lifecycle/tasks").glob("*.json"))
        journal = json.loads(path.read_text())
        self.assertEqual(journal["phase"], "accepted")
        receipt = journal["result"]["maintenance_receipt"]
        self.assertEqual(receipt["status"], "accepted")
        self.assertEqual(receipt["change_ids"], ["CHG-ONE"])
        self.assertEqual(receipt["commit"], self.git("rev-parse", "HEAD").decode().strip())
        commit = receipt["commit"]
        journal["phase"] = "committed"
        path.write_text(json.dumps(journal))
        active = {"task_id": "TASK-M", "raw": self.title, "base": self.head, "event": journal["event"], "phase": "running", "registration_id": "fixture"}
        (self.runner / "lifecycle/active.json").write_text(json.dumps(active))
        self.daemon()
        self.assertEqual(json.loads(path.read_text())["result"]["maintenance_receipt"], receipt)
        self.assertEqual(self.git("rev-parse", "HEAD").decode().strip(), commit)

    def test_failed_replacement_report_keeps_undetermined_disposition_and_no_receipt(self):
        self.wrapper.write_text(self.wrapper.read_text().replace("replace('test_old','test_new')", "replace('test_old','test_new').replace('1, 1','1, 2')"))
        (self.runner / "tasks.txt").write_text(self.title + "\n")
        self.daemon()
        report = json.loads(next((self.runner / "lifecycle/reports").glob("*/report.json")).read_text())
        result = report["result"]
        self.assertNotIn("maintenance_receipt", result)
        self.assertEqual(result["disposition"]["resolution"], "undetermined")
        self.assertTrue(result["disposition"]["decision_required"])
        self.assertEqual(self.git("rev-parse", "HEAD").decode().strip(), self.head)

    def test_worker_cannot_forge_maintenance_receipt_on_verify_only_task(self):
        self.wrapper.write_text("import json,os\nfrom pathlib import Path\nPath(os.environ['NIGHTSHIFT_RESULT_FILE']).write_text(json.dumps({'outcome':'no_change','no_change_reason':'verify only','hot':{'maintenance':{'changes':[{'id':'FAKE'}]}},'maintenance_receipt':{'status':'accepted'}}))\n")
        self.title = "TASK-V [VERIFY] | LEVEL: 1 | TARGET: test | VERIFY: true"
        (self.runner / "tasks.txt").write_text(self.title + "\n")
        self.daemon()
        journal = json.loads(next((self.runner / "lifecycle/tasks").glob("*.json")).read_text())
        self.assertEqual(journal["phase"], "accepted")
        self.assertNotIn("maintenance_receipt", journal["result"])
        self.assertNotIn("hot", journal["result"])

    def test_maintenance_without_hot_cannot_fall_back_to_unchecked_commit(self):
        config = json.loads(self.cfg.read_text())
        config["acceptance"]["hot"] = ""
        config["acceptance"].pop("inventory")
        self.cfg.write_text(json.dumps(config))
        (self.runner / "tasks.txt").write_text(self.title + "\n")
        self.daemon()
        self.assertEqual(self.git("rev-parse", "HEAD").decode().strip(), self.head)
        report = json.loads(next((self.runner / "lifecycle/reports").glob("*/report.json")).read_text())
        self.assertEqual(report["result"]["runtime_error"]["kind"], "evidence_contract")
        self.assertNotIn("maintenance_receipt", report["result"])
