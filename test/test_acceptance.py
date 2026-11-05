import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
_NS_CORE = Path(os.environ.get('NIGHTSHIFT_CORE', ROOT.parent / 'NightShift'))
_ns_dir = str(_NS_CORE / 'scripts') if (_NS_CORE / 'scripts').is_dir() else (str(ROOT / 'scripts') if (ROOT / 'scripts').is_dir() else str(ROOT / 'nightshift'))
if _ns_dir not in sys.path:
    sys.path.insert(0, _ns_dir)
import acceptance
_NS_HOT = _NS_CORE / 'scripts' / 'unittest_hot.py' if (_NS_CORE / 'scripts' / 'unittest_hot.py').is_file() else ROOT / 'scripts' / 'unittest_hot.py'


class AcceptanceTests(unittest.TestCase):
    def test_configuration_rejects_zero_cold_interval(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'nightshift' / 'config.json'
            config.parent.mkdir()
            config.write_text(json.dumps({'version': 1, 'acceptance': {'cold_every': 0}}))
            with self.assertRaisesRegex(acceptance.GateError, 'positive integer'):
                acceptance.config(directory)

    def test_hot_adapter_discovers_and_runs_real_case(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root / 'test').mkdir()
            (root / 'test' / 'test_sample.py').write_text(
                'import unittest\nclass Sample(unittest.TestCase):\n'
                '    def test_value(self):\n        self.assertEqual(2 + 2, 4)\n')
            result = root / 'evidence.json'
            env = dict(os.environ, NIGHTSHIFT_BASE='HEAD', NIGHTSHIFT_RESULT=str(result),
                       NIGHTSHIFT_RUN='fixture', PYTHONDONTWRITEBYTECODE='1')
            for phase in ('discover', 'run'):
                env['NIGHTSHIFT_PHASE'] = phase
                subprocess.run([sys.executable, str(_NS_HOT),
                                '--start', 'test'], cwd=root, env=env, check=True,
                               capture_output=True, text=True)
                evidence = json.loads(result.read_text())
                self.assertEqual(evidence['run'], 'fixture')
                self.assertEqual(evidence['cases'][0]['id'], 'test_sample.Sample.test_value')
                self.assertIsNone(evidence['cases'][0]['baseline_fingerprint'])
                if phase == 'run':
                    self.assertEqual(evidence['cases'][0]['status'], 'passed')

    def test_hot_adapter_does_not_report_skipped_case_as_passed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root / 'test').mkdir()
            (root / 'test' / 'test_sample.py').write_text(
                'import unittest\nclass Sample(unittest.TestCase):\n'
                '    @unittest.skip("reason")\n    def test_value(self): pass\n')
            result = root / 'evidence.json'
            env = dict(os.environ, NIGHTSHIFT_BASE='HEAD', NIGHTSHIFT_RESULT=str(result),
                       NIGHTSHIFT_RUN='fixture', NIGHTSHIFT_PHASE='run', PYTHONDONTWRITEBYTECODE='1')
            subprocess.run([sys.executable, str(_NS_HOT),
                            '--start', 'test'], cwd=root, env=env, check=True, capture_output=True)
            self.assertEqual(json.loads(result.read_text())['cases'][0]['status'], 'failed_or_skipped')

    def test_clean_start_restores_head_removes_untracked_and_preserves_ignored_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root / '.gitignore').write_text(
                'nightshift/tasks.txt\nnightshift/.reports/\nnightshift/.worker-state.json\n.DS_Store\n')
            (root / 'product.py').write_text('value = "HEAD"\n')
            (root / 'nightshift').mkdir()
            (root / 'nightshift' / 'worker.py').write_text('runtime = True\n')
            (root / 'nightshift' / 'config.json').write_text('{"setting": "HEAD"}\n')
            subprocess.run(['git', '-C', str(root), 'add', '.gitignore', 'product.py', 'nightshift'], check=True)
            subprocess.run(['git', '-C', str(root), '-c', 'user.name=Fixture', '-c',
                            'user.email=fixture@example.test', 'commit', '-qm', 'fixture'], check=True)

            (root / 'product.py').write_text('value = "dirty"\n')
            (root / 'product-leftover').mkdir()
            (root / 'product-leftover' / 'output.py').write_text('unfinished = True\n')
            (root / 'nightshift' / 'acceptance_leftover.py').write_text('helper = True\n')
            (root / 'nightshift' / 'config.json').write_text('{"setting": "local"}\n')
            (root / 'nightshift' / 'tasks.txt').write_text('queued task\n')
            reports = root / 'nightshift' / '.reports' / 'active'
            reports.mkdir(parents=True)
            (reports / 'SUMMARY.md').write_text('runtime report\n')
            (root / 'nightshift' / '.worker-state.json').write_text('{}\n')
            (root / '.DS_Store').write_text('metadata\n')

            acceptance.clean(root)

            self.assertEqual((root / 'product.py').read_text(), 'value = "HEAD"\n')
            self.assertFalse((root / 'product-leftover').exists())
            self.assertEqual((root / 'nightshift' / 'worker.py').read_text(), 'runtime = True\n')
            self.assertEqual((root / 'nightshift' / 'acceptance_leftover.py').read_text(), 'helper = True\n')
            self.assertEqual((root / 'nightshift' / 'config.json').read_text(), '{"setting": "local"}\n')
            self.assertEqual((root / 'nightshift' / 'tasks.txt').read_text(), 'queued task\n')
            self.assertEqual((reports / 'SUMMARY.md').read_text(), 'runtime report\n')
            self.assertEqual((root / 'nightshift' / '.worker-state.json').read_text(), '{}\n')
            self.assertEqual((root / '.DS_Store').read_text(), 'metadata\n')
