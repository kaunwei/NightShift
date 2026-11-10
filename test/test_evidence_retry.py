"""Metadata recovery preserves the patch and delegates acceptance to normal runtime."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import evidence_retry
import lifecycle


class EvidenceRetryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name).resolve()/'project'
        self.root.mkdir()
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        subprocess.run(['git','-C',str(self.root),'-c','user.name=Test','-c','user.email=test@example.invalid',
                        'commit','--allow-empty','-qm','baseline'],check=True)
        self.base=subprocess.check_output(['git','-C',str(self.root),'rev-parse','HEAD'],text=True).strip()
        (self.root/'product.txt').write_text('preserved implementation')
        self.runner=self.root.parent/'runner'
        self.state=self.runner/'lifecycle'
        self.state.mkdir(parents=True)
        self.snapshot=self.runner/'.scratch/attempts/TASK-ONE/attempt/baseline'
        self.snapshot.mkdir(parents=True)
        self.cases=[{'id':'test_behavior.Cases.test_new','source':'test/test_behavior.py'},
                    {'id':'test_behavior.Cases.test_old','source':'test/test_behavior.py'}]
        self.raw='TASK-ONE | LEVEL: 1 | AFTER: TASK-PREVIOUS | TARGET: product.txt,test | ACTION: behavior | VERIFY: regression'
        self.event='failure-1'
        self.save(self.snapshot/'snapshot.json',dict(task_id='TASK-ONE',head=self.base,
                  work_dir=str(self.root),audit_tree=self.base))
        self.save(self.state/'paused.json',dict(task='TASK-ONE',detail='unchanged declaration'))
        self.save(self.runner/'worker.status',dict(state='PAUSED_FOR_PLANNER'))
        self.save(self.state/'reports'/self.event/'report.json',dict(task=self.raw,base=self.base,result={
            'outcome':'complete','terminal_status':'complete','commit_message':'feat: behavior',
            'registration_id':'agent','tdd_cases':self.cases,'runtime_error':{'phase':'hot',
            'message':'TDD case unchanged or source evidence unsupported: test_behavior.Cases.test_old'}}))
        self.save(self.state/'runs'/self.event/'output.json',{'terminal_artifacts':{'result':str(
            self.snapshot.parent/'adapter/attempt/.runtime-terminal/result.json')}})
        self.env=patch.dict(os.environ,{'NIGHTSHIFT_STATE_DIR':str(self.runner)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.permanent={self.cases[0]['id']:{'source':self.cases[0]['source'],'fingerprint':'a'*64,
            'baseline_fingerprint':None},self.cases[1]['id']:{'source':self.cases[1]['source'],
            'fingerprint':'b'*64,'baseline_fingerprint':'b'*64}}

    @staticmethod
    def save(path,value):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value))

    def schedule(self,cases):
        with patch.object(evidence_retry.gate,'config',return_value={}), \
             patch.object(evidence_retry.gate,'invoke',return_value=(self.permanent,{})):
            return evidence_retry.schedule(self.root,self.state,self.event,cases,self.snapshot)

    def test_corrected_subset_queues_normal_runtime_revalidation_without_accepting(self):
        before=evidence_retry.runtime.worktree_tree(self.root)
        result=self.schedule(self.cases[:1])
        self.assertEqual(result['state'],'queued_for_runtime_revalidation')
        self.assertEqual(evidence_retry.runtime.worktree_tree(self.root),before)
        self.assertFalse((self.state/'paused.json').exists())
        active=json.loads((self.state/'active.json').read_text())
        self.assertEqual(active['task_id'],'TASK-ONE')
        self.assertNotEqual(active['event'],self.event)
        journal=json.loads(next((self.state/'tasks').glob('*.json')).read_text())
        self.assertEqual(journal['phase'],'ready_commit')
        self.assertEqual(journal['args']['level'],'1')
        self.assertEqual(journal['result']['tdd_cases'],self.cases[:1])
        self.assertEqual(journal['args']['attempt_baseline'],str(self.snapshot))
        self.assertNotIn('commit',journal)
        self.assertFalse((self.runner/'tasks.done').exists())
        self.assertEqual(subprocess.check_output(['git','-C',str(self.root),'rev-parse','HEAD'],text=True).strip(),self.base)

    def test_refuses_to_drop_changed_case_or_retain_unchanged_case(self):
        with self.assertRaisesRegex(ValueError,'cannot drop a changed case'):
            self.schedule(self.cases[1:])
        self.assertTrue((self.state/'paused.json').exists())
        self.assertFalse((self.state/'active.json').exists())

    def test_refuses_unknown_declaration_without_mutating_pause(self):
        with self.assertRaisesRegex(ValueError,'original subset'):
            self.schedule([{'id':'invented','source':'test/x.py'}])
        self.assertTrue((self.state/'paused.json').exists())

    def test_refuses_patch_changed_during_discovery(self):
        def discovery(*args):
            (self.root/'product.txt').write_text('concurrent edit')
            return self.permanent,{}
        with patch.object(evidence_retry.gate,'config',return_value={}), \
             patch.object(evidence_retry.gate,'invoke',side_effect=discovery):
            with self.assertRaisesRegex(ValueError,'workspace changed'):
                evidence_retry.schedule(self.root,self.state,self.event,self.cases[:1],self.snapshot)
        self.assertTrue((self.state/'paused.json').exists())
        self.assertFalse((self.state/'active.json').exists())

    def test_ready_commit_reports_actual_finalization_error(self):
        request=self.schedule(self.cases[:1])
        active_path=self.state/'active.json'
        runtime=evidence_retry.runtime
        def reject(args,result):
            result['runtime_error']={'phase':'pre_commit_audit','message':'scope audit fixture rejection'}
            return 1
        with patch.dict(os.environ,{'NIGHTSHIFT_CONFIG_FILE':str(self.runner/'config.json'),'RUN_ONCE':'1'}), \
             patch.object(runtime,'load_agent_registry',return_value=[]), \
             patch.object(runtime,'finalize_structured_adapter_result',side_effect=reject), \
             patch.object(evidence_retry.gate,'config',return_value={'hot':'fixture'}):
            self.assertEqual(lifecycle.run(self.root,runtime),0)
        report=json.loads((self.state/'reports'/request['retry_event']/'report.json').read_text())
        self.assertEqual(report['result']['runtime_error']['phase'],'pre_commit_audit')
        self.assertIn('scope audit fixture rejection',(self.state/'paused.json').read_text())
        self.assertFalse(active_path.exists())
