"""Automatic scratch-review tickets and their bounded Worker-only contract."""
import json
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "nightshift/worker_runtime.py"
sys.path.insert(0, str(RUNTIME.parent))
import scratch_review
import worker_runtime


class ScratchReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.runtime = self.root / "nightshift"
        self.runtime.mkdir()
        (self.runtime / "tasks.txt").write_text("USER-TASK | ACTION: preserve work\n")
        (self.runtime / "tasks.done").write_text("")
        self.env = {**os.environ, "SCRATCH_REVIEW_ATTEMPTS_MB": "1",
                    "SCRATCH_REVIEW_FAILED_MB": "0", "SCRATCH_REVIEW_FAILED_DIRS": "3"}

    def tearDown(self):
        self.temporary.cleanup()

    def cli(self, *arguments):
        return subprocess.run([sys.executable, str(RUNTIME), *map(str, arguments)],
                              capture_output=True, text=True, env=self.env)

    def check(self, *arguments):
        result = self.cli("scratch-review-check", "--root", self.root, *arguments)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def large_attempt(self):
        artifact = self.runtime / ".scratch/attempts/OLD/old-attempt/adapter/output.log"
        artifact.parent.mkdir(parents=True)
        with artifact.open("wb") as output:
            output.truncate(1024 * 1024)
        return artifact

    def test_threshold_enqueues_one_review_without_losing_existing_work(self):
        artifact = self.large_attempt()
        first = self.check()
        self.assertEqual(first["state"], "queued")
        queue = (self.runtime / "tasks.txt").read_text()
        self.assertIn("[MAINTENANCE: SCRATCH]", queue)
        self.assertIn("nightshift/.scratch/review/last-review.json", queue)
        self.assertTrue(queue.endswith("USER-TASK | ACTION: preserve work\n"))
        self.assertEqual(self.check()["state"], "pending")
        self.assertEqual((self.runtime / "tasks.txt").read_text().count("[MAINTENANCE: SCRATCH]"), 1)
        self.assertEqual(artifact.stat().st_size, 1024 * 1024)


    def write_report(self, task_id, **changes):
        report = dict(task_id=task_id, status="reviewed", before_bytes=1048576,
                      after_bytes=1048576, removed=[], kept={"pending": 1}, note="kept pending work")
        report.update(changes)
        path = self.runtime / ".scratch/review/last-review.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report))
        return path

    def test_concurrent_monitors_enqueue_only_one_ticket(self):
        self.large_attempt()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.cli("scratch-review-check", "--root", self.root), range(4)))
        self.assertTrue(all(result.returncode == 0 for result in results))
        self.assertEqual((self.runtime / "tasks.txt").read_text().count(scratch_review.TAG), 1)

    def test_below_threshold_disabled_and_stats_only_do_not_enqueue(self):
        self.assertEqual(self.check()["state"], "below_threshold")
        self.large_attempt()
        self.assertEqual(self.check("--stats-only")["attempts_bytes"], 1048576)
        self.env["SCRATCH_REVIEW_ENABLED"] = "0"
        self.assertEqual(self.check()["state"], "disabled")
        self.assertNotIn("MAINTENANCE", (self.runtime / "tasks.txt").read_text())

    def test_failure_count_threshold_and_orphan_recovery_preserve_same_ticket(self):
        for number in range(3):
            (self.runtime / f".scratch/failed_tasks/old-{number}").mkdir(parents=True)
        self.assertEqual(self.check()["state"], "queued")
        task = (self.runtime / "tasks.txt").read_text().splitlines()[0]
        (self.runtime / "tasks.txt").write_text("USER-TASK | ACTION: preserve work\n")
        state_path = self.runtime / ".scratch/review/state.json"
        state = json.loads(state_path.read_text())
        state["queued_at"] = time.time() - 121
        state_path.write_text(json.dumps(state))
        self.assertEqual(self.check()["state"], "requeued")
        self.assertEqual((self.runtime / "tasks.txt").read_text().splitlines()[0], task)

    def test_live_claim_is_not_duplicated(self):
        self.large_attempt()
        self.check()
        task = (self.runtime / "tasks.txt").read_text().splitlines()[0]
        (self.runtime / "tasks.txt").write_text("")
        (self.runtime / "worker.status").write_text(json.dumps(dict(pid=os.getpid(), current_task=task)))
        self.assertEqual(self.check()["state"], "running")
        self.assertEqual((self.runtime / "tasks.txt").read_text(), "")

    def test_fixed_report_overwrites_and_cooldown_prevents_repeat_work(self):
        self.large_attempt()
        self.check()
        task = (self.runtime / "tasks.txt").read_text().splitlines()[0]
        task_id = task.split("|", 1)[0].strip()
        (self.runtime / "tasks.txt").write_text("")
        path = self.write_report(task_id)
        scratch_review.finish(self.runtime, task_id, worker_runtime.atomic_write)
        self.assertEqual(self.check()["state"], "cooldown")
        scratch_review.finish(self.runtime, task_id, worker_runtime.atomic_write, "failed review")
        self.assertEqual(json.loads(path.read_text())["status"], "failed")
        self.assertLessEqual(path.stat().st_size, 1024)
        self.assertEqual(len(list(path.parent.glob("last-review*"))), 1)
        with (self.runtime / ".scratch/attempts/OLD/old-attempt/adapter/output.log").open("ab") as output:
            output.write(b"x" * 1048576)
        self.assertEqual(self.check()["state"], "queued")

    def test_receipt_rejects_oversize_stale_and_out_of_scope_paths(self):
        for changes in ({"task_id": "stale"}, {"removed": ["nightshift/.scratch/code-index"]},
                        {"removed": ["nightshift/.scratch/attempts/../secret"]},
                        {"note": "x" * 1500}, {"removed": ["nightshift/.scratch/attempts/CURRENT/current"]}):
            with self.subTest(changes=changes):
                self.write_report("CURRENT", **changes) if "task_id" not in changes else self.write_report("stale")
                with self.assertRaises(ValueError):
                    scratch_review.validate_report(self.runtime, "CURRENT")

    def test_symlink_roots_are_refused(self):
        external = self.root / "external"
        external.mkdir()
        (self.runtime / ".scratch").symlink_to(external, target_is_directory=True)
        result = self.cli("scratch-review-check", "--root", self.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(external.iterdir()), [])

    def test_prompt_is_bounded_and_does_not_include_normal_planner_contract(self):
        task = scratch_review.task_line("SCRATCH-REVIEW-test")
        prompt = worker_runtime.build_task_prompt(task, "SCRATCH-REVIEW-test", "1", "", "none", "", "", 17, 1, 12, 5, "progress.log")
        for term in ("7 days", "recovered:true", "Planner_Review: accept", "newest attempt",
                     "Do not dump raw logs", "<=1024", "Never stage or commit"):
            self.assertIn(term, prompt)
        self.assertNotIn("LAUNCHER CONTRACT", prompt)
        self.assertNotIn("engineering/tdd", prompt)

    def test_daemon_reviews_internally_then_continues_user_queue(self):
        self.run_daemon_review(False)

    def test_bad_receipt_does_not_block_user_queue_or_create_planner_audit(self):
        self.run_daemon_review(True)

    def run_daemon_review(self, invalid):
        # Real daemon + generic adapter; fake executable exercises the prompt/result protocol.
        shutil.copy2(RUNTIME, self.runtime / "worker_runtime.py")
        shutil.copy2(RUNTIME.parent / "scratch_review.py", self.runtime / "scratch_review.py")
        shutil.copy2(RUNTIME.parent / "worker.sh", self.runtime / "worker.sh")
        shutil.copytree(RUNTIME.parent / "adapters", self.runtime / "adapters")
        (self.root / ".gitignore").write_text("nightshift/.scratch/\nnightshift/tasks*\nnightshift/progress.log\nnightshift/worker*.status\nnightshift/.worker*\n")
        (self.runtime / "tasks.txt").write_text("USER-TASK | LEVEL: 1 | TARGET: product.txt | ACTION: preserve | VERIFY: true\n")
        (self.root / "product.txt").write_text("product\n")
        fake = self.root / "fake.py"
        fake.write_text("""import json, os
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path('nightshift').resolve()))
import scratch_review
ident = os.environ['NIGHTSHIFT_TASK_ID']
if ident.startswith('SCRATCH-REVIEW-'):
    prompt = Path(os.environ['NIGHTSHIFT_PROMPT_FILE']).read_text()
    assert 'DELETE BOUNDARY' in prompt and '<=1024' in prompt
    before = scratch_review.inventory('nightshift')
    old = Path('nightshift/.scratch/attempts/OLD/old-attempt')
    assert (old / 'baseline/snapshot.json').exists()
    metadata = json.loads((old / 'baseline/snapshot.json').read_text())
    assert metadata['task_id'] == 'OLD' and metadata['work_dir'] == str(Path.cwd())
    assert all(p.stat().st_mtime < __import__('time').time()-7*86400 for p in old.rglob('*'))
    assert 'Planner_Review: accept' in Path('nightshift/progress.log').read_text()
    if not os.environ.get('INVALID_RECEIPT'):
        shutil.rmtree(old)
    after = scratch_review.inventory('nightshift')
    receipt = dict(task_id=('wrong' if os.environ.get('INVALID_RECEIPT') else ident),status='reviewed',
        before_bytes=before['attempts_bytes']+before['failed_bytes'],
        after_bytes=after['attempts_bytes']+after['failed_bytes'],
        removed=[] if old.exists() else [str(old)],kept={'anchor':1},note='removed closed old fixture')
    Path('nightshift/.scratch/review/last-review.json').write_text(json.dumps(receipt))
json.dump(dict(outcome='complete',changed=False,verification_evidence='fixture verified',
    commit_message='test: reviewed',attempts=1,confidence='HIGH'),open(os.environ['NIGHTSHIFT_RESULT_FILE'],'w'))
""")
        registration = {"test": {"default": True,"worker": {"task_timeout_seconds":30},
                         "agent": {"adapter":"generic", "command":sys.executable, "args":[str(fake)]}}}
        (self.runtime / "adapters/agents.json").write_text(json.dumps(registration))
        for arguments in (("init", "-q"), ("config","user.name","Test"),
                          ("config","user.email","test@example.invalid"), ("add","."), ("commit","-qm","fixture")):
            subprocess.run(["git","-C",str(self.root),*arguments],check=True,capture_output=True)
        self.large_attempt()
        baseline = self.runtime / ".scratch/attempts/OLD/old-attempt/baseline/snapshot.json"
        baseline.parent.mkdir()
        baseline.write_text(json.dumps(dict(task_id="OLD", attempt_id="old-attempt", work_dir=str(self.root))))
        old = baseline.parent.parent
        for path in [*old.rglob("*"), old]:
            os.utime(path,(time.time()-8*86400, time.time()-8*86400))
        (self.runtime / "tasks.done").write_text("[DONE] OLD\n")
        (self.runtime / "progress.log").write_text("[MECHANICAL_AUDIT] Status: PASS | Task: OLD | Planner_Review: accept\n")
        anchor = self.runtime / ".scratch/attempts/OLD/new-attempt/evidence"
        anchor.parent.mkdir(parents=True)
        anchor.write_text("keep")
        env = {**self.env,"RUN_ONCE":"1","POLL_INTERVAL":"0","INVALID_RECEIPT":"1" if invalid else ""}
        result = subprocess.run(["bash",str(self.runtime / "worker.sh")],cwd=self.root,
                                env=env,capture_output=True,text=True,timeout=35)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn("[SCRATCH_REVIEW]",result.stdout,result.stdout+result.stderr)
        report = json.loads((self.runtime / ".scratch/review/last-review.json").read_text())
        self.assertEqual(report["status"],"failed" if invalid else "reviewed",result.stdout+result.stderr)
        self.assertTrue(anchor.exists())
        self.assertEqual((self.root / "product.txt").read_text(),"product\n")
        self.assertEqual((self.runtime / "tasks.txt").read_text(),"")
        self.assertIn("[DONE] USER-TASK",(self.runtime / "tasks.done").read_text())
        self.assertNotIn("SCRATCH-REVIEW",(self.runtime / "tasks.done").read_text())
        self.assertNotIn("SCRATCH-REVIEW",(self.runtime / "progress.log").read_text())
        self.assertLessEqual((self.runtime / ".scratch/review/last-review.json").stat().st_size,1024)


if __name__ == "__main__":
    unittest.main()
