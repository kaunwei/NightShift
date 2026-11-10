"""Project selection is isolated before external task execution is enabled."""
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


class ExternalProjectSelectionTests(unittest.TestCase):
    def test_selection_and_state_are_isolated_and_queue_is_not_consumed(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            installation = workspace / "tool" / "nightshift"
            installation.mkdir(parents=True)
            for name in ("worker.sh", "worker_runtime.py", "lifecycle.py", "acceptance.py", "acceptance_hooks.py", "hook_control.py",
                         "scratch_review.py", "attempt_archive.py", "preflight.py", "environment_probe.py", "verify_process.py", "evidence_capabilities.py", "project_config.py", "status.sh", "watch_worker.sh", "reorder_queue.sh"):
                shutil.copy2(ROOT / "scripts" / name, installation / name)
            projects = {}
            for name in ("first", "second"):
                root = workspace / f"project {name}"
                root.mkdir()
                subprocess.run(["git", "init", "-q", str(root)], check=True)
                projects[name] = {"path": f"../../project {name}"}
            config = {"version": 1, "default_project": "first", "projects": projects,
                      "agents": {"agent": {"worker": {"step_base": {"L1": 60, "L2": 40, "L3": 20}},
                                           "agent": {"adapter": "generic", "command": "unused"}}}}
            (installation / "config.json").write_text(json.dumps(config))
            env = {**os.environ, "RUN_ONCE": "1", "POLL_INTERVAL": "0"}
            def launch(*args):
                return subprocess.run(["bash", str(installation / "worker.sh"), *args], cwd=workspace,
                                      env=env, capture_output=True, text=True, timeout=10)
            first = launch()
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            second = launch("--project", "second")
            self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
            state_dirs = [p for p in (installation / ".scratch/projects").iterdir() if not p.name.startswith(".")]
            self.assertEqual(len(state_dirs), 2)
            display = subprocess.run(["bash", str(installation / "status.sh"), "--project", "second"],
                                     cwd=workspace, env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(display.returncode, 0, display.stdout + display.stderr)
            reorder = subprocess.run(["bash", str(installation / "reorder_queue.sh"), "--project", "second"],
                                     cwd=workspace, env=env, input="TASK-2 | ACTION: second\n", text=True,
                                     capture_output=True, timeout=10)
            self.assertEqual(reorder.returncode, 0, reorder.stdout + reorder.stderr)
            roots = {json.loads((p / "worker.status").read_text())["work_dir"] for p in state_dirs}
            self.assertEqual(roots, {str((workspace / "project first").resolve()),
                                     str((workspace / "project second").resolve())})
            self.assertFalse((workspace / "project first" / "nightshift").exists())
            self.assertFalse((workspace / "project second" / "nightshift").exists())
            invalid = launch("--project", "missing")
            self.assertNotEqual(invalid.returncode, 0)
            self.assertEqual(len([p for p in (installation / ".scratch/projects").iterdir() if not p.name.startswith(".")]), 2)
            first_state = next(p for p in state_dirs if json.loads((p / "worker.status").read_text())["work_dir"].endswith("project first"))
            queue = first_state / "tasks.txt"
            queue.write_text("TASK-1 | ACTION: preserve\n")
            (workspace / "project first" / "uncommitted.txt").write_text("preserve")
            stopped = launch()
            self.assertNotEqual(stopped.returncode, 0)
            self.assertIn("queue left unchanged", stopped.stderr)
            self.assertEqual(queue.read_text(), "TASK-1 | ACTION: preserve\n")

    def test_external_acceptance_uses_project_override_and_ignored_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config.json"
            config.write_text(json.dumps({"version": 1, "acceptance": {"hot": "default"},
                                          "projects": {"work": {"acceptance": {"hot": "local-check"}}}}))
            env = {"NIGHTSHIFT_CONFIG_FILE": str(config), "NIGHTSHIFT_PROJECT_NAME": "work",
                   "NIGHTSHIFT_STATE_DIR": str(root / "state")}
            with mock.patch.dict(os.environ, env):
                self.assertEqual(acceptance.config(root)["hot"], "local-check")
                self.assertTrue(acceptance.state_dir(root).is_relative_to(root / "state"))

    def test_two_projects_same_task_id_and_linked_worktree_have_isolated_identities_and_locks(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            installation = workspace / "tool" / "nightshift"
            installation.mkdir(parents=True)
            for name in ("worker.sh", "worker_runtime.py", "lifecycle.py", "acceptance.py", "acceptance_hooks.py", "hook_control.py",
                         "scratch_review.py", "attempt_archive.py", "preflight.py", "environment_probe.py", "verify_process.py", "evidence_capabilities.py", "project_config.py", "status.sh", "watch_worker.sh", "reorder_queue.sh"):
                shutil.copy2(ROOT / "scripts" / name, installation / name)

            alpha = workspace / "project alpha"
            alpha.mkdir()
            subprocess.run(["git", "init", "-q", str(alpha)], check=True)
            subprocess.run(["git", "-C", str(alpha), "commit", "--allow-empty", "-m", "init"], check=True)
            beta = workspace / "project beta"
            subprocess.run(["git", "-C", str(alpha), "worktree", "add", "-q", str(beta), "-b", "beta-branch"], check=True)
            gamma = workspace / "project gamma"
            gamma.mkdir()
            subprocess.run(["git", "init", "-q", str(gamma)], check=True)
            subprocess.run(["git", "-C", str(gamma), "commit", "--allow-empty", "-m", "init"], check=True)

            config = {
                "version": 1,
                "default_project": "alpha",
                "projects": {
                    "alpha": {"path": "../../project alpha"},
                    "beta": {"path": "../../project beta"},
                    "gamma": {"path": "../../project gamma"},
                }
            }
            config_file = installation / "config.json"
            config_file.write_text(json.dumps(config))

            name_a, root_a, state_a = project_config.resolve_project(config_file, "alpha")
            name_b, root_b, state_b = project_config.resolve_project(config_file, "beta")
            name_g, root_g, state_g = project_config.resolve_project(config_file, "gamma")

            self.assertEqual(name_a, "alpha")
            self.assertEqual(name_b, "beta")
            self.assertEqual(name_g, "gamma")

            self.assertNotEqual(state_a, state_b)
            self.assertNotEqual(state_a, state_g)
            self.assertNotEqual(state_b, state_g)

            self.assertEqual(root_a, alpha.resolve())
            self.assertEqual(root_b, beta.resolve())
            self.assertEqual(root_g, gamma.resolve())

            import hashlib
            lock_a = state_a.parent / ".locks" / (hashlib.sha256(str(root_a).encode()).hexdigest() + ".lock")
            lock_b = state_b.parent / ".locks" / (hashlib.sha256(str(root_b).encode()).hexdigest() + ".lock")
            self.assertNotEqual(lock_a, lock_b)

    def test_relative_paths_resolve_from_config_regardless_of_cwd_and_invalid_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            installation = workspace / "deep" / "tool" / "nightshift"
            installation.mkdir(parents=True)
            target = workspace / "target project"
            target.mkdir()
            subprocess.run(["git", "init", "-q", str(target)], check=True)

            config = {
                "version": 1,
                "default_project": "main",
                "projects": {
                    "main": {"path": "../../../target project"}
                }
            }
            config_file = installation / "config.json"
            config_file.write_text(json.dumps(config))

            cwd_elsewhere = workspace / "other"
            cwd_elsewhere.mkdir()
            orig_cwd = os.getcwd()
            try:
                os.chdir(cwd_elsewhere)
                name, root, state = project_config.resolve_project(config_file)
                self.assertEqual(root, target.resolve())

                with self.assertRaises(ValueError):
                    project_config.resolve_project(config_file, "nonexistent")
                self.assertFalse((installation / ".scratch").exists())
            finally:
                os.chdir(orig_cwd)

    def test_local_project_backward_compatibility(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            config = {"version": 1, "acceptance": {"hot": "echo ok"}}
            config_file = workspace / "nightshift" / "config.json"
            config_file.parent.mkdir()
            config_file.write_text(json.dumps(config))

            name, root, state = project_config.resolve_project(config_file, selection=None, default_root=workspace)
            self.assertIsNone(name)
            self.assertEqual(root, workspace.resolve())
            self.assertIsNone(state)

    def test_non_clean_project_preserves_tracked_modifications_and_untracked_files(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            installation = workspace / "tool" / "nightshift"
            installation.mkdir(parents=True)
            for name in ("worker.sh", "worker_runtime.py", "lifecycle.py", "acceptance.py", "acceptance_hooks.py", "hook_control.py",
                         "scratch_review.py", "attempt_archive.py", "preflight.py", "environment_probe.py", "verify_process.py", "evidence_capabilities.py", "project_config.py", "status.sh", "watch_worker.sh", "reorder_queue.sh"):
                shutil.copy2(ROOT / "scripts" / name, installation / name)

            project_dir = workspace / "project with spaces"
            project_dir.mkdir()
            subprocess.run(["git", "init", "-q", str(project_dir)], check=True)
            tracked_file = project_dir / "tracked.txt"
            tracked_file.write_text("original content")
            subprocess.run(["git", "-C", str(project_dir), "add", "tracked.txt"], check=True)
            subprocess.run(["git", "-C", str(project_dir), "commit", "-m", "add tracked"], check=True)

            # Introduce both a tracked modification and an untracked file
            tracked_file.write_text("user unsaved changes")
            untracked_file = project_dir / "scratch_work.txt"
            untracked_file.write_text("user draft work")

            config = {
                "version": 1,
                "default_project": "spaced",
                "projects": {
                    "spaced": {"path": "../../project with spaces"}
                },
                "agents": {
                    "agent": {
                        "worker": {"step_base": {"L1": 60, "L2": 40, "L3": 20}},
                        "agent": {"adapter": "generic", "command": "unused"}
                    }
                }
            }
            (installation / "config.json").write_text(json.dumps(config))

            # Put a task in the queue
            _, _, state_dir = project_config.resolve_project(installation / "config.json", "spaced")
            state_dir.mkdir(parents=True, exist_ok=True)
            queue_file = state_dir / "tasks.txt"
            queue_file.write_text("TASK-SPACED | ACTION: do not run on dirty\n")

            env = {**os.environ, "RUN_ONCE": "1", "POLL_INTERVAL": "0"}
            result = subprocess.run(["bash", str(installation / "worker.sh")], cwd=workspace,
                                    env=env, capture_output=True, text=True, timeout=10)

            # Must exit non-zero
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("queue left unchanged", result.stderr)

            # Untracked file and modified file must be completely preserved
            self.assertTrue(untracked_file.exists())
            self.assertEqual(untracked_file.read_text(), "user draft work")
            self.assertEqual(tracked_file.read_text(), "user unsaved changes")

            # Queue must NOT have been consumed
            self.assertEqual(queue_file.read_text(), "TASK-SPACED | ACTION: do not run on dirty\n")

    def test_custom_state_directory_in_project_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            target = workspace / "my-app"
            target.mkdir()
            subprocess.run(["git", "init", "-q", str(target)], check=True)

            config = {
                "version": 1,
                "projects": {
                    "my-app": {
                        "path": str(target),
                        "state": "projects/my-app"
                    }
                }
            }
            config_file = workspace / "config.json"
            config_file.write_text(json.dumps(config))

            name, root, state = project_config.resolve_project(config_file, "my-app")
            self.assertEqual(name, "my-app")
            self.assertEqual(root, target.resolve())
            self.assertEqual(state, (workspace / "projects/my-app").resolve())

    def test_self_contained_project_folder_with_config_json(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            target = workspace / "target-repo"
            target.mkdir()
            subprocess.run(["git", "init", "-q", str(target)], check=True)

            project_dir = workspace / "projects" / "my-app"
            project_dir.mkdir(parents=True)
            config = {
                "version": 1,
                "projects": {
                    "my-app": {
                        "path": str(target)
                    }
                }
            }
            config_file = project_dir / "config.json"
            config_file.write_text(json.dumps(config))

            # Without selection, automatically picks single project 'my-app' and uses project_dir as state
            name, root, state = project_config.resolve_project(config_file)
            self.assertEqual(name, "my-app")
            self.assertEqual(root, target.resolve())
            self.assertEqual(state, project_dir.resolve())

