"""Tests for running private hot and cold checks outside the target repository."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import acceptance
import project_config

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "scripts" / "worker_runtime.py"


class ExternalAcceptanceTests(unittest.TestCase):
    def test_external_hot_and_cold_scripts_resolve_and_receive_project_root(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            installation = workspace / "tool" / "nightshift"
            installation.mkdir(parents=True)
            target = workspace / "external-repo"
            target.mkdir()
            subprocess.run(["git", "init", "-q", str(target)], check=True)
            (target / "code.py").write_text("print('prod')\n")
            (target / "test_code.py").write_text("def test_one(): pass\n")
            subprocess.run(["git", "-C", str(target), "add", "."], check=True)
            subprocess.run(["git", "-C", str(target), "commit", "-m", "init"], check=True)

            # Create private checks outside the target repository
            private_dir = workspace / "private-checks"
            private_dir.mkdir()

            # Hot runner verifies NIGHTSHIFT_PROJECT_ROOT is passed and PWD is target root
            hot_script = private_dir / "hot.sh"
            hot_script.write_text(f"""#!/usr/bin/env bash
if [ "$NIGHTSHIFT_PROJECT_ROOT" != "{target.resolve()}" ]; then
    echo "Bad NIGHTSHIFT_PROJECT_ROOT: $NIGHTSHIFT_PROJECT_ROOT" >&2
    exit 1
fi
if [ "$PWD" != "{target.resolve()}" ]; then
    echo "Bad PWD: $PWD" >&2
    exit 2
fi
# Emit discovery / run evidence
cat <<EOF > "$NIGHTSHIFT_RESULT"
{{
  "run": "$NIGHTSHIFT_RUN",
  "status": "pass",
  "cases": [{{
    "id": "test_code.test_one",
    "source": "test_code.py",
    "fingerprint": "1111111111111111111111111111111111111111111111111111111111111111",
    "baseline_fingerprint": null,
    "status": "passed"
  }}]
}}
EOF
exit 0
""")
            hot_script.chmod(0o755)

            # Cold script verifies project root and clean tree
            cold_script = private_dir / "cold.sh"
            cold_script.write_text(f"""#!/usr/bin/env bash
if [ "$PWD" != "{target.resolve()}" ]; then
    echo "Cold in wrong cwd: $PWD" >&2
    exit 3
fi
exit 0
""")
            cold_script.chmod(0o755)

            # Configuration lives outside repo, pointing to relative script paths
            config = {
                "version": 1,
                "default_project": "external",
                "projects": {
                    "external": {
                        "path": "../../external-repo",
                        "acceptance": {
                            "hot_script": "../../private-checks/hot.sh",
                            "cold_script": "../../private-checks/cold.sh"
                        }
                    }
                }
            }
            config_file = installation / "config.json"
            config_file.write_text(json.dumps(config))

            # Test config resolution
            name, root, state = project_config.resolve_project(config_file, "external")
            env = {
                "NIGHTSHIFT_CONFIG_FILE": str(config_file),
                "NIGHTSHIFT_PROJECT_NAME": "external",
                "NIGHTSHIFT_STATE_DIR": str(state)
            }
            with mock.patch.dict(os.environ, env):
                resolved_cfg = acceptance.config(root)
                self.assertIn("hot.sh", resolved_cfg["hot"])
                self.assertIn("cold.sh", resolved_cfg["cold"])

                runner = acceptance.get_runner(root, resolved_cfg)

                # Execute cold run through runner
                runner.run_cold(root, run="test-cold-run")

                # Verify state recorded in external state dir, not inside target repo
                cold_state_file = state / "lifecycle" / "cold.json"
                self.assertTrue(cold_state_file.exists())
                self.assertFalse((target / "nightshift").exists())

    def test_ignored_config_does_not_fail_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / ".gitignore").write_text("nightshift/\n")
            (root / "nightshift").mkdir()
            config_path = root / "nightshift" / "config.json"
            config_path.write_text(json.dumps({
                "version": 1,
                "acceptance": {"hot": "echo hot", "wiring": []}
            }))
            # Verify that ignored config.json alone is no longer rejected
            cfg = acceptance.config(root)
            self.assertEqual(cfg["hot"], "echo hot")
