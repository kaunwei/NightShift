"""Real Git/process/daemon seams for script-only follow-up tickets."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import acceptance as gate
import acceptance_hooks as hooks
import attempt_archive
import evidence_capabilities
import hook_control
import lifecycle
import preflight
import worker_runtime as runtime


class Fixture(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.root = self.base / "project"
        self.root.mkdir()
        self.runner = self.base / "runner"
        self.runner.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        (self.root / "file").write_text("base\n")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.head = self.git("rev-parse", "HEAD").decode().strip()
        env = patch.dict(os.environ, {"NIGHTSHIFT_STATE_DIR": str(self.runner),
                                      "NIGHTSHIFT_CONFIG_FILE": str(self.base / "config.json"),
                                      "RUN_ONCE": "1"})
        env.start()
        self.addCleanup(env.stop)

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True).stdout

    def config(self, worker=None, acceptance=None):
        path = self.base / "config.json"
        path.write_text(json.dumps({"version": 1, "agents": {"fixture": {
            "worker": {"step_base": {"L1": 10, "L2": 10, "L3": 10}, **(worker or {})},
            "agent": {"adapter": "generic", "command": sys.executable}}},
            "acceptance": {"version": 1, "hot": "true", **(acceptance or {})}}))
        return path


class RetentionTests(Fixture):
    def test_recovery_retains_staged_worktree_untracked_binary_symlink_and_deletion(self):
        snapshot = self.base / "baseline"
        runtime.capture_attempt_baseline(self.root, "TASK-X", "1", snapshot)
        (self.root / "file").write_text("staged\n")
        self.git("add", "file")
        (self.root / "file").write_text("unstaged\n")
        (self.root / "new.py").write_bytes(b"binary\0payload\xff")
        (self.root / "new.py").chmod(0o750)
        (self.root / "link").symlink_to("/outside/never-follow")
        archive = self.base / "failure"
        runtime.recover_attempt_baseline(self.root, snapshot, archive)
        self.assertEqual((self.root / "file").read_text(), "base\n")
        self.assertFalse((self.root / "new.py").exists())
        data = attempt_archive.verify(archive / "attempt")
        self.assertEqual(data["entries"]["new.py"]["mode"], 0o750)
        self.assertEqual((archive / "attempt/untracked/new.py").read_bytes(), b"binary\0payload\xff")
        self.assertEqual(os.readlink(archive / "attempt/untracked/link"), "/outside/never-follow")
        self.assertIn(b"staged", (archive / "attempt/index.diff").read_bytes())
        self.assertIn(b"unstaged", (archive / "attempt/worktree.diff").read_bytes())

    def test_corrupt_or_unrestorable_package_stops_cleanup(self):
        snapshot = self.base / "baseline"
        runtime.capture_attempt_baseline(self.root, "TASK-X", "1", snapshot)
        (self.root / "file").write_text("do not discard\n")
        with patch.object(attempt_archive, "verify", side_effect=ValueError("cannot restore")):
            with self.assertRaisesRegex(ValueError, "cannot restore"):
                runtime.recover_attempt_baseline(self.root, snapshot, self.base / "failure")
        self.assertEqual((self.root / "file").read_text(), "do not discard\n")

    def test_explicit_clean_and_legacy_rollback_retain_deleted_and_new_files(self):
        (self.root / "file").unlink()
        (self.root / "new").write_text("keep this")
        gate.clean(self.root, external=True)
        package = next((self.runner / "lifecycle/retained").iterdir())
        self.assertEqual(attempt_archive.verify(package)["entries"]["file"]["kind"], "missing")
        (self.root / "newer").write_text("legacy keep")
        archive = runtime.rollback_failed_task(self.root, self.root, "TASK-X", [])
        self.assertEqual((archive / "attempt/untracked/newer").read_text(), "legacy keep")

    def test_package_checksum_is_enforced(self):
        archive = attempt_archive.capture(self.root, self.base / "archive")
        (archive / "worktree.diff").write_text("corrupted")
        with self.assertRaisesRegex(ValueError, "checksum"):
            attempt_archive.verify(archive)


class ReadinessTests(Fixture):
    def test_failure_before_claim_keeps_queue_and_feedback_and_deduplicates(self):
        self.config(worker={"preflight": {"argv": [sys.executable, "-c", "import sys;print('uid map denied',file=sys.stderr);sys.exit(3)"]}})
        queue = self.runner / "tasks.txt"
        queue.write_text("TASK-X [CODE] | TARGET: file\n")
        with patch.object(runtime, "execute_registered_agents", side_effect=AssertionError("model invoked")):
            self.assertEqual(lifecycle.run(self.root, runtime), 2)
        self.assertEqual(queue.read_text(), "TASK-X [CODE] | TARGET: file\n")
        result = json.loads((self.runner / "lifecycle/preflight.json").read_text())
        self.assertEqual(result["status"], "environment-blocked")
        self.assertEqual(result["evidence"][0]["exit"], 3)
        self.assertIn("uid map denied", result["evidence"][0]["output"])
        self.assertFalse((self.runner / "tasks.done").read_text())
        self.assertFalse(json.loads((self.runner / ".worker-score.json").read_text())["feedback"])

    def test_exact_configured_probe_uses_registration_environment_and_runner_roundtrip(self):
        agent = {"id": "fixture", "command": sys.executable, "env": {"PROBE_EXPECTED": "present"},
                 "worker": {"preflight": {"required_tools": [sys.executable], "argv": [
                     "{executable}", "{probe}", "{project}", "{state}"]}}}
        result = preflight.check(self.root, self.runner, [agent], runtime.run_verify)
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["sandbox_probes"], 1)
        self.assertEqual(list((self.runner / "preflight").iterdir()), [])
        agent["worker"]["preflight"]["argv"] = [sys.executable, "-c", "import os;assert os.environ['PROBE_EXPECTED']=='present'"]
        self.assertEqual(preflight.check(self.root, self.runner, [agent], runtime.run_verify)["status"], "ready")

    def test_probe_timeout_and_missing_tool_are_environment_failures(self):
        agent = {"id": "fixture", "command": sys.executable, "worker": {"preflight": {
            "argv": [sys.executable, "-c", "import time;time.sleep(10)"], "timeout": .1}}}
        self.assertEqual(preflight.check(self.root, self.runner, [agent], runtime.run_verify)["evidence"][0]["exit"], 124)
        agent["worker"]["preflight"] = {"required_tools": ["nightshift-nonexistent-tool"]}
        self.assertIn("required tool missing", preflight.check(self.root, self.runner, [agent], runtime.run_verify)["reason"])


class LiveVerifyTests(Fixture):
    def test_log_is_readable_before_exit_and_timeout_preserves_evidence(self):
        command = shlex.join([sys.executable, "-u", "-c", "import time;print('ACTIVE_CASE',flush=True);time.sleep(10)"])
        results = []
        thread = threading.Thread(target=lambda: results.append(runtime.run_verify(command, self.root, 3001, .5)))
        thread.start()
        deadline = time.monotonic() + 3
        found = False
        while thread.is_alive() and time.monotonic() < deadline:
            logs = list((self.runner / "lifecycle/verify").glob("*.log"))
            if logs and b"ACTIVE_CASE" in logs[0].read_bytes():
                found = True
                break
            time.sleep(.01)
        self.assertTrue(found)
        self.assertTrue(thread.is_alive())
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        code, output = results[0]
        self.assertEqual(code, 124)
        self.assertTrue(output.timed_out)
        self.assertIn("ACTIVE_CASE", Path(output.log_path).read_text())
        self.assertEqual(json.loads(Path(output.log_path).with_suffix(".json").read_text())["status"], "timeout")

    def test_large_output_keeps_full_log_and_bounded_tail(self):
        code, output = runtime.run_verify(shlex.join([sys.executable, "-c", "print('x'*200000)"]), self.root, 3001, 3)
        self.assertEqual(code, 0)
        self.assertLessEqual(len(output), 65536)
        self.assertEqual(Path(output.log_path).stat().st_size, 200001)

    def test_truncated_output_cannot_hide_empty_tests_or_invalid_repro(self):
        for title, marker, status in (("[CODE]", "Ran 0 tests", 9),
                                      ("[DIAGNOSTIC]", "syntax error", 4)):
            with self.subTest(title=title):
                command = shlex.join([sys.executable, "-c", f"print({marker!r});print('x'*200000)"])
                result = subprocess.run([sys.executable, str(SCRIPTS / "worker_runtime.py"),
                    "mechanical-audit", "--work-dir", str(self.root), "--base", self.head,
                    "--target", "file", "--title", title, "--task-id", "TASK-X", "--verify", command],
                    check=True, capture_output=True, text=True)
                self.assertEqual(json.loads(result.stdout)["status"], status)


class CapabilityTests(Fixture):
    def test_mixed_framework_contract_keeps_nonce_and_duplicate_checks(self):
        cap = {"frameworks": [{"name": "python", "id_prefixes": ["test_"]},
                              {"name": "gut", "id_prefixes": ["tests/"]}], "case_selection": False}
        evidence = self.base / "mixed.py"
        cases = [{"id": "test_scheduler.Case.test_run", "source": "scheduler.py", "fingerprint": "a" * 64, "baseline_fingerprint": None},
                 {"id": "tests/behavior.gd::test_run", "source": "tests/behavior.gd", "fingerprint": "b" * 64, "baseline_fingerprint": None}]
        def write(rows, stale=False):
            payload = "'stale'" if stale else "os.environ['NIGHTSHIFT_RUN']"
            evidence.write_text("import json,os\nfrom pathlib import Path\nPath(os.environ['NIGHTSHIFT_RESULT']).write_text(json.dumps({'run':"
                                + payload + ", 'cases':" + repr(rows) + ", 'supports_case_selection':False}))\n")
        cfg = {"hot": shlex.join([sys.executable, str(evidence)]), "hot_timeout": 5, "capabilities": cap}
        runner = gate.DefaultAcceptanceRunner()
        write(cases)
        result, _ = runner.invoke(self.root, cfg, "hot", "discover", self.head, runtime.run_verify)
        self.assertEqual(set(result), {c["id"] for c in cases})
        write(cases, stale=True)
        with self.assertRaisesRegex(gate.HotFailure, "stale"):
            runner.invoke(self.root, cfg, "hot", "discover", self.head, runtime.run_verify)
        write([*cases, cases[0]])
        with self.assertRaisesRegex(gate.GateError, "unique"):
            runner.invoke(self.root, cfg, "hot", "discover", self.head, runtime.run_verify)

    def test_mixed_namespaces_validate_and_unknown_differs_from_unsupported(self):
        cap = {"frameworks": [{"name": "unittest", "id_prefixes": ["test_"]},
                              {"name": "gut", "id_prefixes": ["tests/"]}], "case_selection": False}
        self.assertTrue(evidence_capabilities.supports(evidence_capabilities.validate(cap), "test_scheduler.Case.test_run"))
        self.assertTrue(evidence_capabilities.supports(cap, "tests/test_case.gd::test_run"))
        self.config(acceptance={"capabilities": cap})
        command = self.base / "evidence.py"
        command.write_text("import os,json\nfrom pathlib import Path\nPath(os.environ['NIGHTSHIFT_RESULT']).write_text(json.dumps({'run':os.environ['NIGHTSHIFT_RUN'],'cases':[],'supports_case_selection':False}))\n")
        args = type("Args", (), {"work_dir": str(self.root), "base": self.head, "task_id": "TASK-X"})()
        cfg = gate.config(self.root)
        cfg["hot"] = shlex.join([sys.executable, str(command)])
        with patch.object(gate, "config", return_value=cfg):
            for identity, message in (("pytest.X", "namespace unsupported"), ("test_unknown.X", "unknown or ambiguous")):
                with self.subTest(identity=identity), self.assertRaisesRegex(gate.GateError, message):
                    gate.hot(args, {"tdd_cases": [{"id": identity, "source": "file"}]}, runtime.run_verify)


class DurableHookTests(Fixture):
    def scheduler(self, **extra):
        return hooks.Scheduler({"durable_hooks": True, "hooks": [{"id": "periodic", "every": 2, "argv": ["true"]}], **extra},
                               state_path=self.runner / "hooks.json", project=self.root)

    def test_counters_registration_passed_tombstone_and_replay_survive_relaunch(self):
        first = self.scheduler()
        first.register({"id": "once", "after": "TASK-B", "argv": ["true"]})
        first.accepted("TASK-A", "event-a", self.head)
        second = self.scheduler()
        self.assertTrue(second.accepted("TASK-B", "event-b", self.head))
        run = second.next_run()
        self.assertEqual(run["hook"], "periodic")
        second.settle(run["id"], "passed")
        third = self.scheduler()
        self.assertFalse(third.accepted("TASK-B", "event-b", self.head))
        run = third.next_run()
        self.assertEqual(run["hook"], "once")
        third.settle(run["id"], "passed")
        self.assertIsNone(self.scheduler().next_run())

    def test_interrupted_command_requires_explicit_retry_or_cancel(self):
        first = self.scheduler()
        first.accepted("TASK-A", "a", self.head)
        first.accepted("TASK-B", "b", self.head)
        run = first.next_run()
        second = self.scheduler()
        self.assertTrue(second.interrupted())
        second.retry(run["id"])
        self.assertEqual(second.next_run()["id"], run["id"])
        third = self.scheduler()
        third.cancel(run["id"])
        self.assertFalse(third.interrupted())
        self.assertIsNone(self.scheduler().next_run())

    def test_live_pipe_list_cancel_and_retry_are_actual_control_operations(self):
        scheduler = self.scheduler()
        scheduler.accepted("TASK-A", "a", self.head)
        scheduler.accepted("TASK-B", "b", self.head)
        with hook_control.serve(self.root, scheduler):
            result = hook_control.request(self.root, {"command": "list"})
            run_id = result["runs"][0]["id"]
            self.assertTrue(result["durable"])
            hook_control.request(self.root, {"command": "cancel", "run_id": run_id})
        self.assertIsNone(self.scheduler().next_run())

    def test_incompatible_config_is_rejected_without_overwriting_state(self):
        first = self.scheduler()
        first.register({"id": "once", "after": "TASK-B", "argv": ["true"]})
        before = (self.runner / "hooks.json").read_bytes()
        with self.assertRaisesRegex(gate.GateError, "incompatible"):
            self.scheduler(hooks=[])
        self.assertEqual((self.runner / "hooks.json").read_bytes(), before)

    def test_interrupted_run_blocks_daemon_before_claim(self):
        self.config()
        first = self.scheduler()
        first.accepted("TASK-A", "a", self.head)
        first.accepted("TASK-B", "b", self.head)
        first.next_run()
        queue = self.runner / "tasks.txt"
        queue.write_text("TASK-NEXT | TARGET: file\n")
        with patch.object(runtime, "execute_registered_agents", side_effect=AssertionError("model invoked")):
            self.assertEqual(lifecycle.run_session(self.root, runtime, self.scheduler()), 2)
        self.assertEqual(queue.read_text(), "TASK-NEXT | TARGET: file\n")

    def test_storage_failure_never_dispatches_unpersisted_run(self):
        scheduler = self.scheduler()
        scheduler.accepted("TASK-A", "a", self.head)
        with patch.object(gate, "save", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                scheduler.accepted("TASK-B", "b", self.head)
        with self.assertRaisesRegex(gate.GateError, "persistence failed"):
            scheduler.next_run()


class CapacityTests(Fixture):
    def test_capacity_is_read_only_and_reports_outcomes_and_environment_separately(self):
        config = self.config()
        score = runtime.registered_agent_score_path(self.runner / ".worker-agent-scores", "fixture")
        score.parent.mkdir()
        runtime.record_score_result(score, "TASK-A", "accept", event_id="a")
        runtime.record_score_result(score, "TASK-A", "accept", event_id="a")
        runtime.record_score_result(score, "TASK-B", "no_fault")
        gate.save(self.runner / "lifecycle/preflight.json", {"status": "environment-blocked"})
        before = score.read_bytes()
        result = subprocess.run([sys.executable, str(SCRIPTS / "worker_runtime.py"), "capacity", "--root", str(self.root), "--config", str(config)],
                                check=True, capture_output=True, text=True)
        data = json.loads(result.stdout)
        self.assertEqual(data["agents"][0]["recent_outcomes"]["accept"], 1)
        self.assertEqual(data["agents"][0]["recent_accept_streak"], 1)
        self.assertEqual(data["preflight"]["status"], "environment-blocked")
        self.assertEqual(score.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
