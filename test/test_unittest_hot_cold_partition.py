"""Hot partition preserves changed and explicitly required cases."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ADAPTER = Path(__file__).resolve().parents[1] / 'scripts/unittest_hot.py'


class HotColdPartitionTests(unittest.TestCase):
    def test_partition_filters_execution_but_keeps_changed_and_required_cases(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'test').mkdir()
            source = root / 'test/test_fixture.py'
            original = '''import unittest
from pathlib import Path

class Fixture(unittest.TestCase):
    def test_old(self):
        Path('old-ran').touch()
    def test_recent(self):
        Path('recent-ran').touch()
    def test_old_changed(self):
        self.assertEqual(1, 1)
'''
            source.write_text(original)
            subprocess.run(['git', 'init', '-q'], cwd=root, check=True)
            subprocess.run(['git', 'add', 'test'], cwd=root, check=True)
            subprocess.run(['git', '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid',
                            'commit', '-qm', 'baseline'], cwd=root, check=True)
            base = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
            source.write_text(original.replace('self.assertEqual(1, 1)', 'self.assertEqual(2, 2)')
                              + '    def test_new(self):\n        self.assertTrue(True)\n')
            old = 'test_fixture.Fixture.test_old'
            recent = 'test_fixture.Fixture.test_recent'
            changed = 'test_fixture.Fixture.test_old_changed'
            new = 'test_fixture.Fixture.test_new'
            partition = root / 'cold-only.txt'
            partition.write_text('# Archived baseline cases\n' + old + '\n' + changed + '\n')
            result = root / 'result.json'

            def run(phase, required=()):
                env = dict(os.environ, NIGHTSHIFT_BASE=base, NIGHTSHIFT_PHASE=phase,
                           NIGHTSHIFT_RESULT=str(result), NIGHTSHIFT_RUN='fixture',
                           NIGHTSHIFT_REQUIRED=json.dumps(required))
                process = subprocess.run([sys.executable, str(ADAPTER), '--cold-only-file', str(partition)],
                                         cwd=root, env=env, capture_output=True, text=True, timeout=10)
                self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
                return {c['id']: c for c in json.loads(result.read_text())['cases']}

            self.assertEqual(set(run('discover')), {recent, changed, new})
            passed = run('run')
            self.assertEqual(set(passed), {recent, changed, new})
            self.assertTrue(all(case['status'] == 'passed' for case in passed.values()))
            self.assertTrue((root / 'recent-ran').exists())
            self.assertFalse((root / 'old-ran').exists())
            self.assertEqual(run('run', [old])[old]['status'], 'passed')
            self.assertTrue((root / 'old-ran').exists())
