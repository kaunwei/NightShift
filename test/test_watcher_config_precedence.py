"""Activated runner context must win over the shared installation defaults."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class WatcherConfigPrecedenceTests(unittest.TestCase):
    def test_explicit_then_activated_then_installation_config(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scripts = root / 'scripts'
            scripts.mkdir()
            for name in ('watch_worker.sh', 'project_config.py'):
                shutil.copy2(ROOT / 'scripts' / name, scripts / name)
            # Observe the relay boundary without launching a watcher or sending messages.
            (scripts / 'sentinel_relay.py').write_text(
                'import json, os, sys\n'
                'print(json.dumps({"config": os.environ.get("NIGHTSHIFT_CONFIG_FILE"), '
                '"state": os.environ.get("NIGHTSHIFT_STATE_DIR"), "argv": sys.argv[1:]}))\n')
            configs = {}
            for name in ('installation', 'activated', 'explicit'):
                target = root / name
                target.mkdir()
                subprocess.run(["git", "init", "-q", str(target)], check=True)
                config = scripts / 'config.json' if name == 'installation' else target / 'config.json'
                config.write_text(json.dumps({'version': 1, 'projects': {
                    'slugbox': {'path': str(target), 'state': str(target / 'state')}}}))
                configs[name] = config
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith('NIGHTSHIFT_')}
            env['NIGHTSHIFT_PROJECT_NAME'] = 'slugbox'

            def launch(extra=(), activated=None):
                selected_env = dict(env)
                if activated is not None:
                    selected_env['NIGHTSHIFT_CONFIG_FILE'] = str(activated)
                return subprocess.run(
                    ['bash', str(scripts / 'watch_worker.sh'), *extra,
                     '--agent', 'codex', '--planner-id', 'test-thread', '0', '5'],
                    env=selected_env, capture_output=True, text=True, timeout=5)

            for expected, extra, activated in (
                ('activated', (), configs['activated']),
                ('explicit', ('--config', str(configs['explicit'])), configs['activated']),
                ('installation', (), None),
            ):
                with self.subTest(expected=expected):
                    result = launch(extra, activated)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    context = json.loads(result.stdout)
                    self.assertEqual(context['config'], str(configs[expected]))
                    self.assertEqual(context['state'], str(root / expected / 'state'))
                    self.assertEqual(context['argv'][:2], ['--root', str(root / expected)])
            invalid = launch(activated=root / 'missing.json')
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn('Missing NightShift config', invalid.stderr)
            self.assertEqual(invalid.stdout, '')


if __name__ == '__main__':
    unittest.main()
