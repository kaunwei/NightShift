"""Maintenance acceptance through real discovery, execution and Git evidence."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import unittest
from unittest.mock import patch
import test_case_inventory as inventory_fixture
SCRIPTS = inventory_fixture.SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import acceptance

class MaintenanceTests(unittest.TestCase):
    setUp = inventory_fixture.InventoryTests.setUp
    git = inventory_fixture.InventoryTests.git

    def change(self, action="rename", new_ids=None):
        old = "test_sample.Sample.test_old"
        new_ids = new_ids if new_ids is not None else ["test_sample.Sample.test_new"]
        record = {"version": 1, "id": "CHG-ONE", "action": action, "old_cases": [old], "new_cases": new_ids,
                  "reason": "Accepted scenario preserved", "decision_ref": "DEC-ONE",
                  "scenarios": [{"name": "value remains one", "before": [old], "after": new_ids}]}
        directory = self.root / ".nightshift/changes"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "CHG-ONE.json"
        path.write_text(json.dumps(record))
        self.source.write_text(self.source.read_text().replace("test_old", "test_new"))
        return path, record

    def hot(self, maintenance="CHG-ONE", mode="MAINTENANCE", declarations=None, hot_command=None):
        cfg = {"hot": shlex.join([sys.executable, str(SCRIPTS / "unittest_hot.py"), "--start", "test"]),
               "hot_timeout": 20, "wiring": [], "inventory": json.loads(self.config.read_text())}
        if hot_command is not None:
            cfg["hot"] = hot_command
        title = f"TASK-M [CODE: REFACTOR] | EVIDENCE: {mode} | MAINTENANCE: {maintenance} | DECISIONS: DEC-ONE"
        args = argparse.Namespace(work_dir=str(self.root), base=self.base, task_id="TASK-M", title=title,
                                  verify="", worker_port="3001", required_cases=[])
        result = {"tdd_cases": declarations or []}
        def run(command, cwd, port, timeout):
            p = subprocess.run(command, cwd=cwd, shell=True, capture_output=True, text=True, timeout=timeout)
            return p.returncode, p.stdout + p.stderr
        with patch.dict(os.environ, {}, clear=True), patch.object(acceptance, "config", return_value=cfg):
            return acceptance.DefaultAcceptanceRunner().run_hot(args, result, run)

    def test_rename_is_accepted_and_replacement_executes(self):
        self.change()
        hot = self.hot()
        self.assertEqual(hot["maintenance"]["removed"], ["test_sample.Sample.test_old"])
        self.assertEqual(hot["cases"], ["test_sample.Sample.test_new"])

    def test_disappearance_without_authorization_is_rejected(self):
        self.change()
        with self.assertRaisesRegex(ValueError, "unauthorized|MAINTENANCE"):
            self.hot(maintenance="", mode="CHANGED", declarations=[{"id": "test_sample.Sample.test_new", "source": "test/test_sample.py"}])

    def test_missing_or_skipped_replacement_and_forged_decision_are_rejected(self):
        path, record = self.change()
        for mutation in ("missing", "skipped", "decision"):
            with self.subTest(mutation=mutation):
                self.source.write_text("import unittest\nclass Sample(unittest.TestCase):\n def test_new(self): self.assertEqual(1, 1)\n")
                record["decision_ref"] = "DEC-ONE"
                record["new_cases"] = ["test_sample.Sample.test_new"]
                if mutation == "missing": record["new_cases"] = ["missing"]
                if mutation == "skipped": self.source.write_text(self.source.read_text().replace(" def test_new", " @unittest.skip('pending')\n def test_new"))
                if mutation == "decision": record["decision_ref"] = "SELF-APPROVED"
                path.write_text(json.dumps(record))
                with self.assertRaises(ValueError): self.hot()

    def test_retirement_only_runs_surviving_cases_without_fabricated_tdd(self):
        path, record = self.change(action="retire", new_ids=[])
        record["removed_requirement"] = "sample.value@1"
        record["scenarios"][0]["removed"] = True
        record["verification_cases"] = ["test_sample.Sample.test_remaining"]
        path.write_text(json.dumps(record))
        self.source.write_text("import unittest\nclass Sample(unittest.TestCase):\n def test_remaining(self): self.assertTrue(True)\n")
        hot = self.hot()
        self.assertEqual(hot["evidence_mode"], "MAINTENANCE")
        self.assertEqual(hot["cases"], ["test_sample.Sample.test_remaining"])

    def test_merge_retains_scenario_mapping_and_runs_survivor(self):
        self.source.write_text(self.source.read_text() + " def test_duplicate(self): self.assertEqual(1, 1)\n")
        self.git("add", "test")
        self.git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "commit", "-qm", "duplicate")
        self.base = self.git("rev-parse", "HEAD").strip()
        path, record = self.change(action="merge")
        duplicate = "test_sample.Sample.test_duplicate"
        self.source.write_text("import unittest\nclass Sample(unittest.TestCase):\n def test_new(self): self.assertEqual(1, 1)\n")
        record["old_cases"].append(duplicate)
        record["scenarios"][0]["before"].append(duplicate)
        path.write_text(json.dumps(record))
        self.assertEqual(self.hot()["cases"], ["test_sample.Sample.test_new"])

    def test_retirement_requires_removed_behavior_and_remaining_verification(self):
        path, record = self.change(action="retire", new_ids=[])
        self.source.write_text("import unittest\nclass Sample(unittest.TestCase):\n def test_remaining(self): self.assertTrue(True)\n")
        with self.assertRaisesRegex(ValueError, "retire"):
            self.hot()

    def test_requirement_migration_and_recreated_id_have_explicit_lineage(self):
        directory = self.root / ".nightshift"
        directory.mkdir()
        req = {"version": 1, "requirements": [{"id": "sample.value", "version": 1, "status": "active", "behavior": "one", "decision_ref": "DEC-ONE"}]}
        old = "test_sample.Sample.test_old"
        new = "test_sample.Sample.test_new"
        coverage = {"version": 1, "cases": [{"id": old, "generation": "initial", "verifies": [{"requirement": "sample.value@1", "scenario": "normal"}]}]}
        (directory / "requirements.json").write_text(json.dumps(req))
        (directory / "coverage.json").write_text(json.dumps(coverage))
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "commit", "-qm", "initial model")
        self.base = self.git("rev-parse", "HEAD").strip()
        path, record = self.change()
        req["requirements"].append({"id": "sample.value", "version": 2, "status": "active", "behavior": "one using renamed observation", "decision_ref": "DEC-ONE", "supersedes": "sample.value@1", "affected_scenarios": ["normal"]})
        (directory / "requirements.json").write_text(json.dumps(req))
        coverage["cases"][0]["id"] = new
        coverage["cases"][0]["verifies"][0]["requirement"] = "sample.value@2"
        (directory / "coverage.json").write_text(json.dumps(coverage))
        self.assertTrue(self.hot()["maintenance"]["traceability"]["enabled"])
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "commit", "-qm", "rename and requirement migration")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.source.write_text(self.source.read_text() + " def test_old(self): self.assertEqual(1, 1)\n")
        coverage["cases"].append({"id": old, "generation": "initial", "verifies": [{"requirement": "sample.value@2", "scenario": "normal"}]})
        (directory / "coverage.json").write_text(json.dumps(coverage))
        with self.assertRaisesRegex(ValueError, "recreated ID"):
            self.hot(maintenance="", mode="CHANGED", declarations=[{"id": old, "source": "test/test_sample.py"}])
        record = {"version": 1, "id": "CHG-TWO", "action": "reintroduce", "old_cases": [], "new_cases": [old], "reason": "New independent case", "decision_ref": "DEC-ONE", "predecessor_change": "CHG-ONE", "scenarios": [{"name": "normal", "before": [], "after": [old]}]}
        (path.parent / "CHG-TWO.json").write_text(json.dumps(record))
        coverage["cases"][-1].update(generation="CHG-TWO", previous_change="CHG-ONE")
        (directory / "coverage.json").write_text(json.dumps(coverage))
        self.assertEqual(self.hot(maintenance="CHG-TWO")["cases"], sorted([old, new]))

    def test_omitted_unrelated_hot_result_is_rejected(self):
        self.source.write_text(self.source.read_text() + " def test_unrelated(self): self.assertEqual(2, 2)\n")
        self.git("add", "test")
        self.git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "commit", "-qm", "unrelated coverage")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.change()
        wrapper = self.root / "hot_wrapper.py"
        code = "import json,os,subprocess,sys\nfrom pathlib import Path\nsubprocess.run([sys.executable," + repr(str(SCRIPTS / "unittest_hot.py")) + ",'--start','test'],check=True)\n"
        code += "if os.environ['NIGHTSHIFT_PHASE']=='run':\n p=Path(os.environ['NIGHTSHIFT_RESULT']);d=json.loads(p.read_text());d['cases']=[c for c in d['cases'] if not c['id'].endswith('test_unrelated')];p.write_text(json.dumps(d))\n"
        wrapper.write_text(code)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.hot(hot_command=shlex.join([sys.executable, str(wrapper)]))

    def test_accepted_maintenance_record_cannot_be_deleted(self):
        path, _ = self.change()
        self.hot()
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "commit", "-qm", "accepted rename")
        self.base = self.git("rev-parse", "HEAD").strip()
        path.unlink()
        self.source.write_text(self.source.read_text().replace("1, 1", "2, 2"))
        with self.assertRaisesRegex(ValueError, "cannot disappear"):
            self.hot(maintenance="", mode="CHANGED", declarations=[{"id": "test_sample.Sample.test_new", "source": "test/test_sample.py"}])

    def test_merge_cannot_drop_a_mapped_active_scenario(self):
        old = "test_sample.Sample.test_old"
        duplicate = "test_sample.Sample.test_duplicate"
        new = "test_sample.Sample.test_new"
        self.source.write_text(self.source.read_text() + " def test_duplicate(self): self.assertEqual(1, 1)\n")
        directory = self.root / ".nightshift"
        directory.mkdir()
        (directory / "requirements.json").write_text(json.dumps({"version": 1, "requirements": [{"id": "sample.value", "version": 1, "status": "active", "behavior": "one across conditions", "decision_ref": "DEC-ONE"}]}))
        coverage = {"version": 1, "cases": [{"id": old, "generation": "initial-normal", "verifies": [{"requirement": "sample.value@1", "scenario": "normal"}]}, {"id": duplicate, "generation": "initial-edge", "verifies": [{"requirement": "sample.value@1", "scenario": "edge"}]}]}
        (directory / "coverage.json").write_text(json.dumps(coverage))
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "commit", "-qm", "mapped scenarios")
        self.base = self.git("rev-parse", "HEAD").strip()
        path, record = self.change(action="merge")
        self.source.write_text("import unittest\nclass Sample(unittest.TestCase):\n def test_new(self): self.assertEqual(1, 1)\n")
        record["old_cases"].append(duplicate)
        record["scenarios"][0]["before"].append(duplicate)
        path.write_text(json.dumps(record))
        coverage["cases"] = [{"id": new, "generation": "initial-normal", "verifies": [{"requirement": "sample.value@1", "scenario": "normal"}]}]
        (directory / "coverage.json").write_text(json.dumps(coverage))
        with self.assertRaisesRegex(ValueError, "scenario|coverage"):
            self.hot()

    def test_mapped_requirement_retirement_is_authorized_and_preserves_legacy_execution(self):
        old = "test_sample.Sample.test_old"
        remaining = "test_sample.Sample.test_remaining"
        self.source.write_text(self.source.read_text() + " def test_remaining(self): self.assertEqual(2, 2)\n")
        directory = self.root / ".nightshift"
        directory.mkdir()
        requirements = {"version": 1, "requirements": [{"id": "sample.value", "version": 1, "status": "active", "behavior": "one", "decision_ref": "DEC-ONE"}]}
        (directory / "requirements.json").write_text(json.dumps(requirements))
        (directory / "coverage.json").write_text(json.dumps({"version": 1, "cases": [{"id": old, "generation": "initial", "verifies": [{"requirement": "sample.value@1", "scenario": "normal"}]}]}))
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "commit", "-qm", "mapped requirement")
        self.base = self.git("rev-parse", "HEAD").strip()
        path, record = self.change(action="retire", new_ids=[])
        record.update(removed_requirement="sample.value@1", verification_cases=[remaining])
        record["scenarios"][0]["removed"] = True
        path.write_text(json.dumps(record))
        self.source.write_text("import unittest\nclass Sample(unittest.TestCase):\n def test_remaining(self): self.assertEqual(2, 2)\n")
        (directory / "coverage.json").write_text(json.dumps({"version": 1, "cases": []}))
        with self.assertRaisesRegex(ValueError, "coverage|retire"):
            self.hot()
        requirements["requirements"].append({"id": "sample.value", "version": 2, "status": "retired", "behavior": "one feature removed", "decision_ref": "DEC-ONE", "supersedes": "sample.value@1", "affected_scenarios": ["normal"]})
        (directory / "requirements.json").write_text(json.dumps(requirements))
        self.assertEqual(self.hot()["cases"], [remaining])

    def test_inventory_timeout_is_execution_failure_not_a_regression(self):
        provider = self.root / "slow_inventory.py"
        provider.write_text("import time\ntime.sleep(5)\n")
        self.config.write_text(json.dumps({"command": [sys.executable, str(provider)], "timeout": 0.05}))
        self.change()
        with self.assertRaises(acceptance.HotFailure) as raised:
            self.hot()
        self.assertEqual(raised.exception.kind, "timeout")
        self.assertEqual(raised.exception.evidence["phase"], "inventory")

    def test_ignored_requirement_or_coverage_cannot_authorize_maintenance(self):
        self.change()
        directory = self.root / ".nightshift"
        (directory / "requirements.json").write_text(json.dumps({"version": 1, "requirements": [
            {"id": "sample.value", "version": 1, "status": "active", "behavior": "one", "decision_ref": "DEC-ONE"}]}))
        (directory / "coverage.json").write_text(json.dumps({"version": 1, "cases": [
            {"id": "test_sample.Sample.test_new", "generation": "initial", "verifies": [
                {"requirement": "sample.value@1", "scenario": "normal"}]}]}))
        for name in ("requirements.json", "coverage.json"):
            with self.subTest(name=name):
                (self.root / ".gitignore").write_text("__pycache__/\n.nightshift/" + name + "\n")
                with self.assertRaisesRegex(ValueError, "delivered in Git"):
                    self.hot()

    def test_merge_remaining_verification_must_execute_even_when_normally_cold(self):
        old = "test_sample.Sample.test_old"
        duplicate = "test_sample.Sample.test_duplicate"
        cold = "test_sample.Sample.test_cold"
        new = "test_sample.Sample.test_new"
        self.source.write_text(self.source.read_text() +
            " def test_duplicate(self): self.assertEqual(1, 1)\n"
            " def test_cold(self): self.assertEqual(1, 2)\n")
        directory = self.root / ".nightshift"
        directory.mkdir()
        (directory / "requirements.json").write_text(json.dumps({"version": 1, "requirements": [
            {"id": "sample.value", "version": 1, "status": "active", "behavior": "normal and edge", "decision_ref": "DEC-ONE"}]}))
        coverage = {"version": 1, "cases": [
            {"id": identity, "generation": identity, "verifies": [{"requirement": "sample.value@1", "scenario": scenario}]}
            for identity, scenario in [(old, "normal"), (duplicate, "edge")]]}
        (directory / "coverage.json").write_text(json.dumps(coverage))
        partition = self.root / "cold.txt"
        partition.write_text(cold + "\n")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "commit", "-qm", "cold edge verification")
        self.base = self.git("rev-parse", "HEAD").strip()
        path, record = self.change(action="merge")
        record["old_cases"].append(duplicate)
        record["scenarios"][0]["before"].append(duplicate)
        record["verification_cases"] = [cold]
        path.write_text(json.dumps(record))
        self.source.write_text(self.source.read_text().replace(" def test_duplicate(self): self.assertEqual(1, 1)\n", ""))
        coverage["cases"] = [
            {"id": identity, "generation": identity, "verifies": [{"requirement": "sample.value@1", "scenario": scenario}]}
            for identity, scenario in [(new, "normal"), (cold, "edge")]]
        (directory / "coverage.json").write_text(json.dumps(coverage))
        command = shlex.join([sys.executable, str(SCRIPTS / "unittest_hot.py"), "--start", "test", "--cold-only-file", str(partition)])
        with self.assertRaises(acceptance.HotFailure):
            self.hot(hot_command=command)
        self.source.write_text(self.source.read_text().replace("1, 2", "2, 2"))
        self.assertEqual(self.hot(hot_command=command)["cases"], sorted([new, cold]))

    def repeated_lineage(self, modeled):
        old, new = "test_sample.Sample.test_old", "test_sample.Sample.test_new"
        directory = self.root / ".nightshift"
        directory.mkdir()
        if modeled:
            (directory / "requirements.json").write_text(json.dumps({"version": 1, "requirements": [
                {"id": "sample.value", "version": 1, "status": "active", "behavior": "one", "decision_ref": "DEC-ONE"}]}))
        def coverage(identities):
            if modeled:
                (directory / "coverage.json").write_text(json.dumps({"version": 1, "cases": [
                    {"id": identity, "generation": generation, "verifies": [{"requirement": "sample.value@1", "scenario": "normal"}], **extra}
                    for identity, generation, extra in identities]}))
        def commit():
            self.git("add", ".")
            self.git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "commit", "-qm", "accepted lineage step")
            self.base = self.git("rev-parse", "HEAD").strip()
        coverage([(old, "original", {})])
        commit()
        path, _ = self.change()
        coverage([(new, "original", {})])
        self.hot()
        commit()
        records = path.parent
        def restore(identity, predecessor):
            record = {"version": 1, "id": identity, "action": "reintroduce", "old_cases": [], "new_cases": [old],
                "reason": "New independent case", "decision_ref": "DEC-ONE", "predecessor_change": predecessor,
                "scenarios": [{"name": "normal", "before": [], "after": [old]}]}
            (records / (identity + ".json")).write_text(json.dumps(record))
            coverage([(new, "original", {}), (old, identity, {"previous_change": predecessor})])
        self.source.write_text(self.source.read_text() + " def test_old(self): self.assertEqual(1, 1)\n")
        restore("CHG-TWO", "CHG-ONE")
        self.hot(maintenance="CHG-TWO")
        commit()
        self.source.write_text(self.source.read_text().replace(" def test_old(self): self.assertEqual(1, 1)\n", ""))
        (records / "CHG-THREE.json").write_text(json.dumps({"version": 1, "id": "CHG-THREE", "action": "merge",
            "old_cases": [old, new], "new_cases": [new], "reason": "Merge same scenario", "decision_ref": "DEC-ONE",
            "scenarios": [{"name": "normal", "before": [old, new], "after": [new]}]}))
        coverage([(new, "original", {})])
        self.hot(maintenance="CHG-THREE")
        commit()
        self.source.write_text(self.source.read_text() + " def test_old(self): self.assertEqual(1, 1)\n")
        restore("CHG-FOUR", "CHG-ONE")
        with self.assertRaisesRegex(ValueError, "predecessor|lineage"):
            self.hot(maintenance="CHG-FOUR")
        restore("CHG-FOUR", "CHG-THREE")
        self.assertEqual(self.hot(maintenance="CHG-FOUR")["cases"], sorted([old, new]))

    def test_repeated_legacy_reintroduction_requires_unconsumed_removal(self):
        self.repeated_lineage(modeled=False)

    def test_repeated_mapped_reintroduction_requires_unconsumed_removal(self):
        self.repeated_lineage(modeled=True)

    def test_one_recreated_id_cannot_have_two_new_lineage_events(self):
        path, _ = self.change()
        self.hot()
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "commit", "-qm", "accepted removal")
        self.base = self.git("rev-parse", "HEAD").strip()
        old = "test_sample.Sample.test_old"
        self.source.write_text(self.source.read_text() + " def test_old(self): self.assertEqual(1, 1)\n")
        for identity in ("CHG-A", "CHG-B"):
            (path.parent / (identity + ".json")).write_text(json.dumps({
                "version": 1, "id": identity, "action": "reintroduce", "old_cases": [], "new_cases": [old],
                "reason": "Restore one case", "decision_ref": "DEC-ONE", "predecessor_change": "CHG-ONE",
                "scenarios": [{"name": "normal", "before": [], "after": [old]}]}))
        with self.assertRaisesRegex(ValueError, "exactly one|ambiguous"):
            self.hot(maintenance="CHG-A,CHG-B")
