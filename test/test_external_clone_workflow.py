"""External execution commits only disposable clones, preserving original work."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "scripts/worker_runtime.py"


class ExternalCloneWorkflowTests(unittest.TestCase):
    def git(self, root, *args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()

    def test_two_projects_commit_only_clones_and_preserve_dirty_originals(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            projects, originals = {}, {}
            for name in ("one", "two"):
                original = workspace / ("original-" + name)
                original.mkdir()
                self.git(original, "init", "-q")
                self.git(original, "config", "user.name", "Fixture")
                self.git(original, "config", "user.email", "fixture@example.invalid")
                (original / ".gitignore").write_text("__pycache__/\n")
                (original / "value.txt").write_text(name + "\n")
                (original / "tests").mkdir()
                (original / "tests/test_behavior.py").write_text(
                    "import unittest\nfrom pathlib import Path\nclass Behavior(unittest.TestCase):\n"
                    f" def test_baseline(self): self.assertTrue(Path('value.txt').read_text().startswith({name!r}))\n")
                self.git(original, "add", ".")
                self.git(original, "commit", "-qm", "fixture baseline")
                (original / "draft.txt").write_text("keep user draft " + name)
                originals[name] = (original, self.git(original, "rev-parse", "HEAD"),
                                   self.git(original, "status", "--porcelain"))
                clone = workspace / ("clone-" + name)
                subprocess.run(["git", "clone", "-q", str(original), str(clone)], check=True)
                self.git(clone, "config", "user.name", "Fixture")
                self.git(clone, "config", "user.email", "fixture@example.invalid")
                state = workspace / "runner" / name
                state.mkdir(parents=True)
                projects[name] = {"path": str(clone), "state": str(state)}
                (state / "tasks.txt").write_text(
                    "TASK-VERIFY [CODE: FIX] | LEVEL: 3 | TARGET: value.txt,tests | VERIFY: true\n")

            worker = workspace / "worker.py"
            worker.write_text('''import json,os
from pathlib import Path
with Path('value.txt').open('a') as f:f.write('verified\\n')
with Path('tests/test_behavior.py').open('a') as f:
 f.write(" def test_verified(self): self.assertTrue(Path('value.txt').read_text().endswith('verified\\\\n'))\\n")
result={'outcome':'complete','commit_message':'test: verify clone routing',
        'tdd_cases':[{'id':'test_behavior.Behavior.test_verified','source':'tests/test_behavior.py'}]}
Path(os.environ['NIGHTSHIFT_RESULT_FILE']).write_text(json.dumps(result))
''')
            config = workspace / "runner/config.json"
            config.write_text(json.dumps({"version": 1, "projects": projects,
                "acceptance": {"version": 1, "hot": f"{sys.executable} {ROOT / 'scripts/unittest_hot.py'} --start tests"},
                "agents": {"fixture": {"worker": {"task_timeout_seconds": 15,
                    "step_base": {"L1": 60, "L2": 40, "L3": 20}},
                    "agent": {"adapter": "generic", "command": sys.executable,
                              "args": [str(worker)], "config": {"initial_score": 5}}}}}))
            env = {key: value for key, value in os.environ.items() if not key.startswith("NIGHTSHIFT_")}
            env.update(RUN_ONCE="1", POLL_INTERVAL=".01")
            for name, entry in projects.items():
                with self.subTest(project=name):
                    clone, state = Path(entry["path"]), Path(entry["state"])
                    result = subprocess.run([sys.executable, str(RUNTIME), "daemon", "--root", str(workspace), "--config", str(config),
                        "--project", name], cwd=workspace, env=env, capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertIn("[DONE] TASK-VERIFY", (state / "tasks.done").read_text())
                    self.assertEqual((clone / "value.txt").read_text(), name + "\nverified\n")
                    self.assertEqual(set(self.git(clone, "show", "--format=", "--name-only", "HEAD").splitlines()),
                                     {"value.txt", "tests/test_behavior.py"})
                    self.assertEqual(self.git(clone, "status", "--porcelain"), "")
                    self.assertFalse((clone / "nightshift").exists())
                    self.assertFalse((clone / ".agents").exists())
                    for original_name, (original, head, status) in originals.items():
                        self.assertEqual(self.git(original, "rev-parse", "HEAD"), head)
                        self.assertEqual(self.git(original, "status", "--porcelain"), status)
                        self.assertEqual((original / "draft.txt").read_text(), "keep user draft " + original_name)
