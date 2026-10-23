"""Behavioral checks for the worker's stable command-line seams."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor


ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "worker.sh").exists())
RUNTIME = ROOT / "worker_runtime.py"


def runtime(*args, env=None):
    return subprocess.run(
        [sys.executable, str(RUNTIME), *map(str, args)],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


class QueueContractTests(unittest.TestCase):
    def test_pop_preserves_comments_and_only_removes_first_task(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = Path(directory) / "tasks.txt"
            queue.write_text("# heading\n\nTASK-1 | TARGET: a.py\nTASK-2 | TARGET: b.py\n")

            result = runtime("queue-pop", queue)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), "TASK-1 | TARGET: a.py")
            self.assertEqual(queue.read_text(), "# heading\n\nTASK-2 | TARGET: b.py\n")

    def test_pop_empty_queue_leaves_file_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = Path(directory) / "tasks.txt"
            queue.write_text("# heading\n\n")
            result = runtime("queue-pop", queue)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertEqual(queue.read_text(), "# heading\n\n")

    def test_parallel_claims_do_not_duplicate_a_task(self):
        with tempfile.TemporaryDirectory() as directory:
            queue = Path(directory) / "tasks.txt"
            queue.write_text("".join(f"TASK-{i}\n" for i in range(8)))
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(lambda _: runtime("queue-pop", queue), range(8)))
            self.assertTrue(all(result.returncode == 0 for result in results))
            self.assertEqual({result.stdout.strip() for result in results},
                             {f"TASK-{i}" for i in range(8)})
            self.assertEqual(queue.read_text(), "")

    def test_field_allows_pipe_inside_value(self):
        result = runtime(
            "task-field",
            "TASK-1 | TARGET: src/a.py | VERIFY: python -c 'print(1 | 2)' | CONSTRAINTS: safe",
            "VERIFY",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "python -c 'print(1 | 2)'")


class PollContractTests(unittest.TestCase):
    def test_empty_queue_reports_idle_without_modification(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks, done = root / "tasks.txt", root / "tasks.done"
            tasks.write_text("# no work\n")
            done.write_text("[DONE] TASK-1\n")
            result = runtime("poll-next", "--tasks", tasks, "--done", done,
                             "--pause", root / "PAUSE", "--work-dir", root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.split("\0")[:5], ["idle", "", "1", "0", "1"])
            self.assertEqual(tasks.read_text(), "# no work\n")

    def test_pause_does_not_claim_task(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks, done, pause = root / "tasks.txt", root / "tasks.done", root / "PAUSE"
            tasks.write_text("TASK-1 | TARGET: src/a.py\n")
            done.write_text("")
            pause.touch()
            result = runtime("poll-next", "--tasks", tasks, "--done", done,
                             "--pause", pause, "--work-dir", root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.split("\0")[0], "paused")
            self.assertIn("TASK-1", tasks.read_text())

    def test_claim_calculates_progress_and_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tasks, done = root / "tasks.txt", root / "tasks.done"
            tasks.write_text("# queued\nTASK-2 | LEVEL: 2 | TARGET: a.py,b.py | VERIFY: true\n")
            done.write_text("[DONE] TASK-1\n")
            result = runtime("poll-next", "--tasks", tasks, "--done", done,
                             "--pause", root / "PAUSE", "--work-dir", root,
                             "--step-base", "12", "--step-per-file", "5")
            self.assertEqual(result.returncode, 0, result.stderr)
            fields = result.stdout.split("\0")
            self.assertEqual(fields[:7], ["task", "TASK-2 | LEVEL: 2 | TARGET: a.py,b.py | VERIFY: true",
                                          "1", "1", "2", "2", "50"])
            self.assertEqual(fields[8], "TASK-2")
            self.assertEqual(fields[15], "22")
            self.assertEqual(tasks.read_text(), "# queued\n")


class StatusContractTests(unittest.TestCase):
    def test_status_is_valid_json_for_quoted_task_and_path(self):
        with tempfile.TemporaryDirectory() as directory:
            status = Path(directory) / "worker.status"
            task = 'TASK-1 | GOAL: write "a\\b"\nthen test'
            result = runtime(
                "status-write", status, "default", "mac", "macOS", "true",
                Path(directory) / 'folder "quoted"', "RUNNING", task,
                "3", "1", "2", "1", "50%", "[###---]", "42",
                "gpt-6-luna", "codex", "1800",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(status.read_text())
            self.assertEqual(data["current_task"], task)
            self.assertEqual(data["work_dir"], str(Path(directory) / 'folder "quoted"'))
            self.assertIs(data["isolation"], True)
            self.assertEqual(data["model"], "gpt-6-luna")
            self.assertEqual(data["progress"]["remaining"], 1)
            display = runtime("status-display", status)
            self.assertEqual(display.returncode, 0, display.stderr)
            self.assertIn(task, display.stdout)


class CliContractTests(unittest.TestCase):
    def test_codex_args_keep_low_cost_model_and_safe_auto_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            result = runtime(
                "codex-args", "--last-message", Path(directory) / "message.txt",
                "--model", "gpt-6-luna", "--effort", "none",
                "--approval-mode", "auto", "--sandbox", "workspace-write",
                "--ephemeral", "1", "--additional-dirs", directory,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            args = result.stdout.split("\0")[:-1]
            self.assertEqual(args[:3], ["exec", "--color", "never"])
            self.assertIn("--approve-for-me", args)
            self.assertIn("gpt-6-luna", args)
            self.assertIn("model_reasoning_effort=none", args)
            self.assertEqual(args[args.index("--add-dir") + 1], directory)

    def test_codex_args_reject_unknown_approval_policy(self):
        result = runtime("codex-args", "--last-message", "/tmp/message",
                         "--approval-mode", "unknown")
        self.assertEqual(result.returncode, 2)
        self.assertIn("approval", result.stderr.lower())


class TimeoutContractTests(unittest.TestCase):
    def test_run_timeout_preserves_exit_code_and_streamed_output(self):
        result = runtime("run-timeout", "5", "--", sys.executable, "-c",
                         "import sys; print('started', flush=True); sys.exit(7)")
        self.assertEqual(result.returncode, 7)
        self.assertIn("started", result.stdout)

    def test_run_timeout_returns_124_and_terminates_child(self):
        result = runtime("run-timeout", "0.1", "--", sys.executable, "-c",
                         "import time; print('started', flush=True); time.sleep(10)")
        self.assertEqual(result.returncode, 124)
        self.assertIn("started", result.stdout)


class GitAuditContractTests(unittest.TestCase):
    def audit_case(self, files, *, target="src/a.py", title="[CODE: EXPAND]", level="1", constraints="", untracked=None, baseline_source="first\nsecond\n"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args],
                                      check=True, capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "Audit Test")
            git("config", "user.email", "audit@example.invalid")
            (root / "src").mkdir()
            (root / "src/a.py").write_text(baseline_source)
            (root / "tests").mkdir()
            (root / "tests/test_a.py").write_text("assert True\n")
            git("add", ".")
            git("commit", "-qm", "baseline")
            base = git("rev-parse", "HEAD")
            for path, content in files.items():
                destination = root / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(content)
            git("add", ".")
            git("commit", "-qm", "change")
            if untracked:
                (root / untracked).write_text("ghost\n")
            return runtime("git-audit", "--work-dir", root, "--base", base,
                           "--target", target, "--constraints", constraints,
                           "--title", title, "--level", level)

    def test_accepts_declared_target(self):
        self.assertEqual(self.audit_case({"src/a.py": "updated\n"}).returncode, 0)

    def test_rejects_file_outside_target(self):
        result = self.audit_case({"src/other.py": "new\n"})
        self.assertEqual(result.returncode, 2)
        self.assertIn("Target Whitelist", result.stdout)

    def test_diagnostic_cannot_commit_product_code(self):
        result = self.audit_case({"src/a.py": "updated\n"}, title="[DIAGNOSTIC]")
        self.assertEqual(result.returncode, 4)

    def test_fix_cannot_modify_tests(self):
        result = self.audit_case({"tests/test_a.py": "assert False\n"},
                                 target="tests/test_a.py", title="[CODE: FIX]")
        self.assertEqual(result.returncode, 5)

    def test_rejects_decreased_assertions(self):
        result = self.audit_case({"tests/test_a.py": "pass\n"},
                                 target="tests/test_a.py", title="[CODE: REFACTOR]")
        self.assertEqual(result.returncode, 7)

    def test_rejects_untracked_file(self):
        result = self.audit_case({"src/a.py": "updated\n"}, untracked="ghost.txt")
        self.assertEqual(result.returncode, 1)

    def test_rejects_micro_task_large_deletion(self):
        result = self.audit_case({"src/a.py": "kept\n"}, level="3",
                                 baseline_source="".join(f"line {i}\n" for i in range(50)))
        self.assertEqual(result.returncode, 8)


class IsolationPreviewContractTests(unittest.TestCase):
    def test_worktree_setup_mirrors_config_and_preview_publishes_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args],
                                      check=True, capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "Preview Test")
            git("config", "user.email", "preview@example.invalid")
            (root / "source.txt").write_text("baseline\n")
            (root / ".env").write_text("SAMPLE=1\n")
            (root / ".gitignore").write_text(".env\n.worker.env\n.reports\n")
            git("add", "source.txt", ".gitignore")
            git("commit", "-qm", "baseline")

            setup = runtime("ensure-worktree", "--root", root)
            self.assertEqual(setup.returncode, 0, setup.stderr)
            tree = root / ".worker-tree"
            self.assertEqual((tree / "source.txt").read_text(), "baseline\n")
            self.assertEqual((tree / ".env").read_text(), "SAMPLE=1\n")
            self.assertTrue((tree / ".reports").exists())
            self.assertEqual(runtime("ensure-worktree", "--root", root).returncode, 0)

            (root / "source.txt").write_text("new baseline\n")
            git("add", "source.txt")
            git("commit", "-qm", "advance root")
            advanced = runtime("ensure-worktree", "--root", root)
            self.assertEqual(advanced.returncode, 0, advanced.stderr)
            self.assertEqual((tree / "source.txt").read_text(), "new baseline\n")

            (tree / "source.txt").write_text("worker result\n")
            (tree / "source-link.txt").symlink_to("source.txt")
            subprocess.run(["git", "-C", str(tree), "add", "source.txt", "source-link.txt"], check=True)
            subprocess.run(["git", "-C", str(tree), "commit", "-qm", "result"], check=True)
            (tree / "build/bin").mkdir(parents=True)
            (tree / "build/bin/app").write_text("compiled\n")
            preview = runtime("publish-preview", "--root", root,
                              "--task-id", "TASK-1", "--title", 'A "quoted" task')
            self.assertEqual(preview.returncode, 0, preview.stderr)
            self.assertEqual((root / ".preview/source.txt").read_text(), "worker result\n")
            self.assertTrue((root / ".preview/source-link.txt").is_symlink())
            self.assertEqual((root / ".preview/build/bin/app").read_text(), "compiled\n")
            metadata = json.loads((root / ".preview/version.json").read_text())
            self.assertEqual(metadata["task_id"], "TASK-1")
            self.assertEqual(metadata["summary"], 'A "quoted" task')


class WorkerIntegrationTests(unittest.TestCase):
    def test_codex_task_keeps_queue_status_commit_and_guard_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", "worker_runtime.py", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / ".worker.env").write_text(
                "AI_CLI=codex\nAI_MODEL=gpt-6-luna\nAI_EFFORT=none\n"
                "CODEX_APPROVAL_MODE=auto\nWORKER_ISOLATION=0\n"
                "RUN_ONCE=1\nPOLL_INTERVAL=0\nTASK_TIMEOUT=30\n"
            )
            (root / "tasks.txt").write_text(
                "TASK-1 | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: EXPAND] "
                "Write output | VERIFY: test -f output.txt\n"
            )
            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "codex"
            fake.write_text(
                "#!/bin/sh\n"
                "printf '%s\\n' \"$@\" > \"$FAKE_ARGS_LOG\"\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = --output-last-message ]; then\n"
                "    shift; printf 'Attempts: 1 | Confidence: HIGH\\n' > \"$1\"\n"
                "  fi\n"
                "  shift\n"
                "done\n"
                "printf 'hello\\n' > output.txt\n"
                "if [ \"${FAKE_OUTSIDE:-0}\" = 1 ]; then printf 'bad\\n' > outside.txt; fi\n"
            )
            fake.chmod(0o755)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args],
                                      capture_output=True, text=True, check=True).stdout.strip()
            git("init", "-q")
            git("config", "user.name", "Worker Test")
            git("config", "user.email", "worker@example.invalid")
            git("add", "worker.sh", "worker_runtime.py", ".gitignore", "tasks.txt")
            git("commit", "-qm", "fixture")
            args_log = Path(directory) / "args.txt"
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
            env["FAKE_ARGS_LOG"] = str(args_log)

            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                    env=env, capture_output=True, text=True, timeout=45)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((root / "tasks.txt").read_text(), "")
            self.assertIn("[DONE]", (root / "tasks.done").read_text())
            self.assertEqual((root / "output.txt").read_text(), "hello\n")
            self.assertEqual(git("show", "HEAD:output.txt"), "hello")
            self.assertIn("--model\ngpt-6-luna", args_log.read_text())
            self.assertIn("model_reasoning_effort=none", args_log.read_text())
            self.assertIn("--approve-for-me", args_log.read_text())
            self.assertEqual(json.loads((root / "worker.status").read_text())["state"], "STOPPED")
            self.assertIn("[MECHANICAL_AUDIT] Status: PASS", (root / "progress.log").read_text())

            # The same public worker entry point must reject an undeclared edit.
            (root / "tasks.txt").write_text(
                "TASK-2 | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: EXPAND] "
                "Try an out-of-scope edit | VERIFY: test -f output.txt\n"
            )
            env["FAKE_OUTSIDE"] = "1"
            rejected = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                      env=env, capture_output=True, text=True, timeout=45)
            self.assertEqual(rejected.returncode, 0, rejected.stdout + rejected.stderr)
            self.assertIn("[FAILED]", (root / "tasks.done").read_text())
            self.assertIn("[MECHANICAL_AUDIT] Status: FAIL", (root / "progress.log").read_text())
            self.assertFalse((root / "outside.txt").exists())
            self.assertEqual(git("show", "HEAD:output.txt"), "hello")


class InstallerIntegrationTests(unittest.TestCase):
    @unittest.skipUnless((ROOT / "install.sh").exists(), "source checkout only")
    def test_installer_deploys_python_runtime_and_regression_pattern(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "project"
            target.mkdir()
            subprocess.run(["git", "init", "-q", str(target)], check=True)
            result = subprocess.run(["bash", str(ROOT / "install.sh"), str(target)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((target / "worker_runtime.py").is_file())
            self.assertTrue((target / "test/nightshift_worker/test_worker_runtime.py").is_file())
            self.assertTrue((target / "test/nightshift_worker/README.md").is_file())
            self.assertTrue((target / ".worker.env").is_file())
            installed = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "test", "-v"],
                cwd=target, capture_output=True, text=True, timeout=45,
            )
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)


if __name__ == "__main__":
    unittest.main()
