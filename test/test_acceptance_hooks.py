"""Exercise live hook ownership, cold normalization and fresh worker launches."""
from contextlib import redirect_stdout
import io
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

    def test_idle_flush_drains_partial_counters_once_in_order(self):
        cfg = {"cold_every": 5, "cold": "true", "hooks": [
            {"id": name, "every": 5, "argv": ["true"]}
            for name in ("first", "second")]}
        scheduler = hooks.Scheduler(cfg)
        for index in range(3):
            scheduler.accepted(f"TASK-{index}", str(index), self.head, committed=True)
        self.assertTrue(scheduler.flush_idle(self.head))
        self.assertEqual(scheduler.counts, {"nightshift-cold": 0, "first": 0, "second": 0})
        self.assertFalse(scheduler.flush_idle(self.head))
        for name in ("nightshift-cold", "first", "second"):
            run = scheduler.next_run()
            self.assertEqual((run["hook"], run["revision"]), (name, self.head))
            scheduler.settle(run["id"], "passed")
        self.assertFalse(scheduler.flush_idle(self.head))
        scheduler.accepted("TASK-NEW", "new", self.head)
        self.assertTrue(scheduler.flush_idle(self.head))
        self.assertEqual(scheduler.next_run()["hook"], "first")

    def test_idle_flush_background_uses_existing_single_slot(self):
        scheduler = hooks.Scheduler({"hooks": [{"id": "background", "every": 5,
            "argv": ["true"], "second_stage": {"argv": ["true"]}}]})
        scheduler.accepted("TASK-A", "a", self.head, committed=True)
        self.assertFalse(scheduler.background.has_work())
        self.assertTrue(scheduler.flush_idle(self.head))
        run = scheduler.background.next(self.root, self.runner / "background")
        self.assertEqual(run["trigger_task"], "TASK-A")
        self.assertEqual(scheduler.background.counts["background"], 0)
        scheduler.accepted("TASK-B", "b", self.head, committed=True)
        self.assertFalse(scheduler.flush_idle(self.head))
        self.assertEqual(scheduler.background.counts["background"], 1)

    def test_daemon_flushes_only_after_sixty_idle_seconds(self):
        marker = self.runner / "idle-marker"
        command = ("from pathlib import Path\n"
                   f"with Path({str(marker)!r}).open('a') as stream:\n"
                   "    stream.write('ran')\n")
        scheduler = hooks.Scheduler({"hooks": [{"id": "partial", "every": 5,
            "argv": [sys.executable, "-c", command]}]})
        scheduler.accepted("TASK-A", "a", self.head)
        clock = [0]
        observations = []

        def empty_queue(*args, **kwargs):
            clock[0] += 30
            observations.append(marker.exists())
            if len(observations) == 7:
                raise RuntimeError("fixture complete")
            return ""

        with patch.dict(os.environ, {"RUN_ONCE": "0", "POLL_INTERVAL": ".001"}), \
                patch.object(lifecycle, "time", wraps=time) as session_time, \
                patch.object(runtime, "pop_task", side_effect=empty_queue):
            session_time.monotonic.side_effect = lambda: clock[0]
            with self.assertRaisesRegex(RuntimeError, "fixture complete"):
                lifecycle.run_session(self.root, runtime, scheduler)
        self.assertEqual(observations[:3], [False, False, False])
        self.assertTrue(all(observations[3:]))
        self.assertEqual(marker.read_text(), "ran")
        self.assertEqual(scheduler.counts["partial"], 0)

    def test_pause_restarts_the_idle_flush_timer(self):
        scheduler = hooks.Scheduler(self.cfg)
        scheduler.accepted("TASK-A", "a", self.head)
        clock = [0]
        counts_at_claim = []
        pause = self.runner / "PAUSE"
        save = gate.save

        def observe_status(path, value):
            save(path, value)
            if Path(path).name == "worker.status" and value.get("state") == "PAUSED":
                clock[0] = 120
                pause.unlink()

        def empty_queue(*args, **kwargs):
            clock[0] += 30
            counts_at_claim.append(scheduler.counts["periodic"])
            if len(counts_at_claim) == 2:
                pause.touch()
            if len(counts_at_claim) == 6:
                raise RuntimeError("fixture complete")
            return ""

        with patch.dict(os.environ, {"RUN_ONCE": "0", "POLL_INTERVAL": ".001"}), \
                patch.object(lifecycle, "time", wraps=time) as session_time, \
                patch.object(runtime, "pop_task", side_effect=empty_queue), \
                patch.object(gate, "save", side_effect=observe_status):
            session_time.monotonic.side_effect = lambda: clock[0]
            with self.assertRaisesRegex(RuntimeError, "fixture complete"):
                lifecycle.run_session(self.root, runtime, scheduler)
        self.assertEqual(counts_at_claim, [1, 1, 1, 1, 1, 0])

    def test_external_no_response_waits_without_repeated_dispatch_or_messages(self):
        self.runner.mkdir(exist_ok=True)
        task = "TASK-WAIT [CODE: FIX] | LEVEL: 1 | TARGET: fixture | VERIFY: true"
        (self.runner / "tasks.txt").write_text(task + "\n")
        scheduler = hooks.Scheduler(self.cfg)
        scheduler.accepted("TASK-PREVIOUS", "previous", self.head)
        output = io.StringIO()
        clock = [0]

        def no_response(args, agents, agent_state, recover):
            args.agent_no_response = True
            agent_state["consecutive_no_response"] = len(agents)
            return 1, False

        def boundary():
            clock[0] += 30
            if clock[0] >= 180:
                raise RuntimeError("fixture complete")

        with patch.dict(os.environ, {"RUN_ONCE": "0", "POLL_INTERVAL": ".001"}), \
                patch.object(runtime, "load_agent_registry", return_value=[{"id": "fixture"}]), \
                patch.object(runtime, "validate_task_capacity"), \
                patch.object(lifecycle.preflight, "check", return_value={"status": "ready"}), \
                patch.object(runtime, "execute_registered_agents", side_effect=no_response) as execute, \
                patch.object(lifecycle, "time", wraps=time) as session_time, \
                patch.object(scheduler.background, "poll", side_effect=boundary), \
                patch.object(scheduler, "flush_idle") as flush, redirect_stdout(output):
            session_time.monotonic.side_effect = lambda: clock[0]
            with self.assertRaisesRegex(RuntimeError, "fixture complete"):
                lifecycle.run_session(self.root, runtime, scheduler)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(output.getvalue().count("reporting to planner."), 1)
        self.assertEqual((self.runner / "tasks.txt").read_text(), task + "\n")
        flush.assert_not_called()

    def test_pending_queue_failure_and_pause_gates_exclude_idle_flush(self):
        self.runner.mkdir(exist_ok=True)
        task = "TASK-PENDING [CODE: FIX] | LEVEL: 1 | TARGET: fixture | VERIFY: false\n"
        queue = self.runner / "tasks.txt"
        queue.write_text(task)
        for gate_file, expected in (("lifecycle/paused.json", "PAUSED_FOR_PLANNER"),
                                    (".worker-dispatch-gate.json", "PAUSED_FOR_PLANNER"),
                                    ("PAUSE", "PAUSED")):
            with self.subTest(gate_file=gate_file):
                blocker = self.runner / gate_file
                gate.save(blocker, {"reason": "hot acceptance failed; awaiting Planner repair"})
                scheduler = hooks.Scheduler(self.cfg)
                scheduler.accepted("TASK-PREVIOUS", "previous", self.head)
                clock = [0]

                def boundary():
                    clock[0] += 30
                    if clock[0] >= 180:
                        raise RuntimeError("fixture complete")

                with patch.dict(os.environ, {"RUN_ONCE": "0", "POLL_INTERVAL": ".001"}), \
                        patch.object(lifecycle, "time", wraps=time) as session_time, \
                        patch.object(scheduler.background, "poll", side_effect=boundary), \
                        patch.object(scheduler, "flush_idle") as flush, \
                        patch.object(runtime, "pop_task") as claim:
                    session_time.monotonic.side_effect = lambda: clock[0]
                    with self.assertRaisesRegex(RuntimeError, "fixture complete"):
                        lifecycle.run_session(self.root, runtime, scheduler)
                self.assertEqual(json.loads((self.runner / "worker.status").read_text())["state"], expected)
                self.assertEqual(scheduler.counts["periodic"], 1)
                self.assertEqual(queue.read_text(), task)
                flush.assert_not_called()
                claim.assert_not_called()
                blocker.unlink()

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
