"""Acceptance phase budgets reach real hooks without sleeping for their limits."""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import acceptance


class PhaseTimeoutTests(unittest.TestCase):
    def exercise(self,settings):
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory).resolve()
            root=parent/'project'
            root.mkdir()
            (root/'scripts').mkdir()
            source=root/'test_case.py'
            source.write_text('before\n')
            hook=parent/'hook.py'
            hook.write_text('import json,os\nfrom pathlib import Path\n'
                'case={"id":"case.behavior","source":"test_case.py","fingerprint":"a"*64,"baseline_fingerprint":"b"*64}\n'
                'if os.environ["NIGHTSHIFT_PHASE"]=="run": case["status"]="passed"\n'
                'Path(os.environ["NIGHTSHIFT_RESULT"]).write_text(json.dumps({"run":os.environ["NIGHTSHIFT_RUN"],"cases":[case]}))\n')
            config={'version':1,'acceptance':{'hot':shlex.join([sys.executable,str(hook)]),'cold':'true',**settings}}
            (root/'scripts/config.json').write_text(json.dumps(config))
            def git(*args):
                return subprocess.check_output(['git','-C',str(root),*args],text=True).strip()
            git('init','-q');git('config','user.name','Fixture');git('config','user.email','fixture@example.invalid')
            git('add','.');git('commit','-qm','baseline')
            base=git('rev-parse','HEAD')
            source.write_text('after\n')
            observed=[]
            def run(command,cwd,port,timeout):
                observed.append(timeout)
                result=subprocess.run(command,cwd=cwd,shell=True,capture_output=True,text=True,timeout=5)
                return result.returncode,result.stdout+result.stderr
            args=argparse.Namespace(work_dir=str(root),base=base,task_id='TASK-X',verify='true',worker_port='3001')
            with patch.dict(os.environ,{'NIGHTSHIFT_STATE_DIR':str(parent/'runner')},clear=True):
                acceptance.hot(args,{'tdd_cases':[{'id':'case.behavior','source':'test_case.py'}]},run)
                git('add','test_case.py');git('commit','-qm','accepted fixture')
                acceptance.cold(root,run)
            return observed

    def assert_budgets(self, observed, hot, cold):
        self.assertEqual(len(observed), 4)
        self.assertGreater(hot, observed[0])
        self.assertGreater(observed[0], observed[1])
        self.assertGreater(observed[1], observed[2])
        self.assertGreater(observed[2], hot - 3)
        self.assertEqual(observed[3], cold)

    def test_phase_defaults_are_hot_five_minutes_cold_thirty_minutes(self):
        self.assert_budgets(self.exercise({}), 300, 1800)

    def test_explicit_legacy_timeout_is_fallback_for_both_phases(self):
        self.assert_budgets(self.exercise({'timeout':7}), 7, 7)

    def test_phase_fields_override_legacy_timeout(self):
        self.assert_budgets(self.exercise({'timeout':7,'hot_timeout':11,'cold_timeout':13}), 11, 13)

    def test_each_phase_can_override_without_changing_other_default(self):
        self.assert_budgets(self.exercise({'hot_timeout':11}), 11, 1800)
        self.assert_budgets(self.exercise({'cold_timeout':13}), 300, 13)

    def test_invalid_explicit_budgets_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'scripts').mkdir()
            path=root/'scripts/config.json'
            for field in ('timeout','hot_timeout','cold_timeout'):
                for value in (None,True,False,0,-1,float('inf'),float('nan'),'300'):
                    with self.subTest(field=field,value=value):
                        path.write_text(json.dumps({'version':1,'acceptance':{field:value}}))
                        with patch.dict(os.environ,{},clear=True),self.assertRaises(acceptance.GateError):
                            acceptance.config(root)
