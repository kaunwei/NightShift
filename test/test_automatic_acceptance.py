"""Acceptance behavior through the public runtime CLI and real unittest hooks."""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "scripts/worker_runtime.py"
HOT = ROOT / "scripts/unittest_hot.py"
sys.path.insert(0, str(ROOT / "scripts"))
import acceptance
import worker_runtime as runtime_module


class AutomaticAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="nightshift-acceptance-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.root = self.directory / "project"
        self.root.mkdir()
        (self.root / "nightshift/adapters").mkdir(parents=True)
        (self.root / "test").mkdir()
        (self.root / "test/test_behavior.py").write_text(
            "import unittest\nclass Behavior(unittest.TestCase):\n"
            "    def test_existing(self):\n        self.assertEqual(1, 1)\n")
        (self.root / "value.txt").write_text("before\n")
        (self.root / ".gitignore").write_text("*.ignored\n__pycache__/\n")
        self.cfg = {"version": 1, "hot": shlex.join([sys.executable, str(HOT)]),
                    "cold": "true", "timeout": 5, "wiring": ["hot.json"]}
        self.write_config()
        self.git("init", "-q")
        self.git("config", "user.name", "Acceptance Fixture")
        self.git("config", "user.email", "acceptance@example.invalid")
        self.git("add", ".")
        self.git("commit", "-qm", "baseline")
        self.base = self.git("rev-parse", "HEAD")
        self.branch = self.git("branch", "--show-current")
        self.plan = self.directory / "plan.json"
        self.plan.write_text("{}")
        self.wrapper = self.directory / "worker.py"
        self.wrapper.write_text('''import json,os,pathlib
p=json.loads(pathlib.Path(os.environ['FIXTURE_PLAN']).read_text())
root=pathlib.Path.cwd();task=os.environ['NIGHTSHIFT_TASK_ID']
ghost=os.environ.get('NIGHTSHIFT_EXECUTION_KIND')=='closeout'
if ghost:
 if p.get('ghost_code'): (root/'value.txt').write_text('forbidden')
 if p.get('ghost_wire'): (root/'hot.json').write_text('{}')
 result={'outcome':'complete','commit_message':'fix: ghost message'} if p.get('ghost_message') or p.get('ghost_wire') else {'outcome':'blocked','diagnostic':'fixture diagnosis'}
else:
 name='test_'+task.replace('-','_')
 if not p.get('unchanged'):
  with (root/'test/test_behavior.py').open('a') as f:
   if p.get('skip'): f.write('    @unittest.skip("fixture")\\n')
   f.write('    def '+name+'(self):\\n        self.assertEqual(1, '+('2' if p.get('fail') else '1')+')\\n')
  (root/'value.txt').write_text(task)
 source='test/test_behavior.py'
 case='test_behavior.Behavior.'+('test_existing' if p.get('unchanged') else name)
 if p.get('task_only'): source='extra_test.py';(root/source).write_text('import unittest\\nclass Extra(unittest.TestCase):\\n def test_new(self): self.assertTrue(True)\\n');case='extra_test.Extra.test_new'
 result={'outcome':'complete','changed':True,'commit_message':'fix: '+task,'tdd_cases':[{'id':case,'source':source}]}
 if p.get('missing_declaration'): result.pop('tdd_cases')
 if p.get('empty_declaration'): result['tdd_cases']=[]
 if p.get('missing_message'): result.pop('commit_message')
 if p.get('comment_only'):
  (root/'test/test_behavior.py').write_text('import unittest\\nclass Behavior(unittest.TestCase):\\n    def test_existing(self):\\n        self.assertEqual(1, 1) # comment\\n')
  result['tdd_cases']=[{'id':'test_behavior.Behavior.test_existing','source':'test/test_behavior.py'}]
 if p.get('outside'): (root/'outside.txt').write_text('unexpected')
pathlib.Path(os.environ['NIGHTSHIFT_RESULT_FILE']).write_text(json.dumps(result))
''')
        registry = {"fixture": {"default": True, "worker": {"task_timeout_seconds": 8, "step_base": {"L1": 60, "L2": 40, "L3": 20}},
                                "agent": {"adapter": "generic", "command": sys.executable,
                                          "args": [str(self.wrapper)], "env": {"FIXTURE_PLAN": str(self.plan)},
                                          "config": {"initial_score": 3}}}}
        config_path = self.root / "nightshift/config.json"
        config = json.loads(config_path.read_text())
        config["agents"] = registry
        config_path.write_text(json.dumps(config))
        self.git("add", "nightshift/config.json")
        self.git("commit", "-qm", "register fixture")
        self.base = self.git("rev-parse", "HEAD")
        self.env = {**os.environ, "RUN_ONCE": "1", "POLL_INTERVAL": "0.01",
                    "WORKER_GHOST_TIMEOUT": "3", "PYTHONDONTWRITEBYTECODE": "1"}

    def write_config(self):
        path = self.root / "nightshift/config.json"
        config = json.loads(path.read_text()) if path.exists() else {}
        config.update(version=1, acceptance=dict(self.cfg))
        path.write_text(json.dumps(config))

    def git(self, *args):
        process = subprocess.run(["git", "-C", str(self.root), *args], text=True, capture_output=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        return process.stdout.strip()

    def cli(self, *args):
        process = subprocess.run([sys.executable, str(RUNTIME), *args], env=self.env,
                                 text=True, capture_output=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        return process

    def task(self, identity="TASK-A", **plan):
        self.plan.write_text(json.dumps(plan))
        tasks = self.root / "nightshift/tasks.txt"
        with tasks.open("a") as output:
            output.write(f"{identity} [CODE: FIX] | LEVEL: 3 | TARGET: value.txt,test,hot.json,extra_test.py | VERIFY: true\n")
        return self.cli("daemon", "--root", str(self.root))

    def state(self, name):
        return acceptance.load(acceptance.state_dir(self.root) / name)

    def test_external_worker_executes_and_commits_only_project_changes(self):
        import project_config
        external = self.directory / "external-config.json"
        cfg = json.loads((self.root / "nightshift/config.json").read_text())
        checks = self.directory / "checks"
        checks.mkdir()
        (checks / "hot.sh").write_text("test \"$PWD\" = \"$NIGHTSHIFT_PROJECT_ROOT\" || exit 9\nexec " + shlex.join([sys.executable, str(HOT)]) + "\n")
        cfg["projects"] = {"company": {"path": "project", "acceptance": {
            "hot_script": "checks/hot.sh", "cold": "true"}}}
        external.write_text(json.dumps(cfg))
        _, _, state = project_config.resolve_project(external, "company", self.root)
        state.mkdir(parents=True)
        (state / "tasks.txt").write_text(
            "TASK-EXTERNAL [CODE: FIX] | LEVEL: 3 | TARGET: value.txt,test,hot.json,extra_test.py | VERIFY: true\n")
        self.plan.write_text("{}")
        process = subprocess.run([sys.executable, str(RUNTIME), "daemon", "--root", str(self.directory),
                                  "--config", str(external), "--project", "company"],
                                 env=self.env, text=True, capture_output=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        self.assertNotEqual(self.git("rev-parse", "HEAD"), self.base, process.stdout + process.stderr)
        self.assertEqual(self.git("show", "HEAD:value.txt"), "TASK-EXTERNAL")
        changed = set(self.git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines())
        self.assertEqual(changed, {"value.txt", "test/test_behavior.py"})
        self.assertFalse((self.root / ".reports").exists())
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertTrue((state / "lifecycle/last-adapter.json").is_file())
        self.assertIn("Project: company", next((state / "lifecycle/runs").glob("*/prompt.txt")).read_text())

    @unittest.skipUnless((ROOT / "scripts/tools/.venv/bin/python").is_file(), "parser environment required")
    def test_external_index_uses_private_config_and_storage(self):
        import project_config
        external = self.directory / "external-config.json"
        cfg = json.loads((self.root / "nightshift/config.json").read_text())
        cfg["projects"] = {"company": {"path": "project", "code_index": {
            "include": ["test/**"], "exclude": [], "tool": [], "project": ["test/**"]}}}
        external.write_text(json.dumps(cfg))
        _, _, state = project_config.resolve_project(external, "company", self.root)
        process = subprocess.run([sys.executable, str(RUNTIME), "code-index", "--config", str(external),
                                  "--project", "company", "ensure"], cwd=self.directory,
                                 env=self.env, text=True, capture_output=True, timeout=30)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(Path(result["index_path"]), state / "code-index/index.json")
        self.assertTrue((state / "code-index/INDEX.md").is_file())
        self.assertFalse((self.root / "nightshift/.scratch/code-index").exists())
        data = json.loads((state / "code-index/index.json").read_text())
        self.assertTrue(any(entry["path"] == "test/test_behavior.py" for entry in data["files"]))

    def test_worker_restart_uses_changed_agent_budget_and_timeout(self):
        launcher = self.root / "nightshift/worker.sh"
        shutil.copy2(ROOT / "scripts/worker.sh", launcher)
        (self.root / "nightshift/worker_runtime.py").symlink_to(RUNTIME)
        config_path = self.root / "nightshift/config.json"
        config = json.loads(config_path.read_text())
        config["agents"]["fixture"]["worker"].update(
            task_timeout_seconds=11, step_base={"L1": 41, "L2": 31, "L3": 21})
        config_path.write_text(json.dumps(config))
        self.plan.write_text(json.dumps({}))
        (self.root / "nightshift/tasks.txt").write_text(
            "TASK-A [CODE: FIX] | LEVEL: 3 | TARGET: value.txt,test,hot.json,extra_test.py | VERIFY: true\n")
        env = {**self.env, "STEP_BASE": "999"}
        first = subprocess.run(["bash", str(launcher)], cwd=self.root, env=env,
                               capture_output=True, text=True, timeout=30)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        request = acceptance.load(acceptance.state_dir(self.root) / "last-adapter.json")["request"]
        self.assertEqual(request["limits"]["execution_timeout_seconds"], 11)
        self.assertEqual(request["limits"]["action_limit"], 41)
        self.assertIn("(21+4", Path(request["prompt_path"]).read_text())
        config = json.loads(config_path.read_text())
        config["agents"]["fixture"]["worker"].update(
            task_timeout_seconds=13, step_base={"L1": 42, "L2": 32, "L3": 22})
        config_path.write_text(json.dumps(config))
        (self.root / "nightshift/tasks.txt").write_text(
            "TASK-B [CODE: FIX] | LEVEL: 2 | TARGET: value.txt,test,hot.json,extra_test.py | VERIFY: true\n")
        second = subprocess.run(["bash", str(launcher)], cwd=self.root, env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        request = acceptance.load(acceptance.state_dir(self.root) / "last-adapter.json")["request"]
        self.assertEqual(request["limits"]["execution_timeout_seconds"], 13)
        self.assertEqual(request["limits"]["action_limit"], 52)
        self.assertIn("(32+4", Path(request["prompt_path"]).read_text())

    def test_success_commits_scores_and_stays_on_branch(self):
        self.task()
        self.assertNotEqual(self.git("rev-parse", "HEAD"), self.base)
        self.assertEqual(self.git("branch", "--show-current"), self.branch)
        self.assertEqual(self.git("status", "--porcelain"), "")
        scores = list((self.root / "nightshift/.worker-agent-scores").glob("*.json"))
        score = json.loads(scores[0].read_text())
        self.assertEqual(score["success_window"], ["TASK-A"])
        self.assertEqual(score["feedback"][-1]["result"], "accept")
        self.assertIsNone(self.state("paused.json"))

    def test_tdd_persists_in_next_task_hot(self):
        self.task()
        self.task("TASK-B")
        entries = list((acceptance.state_dir(self.root) / "tasks").glob("*.json"))
        second = next(acceptance.load(p) for p in entries if acceptance.load(p)["task_id"] == "TASK-B")
        self.assertIn("test_behavior.Behavior.test_TASK_A", second["result"]["hot"]["cases"])
        self.assertIn("test_behavior.Behavior.test_TASK_B", second["result"]["hot"]["cases"])

    def test_reject_missing_empty_unchanged_comment_task_only_skipped_and_failed(self):
        for plan in ("missing_declaration", "empty_declaration", "unchanged", "comment_only", "task_only", "skip", "fail", "outside"):
            with self.subTest(plan=plan):
                self.task("TASK-" + plan, **{plan: True})
                self.assertIsNotNone(self.state("paused.json"))
                self.assertEqual(self.git("rev-parse", "HEAD"), self.base)
                self.cli("restart", "--root", str(self.root))
        self.assertTrue(list((acceptance.state_dir(self.root) / "reports").glob("*/REPORT.md")))

    def test_ghost_supplies_message_but_cannot_change_code(self):
        self.task(missing_message=True, ghost_message=True)
        self.assertIsNone(self.state("paused.json"))
        self.assertIn("ghost message", self.git("log", "-1", "--format=%s"))
        head = self.git("rev-parse", "HEAD")
        self.task("TASK-B", missing_message=True, ghost_code=True, ghost_message=True)
        self.assertEqual(self.git("rev-parse", "HEAD"), head)
        self.assertIsNotNone(self.state("paused.json"))

    def test_failure_pause_requires_restart_and_cleans_before_new_worker(self):
        self.task(fail=True)
        self.assertEqual(self.git("status", "--porcelain"), "")
        report = json.loads(next((acceptance.state_dir(self.root) / "reports").glob("*/report.json")).read_text())
        self.assertTrue((Path(report["result"]["recovery_archive"]) / "changes.diff").is_file())
        (self.root / "keep.ignored").write_text("keep")
        (self.root / "discard.txt").write_text("discard")
        self.task("TASK-B")
        self.assertEqual(self.git("rev-parse", "HEAD"), self.base)
        self.assertIn("TASK-B", (self.root / "nightshift/tasks.txt").read_text())
        self.cli("restart", "--root", str(self.root))
        self.cli("daemon", "--root", str(self.root))
        self.assertEqual(self.git("show", "HEAD:value.txt"), "TASK-B")
        self.assertNotIn("test_TASK_A", (self.root / "test/test_behavior.py").read_text())
        self.assertFalse((self.root / "discard.txt").exists())
        self.assertTrue((self.root / "keep.ignored").exists())
        self.assertEqual(self.git("stash", "list"), "")

    def test_external_restart_cleans_failed_work_before_clean_preflight(self):
        external = self.directory / "external-config.json"
        state = self.directory / "runner"
        cfg = json.loads((self.root / "nightshift/config.json").read_text())
        cfg["projects"] = {"sample": {"path": str(self.root), "state": str(state)}}
        external.write_text(json.dumps(cfg))
        state.mkdir()
        queue = state / "tasks.txt"
        queue.write_text("TASK-FAIL [CODE: FIX] | LEVEL: 3 | TARGET: value.txt,test | VERIFY: true\n")
        self.plan.write_text(json.dumps({"fail": True}))
        command = [sys.executable, str(RUNTIME)]
        context = ["--root", str(self.root), "--config", str(external), "--project", "sample"]
        def call(operation):
            result = subprocess.run(command + [operation] + context, env=self.env,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result
        call("daemon")
        self.assertTrue((state / "lifecycle/paused.json").is_file())
        (self.root / "value.txt").write_text("failed attempt residue")
        (self.root / "scripts").mkdir(exist_ok=True)
        (self.root / "scripts/generated.uid").write_text("failed import")
        (self.root / "keep.ignored").write_text("keep")
        (state / "keep.txt").write_text("runner state")
        queue.write_text("TASK-NEXT [CODE: FIX] | LEVEL: 3 | TARGET: value.txt,test | VERIFY: true\n")
        self.plan.write_text("{}")
        call("daemon")  # Pause alone cannot authorize removing failed output.
        self.assertEqual((self.root / "value.txt").read_text(), "failed attempt residue")
        self.assertTrue((self.root / "scripts/generated.uid").is_file())
        call("restart")
        call("daemon")
        self.assertEqual(self.git("show", "HEAD:value.txt"), "TASK-NEXT")
        self.assertFalse((self.root / "scripts/generated.uid").exists())
        self.assertTrue((self.root / "keep.ignored").is_file())
        self.assertEqual((state / "keep.txt").read_text(), "runner state")
        self.assertFalse((state / "lifecycle/restart-clean.json").exists())
        self.assertEqual(self.git("stash", "list"), "")
        # A no-op restart must not authorize clearing unrelated future changes.
        (self.root / "unrelated.txt").write_text("preserve")
        call("restart")
        self.assertFalse((state / "lifecycle/restart-clean.json").exists())
        self.assertEqual((self.root / "unrelated.txt").read_text(), "preserve")

    def test_external_restart_refuses_cleanup_after_head_changes(self):
        external = self.directory / "external-config.json"
        state = self.directory / "runner"
        cfg = json.loads((self.root / "nightshift/config.json").read_text())
        cfg["projects"] = {"sample": {"path": str(self.root), "state": str(state)}}
        external.write_text(json.dumps(cfg))
        lifecycle = state / "lifecycle"
        lifecycle.mkdir(parents=True)
        (lifecycle / "paused.json").write_text('{"task":"TASK-FAILED"}')
        command = [sys.executable, str(RUNTIME)]
        context = ["--root", str(self.root), "--config", str(external), "--project", "sample"]
        subprocess.run(command + ["restart"] + context, env=self.env, check=True,
                       capture_output=True, text=True, timeout=10)
        self.git("commit", "--allow-empty", "-qm", "intervening commit")
        (self.root / "value.txt").write_text("preserve after HEAD change")
        result = subprocess.run(command + ["daemon"] + context, env=self.env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("HEAD changed after restart", (lifecycle / "paused.json").read_text())
        self.assertTrue((lifecycle / "restart-clean.json").is_file())
        self.assertEqual((self.root / "value.txt").read_text(), "preserve after HEAD change")

    def test_cold_cadence_counts_only_within_a_live_session(self):
        self.cfg["cold_every"] = 2
        self.write_config()
        self.git("add", "nightshift/config.json")
        self.git("commit", "-qm", "cold cadence")
        self.task()
        self.task("TASK-B")
        self.assertIsNone(self.state("cold.json"))  # Two launches are two fresh counters.
        queue = self.root / "nightshift/tasks.txt"
        queue.write_text("".join(f"{identity} [CODE: FIX] | LEVEL: 3 | TARGET: value.txt,test,hot.json | VERIFY: true\n"
                                 for identity in ("TASK-C", "TASK-D")))
        process = self.cli("daemon", "--root", str(self.root))
        head = self.git("rev-parse", "HEAD")
        self.assertEqual(self.state("cold.json")["passed"], head)
        self.assertNotIn("[COLD]", queue.read_text())
        self.assertIn("TASK-D", self.git("log", "-1", "--format=%B"))
        self.assertNotIn("TASK-COLD", process.stdout)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_cold_failure_diagnoses_without_reverting_accepted_commit(self):
        self.cfg.update(cold_every=1, cold="echo COLD_ERROR; exit 2")
        self.write_config()
        self.git("add", "nightshift/config.json")
        self.git("commit", "-qm", "cold failure")
        self.task()
        self.assertIsNotNone(self.state("paused.json"))
        reports = list((acceptance.state_dir(self.root) / "reports").glob("*/report.json"))
        self.assertIn("COLD_ERROR", reports[-1].read_text())
        self.assertEqual(self.git("show", "HEAD:value.txt"), "TASK-A")
        score = json.loads(next((self.root / "nightshift/.worker-agent-scores").glob("*.json")).read_text())
        self.assertEqual(len(score["success_window"]), 1)

    def test_score_replay_does_not_recreate_cold_in_a_new_session(self):
        self.cfg["cold_every"] = 1
        self.write_config()
        self.git("add", "nightshift/config.json")
        self.git("commit", "-qm", "cadence")
        self.task()
        record_path = next((acceptance.state_dir(self.root) / "tasks").glob("*.json"))
        record = acceptance.load(record_path)
        event = next(iter(json.loads(next((self.root / "nightshift/.worker-agent-scores").glob("*.json")).read_text())["applied_events"])).split(":")[0]
        acceptance.save(acceptance.state_dir(self.root) / "active.json", {
            "raw": record["title"], "task_id": record["task_id"], "base": record["base"], "event": event, "phase": "running"})
        self.cli("daemon", "--root", str(self.root))
        score = json.loads(next((self.root / "nightshift/.worker-agent-scores").glob("*.json")).read_text())
        self.assertEqual(len(score["success_window"]), 1)
        self.assertEqual((self.root / "nightshift/progress.log").read_text().count("[HOOK_PASS]"), 1)

    def test_workspace_lock_rejects_second_runtime(self):
        with acceptance.workspace(self.root):
            process = subprocess.run([sys.executable, str(RUNTIME), "daemon", "--root", str(self.root)],
                                     env=self.env, text=True, capture_output=True)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("another runtime", process.stderr)

    def test_unified_config_loads_both_acceptance_and_agents(self):
        unified = {
            "version": 1,
            "acceptance": {
                "hot": "python3 nightshift/unittest_hot.py --start test",
                "cold": "python3 -m unittest discover -s test",
                "cold_every": 3,
                "timeout": 120,
                "wiring": []
            },
            "agents": {
                "fixture-agent": {
                    "default": True,
                    "worker": {"task_timeout_seconds": 1200, "step_base": {"L1": 60, "L2": 40, "L3": 20}},
                    "agent": {"adapter": "generic", "command": "custom_agent"}
                }
            },
            "code_index": {
                "include": ["src/**"],
                "exclude": ["tmp/**"],
                "tool": ["tools/**"],
                "project": ["src/**"]
            }
        }
        (self.root / "nightshift/config.json").write_text(json.dumps(unified))
        (self.root / "nightshift/acceptance.json").unlink(missing_ok=True)
        (self.root / "nightshift/adapters/agents.json").unlink(missing_ok=True)

        cfg = acceptance.config(self.root)
        self.assertEqual(cfg["cold_every"], 3)
        self.assertEqual(cfg["timeout"], 120)

        agents = runtime_module.load_agent_registry(self.root / "nightshift/config.json")
        self.assertEqual(len(agents), 1)
        self.assertEqual(agents[0]["id"], "fixture-agent")
        self.assertEqual(agents[0]["command"], "custom_agent")

        from tools import index as index_tool
        idx_cfg = index_tool.project_config(self.root)
        self.assertEqual(idx_cfg["include"], ["src/**"])
        self.assertEqual(idx_cfg["exclude"], ["tmp/**"])
        self.assertEqual(idx_cfg["tool_paths"], ["tools/**"])
        self.assertEqual(idx_cfg["project_paths"], ["src/**"])

    def test_custom_project_acceptance_runner_overrides_hot_and_cold(self):
        import argparse
        hook_path = self.root / "nightshift/acceptance_runner.py"
        hook_path.write_text("""import acceptance
class CustomRunner(acceptance.DefaultAcceptanceRunner):
    def run_hot(self, args, result, run):
        return {"cases": ["custom.project.case"], "evidence": [{"phase": "custom", "command": "custom_hot", "exit": 0, "output": "ok"}]}
    def run_cold(self, root, run):
        (root / "custom_cold_ran.txt").write_text("cold_done")
def get_runner(root, cfg):
    return CustomRunner()
""")
        runner = acceptance.get_runner(self.root, self.cfg)
        self.assertEqual(runner.__class__.__name__, "CustomRunner")
        hot_res = runner.run_hot(argparse.Namespace(work_dir=str(self.root), verify="", worker_port=3001), {}, lambda *_: (0, ""))
        self.assertEqual(hot_res["cases"], ["custom.project.case"])
        runner.run_cold(self.root, lambda *_: (0, ""))
        self.assertTrue((self.root / "custom_cold_ran.txt").exists())


if __name__ == "__main__":
    unittest.main()
