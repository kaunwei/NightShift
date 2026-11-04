import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


class WatcherTests(unittest.TestCase):
    def test_existing_pause_with_pending_queue_exits_immediately(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            nightshift = root / 'nightshift'
            nightshift.mkdir()
            shutil.copy(Path(__file__).resolve().parents[1] / 'nightshift/watch_worker.sh', nightshift)
            (nightshift / 'tasks.txt').write_text('TASK-NEXT | LEVEL: 1\n')
            (nightshift / 'worker.status').write_text(json.dumps({'state': 'PAUSED_FOR_PLANNER', 'current_task': None}))
            env = dict(os.environ, WORKER_INACTIVE_REPEAT='1', WORKER_INACTIVE_TIMEOUT='0')
            result = subprocess.run(['bash', str(nightshift / 'watch_worker.sh'), '0', '1'], env=env, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('[BLOCKED]', result.stdout)
            self.assertIn('Remaining: 1', result.stdout)
