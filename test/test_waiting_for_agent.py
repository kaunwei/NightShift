"""Black-box checks for an exhausted queue head in a mounted daemon."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / 'scripts' / 'worker_runtime.py'


class WaitingForAgentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        parent = Path(temporary.name).resolve()
        self.project = parent / 'project'
        self.runner = parent / 'runner'
        self.project.mkdir()
        self.runner.mkdir()
        subprocess.run(['git', 'init', '-q', str(self.project)], check=True)
        subprocess.run(['git', '-C', str(self.project), '-c', 'user.name=Fixture',
                        '-c', 'user.email=fixture@example.invalid', 'commit', '--allow-empty',
                        '-qm', 'baseline'], check=True)
        self.adapter = parent / 'fixture.py'
        self.adapter.write_text(
            'import json, os, time\n'
            'if os.environ["NIGHTSHIFT_TASK_ID"] == "TASK-EXHAUSTED" and os.environ.get("FIXTURE_SLOW") == "1":\n'
            '    time.sleep(2)\n'
            'with open(os.environ["NIGHTSHIFT_RESULT_FILE"], "w") as result:\n'
            '    json.dump({"outcome":"complete","changed":False,"commit_message":"test: finish fixture","verification_evidence":"Fixture success"}, result)\n')
        self.config = self.runner / 'config.json'
        self.exhausted = 'TASK-EXHAUSTED | LEVEL: 1 | TARGET: output.txt | ACTION: Fixture | VERIFY: true'
        self.replacement = 'TASK-REPLACEMENT | LEVEL: 1 | TARGET: output.txt | ACTION: Fixture | VERIFY: true'
        self.queue = self.runner / 'tasks.txt'
        self.queue.write_text(self.exhausted + '\n')
        self.write_registry(slow=True)
        self.log = (parent / 'daemon.log').open('w+')
        self.addCleanup(self.log.close)
        env = {key: value for key, value in os.environ.items()
               if not key.startswith('NIGHTSHIFT_') and key not in ('RUN_ONCE', 'PAUSE_FILE')}
        self.process = subprocess.Popen([sys.executable, str(RUNTIME), 'daemon', '--root', str(ROOT),
                                         '--config', str(self.config), '--project', 'fixture'],
                                        env=dict(env, RUN_ONCE='0', POLL_INTERVAL='0.05'),
                                        stdout=self.log, stderr=subprocess.STDOUT)
        self.addCleanup(self.stop)
        self.wait_for(lambda: self.status().get('state') == 'WAITING_FOR_AGENT')

    def write_registry(self, slow):
        entry = {'default': True, 'worker': {'step_base': {'L1': 10, 'L2': 10, 'L3': 10},
                                             'task_timeout_seconds': 0.5},
                 'agent': {'adapter': 'generic', 'config': {'initial_score': 5}, 'command': sys.executable, 'args': [str(self.adapter)],
                           'env': {'FIXTURE_SLOW': '1' if slow else '0'}}}
        temp = self.config.with_suffix('.tmp')
        temp.write_text(json.dumps({'version': 1, 'projects': {'fixture': {'path': str(self.project),
                                                                             'state': str(self.runner)}},
                                    'agents': {'test': entry}}))
        temp.replace(self.config)

    def status(self):
        path = self.runner / 'worker.status'
        return json.loads(path.read_text()) if path.exists() else {}

    def stop(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def wait_for(self, predicate):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if predicate():
                return
            if self.process.poll() is not None:
                break
            time.sleep(0.02)
        self.log.seek(0)
        self.fail('Expected daemon state not reached:\n' + self.log.read()[-5000:])

    def test_exhausted_head_does_not_reclaim_and_changed_head_wakes(self):
        runs = self.runner / 'lifecycle' / 'runs'
        progress = self.runner / 'progress.log'
        initial_heartbeat = self.status()['last_heartbeat']
        self.wait_for(lambda: self.status()['last_heartbeat'] != initial_heartbeat)
        self.assertEqual(len(list(runs.iterdir())), 1)
        self.assertEqual(progress.read_text().count('[AGENT_UNAVAILABLE] TASK-EXHAUSTED:'), 1)
        self.assertEqual(self.queue.read_text(), self.exhausted + '\n')
        pause = self.runner / 'PAUSE'
        pause.touch()
        self.wait_for(lambda: self.status().get('state') == 'PAUSED')
        self.queue.write_text(self.replacement + '\n')
        self.assertEqual(len(list(runs.iterdir())), 1)
        pause.unlink()
        self.wait_for(lambda: '[DONE] TASK-REPLACEMENT' in (self.runner / 'tasks.done').read_text())
        self.assertEqual(len(list(runs.iterdir())), 2)
        self.assertEqual(self.status()['pid'], self.process.pid)

    def test_changed_registration_reconsiders_the_same_head(self):
        self.write_registry(slow=False)
        self.wait_for(lambda: '[DONE] TASK-EXHAUSTED' in (self.runner / 'tasks.done').read_text())
        self.assertEqual(len(list((self.runner / 'lifecycle' / 'runs').iterdir())), 2)
        self.assertEqual(self.status()['pid'], self.process.pid)
