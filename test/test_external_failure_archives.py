"""Failed external attempts must leave recovery evidence outside the project."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import worker_runtime


class ExternalFailureArchiveTests(unittest.TestCase):
    def test_failed_attempt_recovers_clean_project_and_archives_in_runner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            project = root / 'project'
            project.mkdir()
            subprocess.run(['git', 'init', '-q', str(project)], check=True)
            subprocess.run(['git', '-C', str(project), '-c', 'user.name=Test',
                            '-c', 'user.email=test@example.invalid', 'commit',
                            '--allow-empty', '-qm', 'baseline'], check=True)
            state = root / 'runner'
            snapshot = state / '.scratch/attempts/TASK-FAIL/attempt-1'
            environment = {'NIGHTSHIFT_CONFIG_FILE': str(state / 'config.json'),
                           'NIGHTSHIFT_STATE_DIR': str(state)}
            with patch.dict(os.environ, environment):
                worker_runtime.capture_attempt_baseline(project, 'TASK-FAIL', 'attempt-1', snapshot)
                (project / 'failed-product-change.txt').write_text('failed attempt\n')
                archive = worker_runtime.rollback_failed_task(
                    project, project, 'TASK-FAIL', [], snapshot, 'attempt-1')
            self.assertEqual(archive, state / '.scratch/failed_tasks/TASK-FAIL_attempt-1')
            self.assertTrue((archive / 'recovery.json').is_file())
            self.assertIn('failed-product-change.txt', (archive / 'status.txt').read_text())
            self.assertFalse((project / '.scratch').exists())
            self.assertEqual(subprocess.check_output(
                ['git', '-C', str(project), 'status', '--porcelain']), b'')

    def test_embedded_scratch_location_remains_compatible(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / 'nightshift').mkdir()
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(worker_runtime._scratch_state_root(project),
                                 project / 'nightshift/.scratch')
