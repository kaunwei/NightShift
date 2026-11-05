"""Tests for building and querying an external project index."""
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


@unittest.skipUnless((ROOT / "scripts/tools/.venv/bin/python").is_file(), "parser environment required")
class ExternalProjectIndexTests(unittest.TestCase):
    def test_external_index_build_query_and_isolation_between_two_projects(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            installation = workspace / "tool" / "nightshift"
            installation.mkdir(parents=True)

            # Two distinct projects
            p1 = workspace / "project-one"
            p1.mkdir()
            subprocess.run(["git", "init", "-q", str(p1)], check=True)
            (p1 / "alpha.py").write_text("def alpha_func(): return 1\n")
            subprocess.run(["git", "-C", str(p1), "add", "."], check=True)
            subprocess.run(["git", "-C", str(p1), "commit", "-m", "init p1"], check=True)

            p2 = workspace / "project-two"
            p2.mkdir()
            subprocess.run(["git", "init", "-q", str(p2)], check=True)
            (p2 / "beta.py").write_text("def beta_func(): return 2\n")
            subprocess.run(["git", "-C", str(p2), "add", "."], check=True)
            subprocess.run(["git", "-C", str(p2), "commit", "-m", "init p2"], check=True)

            config = {
                "version": 1,
                "projects": {
                    "one": {"path": "../../project-one"},
                    "two": {"path": "../../project-two"}
                }
            }
            config_file = installation / "config.json"
            config_file.write_text(json.dumps(config))

            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

            # Build index for project one from an arbitrary working directory
            res1 = subprocess.run([
                sys.executable, str(RUNTIME), "code-index",
                "--config", str(config_file),
                "--project", "one",
                "ensure"
            ], cwd=workspace, env=env, capture_output=True, text=True, check=True)
            data1 = json.loads(res1.stdout)

            # Build index for project two
            res2 = subprocess.run([
                sys.executable, str(RUNTIME), "code-index",
                "--config", str(config_file),
                "--project", "two",
                "ensure"
            ], cwd=workspace, env=env, capture_output=True, text=True, check=True)
            data2 = json.loads(res2.stdout)

            _, _, state1 = project_config.resolve_project(config_file, "one")
            _, _, state2 = project_config.resolve_project(config_file, "two")

            idx1_path = Path(data1["index_path"]).resolve()
            idx2_path = Path(data2["index_path"]).resolve()

            # Verify index files are outside repositories
            self.assertFalse(idx1_path.is_relative_to(p1.resolve()))
            self.assertFalse(idx2_path.is_relative_to(p2.resolve()))
            self.assertTrue(idx1_path.is_relative_to(state1.resolve()))
            self.assertTrue(idx2_path.is_relative_to(state2.resolve()))

            # Verify contents are isolated
            content1 = json.loads(idx1_path.read_text())
            content2 = json.loads(idx2_path.read_text())
            files1 = {f["path"] for f in content1["files"]}
            files2 = {f["path"] for f in content2["files"]}
            self.assertEqual(files1, {"alpha.py"})
            self.assertEqual(files2, {"beta.py"})

            # Verify working trees remain completely clean with no nightshift files
            self.assertFalse((p1 / "nightshift").exists())
            self.assertFalse((p2 / "nightshift").exists())
            status1 = subprocess.run(["git", "-C", str(p1), "status", "--porcelain"], capture_output=True, text=True, check=True)
            status2 = subprocess.run(["git", "-C", str(p2), "status", "--porcelain"], capture_output=True, text=True, check=True)
            self.assertEqual(status1.stdout.strip(), "")
            self.assertEqual(status2.stdout.strip(), "")

    def test_cache_reuse_and_invalidation_on_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            installation = workspace / "tool" / "nightshift"
            installation.mkdir(parents=True)

            repo = workspace / "my-repo"
            repo.mkdir()
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "one.py").write_text("x = 1\n")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-m", "init"], check=True)

            config = {
                "version": 1,
                "projects": {
                    "my-repo": {"path": "../../my-repo"}
                }
            }
            config_file = installation / "config.json"
            config_file.write_text(json.dumps(config))

            env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}

            # First build: rebuilt
            r1 = subprocess.run([
                sys.executable, str(RUNTIME), "code-index",
                "--config", str(config_file),
                "--project", "my-repo", "ensure"
            ], cwd=workspace, env=env, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(r1.stdout)["status"], "rebuilt")

            # Second build without changes: current
            r2 = subprocess.run([
                sys.executable, str(RUNTIME), "code-index",
                "--config", str(config_file),
                "--project", "my-repo", "ensure"
            ], cwd=workspace, env=env, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(r2.stdout)["status"], "current")

            # Modify file and commit
            (repo / "one.py").write_text("x = 2\n")
            subprocess.run(["git", "-C", str(repo), "commit", "-am", "update"], check=True)

            # Third build after commit: rebuilt
            r3 = subprocess.run([
                sys.executable, str(RUNTIME), "code-index",
                "--config", str(config_file),
                "--project", "my-repo", "ensure"
            ], cwd=workspace, env=env, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(r3.stdout)["status"], "rebuilt")

