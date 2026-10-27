"""Installer parser readiness must exercise the parser, not just pip metadata."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ParserSetupTests(unittest.TestCase):
    def test_matching_stamp_and_pip_check_do_not_hide_a_broken_parser(self):
        with tempfile.TemporaryDirectory() as d:
            tools = Path(d)
            for name in ('setup.sh', 'requirements.txt', 'check_env.py'):
                shutil.copy2(ROOT / 'nightshift/tools' / name, tools / name)
            venv = tools / '.venv'
            (venv / 'bin').mkdir(parents=True)
            python = venv / 'bin/python'
            python.write_text('#!/usr/bin/python3\nimport sys\n'
                              'sys.exit(0 if sys.argv[1:3] == ["-m", "pip"] else 1)\n')
            python.chmod(0o755)
            stamp = venv / '.requirements.sha256'
            stamp.write_text(hashlib.sha256((tools / 'requirements.txt').read_bytes()).hexdigest() + '\n')
            result = subprocess.run(['sh', str(tools / 'setup.sh')], capture_output=True,
                                    text=True, timeout=10)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn('already installed', result.stdout)

    def test_installer_validates_index_cli_and_exclusions_survive_ignore_rollback(self):
        import json
        import os
        import sys
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / 'project'
            target.mkdir()
            def git(*args):
                return subprocess.run(['git', '-C', str(target), *args],
                                      capture_output=True, text=True, check=True)
            git('init', '-q')
            git('config', 'user.name', 'Installer Test')
            git('config', 'user.email', 'installer@example.invalid')
            (target / '.gitignore').write_text('existing/\n')
            (target / 'example.c').write_text('int useful(void) { return 7; }\n')
            git('add', '.')
            git('commit', '-qm', 'fixture baseline')
            baseline = git('rev-parse', 'HEAD').stdout.strip()
            environment = Path(os.environ.get('NIGHTSHIFT_TEST_PARSER_VENV', ROOT / 'nightshift/tools/.venv'))
            venv = target / 'nightshift/tools/.venv'
            (venv / 'bin').mkdir(parents=True)
            (venv / 'bin/python').symlink_to(environment / 'bin/python')
            (venv / 'lib').symlink_to(environment / 'lib', target_is_directory=True)
            shutil.copy2(environment / 'pyvenv.cfg', venv / 'pyvenv.cfg')
            shutil.copy2(environment / '.requirements.sha256', venv / '.requirements.sha256')
            result = subprocess.run(['bash', str(ROOT / 'install.sh'), str(target)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((target / 'nightshift/tools/check_env.py').is_file())
            # Simulate the exact ignore rollback window without touching the venv.
            (target / '.gitignore').write_text(git('show', baseline + ':.gitignore').stdout)
            ignored = git('check-ignore', '-v', 'nightshift/tools/.venv/bin/python')
            self.assertIn('info/exclude', ignored.stdout)
            # Commit only this disposable fixture, then prove the installed CLI builds.
            git('add', '.')
            git('commit', '-qm', 'installed fixture')
            built = subprocess.run([sys.executable, str(target / 'nightshift/worker_runtime.py'),
                                    'code-index', 'build'], cwd=target,
                                   capture_output=True, text=True, timeout=20)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            self.assertTrue(Path(json.loads(built.stdout)['summary_path']).is_file())
