"""Exercise live hook ownership, cold normalization and fresh worker launches."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import acceptance as gate
import acceptance_hooks as hooks
import hook_control
import lifecycle
import worker_runtime as runtime


class HookTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        parent = Path(temp.name).resolve()
        self.root, self.runner = parent / "project", parent / "runner"
        self.root.mkdir()
        self.config = parent / "config.json"
        self.cfg = {"hooks": [{"id": "periodic", "every": 2, "argv": ["true"]}]}
        self.write_config()
        env = patch.dict(os.environ, {"NIGHTSHIFT_CONFIG_FILE": str(self.config),
                                     "NIGHTSHIFT_STATE_DIR": str(self.runner),
                                     "RUN_ONCE": "1"}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        (self.root / "fixture").write_text("accepted")
        self.git("add", "fixture")
        self.git("commit", "-qm", "accepted")
        self.head = self.git("rev-parse", "HEAD")

    def write_config(self, agents=None):
        self.config.write_text(json.dumps({"version": 1, "acceptance": self.cfg,
                                          "projects": {"fixture": {"path": str(self.root),
                                                                   "state": str(self.runner)}},
                                          "agents": agents or {}}))

    def git(self, *argv):
        return subprocess.check_output(["git", "-C", str(self.root), *argv], text=True).strip()

    def test_periodic_cold_and_one_shot_share_live_scheduler(self):
        scheduler = hooks.Scheduler({**self.cfg, "cold_every": 1, "cold": "echo cold"})
        scheduler.accepted("TASK-A", "a", self.head)
        self.assertIsNone(scheduler.next_run())
        spec = {"id": "demo", "after": "TASK-B", "argv": [sys.executable, "-c",
                "import os; print(os.environ['NIGHTSHIFT_HOOK_REVISION'])"]}
        self.assertTrue(scheduler.register(spec))
        self.assertFalse(scheduler.register(spec))
        scheduler.accepted("TASK-A", "a", self.head)
        scheduler.accepted("TASK-B", "b", self.head, committed=True)
        run = scheduler.next_run()
        self.assertEqual(run["kind"], "cold")
        scheduler.settle(run["id"], "passed")
        run = scheduler.next_run()
        self.assertEqual(run["hook"], "periodic")
        scheduler.settle(run["id"], "passed")
        run = scheduler.next_run()
        self.assertEqual(run["trigger_task"], "TASK-B")
        self.assertEqual(hooks.execute(self.root, run, runtime.run_verify).strip(), self.head)
        scheduler.settle(run["id"], "passed")
        self.assertIsNone(scheduler.next_run())

    def test_new_session_discards_counters_pending_work_and_registrations(self):
        spec = {"id": "demo", "after": "TASK-B", "argv": ["true"]}
        first = hooks.Scheduler(self.cfg)
        first.register(spec)
        first.accepted("TASK-A", "a", self.head)
        first.accepted("TASK-B", "b", self.head)
        self.assertEqual(len(first.pending), 2)
        second = hooks.Scheduler(self.cfg)
        self.assertIsNone(second.next_run())
        second.accepted("TASK-C", "c", self.head)
        self.assertIsNone(second.next_run())
        self.assertTrue(second.register(spec))

    def test_failed_hook_pauses_without_reverting_and_can_retry_live(self):
        scheduler = hooks.Scheduler(self.cfg)
        scheduler.register({"id": "broken", "after": "TASK-A",
                            "argv": [sys.executable, "-c", "raise SystemExit(7)"]})
        scheduler.accepted("TASK-A", "a", self.head)
        lifecycle.run_session(self.root, runtime, scheduler)
        report = json.loads(next((self.runner / "lifecycle/reports").glob("*/report.json")).read_text())
        self.assertIn("exited 7", report["result"]["runtime_error"]["message"])
        self.assertTrue((self.runner / "lifecycle/paused.json").exists())
        self.assertEqual(self.git("rev-parse", "HEAD"), self.head)
        scheduler.retry(report["result"]["hook"]["id"])
        self.assertIsNotNone(scheduler.next_run())

    def test_manual_cold_ignores_previous_audit_and_legacy_ledger(self):
        marker = self.runner / "cold-marker"
        self.cfg["cold"] = f"echo ran >> {marker}"
        self.write_config()
        state = self.runner / "lifecycle"
        gate.save(state / "cold.json", {"passed": self.head})
        (state / "acceptance-hooks.json").write_text("legacy file is not read")
        (self.runner / "tasks.txt").write_text("TASK-COLD [COLD] | LEVEL: 1\n")
        lifecycle.run(self.root, runtime)
        self.assertEqual(marker.read_text().splitlines(), ["ran"])
        self.assertEqual((state / "acceptance-hooks.json").read_text(), "legacy file is not read")

    def test_worker_launcher_restart_drops_registration_and_live_reregistration_fires(self):
        adapter = self.runner.parent / "adapter.py"
        adapter.write_text("import json, os\nfrom pathlib import Path\n"
                           "Path('output.txt').write_text('fixture')\n"
                           "with open(os.environ['NIGHTSHIFT_RESULT_FILE'], 'w') as out:\n"
                           "    json.dump({'outcome':'complete','changed':True,'commit_message':'test: fixture'}, out)\n")
        self.write_config({"fixture": {"worker": {"step_base": {"L1": 10, "L2": 10, "L3": 10}},
                                      "agent": {"adapter": "generic", "config": {"initial_score": 5}, "command": sys.executable, "args": [str(adapter)]}}})
        marker = self.runner / "launcher-marker"
        spec = {"id": "launch", "after": "TASK-A", "argv": [sys.executable, "-c",
                f"open({str(marker)!r}, 'a').write('ran\\n')"]}
        command = [sys.executable, str(SCRIPTS / "worker_runtime.py"), "hook-register",
                   "--root", str(self.root), "--config", str(self.config), "--project", "fixture",
                   "--spec", json.dumps(spec)]

        log_path = self.runner.parent / "launch.log"

        def launch():
            log = log_path.open("a")
            self.addCleanup(log.close)
            worker = subprocess.Popen(["bash", str(SCRIPTS / "worker.sh"), "--config", str(self.config),
                                       "--project", "fixture"], stdout=log, stderr=subprocess.STDOUT,
                                      env=dict(os.environ, RUN_ONCE="0", POLL_INTERVAL="0.05"))
            def stop():
                if worker.poll() is None:
                    worker.terminate()
                    worker.wait(timeout=8)
            self.addCleanup(stop)
            return stop

        def register():
            end = time.monotonic() + 6
            while time.monotonic() < end:
                proc = subprocess.run(command, capture_output=True, text=True, timeout=4)
                if proc.returncode == 0:
                    return json.loads(proc.stdout)["registered"]
                time.sleep(.05)
            self.fail(proc.stderr)

        stop = launch()
        self.assertTrue(register())
        self.assertFalse(register())
        stop()
        stop = launch()
        self.assertTrue(register())  # A fresh worker has no record of the prior registration.
        runtime.insert_task_front(self.runner / "tasks.txt", "TASK-A | LEVEL: 1 | TARGET: output.txt | VERIFY: true")
        end = time.monotonic() + 6
        while time.monotonic() < end and not marker.exists():
            time.sleep(.05)
        self.assertTrue(marker.exists(), log_path.read_text())
        self.assertEqual(marker.read_text().splitlines(), ["ran"])
        stop()
        self.assertFalse((self.runner / "lifecycle/acceptance-hooks.json").exists())
