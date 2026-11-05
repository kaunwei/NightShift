"""Verification of the complete external workflow against clones of TometoClock and matronome."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import project_config

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "scripts" / "worker_runtime.py"
MATRONOME_ORIGINAL = (ROOT.parent / "matronome").resolve()
TOMETOCLOCK_ORIGINAL = (ROOT.parent / "TometoClock").resolve()


class ExternalRealProjectsVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Record baseline before tests
        if MATRONOME_ORIGINAL.is_dir():
            cls.matronome_head = subprocess.check_output(
                ["git", "-C", str(MATRONOME_ORIGINAL), "rev-parse", "HEAD"], text=True
            ).strip()
            cls.matronome_status = subprocess.check_output(
                ["git", "-C", str(MATRONOME_ORIGINAL), "status", "--porcelain"], text=True
            ).strip()
        if TOMETOCLOCK_ORIGINAL.is_dir():
            cls.tometo_head = subprocess.check_output(
                ["git", "-C", str(TOMETOCLOCK_ORIGINAL), "rev-parse", "HEAD"], text=True
            ).strip()
            cls.tometo_status = subprocess.check_output(
                ["git", "-C", str(TOMETOCLOCK_ORIGINAL), "status", "--porcelain"], text=True
            ).strip()

    def tearDown(self):
        # Verify original workspaces remain pristine after each test
        if MATRONOME_ORIGINAL.is_dir():
            current_head = subprocess.check_output(
                ["git", "-C", str(MATRONOME_ORIGINAL), "rev-parse", "HEAD"], text=True
            ).strip()
            current_status = subprocess.check_output(
                ["git", "-C", str(MATRONOME_ORIGINAL), "status", "--porcelain"], text=True
            ).strip()
            self.assertEqual(current_head, self.matronome_head, "Original matronome HEAD must not change!")
            self.assertEqual(current_status, self.matronome_status, "Original matronome working tree must remain clean!")

        if TOMETOCLOCK_ORIGINAL.is_dir():
            current_head = subprocess.check_output(
                ["git", "-C", str(TOMETOCLOCK_ORIGINAL), "rev-parse", "HEAD"], text=True
            ).strip()
            current_status = subprocess.check_output(
                ["git", "-C", str(TOMETOCLOCK_ORIGINAL), "status", "--porcelain"], text=True
            ).strip()
            self.assertEqual(current_head, self.tometo_head, "Original TometoClock HEAD must not change!")
            self.assertEqual(current_status, self.tometo_status, "Original TometoClock working tree must remain clean!")

    @unittest.skipUnless(MATRONOME_ORIGINAL.is_dir() and TOMETOCLOCK_ORIGINAL.is_dir(),
                         "matronome and TometoClock repositories required")
    def test_workflow_on_isolated_clones_leaves_originals_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            installation = workspace / "tool" / "nightshift"
            installation.mkdir(parents=True)

            # Clone tometo and matronome to temporary isolated locations
            clone_tometo = workspace / "tometo-clone"
            subprocess.run(["git", "clone", "-q", str(TOMETOCLOCK_ORIGINAL), str(clone_tometo)], check=True)
            clone_matronome = workspace / "matronome-clone"
            subprocess.run(["git", "clone", "-q", str(MATRONOME_ORIGINAL), str(clone_matronome)], check=True)

            checks = workspace / "external-checks"
            checks.mkdir()
            hot_runner = checks / "hot_runner.py"
            hot_runner.write_text('''import json, os, pathlib
res = pathlib.Path(os.environ["NIGHTSHIFT_RESULT"])
run_id = os.environ.get("NIGHTSHIFT_RUN", "")
res.write_text(json.dumps({
    "run": run_id,
    "status": "pass",
    "cases": [{
        "id": "test_verification",
        "source": "Package.swift",
        "fingerprint": "2" * 64,
        "baseline_fingerprint": None,
        "status": "passed"
    }]
}))
''')
            (checks / "hot.sh").write_text(f"exec {sys.executable} {hot_runner}\n")

            # Worker script modifying a target file in clone
            worker_script = workspace / "worker.py"
            worker_script.write_text('''import json, os, pathlib
target = pathlib.Path(os.environ.get("NIGHTSHIFT_PROJECT_ROOT", "."))
pkg = target / "Package.swift"
with pkg.open("a") as f:
    f.write("\\n// verified change\\n")
result = {
    "outcome": "complete",
    "changed": True,
    "commit_message": "chore: external test commit",
    "tdd_cases": [{"id": "test_verification", "source": "Package.swift"}]
}
pathlib.Path(os.environ["NIGHTSHIFT_RESULT_FILE"]).write_text(json.dumps(result))
''')

            config = {
                "version": 1,
                "default_project": "matronome",
                "projects": {
                    "matronome": {
                        "path": "../../matronome-clone",
                        "acceptance": {"hot_script": "../../external-checks/hot.sh"}
                    },
                    "tometo": {
                        "path": "../../tometo-clone",
                        "acceptance": {"hot_script": "../../external-checks/hot.sh"}
                    }
                },
                "agents": {
                    "fake": {
                        "default": True,
                        "worker": {
                            "task_timeout_seconds": 15,
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

            # Put task in queue for matronome
            _, _, state_dir = project_config.resolve_project(config_file, "matronome")
            state_dir.mkdir(parents=True, exist_ok=True)
            queue_file = state_dir / "tasks.txt"
            queue_file.write_text("TASK-MATRONOME [CODE: FIX] | LEVEL: 3 | TARGET: Package.swift | VERIFY: true\n")

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
                "--project", "matronome"
            ], env=env, capture_output=True, text=True, timeout=25)

            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)

            # Check that only Package.swift was changed in clone commit
            log = subprocess.run([
                "git", "-C", str(clone_matronome), "log", "-n", "1", "--name-only", "--pretty=format:"
            ], capture_output=True, text=True, check=True)
            changed_files = [f.strip() for f in log.stdout.strip().splitlines() if f.strip()]
            self.assertEqual(changed_files, ["Package.swift"])

            # Verify no unstaged/untracked changes in clone
            status = subprocess.run([
                "git", "-C", str(clone_matronome), "status", "--porcelain"
            ], capture_output=True, text=True, check=True)
            self.assertEqual(status.stdout.strip(), "")
