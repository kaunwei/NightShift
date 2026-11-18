"""Complete inventory and revision comparisons through the supported command."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"

class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "test").mkdir()
        self.source = self.root / "test/test_sample.py"
        self.source.write_text("import unittest\nclass Sample(unittest.TestCase):\n def test_old(self): self.assertEqual(1, 1)\n")
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.config = self.root / "inventory-config.json"
        self.config.write_text(json.dumps({"command": [sys.executable, str(SCRIPTS / "unittest_hot.py"), "--start", "test"]}))

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True)

    def cli(self, *args, success=True):
        result = subprocess.run([sys.executable, str(SCRIPTS / "case_inventory.py"), "--root", str(self.root), "--config", str(self.config), *args], capture_output=True, text=True, env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertEqual(result.returncode == 0, success, result.stdout + result.stderr)
        return json.loads(result.stdout) if success else result.stderr

    def test_complete_inventory_and_deleted_file_comparison(self):
        cold = self.root / "cold.txt"
        cold.write_text("test_sample.Sample.test_old\n")
        config = json.loads(self.config.read_text())
        config["command"] += ["--cold-only-file", str(cold)]
        self.config.write_text(json.dumps(config))
        self.assertEqual([c["id"] for c in self.cli("list")["cases"]], ["test_sample.Sample.test_old"])
        cold.unlink()  # Complete discovery must not depend on the scheduling file.
        self.assertEqual([c["id"] for c in self.cli("list")["cases"]], ["test_sample.Sample.test_old"])
        self.source.unlink()
        (self.root / "test/test_new.py").write_text("import unittest\nclass New(unittest.TestCase):\n def test_new(self): self.assertTrue(True)\n")
        diff = self.cli("diff", "--base", self.base)
        self.assertEqual(diff["removed"], ["test_sample.Sample.test_old"])
        self.assertEqual(diff["added"], ["test_new.New.test_new"])
        self.assertEqual(diff["modified"], [])
        self.assertEqual(diff["baseline"]["revision"], self.base)

    def test_unknown_revision_and_discovery_error_fail_closed(self):
        self.assertIn("inventory", self.cli("diff", "--base", "invalid-revision", success=False).lower())
        self.source.write_text("invalid python !!!")
        self.assertIn("inventory", self.cli("list", success=False).lower())

    def test_modified_and_unchanged_ids_and_candidate_input_digest(self):
        first = self.cli("list")
        self.source.write_text(self.source.read_text().replace("1, 1", "2, 2"))
        second = self.cli("diff", "--base", self.base)
        self.assertEqual(second["modified"], ["test_sample.Sample.test_old"])
        self.assertNotEqual(first["input_digest"], second["candidate"]["input_digest"])
        self.assertEqual(second["added"], [])
        self.assertEqual(second["removed"], [])

    def test_provider_must_attest_complete_fresh_and_unique_evidence(self):
        provider = self.root / "provider.py"
        valid = {"id": "test_sample.Sample.test_old", "source": "test/test_sample.py", "fingerprint": "a" * 64}
        for mutation in ("incomplete", "stale", "duplicate"):
            with self.subTest(mutation=mutation):
                code = "import json,os\nfrom pathlib import Path\ndata={'run':os.environ['NIGHTSHIFT_RUN'],'inventory_complete':True,'cases':" + repr([valid]) + "}\n"
                if mutation == "incomplete": code += "data['inventory_complete']=False\n"
                if mutation == "stale": code += "data['run']='old-run'\n"
                if mutation == "duplicate": code += "data['cases']*=2\n"
                code += "Path(os.environ['NIGHTSHIFT_RESULT']).write_text(json.dumps(data))\n"
                provider.write_text(code)
                self.config.write_text(json.dumps({"command": [sys.executable, str(provider)]}))
                self.assertIn("inventory", self.cli("list", success=False))

    def test_move_between_test_sources_is_a_lineage_change(self):
        self.source.rename(self.source.with_name("test_moved.py"))
        diff = self.cli("diff", "--base", self.base)
        self.assertEqual(diff["removed"], ["test_sample.Sample.test_old"])
        self.assertEqual(diff["added"], ["test_moved.Sample.test_old"])

    def test_mutation_of_tracked_ignored_baseline_source_is_rejected(self):
        (self.root / ".gitignore").write_text("test/test_sample.py\n")
        self.git("add", ".gitignore")
        self.git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "commit", "-qm", "ignore tracked source")
        self.base = self.git("rev-parse", "HEAD").strip()
        provider = self.root / "provider.py"
        provider.write_text("import json,os\nfrom pathlib import Path\n"
            "Path('test/test_sample.py').write_text('changed during discovery')\n"
            "Path(os.environ['NIGHTSHIFT_RESULT']).write_text(json.dumps({'run':os.environ['NIGHTSHIFT_RUN'],"
            "'inventory_complete':True,'cases':[{'id':'sample','source':'test/test_sample.py','fingerprint':'a'*64}]}))\n")
        self.config.write_text(json.dumps({"command": [sys.executable, str(provider)]}))
        self.assertIn("inputs changed", self.cli("list", "--revision", self.base, success=False))

    def test_archive_attributes_cannot_hide_a_disappeared_baseline_case(self):
        (self.root / ".gitattributes").write_text("test/test_sample.py export-ignore\n")
        self.git("add", ".gitattributes")
        self.git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "commit", "-qm", "archive exclusion")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.source.unlink()
        self.assertEqual(self.cli("diff", "--base", self.base)["removed"], ["test_sample.Sample.test_old"])

    def test_archive_substitution_cannot_rewrite_baseline_test_content(self):
        (self.root / ".gitattributes").write_text("test/test_sample.py export-subst\n")
        self.source.write_text(self.source.read_text().replace("1, 1", "'$Format:%H$', '$Format:%H$'"))
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=f@example.invalid", "commit", "-qm", "archive substitution")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.assertEqual(self.cli("diff", "--base", self.base)["modified"], [])

    def test_comparison_rejects_provider_change_between_collections(self):
        sys.path.insert(0, str(SCRIPTS))
        import case_inventory
        provider = self.root / "provider.py"
        code = ("import json,os\nfrom pathlib import Path\n"
                "Path(os.environ['NIGHTSHIFT_RESULT']).write_text(json.dumps({'run':os.environ['NIGHTSHIFT_RUN'],"
                "'inventory_complete':True,'cases':[{'id':'sample','source':'test/test_sample.py','fingerprint':'a'*64}]}))\n")
        provider.write_text(code)
        self.config.write_text(json.dumps({"command": [sys.executable, str(provider)]}))
        baseline = self.cli("list", "--revision", self.base)
        provider.write_text(code + "# different approved provider content\n")
        candidate = self.cli("list")
        with self.assertRaisesRegex(ValueError, "provider changed"):
            case_inventory.compare(baseline, candidate)
