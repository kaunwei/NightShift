"""Two-stage hooks through real daemon, Git snapshots and owned processes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from test_runtime_hardening import Fixture, SCRIPTS
import acceptance as gate
import acceptance_hooks as hooks
import background_hooks as background


class BackgroundHookTests(Fixture):
    def setUp(self):
        super().setUp()
        (self.root / ".gitignore").write_text("__pycache__/\n")
        (self.root / "test").mkdir()
        (self.root / "test/test_checks.py").write_text("import unittest\nclass Checks(unittest.TestCase):\n pass\n")
        self.control = self.runner / "control.json"
        self.trace = self.runner / "trace"
        (self.root / "prepare.py").write_text('''import os
from pathlib import Path
Path(os.environ['NIGHTSHIFT_HOOK_ARTIFACT_DIR'],'payload').write_text(Path('file').read_text())
with Path(os.environ['FIXTURE_TRACE']).open('a') as f:f.write('prepare:'+Path('file').read_text()+'\\n')
''')
        (self.root / "analyze.py").write_text('''import json,os,time
from pathlib import Path
c=json.loads(Path(os.environ['FIXTURE_CONTROL']).read_text())
inputs=Path(os.environ['NIGHTSHIFT_HOOK_ARTIFACT_DIR']); reports=Path(os.environ['NIGHTSHIFT_HOOK_REPORT_DIR'])
before=Path('file').read_text(); payload=(inputs/'payload').read_text()
with Path(os.environ['FIXTURE_TRACE']).open('a') as f:f.write('background:'+before+'\\n')
Path(os.environ['FIXTURE_TRACE']+'.started').touch()
if before=='TASK-'+str(c.get('first',3)):
 end=time.monotonic()+10
 while not Path(os.environ['FIXTURE_TRACE']+'.release').exists():
  if time.monotonic()>end: raise RuntimeError('fixture release deadline')
  time.sleep(.01)
after=Path('file').read_text()
(reports/'analysis.json').write_text(json.dumps({'before':before,'after':after,'payload':payload,'revision':os.environ['NIGHTSHIFT_HOOK_REVISION']}))
if c.get('mutate'): Path('file').write_text('forbidden')
if c.get('fail'): raise SystemExit(7)
''')
        self.git("add", "."); self.git("commit", "-qm", "hook fixture")
        self.worker = self.base / "worker.py"
        self.worker.write_text('''import json,os,time
from pathlib import Path
c=json.loads(Path(os.environ['FIXTURE_CONTROL']).read_text());trace=Path(os.environ['FIXTURE_TRACE'])
task=os.environ['NIGHTSHIFT_TASK_ID']
def wait(predicate):
 end=time.monotonic()+10
 while not predicate():
  if time.monotonic()>end: raise RuntimeError('fixture wait deadline')
  time.sleep(.01)
if os.environ.get('NIGHTSHIFT_EXECUTION_KIND')=='closeout':
 with trace.open('a') as f:f.write('ghost:'+Path(c['live_root'],'file').read_text()+'\\n')
 result={'outcome':'blocked','diagnostic':'fixture diagnosed background exit; propose scoped repair'}
else:
 number=int(task.split('-')[-1]);first=c.get('first',3)
 with trace.open('a') as f:f.write('worker:'+task+'\\n')
 if number==first+1:
  wait(lambda:Path(str(trace)+'.started').exists())
 if number==c.get('release_at',10):
  Path(str(trace)+'.release').touch()
  wait(lambda:any(Path(c['results']).glob('*/result.json')))
 Path('file').write_text(task)
 method='test_'+task.replace('-','_')
 with Path('test/test_checks.py').open('a') as f:f.write(' def '+method+'(self): self.assertTrue(True)\\n')
 result={'outcome':'complete','commit_message':'fix: '+task,'tdd_cases':[{'id':'test_checks.Checks.'+method,'source':'test/test_checks.py'}]}
Path(os.environ['NIGHTSHIFT_RESULT_FILE']).write_text(json.dumps(result))
''')
        self.second = {"argv": [sys.executable, "analyze.py"], "timeout": 10}
        self.cfg = {"hot": f"{sys.executable} {SCRIPTS / 'unittest_hot.py'} --start test",
                    "cold_timeout": 10,
                    "hooks": [{"id": "analyze", "every": 3, "argv": [sys.executable, "prepare.py"],
                               "second_stage": self.second}]}
        path = self.config(acceptance=self.cfg)
        value = json.loads(path.read_text())
        value["agents"]["fixture"]["agent"].update(args=[str(self.worker)], env={
            "FIXTURE_CONTROL": str(self.control), "FIXTURE_TRACE": str(self.trace)})
        path.write_text(json.dumps(value))
        self.config_path = path
        self.control.write_text(json.dumps({"live_root": str(self.root),
            "results": str(self.runner / "lifecycle/background-hooks")}))

    def daemon(self, count, **control):
        value = json.loads(self.control.read_text()); value.update(control); self.control.write_text(json.dumps(value))
        (self.runner / "tasks.txt").write_text("".join(
            f"TASK-{i} [CODE: FIX] | LEVEL: 3 | TARGET: file,test | VERIFY: true\n" for i in range(1, count+1)))
        result = subprocess.run([sys.executable, str(SCRIPTS / "worker_runtime.py"), "daemon",
            "--root", str(self.root), "--config", str(self.config_path)],
            env={**os.environ, "POLL_INTERVAL": ".01", "FIXTURE_CONTROL": str(self.control),
                 "FIXTURE_TRACE": str(self.trace)}, capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def receipts(self):
        return [json.loads(p.read_text()) for p in sorted((self.runner / "lifecycle/background-hooks").glob("*/result.json"))]

    def test_snapshot_parallelism_coalescing_latest_revision_and_run_once_drain(self):
        self.daemon(10)
        lines = self.trace.read_text().splitlines()
        self.assertEqual([s for s in lines if s.startswith('prepare:')], ['prepare:TASK-3','prepare:TASK-10'])
        self.assertEqual([s for s in lines if s.startswith('background:')], ['background:TASK-3','background:TASK-10'])
        self.assertLess(lines.index('background:TASK-3'), lines.index('worker:TASK-5'))
        records = self.receipts(); self.assertEqual(len(records), 2)
        self.assertTrue(all(r['status']=='passed' for r in records))
        for path in (self.runner/'lifecycle/background-hooks').iterdir():
            report=json.loads((path/'reports/analysis.json').read_text())
            self.assertEqual(report['before'],report['after']); self.assertEqual(report['before'],report['payload'])
            self.assertFalse((path/'snapshot').exists()); self.assertFalse((path/'inputs').exists())
            self.assertTrue((path/'logs').is_dir())
            receipt=json.loads((path/'result.json').read_text())
            self.assertEqual(receipt['freshness'],'older_snapshot' if report['before']=='TASK-3' else 'same_revision')
        self.assertEqual(self.git('worktree','list','--porcelain').decode().count('worktree '),1)
        self.assertEqual((self.root/'file').read_text(),'TASK-10')

    def test_background_failure_waits_current_commit_then_ghost_and_priority_pause(self):
        cfg=json.loads(self.config_path.read_text());cfg['acceptance']['hooks'][0]['every']=1
        cfg['agents']['fixture']['agent']['env']['TOKEN']='GHOST_SECRET_CANARY'
        self.config_path.write_text(json.dumps(cfg))
        self.daemon(3, first=1, release_at=2, fail=True)
        lines=self.trace.read_text().splitlines()
        self.assertIn('ghost:TASK-2',lines)
        self.assertNotIn('worker:TASK-3',lines)
        self.assertEqual((self.root/'file').read_text(),'TASK-2')
        self.assertFalse((self.runner/'lifecycle/paused.json').exists())
        self.assertEqual(json.loads((self.runner/'worker.status').read_text())['state'],'BLOCKED')
        self.assertIn('TASK-3',(self.runner/'tasks.txt').read_text())
        receipt=self.receipts()[0]
        self.assertEqual(receipt['exit'],7)
        self.assertIn('fixture diagnosed',receipt['ghost']['diagnostic'])
        directory=next((self.runner/'lifecycle/background-hooks').iterdir())
        self.assertNotIn('GHOST_SECRET_CANARY',(directory/'ghost/prompt.txt').read_text())
        self.assertNotIn('registration',json.loads((directory/'request.json').read_text()))
        self.assertTrue((directory/'snapshot/.git').is_dir())
        self.assertTrue((directory/'inputs/payload').is_file())
        self.assertFalse((self.runner/'lifecycle/active.json').exists())
        self.assertFalse((self.runner/'.worker-ghost-state.json').exists())
        score=json.loads(next((self.runner/'.worker-agent-scores').glob('*.json')).read_text())
        self.assertEqual(score['success_window'],['TASK-1','TASK-2'])
        self.assertEqual(score['score'],5)
        # A new daemon does not replay the failed run or restore its pause/counts.
        cfg=json.loads(self.config_path.read_text());cfg['acceptance']['hooks'][0]['every']=3
        self.config_path.write_text(json.dumps(cfg))
        result=subprocess.run([sys.executable,str(SCRIPTS/'worker_runtime.py'),'daemon','--root',str(self.root),'--config',str(self.config_path)],
            env={**os.environ,'POLL_INTERVAL':'.01'},capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertEqual((self.root/'file').read_text(),'TASK-3')
        self.assertEqual(self.trace.read_text().count('ghost:'),1)

    def test_contract_validation_and_commit_only_volatile_counts(self):
        for invalid in (None, {}, {"argv": []}, {"argv": ['true'], "timeout": 0}, {"argv": ['true'], "extra": 1}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                hooks.Scheduler({"hooks": [{"id":'x',"every":1,"argv":['true'],"second_stage":invalid}]})
        with self.assertRaises(ValueError):
            hooks.Scheduler({}).register({"id":'x',"after":'TASK-A',"argv":['true'],"second_stage":{"argv":['true']}})
        scheduler=hooks.Scheduler(self.cfg, state_path=self.runner/'durable.json', project=self.root)
        scheduler.accepted('TASK-R','r',self.head,committed=False)
        scheduler.accepted('TASK-N','n',self.head,committed=False)
        self.assertEqual(scheduler.list_runs()['background']['counts']['analyze'],0)
        for i in range(3): scheduler.accepted(f'TASK-{i}',str(i),self.head,committed=True)
        self.assertIsNone(scheduler.next_run())
        self.assertEqual(scheduler.list_runs()['background']['counts']['analyze'],3)
        self.assertEqual(hooks.Scheduler(self.cfg).background.counts['analyze'],0)

    def test_dual_stage_state_is_volatile_even_with_durable_legacy_hooks(self):
        cfg={**self.cfg,'durable_hooks':True}
        scheduler=hooks.Scheduler(cfg,state_path=self.runner/'state.json',project=self.root)
        for i in range(4): scheduler.accepted(f'TASK-{i}',str(i),self.head,committed=True)
        restored=hooks.Scheduler(cfg,state_path=self.runner/'state.json',project=self.root)
        self.assertEqual(restored.background.counts['analyze'],0)
        self.assertFalse(restored.background.has_work())
        self.assertIsNone(restored.next_run())
        self.assertNotIn('analyze',json.loads((self.runner/'state.json').read_text())['counts'])

    def test_run_once_retains_foreground_hook_drain_order_when_mixed(self):
        cfg=json.loads(self.config_path.read_text())
        cfg['acceptance']['hooks'].append({'id':'foreground','every':3,'argv':['true']})
        self.config_path.write_text(json.dumps(cfg))
        self.daemon(4,first=99)
        self.assertNotIn('worker:TASK-4',self.trace.read_text())
        self.assertIn('TASK-4',(self.runner/'tasks.txt').read_text())
        self.assertEqual([r['status'] for r in self.receipts()],['passed'])

    def test_first_stage_failure_preserves_queue_and_does_not_launch_second_stage(self):
        cfg=json.loads(self.config_path.read_text())
        cfg['acceptance']['hooks'][0].update(every=1,argv=[sys.executable,'-c',"print('prepare failed');raise SystemExit(9)"])
        self.config_path.write_text(json.dumps(cfg))
        self.daemon(2)
        self.assertNotIn('background:',self.trace.read_text())
        self.assertIn('TASK-2',(self.runner/'tasks.txt').read_text())
        receipt=self.receipts()[0]
        self.assertEqual(receipt['phase'],'first_stage')
        self.assertEqual(receipt['first_stage']['exit'],9)
        self.assertTrue(Path(receipt['first_stage']['log_path']).is_file())

    def test_snapshot_modification_is_a_failure_and_cannot_edit_live_product(self):
        cfg=json.loads(self.config_path.read_text());cfg['acceptance']['hooks'][0]['every']=1
        self.config_path.write_text(json.dumps(cfg))
        self.daemon(3,first=1,release_at=2,mutate=True)
        self.assertEqual((self.root/'file').read_text(),'TASK-2')
        self.assertIn('changed snapshot',self.receipts()[0]['error'])
        self.assertNotIn('worker:TASK-3',self.trace.read_text())


class BackgroundProcessTests(Fixture):
    def wait_for(self,predicate):
        end=time.monotonic()+8
        while not predicate():
            if time.monotonic()>end: self.fail('background process deadline')
            time.sleep(.02)

    def alive(self,pid):
        try:
            return Path(f'/proc/{pid}/stat').read_text().split()[2]!='Z'
        except FileNotFoundError:
            return False

    def config_value(self,timeout=10):
        code="import os,subprocess,sys,time;from pathlib import Path;child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']);Path(os.environ['NIGHTSHIFT_HOOK_REPORT_DIR'],'pids').write_text(str(os.getpid())+' '+str(child.pid));print('live log',flush=True);time.sleep(60)"
        return {'hooks':[{'id':'sleep','every':1,'argv':['true'],'second_stage':{'argv':[sys.executable,'-c',code],'timeout':timeout}}]}

    def start(self,timeout=10):
        scheduler=hooks.Scheduler(self.config_value(timeout))
        scheduler.accepted('TASK-X','x',self.head,committed=True)
        manager=scheduler.background
        run=manager.next(self.root,self.runner/'background')
        (Path(run['prepared'])/'payload').write_text('sealed')
        manager.launch(self.root,run)
        self.addCleanup(manager.close)
        self.wait_for(lambda:(Path(run['reports'])/'pids').exists())
        return scheduler,run,[int(p) for p in (Path(run['reports'])/'pids').read_text().split()]

    def test_timeout_retains_inputs_and_live_logs_and_can_acknowledge_failure(self):
        scheduler,run,pids=self.start(timeout=.4)
        self.wait_for(lambda:(Path(run['directory'])/'result.json').exists())
        self.wait_for(lambda:scheduler.background.slot['process'].poll() is not None)
        completed=scheduler.background.poll()
        self.assertIsNotNone(completed)
        receipt=completed[1]
        self.assertEqual(receipt['exit'],124)
        self.assertTrue(scheduler.background.blocked())
        self.assertTrue(Path(run['snapshot']).is_dir())
        self.assertIn('live log',Path(receipt['log_path']).read_text())
        self.wait_for(lambda:all(not self.alive(pid) for pid in pids))
        scheduler.cancel(run['id'])
        self.assertFalse(scheduler.background.blocked())

    def test_close_cleans_owned_children_and_new_scheduler_starts_empty(self):
        scheduler,run,pids=self.start()
        (Path(run['prepared'])/'payload').write_text('producer changed')
        self.assertEqual((Path(run['inputs'])/'payload').read_text(),'sealed')
        scheduler.background.close()
        self.wait_for(lambda:all(not self.alive(pid) for pid in pids))
        self.assertTrue(gate.load(Path(run['directory'])/'result.json')['cancelled'])
        self.assertFalse(hooks.Scheduler(self.config_value()).background.has_work())

    def test_killed_owner_pipe_cleans_background_without_replaying_state(self):
        value=self.runner/'owner.json'; value.write_text(json.dumps(self.config_value()))
        ready=self.runner/'ready'
        owner=self.base/'owner.py'
        owner.write_text('''import json,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import acceptance_hooks as hooks
s=hooks.Scheduler(json.loads(Path(sys.argv[2]).read_text()))
s.accepted('TASK-X','x',sys.argv[4],committed=True)
r=s.background.next(Path(sys.argv[3]),Path(sys.argv[5]))
s.background.launch(Path(sys.argv[3]),r)
Path(sys.argv[6]).write_text(r['directory'])
time.sleep(60)
''')
        process=subprocess.Popen([sys.executable,str(owner),str(SCRIPTS),str(value),str(self.root),self.head,str(self.runner/'dead-owner'),str(ready)])
        def cleanup():
            if process.poll() is None: process.kill()
            process.wait(timeout=3)
        self.addCleanup(cleanup)
        self.wait_for(ready.exists)
        directory=Path(ready.read_text())
        self.wait_for(lambda:(directory/'reports/pids').exists())
        pids=[int(p) for p in (directory/'reports/pids').read_text().split()]
        process.kill();process.wait(timeout=3)
        self.wait_for(lambda:(directory/'result.json').exists())
        self.wait_for(lambda:all(not self.alive(pid) for pid in pids))
        self.assertTrue(gate.load(directory/'result.json')['cancelled'])

    def test_unsafe_artifact_link_rejected_and_round_robin_single_slot(self):
        cfg={'hooks':[{'id':name,'every':1,'argv':['true'],'second_stage':{'argv':['true']}} for name in ('a','b')]}
        scheduler=hooks.Scheduler(cfg)
        scheduler.accepted('TASK-X','x',self.head,committed=True)
        manager=scheduler.background
        run=manager.next(self.root,self.runner/'round-robin')
        self.assertEqual(run['hook'],'a');self.assertIsNone(manager.next(self.root,self.runner/'round-robin'))
        (Path(run['inputs'])/'outside').symlink_to(self.root/'file')
        with self.assertRaisesRegex(ValueError,'escapes snapshot'): manager.launch(self.root,run)
        manager.failed_preparation(run,'invalid link');manager.poll();scheduler.cancel(run['id'])
        scheduler.accepted('TASK-Y','y',self.head,committed=True)
        self.assertEqual(manager.next(self.root,self.runner/'round-robin')['hook'],'b')
