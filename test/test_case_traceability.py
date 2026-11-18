"""Requirement queries and validation through the traceability command."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
import test_case_inventory as fixture
SCRIPTS = fixture.SCRIPTS

class TraceabilityTests(unittest.TestCase):
    setUp = fixture.InventoryTests.setUp
    git = fixture.InventoryTests.git

    def model(self):
        directory = self.root / ".nightshift"
        directory.mkdir(exist_ok=True)
        requirements = {"version": 1, "requirements": [
            {"id": "sample.value", "version": 1, "status": "active", "behavior": "value equals one", "decision_ref": "DEC-ONE"}]}
        coverage = {"version": 1, "cases": [{"id": "test_sample.Sample.test_old", "generation": "initial", "verifies": [
            {"requirement": "sample.value@1", "scenario": "normal"}]}]}
        (directory / "requirements.json").write_text(json.dumps(requirements))
        (directory / "coverage.json").write_text(json.dumps(coverage))
        return requirements, coverage

    def cli(self, action, *args, success=True):
        p = subprocess.run([sys.executable, str(SCRIPTS / "case_traceability.py"), "--root", str(self.root), action, *args], capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(p.returncode == 0, success, p.stderr + p.stdout)
        return json.loads(p.stdout) if success else p.stderr

    def test_bidirectional_queries_and_unrelated_requirement_version(self):
        requirements, _ = self.model()
        result = self.cli("requirement", "sample.value@1")
        self.assertEqual(result["cases"], ["test_sample.Sample.test_old"])
        self.assertEqual(self.cli("case", "test_sample.Sample.test_old")["verifies"], [{"requirement": "sample.value@1", "scenario": "normal"}])
        requirements["requirements"].append({"id": "sample.value", "version": 2, "status": "active", "behavior": "special mode becomes two", "decision_ref": "DEC-TWO", "supersedes": "sample.value@1", "affected_scenarios": ["special"]})
        (self.root / ".nightshift/requirements.json").write_text(json.dumps(requirements))
        self.assertEqual(self.cli("check")["mapped_cases"], 1)
        self.assertEqual(self.cli("impact", "sample.value")["cases"], ["test_sample.Sample.test_old"])

    def test_affected_stale_relation_and_unknown_requirement_fail(self):
        requirements, coverage = self.model()
        requirements["requirements"].append({"id": "sample.value", "version": 2, "status": "active", "behavior": "normal becomes two", "decision_ref": "DEC-TWO", "supersedes": "sample.value@1", "affected_scenarios": ["normal"]})
        (self.root / ".nightshift/requirements.json").write_text(json.dumps(requirements))
        self.assertIn("stale", self.cli("check", success=False))
        coverage["cases"][0]["verifies"][0]["requirement"] = "missing@1"
        (self.root / ".nightshift/coverage.json").write_text(json.dumps(coverage))
        self.assertIn("unknown", self.cli("check", success=False))

    def test_legacy_project_without_model_is_valid(self):
        self.assertEqual(self.cli("check")["mapped_cases"], 0)

    def test_branch_switch_and_revert_restore_versioned_relations(self):
        requirements, coverage = self.model()
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "commit", "-qm", "model v1")
        first = self.git("rev-parse", "HEAD").strip()
        self.git("checkout", "-qb", "next-model")
        requirements["requirements"].append({"id": "sample.value", "version": 2, "status": "active", "behavior": "normal becomes two", "decision_ref": "DEC-TWO", "supersedes": "sample.value@1", "affected_scenarios": ["normal"]})
        coverage["cases"][0]["verifies"][0]["requirement"] = "sample.value@2"
        (self.root / ".nightshift/requirements.json").write_text(json.dumps(requirements))
        (self.root / ".nightshift/coverage.json").write_text(json.dumps(coverage))
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "commit", "-qm", "model v2")
        self.assertEqual(self.cli("case", "test_sample.Sample.test_old")["verifies"][0]["requirement"], "sample.value@2")
        self.git("checkout", "--detach", first)
        self.assertEqual(self.cli("case", "test_sample.Sample.test_old")["verifies"][0]["requirement"], "sample.value@1")
        self.git("checkout", "next-model")
        self.assertEqual(self.cli("case", "test_sample.Sample.test_old")["verifies"][0]["requirement"], "sample.value@2")

    def test_disconnected_requirement_version_is_rejected(self):
        requirements, _ = self.model()
        requirements["requirements"].append({"id": "sample.value", "version": 2, "status": "active", "behavior": "changed", "decision_ref": "DEC-TWO"})
        (self.root / ".nightshift/requirements.json").write_text(json.dumps(requirements))
        self.assertIn("predecessor", self.cli("check", success=False))
