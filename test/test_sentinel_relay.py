import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import subprocess

spec = importlib.util.spec_from_file_location('sentinel_relay', Path(__file__).resolve().parents[1] / 'nightshift/sentinel_relay.py')
relay_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay_module)


class RelayTests(unittest.TestCase):
    def test_progress_does_not_queue_a_turn(self):
        with patch.object(subprocess, 'run') as run:
            self.assertFalse(relay_module.relay('[DONE] TASK-ONE', 'thread', 'context'))
            run.assert_not_called()

    def test_blocker_explicitly_queues_and_resumes_selected_thread(self):
        with patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'queued', '')) as run:
            self.assertTrue(relay_module.relay('[SENTINEL_PAUSED_FOR_PLANNER] paused', 'selected-thread', 'context'))
            command = run.call_args.args[0]
            self.assertEqual(command[:4], ['codex', 'queue', '--thread', 'selected-thread'])
            self.assertEqual(command[-1], '--resume')

    def test_resume_failure_is_not_reported_as_delivery(self):
        with patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, '', 'warning: resume failed')):
            with self.assertRaises(RuntimeError):
                relay_module.relay('[SENTINEL_BLOCKED] error', 'thread', 'context')

    def test_agy_resumes_only_explicit_conversation(self):
        with patch.object(subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, 'ok', '')) as run:
            self.assertTrue(relay_module.relay('[SENTINEL_BLOCKED] paused', 'agy-id', 'context', agent='agy'))
            command = run.call_args.args[0]
            self.assertEqual(command[:4], ['agy', '--conversation', 'agy-id', '-p'])
            self.assertNotIn('--continue', command)
            self.assertNotIn('codex', command)

    def test_unknown_agent_cannot_fall_back_to_codex(self):
        with patch.object(subprocess, 'run') as run:
            with self.assertRaises(ValueError):
                relay_module.relay('[SENTINEL_BLOCKED] paused', 'id', 'context', agent='unknown')
            run.assert_not_called()


class ExternalWatcherContextTests(unittest.TestCase):
    def test_nested_watcher_receives_selected_external_config_and_project(self):
        from unittest.mock import MagicMock
        process = MagicMock()
        process.stdout = []
        process.wait.return_value = 0
        environment = {"NIGHTSHIFT_CONFIG_FILE": "/runner/ArtStudio/config.json",
                       "NIGHTSHIFT_PROJECT_NAME": "ArtStudio"}
        with patch.dict(relay_module.os.environ, environment, clear=True), \
             patch.object(relay_module.sys, "argv", ["relay", "--root", "/tmp", "--planner-id", "thread"]), \
             patch.object(relay_module.subprocess, "Popen", return_value=process) as popen:
            self.assertEqual(relay_module.main(), 0)
        command = popen.call_args.args[0]
        self.assertEqual(command[2:6], ["--config", "/runner/ArtStudio/config.json", "--project", "ArtStudio"])
