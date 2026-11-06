"""Hot handoff reconciliation against actual permanent discovery, without relaxing tests."""
import argparse
import copy
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


class TDDReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()
        self.source=self.root/'test/test_sample.py'
        self.source.parent.mkdir()
        self.original='import unittest\nOLD=1\nclass Sample(unittest.TestCase):\n    def test_old(self):\n        self.assertEqual(1, OLD)\n'
        self.source.write_text(self.original)
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        self.git('add','test')
        self.git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','baseline')
        self.base=self.git('rev-parse','HEAD')
        self.source.write_text(self.original+'    def test_new(self):\n        self.assertEqual(2 + 2, 4)\n')
        self.new={'id':'test_sample.Sample.test_new','source':'test/test_sample.py'}
        self.old={'id':'test_sample.Sample.test_old','source':'test/test_sample.py'}
        self.cfg={'hot':shlex.join([sys.executable,str(ROOT/'scripts/unittest_hot.py')]),'timeout':5,'wiring':[]}
        self.args=argparse.Namespace(work_dir=str(self.root),base=self.base,task_id='TASK-X',verify='',worker_port='3001',required_cases=[])
        self.env=patch.dict(os.environ,{},clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)

    def git(self,*args):
        return subprocess.check_output(['git','-C',str(self.root),*args],text=True).strip()

    @staticmethod
    def run_hook(command,cwd,port,timeout):
        result=subprocess.run(command,cwd=cwd,shell=True,capture_output=True,text=True,timeout=timeout)
        return result.returncode,result.stdout+result.stderr

    def hot(self,cases,runner=None):
        result={'tdd_cases':copy.deepcopy(cases)}
        with patch.object(acceptance,'config',return_value=self.cfg):
            hot=(runner or acceptance.DefaultAcceptanceRunner()).run_hot(self.args,result,self.run_hook)
        return result,hot

    def test_repairs_prefix_absolute_source_and_drops_only_unchanged_evidence(self):
        submitted=[{'id':'test.'+self.new['id'],'source':str(self.source)},self.old]
        result,hot=self.hot(submitted)
        self.assertEqual(result['tdd_cases'],[self.new])
        self.assertEqual(hot['cases'],sorted([self.new['id'],self.old['id']]))
        audit=hot['tdd_reconciliation']
        self.assertEqual(audit['original'],submitted)
        self.assertEqual(audit['canonical'],[self.new,self.old])
        self.assertEqual(audit['dropped'],[self.old])
        self.assertEqual(submitted[0]['source'],str(self.source))

    def test_only_unchanged_or_empty_declarations_still_fail(self):
        for cases in ([self.old],[],None):
            with self.subTest(cases=cases),self.assertRaises(acceptance.GateError):
                self.hot(cases)

    def test_unknown_source_mismatch_outside_source_and_duplicate_mapping_fail(self):
        for cases in ([{'id':'unknown','source':self.new['source']}],
                      [{'id':self.new['id'],'source':'test/wrong.py'}],
                      [{'id':self.new['id'],'source':str(self.root.parent/'test_sample.py')}],
                      [self.new,{'id':'test.'+self.new['id'],'source':self.new['source']}]):
            with self.subTest(cases=cases),self.assertRaises(acceptance.GateError):
                self.hot(cases)

    def test_ambiguous_discovered_id_mapping_fails(self):
        class AmbiguousRunner(acceptance.DefaultAcceptanceRunner):
            def invoke(inner,*args,**kwargs):
                cases,evidence=super().invoke(*args,**kwargs)
                if args[3]=='discover':
                    cases['test.'+self.new['id']]={**cases[self.new['id']],'id':'test.'+self.new['id']}
                return cases,evidence
        with self.assertRaises(acceptance.GateError):
            self.hot([{'id':'test.'+self.new['id'],'source':self.new['source']}],AmbiguousRunner())

    def test_failed_new_case_and_failed_unchanged_regression_still_block(self):
        for source in (self.source.read_text().replace('2 + 2, 4','2 + 2, 5'),
                       self.source.read_text().replace('OLD=1','OLD=2')):
            self.source.write_text(source)
            with self.assertRaises(acceptance.GateError):
                self.hot([self.new,self.old])

    def test_skipped_new_case_still_blocks(self):
        self.source.write_text(self.source.read_text().replace('    def test_new','    @unittest.skip("fixture")\n    def test_new'))
        with self.assertRaises(acceptance.GateError):
            self.hot([self.new,self.old])

    def test_unsupported_fingerprint_cannot_be_dropped_as_unchanged(self):
        class UnsupportedRunner(acceptance.DefaultAcceptanceRunner):
            def invoke(inner,*args,**kwargs):
                cases,evidence=super().invoke(*args,**kwargs)
                if args[3]=='discover':
                    cases[self.old['id']]['fingerprint']='unsupported'
                    cases[self.old['id']]['baseline_fingerprint']='unsupported'
                return cases,evidence
        with self.assertRaises(acceptance.GateError):
            self.hot([self.new,self.old],UnsupportedRunner())
