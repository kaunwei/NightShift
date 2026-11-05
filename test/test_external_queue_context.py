import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class ExternalQueueContextTests(unittest.TestCase):
    def test_reorder_uses_activated_runner_not_core_queue(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / 'project'
            project.mkdir()
            subprocess.run(['git', 'init', '-q', str(project)], check=True)
            state = root / 'runner'
            state.mkdir()
            tasks = state / 'tasks.txt'
            tasks.write_text('TASK-OLD\n')
            config = state / 'config.json'
            config.write_text(json.dumps({'version': 1, 'projects': {'sample': {
                'path': str(project), 'state': str(state)}}}))
            environment = dict(os.environ)
            environment.update(NIGHTSHIFT_CONFIG_FILE=str(config),
                               NIGHTSHIFT_PROJECT_NAME='sample', TASKS_FILE=str(tasks))
            command = Path(__file__).resolve().parents[1] / 'scripts/reorder_queue.sh'
            result = subprocess.run(['bash', str(command)], input='TASK-NEW\n', text=True,
                                    env=environment, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(tasks.read_text(), 'TASK-NEW\n')
