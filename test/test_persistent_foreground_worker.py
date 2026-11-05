"""Persistent foreground operation and dirty-worktree backpressure."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


def wait_for(process, predicate, seconds=8):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return
        if process.poll() is not None:
            raise AssertionError(f"daemon exited unexpectedly: {process.returncode}")
        time.sleep(0.03)
    raise AssertionError("condition not reached before deadline")


class PersistentDirtyWorktreeTests(unittest.TestCase):
    def test_dirty_project_waits_without_claiming_or_losing_changes_then_resumes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            project = base / "project"
            project.mkdir()
            subprocess.run(["git", "init", "-q", str(project)], check=True)
            subprocess.run(["git", "-C", str(project), "-c", "user.name=Fixture", "-c",
                            "user.email=fixture@example.test", "commit", "--allow-empty", "-qm", "base"], check=True)
            dirty = project / "user-draft.txt"
            dirty.write_text("preserve user work")
            state = base / "state"
            state.mkdir()
            queue = state / "tasks.txt"
            original = "TASK-WAIT | ACTION: do not claim while dirty\n"
            queue.write_text(original)
            config = base / "config.json"
            config.write_text(json.dumps({"version": 1, "projects": {"sample": {
                "path": str(project), "state_dir": str(state)}}}))
            env = {k: v for k, v in os.environ.items() if not k.startswith("NIGHTSHIFT_")}
            env.update(RUN_ONCE="0", POLL_INTERVAL="0.05")
            status = state / "worker.status"
            def is_state(name):
                try:
                    return json.loads(status.read_text())["state"] == name
                except (FileNotFoundError, json.JSONDecodeError):
                    return False
            with (base / "worker.log").open("w+") as log:
                process = subprocess.Popen(["bash", str(ROOT / "nightshift/worker.sh"), "--config", str(config)],
                                           env=env, stdout=log, stderr=log)
                try:
                    wait_for(process, lambda: is_state("BLOCKED_WORKTREE"))
                    self.assertEqual(queue.read_text(), original)
                    self.assertEqual(dirty.read_text(), "preserve user work")
                    self.assertFalse((state / "lifecycle/active.json").exists())
                    first = json.loads(status.read_text())["last_heartbeat"]
                    wait_for(process, lambda: json.loads(status.read_text())["last_heartbeat"] != first)
                    self.assertIsNone(process.poll())
                    # An operator can revise the queue and resolve their own work.
                    queue.write_text("")
                    dirty.unlink()
                    wait_for(process, lambda: is_state("IDLE"))
                    self.assertIsNone(process.poll())
                finally:
                    process.terminate()
                    process.wait(timeout=8)
                self.assertEqual(process.returncode, 0)


class ForegroundLauncherTests(unittest.TestCase):
    def test_launcher_retries_exit_and_forces_persistent_mode_until_operator_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            runner = base / "runner"
            runner.mkdir()
            launcher = runner / "run_worker.sh"
            launcher.write_bytes((ROOT / "nightshift/templates/run_worker.sh").read_bytes())
            (runner / "config.json").write_text("{}")
            core = base / "core/nightshift"
            core.mkdir(parents=True)
            capture = base / "attempts"
            fake = core / "worker.sh"
            fake.write_text('''#!/usr/bin/env bash
printf '%s\\n' "$RUN_ONCE" >> "$NS_TEST_CAPTURE"
count=$(wc -l < "$NS_TEST_CAPTURE")
if [ "$count" -eq 1 ]; then exit 7; fi
exec python3 -c 'import time; time.sleep(60)'
''')
            fake.chmod(0o755)
            env = dict(os.environ, NIGHTSHIFT_CORE=str(core.parent), NS_TEST_CAPTURE=str(capture),
                       NIGHTSHIFT_RETRY_SECONDS="0.05", RUN_ONCE="1")
            with (base / "launcher.log").open("w+") as log:
                process = subprocess.Popen(["bash", str(launcher)], env=env, stdout=log, stderr=log)
                try:
                    wait_for(process, lambda: capture.exists() and len(capture.read_text().splitlines()) >= 2)
                    self.assertEqual(capture.read_text().splitlines(), ["0", "0"])
                    self.assertIsNone(process.poll())
                finally:
                    process.terminate()
                    process.wait(timeout=8)
                self.assertEqual(process.returncode, 0)
                log.seek(0)
                output = log.read()
                self.assertTrue(output.isascii())
                self.assertIn("Worker exited with status 7", output)
                self.assertIn("Project:", output)
                self.assertIn("Stopped by operator", output)
