"""Permanent hot adapter protocol checks using disposable Git repositories."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
_NS_CORE = Path(os.environ.get('NIGHTSHIFT_CORE', ROOT.parent / 'NightShift'))
ADAPTER = _NS_CORE / 'nightshift' / 'unittest_hot.py' if (_NS_CORE / 'nightshift' / 'unittest_hot.py').is_file() else ROOT / 'nightshift' / 'unittest_hot.py'


class HotProtocolTests(unittest.TestCase):
    def test_discovery_and_execution_emit_fresh_case_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root / 'test').mkdir()
            source = root / 'test' / 'test_sample.py'
            source.write_text(
                'import unittest\nclass Sample(unittest.TestCase):\n'
                '    def test_value(self):\n        self.assertEqual(6 * 7, 42)\n')
            result = root / 'evidence.json'
            env = dict(os.environ, NIGHTSHIFT_BASE='HEAD', NIGHTSHIFT_RESULT=str(result),
                       NIGHTSHIFT_RUN='protocol-fixture', PYTHONDONTWRITEBYTECODE='1')

            for phase in ('discover', 'run'):
                env['NIGHTSHIFT_PHASE'] = phase
                subprocess.run([sys.executable, str(ADAPTER), '--start', 'test'],
                               cwd=root, env=env, check=True, capture_output=True, text=True)
                evidence = json.loads(result.read_text())
                self.assertEqual(evidence['run'], 'protocol-fixture')
                self.assertEqual(len(evidence['cases']), 1)
                case = evidence['cases'][0]
                self.assertEqual(case['id'], 'test_sample.Sample.test_value')
                self.assertEqual(case['source'], 'test/test_sample.py')
                self.assertRegex(case['fingerprint'], r'^[a-f0-9]{64}$')
                self.assertIsNone(case['baseline_fingerprint'])
                if phase == 'run':
                    self.assertEqual(case['status'], 'passed')

    def test_declared_case_fingerprint_tracks_test_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root / 'test').mkdir()
            source = root / 'test' / 'test_sample.py'
            original = ('import unittest\nclass Sample(unittest.TestCase):\n'
                        '    def test_value(self):\n        self.assertEqual(1, 1)\n')
            source.write_text(original)
            subprocess.run(['git', '-C', str(root), 'add', 'test/test_sample.py'], check=True)
            subprocess.run(['git', '-C', str(root), '-c', 'user.name=Fixture', '-c',
                            'user.email=fixture@example.test', 'commit', '-qm', 'baseline'], check=True)
            baseline = subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], check=True,
                                      capture_output=True, text=True).stdout.strip()
            source.write_text(original.replace('1, 1', '2, 2'))
            result = root / 'evidence.json'
            env = dict(os.environ, NIGHTSHIFT_BASE=baseline, NIGHTSHIFT_RESULT=str(result),
                       NIGHTSHIFT_RUN='changed-fixture', NIGHTSHIFT_PHASE='discover',
                       PYTHONDONTWRITEBYTECODE='1')
            subprocess.run([sys.executable, str(ADAPTER), '--start', 'test'], cwd=root,
                           env=env, check=True, capture_output=True, text=True)
            case = json.loads(result.read_text())['cases'][0]
            self.assertNotEqual(case['fingerprint'], case['baseline_fingerprint'])
