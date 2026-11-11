"""Parser setup must exercise the parser, not just trust pip metadata."""
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
                shutil.copy2(ROOT / 'scripts/tools' / name, tools / name)
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
