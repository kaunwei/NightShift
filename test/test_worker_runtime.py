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

from scripts.worker_runtime import build_task_prompt, first_report, publish_research_reports


ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "worker.sh").exists())
RUNTIME = ROOT / "scripts/worker_runtime.py"


def runtime(*args, env=None):
    return subprocess.run(
        [sys.executable, str(RUNTIME), *map(str, args)],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


class WorkerPromptContractTests(unittest.TestCase):
    def test_prompt_preserves_task_scope_budget_verification_and_score_ownership(self):
        prompt = build_task_prompt(
            "[CODE: FIX] Correct the parser", "TASK-9", "2", "src/parser.py",
            "python3 -m unittest", "no thread sleeps", "preserve error messages",
            22, 2, 12, 5, "progress.log",
        )

        for required in (
            "src/parser.py", "Action budget: 22", "base 12 + 2 target files × 5",
            "Timeout is per task invocation", "python3 -m unittest", "TASK-9",
            "Planner reviews the evidence and records the score",
            "[EXEC] <brief action>", "[CLOSEOUT_REQUIRED]", "[SCOPE_BLOCKED]", "[DEAD_END]",
            "progress.log",
        ):
            with self.subTest(required=required):
                self.assertIn(required, prompt)

    def test_prompt_does_not_request_self_scoring_or_destructive_retry_reset(self):
        prompt = build_task_prompt("task", "TASK-1", "1", "src/a.py", "test",
                                  "", "", 17, 1, 12, 5, "progress.log")
        self.assertIn("never adjust the shared score yourself", prompt)
        self.assertIn("do not destructively reset files", prompt.lower())
        self.assertNotIn("restore the clean tree", prompt)


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


class WorkerScoreTests(unittest.TestCase):
    def test_new_worker_starts_at_five_and_maps_to_coarsest_task_level(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "score.json"
            result = runtime("score-read", "--state", state)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data["score"], 5)
            self.assertEqual(data["task_level"], 1)
            self.assertTrue(state.exists())

    def test_only_five_accepted_real_tasks_increase_score(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "score.json"
            state.write_text(json.dumps({"version": 1, "score": 3,
                                         "success_window": [], "failures": {}}))
            for index in range(4):
                result = runtime("score-record", "--state", state,
                                 "--task-id", f"TASK-{index}", "--result", "accept")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["score"], 3)
            result = runtime("score-record", "--state", state,
                             "--task-id", "TASK-4", "--result", "accept")
            self.assertEqual(json.loads(result.stdout)["score"], 4)
            self.assertEqual(json.loads(result.stdout)["successes_in_window"], 0)

    def test_reject_resets_success_window_while_no_fault_is_excluded(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "score.json"
            state.write_text(json.dumps({"version": 1, "score": 4,
                                         "success_window": ["A", "B"], "failures": {}}))
            result = runtime("score-record", "--state", state, "--task-id", "C",
                             "--result", "no_fault", "--evidence", "progress.log#L1")
            persisted = json.loads(state.read_text())
            self.assertEqual(persisted["success_window"], ["A", "B"])
            self.assertEqual(persisted["feedback"][-1]["evidence"], "progress.log#L1")
            result = runtime("score-record", "--state", state, "--task-id", "D",
                             "--result", "reject", "--evidence", "tasks.done#L2")
            self.assertEqual(json.loads(state.read_text())["success_window"], [])

    def test_concurrent_feedback_updates_do_not_lose_score_records(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "score.json"
            state.write_text(json.dumps({"version": 1, "score": 3,
                                         "success_window": [], "failures": {}}))
            with ThreadPoolExecutor(max_workers=5) as pool:
                results = list(pool.map(
                    lambda index: runtime("score-record", "--state", state,
                                           "--task-id", f"TASK-{index}",
                                           "--result", "accept"), range(5)))
            self.assertTrue(all(result.returncode == 0 for result in results))
            persisted = json.loads(state.read_text())
            self.assertEqual(persisted["score"], 4)
            self.assertEqual(len(persisted["feedback"]), 5)

    def test_hard_failures_lower_original_task_score_on_second_and_third_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "score.json"
            for expected in (5, 4, 3):
                result = runtime("score-record", "--state", state,
                                 "--task-id", "TASK-X", "--result", "hard_failure")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["score"], expected)
            result = runtime("score-record", "--state", state,
                             "--task-id", "TASK-X", "--result", "hard_failure")
            self.assertEqual(json.loads(result.stdout)["score"], 3)
            result = runtime("score-record", "--state", state,
                             "--task-id", "TASK-X", "--result", "success")
            self.assertEqual(json.loads(state.read_text())["failures"], {})

    def test_ghost_closeout_prompt_forbids_implementation_and_names_original_task(self):
        with tempfile.TemporaryDirectory() as directory:
            prompt = Path(directory) / "closeout.txt"
            result = runtime("ghost-prompt", "--output", prompt,
                             "--task-id", "TASK-7", "--verify", "python3 -m unittest")
            self.assertEqual(result.returncode, 0, result.stderr)
            text = prompt.read_text()
            self.assertIn("TASK-7", text)
            self.assertIn("MUST NOT modify", text)
            self.assertIn("python3 -m unittest", text)

    def test_codex_jsonl_command_execution_events_are_counted_against_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt, output, last_message = root / "prompt", root / "output", root / "message"
            prompt.write_text("task")
            executable = root / "codex"
            executable.write_text(
                "#!/bin/sh\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = --output-last-message ]; then shift; printf 'done\\n' > \"$1\"; fi\n"
                "  shift\n"
                "done\n"
                "printf '%s\\n' '{\"type\":\"item.completed\",\"item\":{\"type\":\"command_execution\"}}'\n"
                "sleep 0.3\n"
                "touch \"$BUDGET_MARKER\"\n"
            )
            executable.chmod(0o755)
            marker = Path(directory) / "continued-after-budget"
            env = os.environ.copy()
            env["BUDGET_MARKER"] = str(marker)
            result = runtime("task-cli", "--provider", "codex", "--executable", executable,
                             "--work-dir", root, "--prompt-file", prompt, "--output-file", output,
                             "--result-file", last_message, "--timeout", "10", "--model", "gpt-6-luna",
                             "--effort", "none", "--approval-mode", "auto", "--sandbox", "workspace-write",
                             "--ephemeral", "1", "--additional-dirs", "", "--step-budget", "0",
                             "--worker-port", "3001", "--target", "", "--task-id", "TASK-C", "--title", "test",
                             "--level", "1", "--verify", "", "--base", "HEAD", "--progress-file", "progress.log",
                             env=env)
            self.assertEqual(result.returncode, 125)
            self.assertFalse(marker.exists())

    def test_codex_hands_closeout_marker_to_ghost_without_editing_code(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "Codex Test")
            git("config", "user.email", "codex@example.invalid")
            (root / "output.txt").write_text("before\n")
            git("add", "output.txt")
            git("commit", "-qm", "baseline")
            base = git("rev-parse", "HEAD")
            prompt = Path(directory) / "prompt.txt"
            prompt.write_text("implement")
            output, last_message = Path(directory) / "cli.log", Path(directory) / "message.txt"
            executable = root / "codex"
            executable.write_text(
                "#!/bin/sh\n"
                "last='' prev=''\n"
                "for arg in \"$@\"; do if [ \"$prev\" = --output-last-message ]; then last=\"$arg\"; fi; prev=\"$arg\"; done\n"
                "case \"$*\" in\n"
                "  *'CLOSEOUT ONLY'*) printf 'verified closeout\\n' > \"$last\"; git add output.txt; git commit -qm closeout ;;\n"
                "  *) printf '[CLOSEOUT_REQUIRED]\\n' > \"$last\"; printf 'after\\n' > output.txt ;;\n"
                "esac\n"
                "printf '%s\\n' '{\"type\":\"item.completed\",\"item\":{\"type\":\"command_execution\"}}'\n"
            )
            executable.chmod(0o755)
            git("add", "codex")
            git("commit", "-qm", "add fake cli")
            base = git("rev-parse", "HEAD")
            result = runtime("task-cli", "--provider", "codex", "--executable", executable,
                             "--work-dir", root, "--prompt-file", prompt, "--output-file", output,
                             "--result-file", last_message, "--timeout", "10", "--model", "gpt-6-luna",
                             "--effort", "none", "--approval-mode", "auto", "--target", "output.txt",
                             "--task-id", "TASK-CLOSE", "--title", "[CODE: FIX] change output",
                             "--base", base, "--step-budget", "2")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(git("log", "-1", "--pretty=%s"), "closeout")
            self.assertEqual(git("show", "HEAD:output.txt"), "after")
            self.assertEqual(git("status", "--porcelain"), "")


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
            self.assertIn("Worker Score   : 5/5", display.stdout)

    def test_progress_prepend_keeps_new_record_before_existing_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "progress.log"
            path.write_text("older result\n")
            result = runtime("progress-prepend", "--path", path,
                             "--entry", "new result\nsecond detail")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(path.read_text(), "new result\nsecond detail\nolder result\n")


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

    def test_agy_args_preserve_mode_model_step_budget_and_existing_effort_suffix(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "agy"
            executable.write_text("#!/bin/sh\necho --max-turns\n")
            executable.chmod(0o755)
            extra = Path(directory) / "extra"
            extra.mkdir()
            result = runtime(
                "agy-args", "--executable", executable, "--model", "model-low",
                "--effort", "high", "--mode", "accept-edits", "--timeout", "90",
                "--step-budget", "23", "--additional-dirs", f" {extra},/missing",
                "--sandbox", "true",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.split("\0")[:-1], [
                "--sandbox", "--mode", "accept-edits", "--model", "model-low",
                "--print-timeout", "90s", "--add-dir", str(extra),
                "--max-turns", "23",
            ])

    def test_task_cli_streams_output_selects_last_message_and_commits_only_target(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "CLI Test")
            git("config", "user.email", "cli@example.invalid")
            (root / "output.txt").write_text("before\n")
            (root / ".gitignore").write_text("cli.log\ncodex\nmessage.txt\nprompt.txt\n")
            git("add", "output.txt", ".gitignore")
            git("commit", "-qm", "baseline")
            base = git("rev-parse", "HEAD")
            prompt = root / "prompt.txt"
            prompt.write_text("perform the task")
            output, last_message = root / "cli.log", root / "message.txt"
            executable = root / "codex"
            executable.write_text(
                "#!/bin/sh\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = --output-last-message ]; then shift; printf 'Attempts: 2\\n' > \"$1\"; fi\n"
                "  shift\n"
                "done\n"
                "printf 'finished\\n'\n"
                "printf 'after\\n' > output.txt\n"
            )
            executable.chmod(0o755)

            result = runtime(
                "task-cli", "--provider", "codex", "--executable", executable,
                "--work-dir", root, "--prompt-file", prompt, "--output-file", output,
                "--result-file", last_message, "--timeout", "15", "--model", "gpt-6-luna",
                "--effort", "none", "--approval-mode", "auto", "--target", "output.txt",
                "--task-id", "TASK-1", "--title", "[CODE: FIX] update output",
                "--base", base,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("finished", result.stdout)
            self.assertEqual(output.read_text(), "finished\n")
            self.assertEqual(last_message.read_text(), "Attempts: 2\n")
            self.assertEqual(git("show", "HEAD:output.txt"), "after")
            self.assertEqual(git("status", "--porcelain"), "")

    def test_agy_task_cli_uses_one_restricted_closeout_for_dirty_work(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "agy Test")
            git("config", "user.email", "agy@example.invalid")
            (root / "output.txt").write_text("before\n")
            git("add", "output.txt")
            git("commit", "-qm", "baseline")
            base = git("rev-parse", "HEAD")
            prompt = Path(directory) / "prompt.txt"
            prompt.write_text("perform the task")
            output, calls = Path(directory) / "cli.log", Path(directory) / "calls.log"
            executable = root / "agy"
            executable.write_text(
                "#!/bin/sh\n"
                "if [ \"${1:-}\" = --help ]; then echo --max-turns; exit 0; fi\n"
                "printf '%s %s\\n' \"$MAX_STEPS\" \"$*\" >> \"$CALLS_LOG\"\n"
                "printf '[EXEC] step\\n'\n"
                "printf 'after\\n' > output.txt\n"
            )
            executable.chmod(0o755)
            env = os.environ.copy()
            env["CALLS_LOG"] = str(calls)

            result = runtime(
                "task-cli", "--provider", "agy", "--executable", executable,
                "--work-dir", root, "--prompt-file", prompt, "--output-file", output,
                "--timeout", "15", "--step-budget", "2", "--task-id", "TASK-2",
                "--base", base, env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            call_lines = [line for line in calls.read_text().splitlines()
                          if line.startswith(("2 -p", "1 -p"))]
            self.assertEqual(len(call_lines), 2)
            self.assertTrue(call_lines[0].startswith("2 "))
            self.assertTrue(call_lines[1].startswith("1 "))
            self.assertIn("CLOSEOUT ONLY for original task TASK-2", calls.read_text())
            self.assertIn("MUST NOT modify source code", calls.read_text())
            self.assertEqual(output.read_text().count("[EXEC] step"), 2)

    def test_task_cli_converts_provider_print_timeout_to_timeout_exit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt, output = root / "prompt", root / "output"
            prompt.write_text("task")
            executable = root / "fake-cli"
            executable.write_text("#!/bin/sh\necho 'print timeout after 90s'\n")
            executable.chmod(0o755)
            result = runtime("task-cli", "--provider", "generic", "--executable", executable,
                             "--work-dir", root, "--prompt-file", prompt,
                             "--output-file", output, "--timeout", "10")
            self.assertEqual(result.returncode, 124)

    def test_task_cli_stream_timeout_stops_provider_and_preserves_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            prompt, output = root / "prompt", root / "output"
            prompt.write_text("task")
            executable = root / "fake-cli"
            executable.write_text("#!/bin/sh\necho started\nsleep 10\n")
            executable.chmod(0o755)
            result = runtime("task-cli", "--provider", "generic", "--executable", executable,
                             "--work-dir", root, "--prompt-file", prompt,
                             "--output-file", output, "--timeout", "0.5")
            self.assertEqual(result.returncode, 124)
            self.assertIn("started", output.read_text())


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


class MechanicalAuditContractTests(unittest.TestCase):
    def test_research_audit_adds_metadata_and_rejects_invalid_pointers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "Audit Test")
            git("config", "user.email", "audit@example.invalid")
            (root / ".gitignore").write_text(".reports/\n")
            (root / "src.py").write_text("one\ntwo\n")
            git("add", ".gitignore", "src.py")
            git("commit", "-qm", "baseline")
            base = git("rev-parse", "HEAD")
            report = root / ".reports" / "SUMMARY.md"
            report.parent.mkdir()
            report.write_text("# Findings\nInvalid location: src.py#L9\n")

            result = runtime("mechanical-audit", "--work-dir", root, "--base", base,
                             "--target", ".reports/SUMMARY.md", "--title", "[RESEARCH] inspect",
                             "--task-id", "TASK-R1", "--verify", "REPORT_ONLY")

            self.assertEqual(result.returncode, 0, result.stderr)
            audit = json.loads(result.stdout)
            self.assertEqual(audit["status"], 13)
            self.assertIn("Pointer Validity", audit["error"])
            self.assertIn("REPORT_META:", report.read_text().splitlines()[0])

    def test_research_audit_ignores_archived_reports_and_requires_current_task_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "Audit Test")
            git("config", "user.email", "audit@example.invalid")
            (root / ".gitignore").write_text(".reports/\n")
            (root / "source.py").write_text("one\n")
            git("add", ".gitignore", "source.py")
            git("commit", "-qm", "baseline")
            base = git("rev-parse", "HEAD")
            archived = root / ".reports/.archive/old/SUMMARY.md"
            archived.parent.mkdir(parents=True)
            archived.write_text("# Old report\n")

            result = runtime("mechanical-audit", "--work-dir", root, "--base", base,
                             "--target", ".reports/current/SUMMARY.md", "--title", "[RESEARCH] inspect",
                             "--task-id", "TASK-NEW", "--verify", "REPORT_ONLY")
            self.assertEqual(json.loads(result.stdout)["status"], 11)

            report = root / ".reports/current/SUMMARY.md"
            report.parent.mkdir()
            report.write_text("<!-- REPORT_META: Task=TASK-OLD | Commit=abc | Time=now -->\n# Old report\n")
            result = runtime("mechanical-audit", "--work-dir", root, "--base", base,
                             "--target", ".reports/current/SUMMARY.md", "--title", "[RESEARCH] inspect",
                             "--task-id", "TASK-NEW", "--verify", "REPORT_ONLY")
            audit = json.loads(result.stdout)
            self.assertEqual(audit["status"], 11)
            self.assertIn("Stale", audit["error"])

    def test_research_report_discovery_only_uses_declared_reports_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / ".reports/.archive/old/SUMMARY.md"
            old.parent.mkdir(parents=True)
            old.write_text("# Archived\n")
            tree = root / ".worker-tree"
            current = tree / ".reports/current/SUMMARY.md"
            current.parent.mkdir(parents=True)
            current.write_text("# Current\n")

            self.assertEqual(first_report(tree, ".reports/current/SUMMARY.md"), current.resolve())
            self.assertIsNone(first_report(tree, "docs/research/"))
            publish_research_reports(root, tree, ".reports/current/SUMMARY.md")
            self.assertEqual((root / ".reports/current/SUMMARY.md").read_text(), "# Current\n")

    def test_code_verification_timeout_is_a_guard_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "Audit Test")
            git("config", "user.email", "audit@example.invalid")
            (root / "source.txt").write_text("baseline\n")
            git("add", "source.txt")
            git("commit", "-qm", "baseline")
            base = git("rev-parse", "HEAD")

            result = runtime("mechanical-audit", "--work-dir", root, "--base", base,
                             "--target", "source.txt", "--title", "[CODE: FIX] verify",
                             "--task-id", "TASK-C1", "--verify", "sleep 10",
                             "--verify-timeout", "0.1")

            self.assertEqual(result.returncode, 0, result.stderr)
            audit = json.loads(result.stdout)
            self.assertEqual(audit["status"], 6)
            self.assertEqual(audit["verify_exit"], 124)


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
            self.assertTrue((tree / ".reports").is_dir())
            self.assertFalse((tree / ".reports").is_symlink())
            git_dir = subprocess.run(["git", "-C", str(tree), "rev-parse", "--git-path", "ORIG_HEAD"],
                                     check=True, capture_output=True, text=True).stdout.strip()
            orig_head = tree / git_dir
            original_metadata = (orig_head.read_bytes(), orig_head.stat().st_mtime_ns) if orig_head.exists() else None
            self.assertEqual(runtime("ensure-worktree", "--root", root).returncode, 0)
            updated_metadata = (orig_head.read_bytes(), orig_head.stat().st_mtime_ns) if orig_head.exists() else None
            self.assertEqual(updated_metadata, original_metadata,
                             "an identical HEAD must not run git merge and rewrite ORIG_HEAD")

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


class ReportArchiveContractTests(unittest.TestCase):
    def test_research_archive_moves_active_reports_but_keeps_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            reports = root / ".reports"
            (reports / "one").mkdir(parents=True)
            (reports / ".archive").mkdir()
            (reports / "one" / "SUMMARY.md").write_text("research")
            (reports / ".archive" / "old").write_text("old")

            result = runtime("archive-reports", "--root", root)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((reports / "one").exists())
            self.assertEqual(len(list((reports / ".archive").iterdir())), 2)

    def test_changed_report_reference_is_archived_without_moving_unrelated_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "Archive Test")
            git("config", "user.email", "archive@example.invalid")
            (root / "src").mkdir()
            (root / "src/a.py").write_text("before\n")
            git("add", "src/a.py")
            git("commit", "-qm", "baseline")
            base = git("rev-parse", "HEAD")
            (root / "src/a.py").write_text("after\n")
            git("commit", "-qam", "change")
            reports = root / ".reports"
            (reports / "related").mkdir(parents=True)
            (reports / "unrelated").mkdir()
            (reports / "related" / "SUMMARY.md").write_text("Findings in src/a.py")
            (reports / "unrelated" / "SUMMARY.md").write_text("Findings in src/b.py")

            result = runtime("archive-overlapping-reports", "--root", root,
                             "--work-dir", root, "--base", base)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((reports / "related").exists())
            self.assertTrue((reports / "unrelated").exists())


class RollbackContractTests(unittest.TestCase):
    def test_failed_workspace_changes_are_saved_and_runtime_files_survive_restore(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            def git(*args):
                return subprocess.run(["git", "-C", str(root), *args], check=True,
                                      capture_output=True, text=True).stdout.strip()
            git("config", "user.name", "Rollback Test")
            git("config", "user.email", "rollback@example.invalid")
            (root / "source.txt").write_text("baseline\n")
            (root / "tasks.txt").write_text("baseline queue\n")
            git("add", "source.txt", "tasks.txt")
            git("commit", "-qm", "baseline")
            (root / "source.txt").write_text("failed edit\n")
            (root / "tasks.txt").write_text("remaining task\n")
            (root / "new.txt").write_text("untracked work\n")

            result = runtime("rollback-failed-task", "--root", root,
                             "--work-dir", root, "--task-id", "TASK-9",
                             "--tasks", root / "tasks.txt")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / "source.txt").read_text(), "baseline\n")
            self.assertEqual((root / "tasks.txt").read_text(), "remaining task\n")
            self.assertFalse((root / "new.txt").exists())
            backup = Path(result.stdout.strip())
            self.assertEqual((backup / "untracked/new.txt").read_text(), "untracked work\n")
            self.assertIn("source.txt", (backup / "changes.diff").read_text())
            self.assertIn("?? new.txt", (backup / "status.txt").read_text())


class WorkerIntegrationTests(unittest.TestCase):
    def test_worker_rejects_zero_exit_when_final_response_says_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            shutil.copy2(RUNTIME, root / "scripts/worker_runtime.py")
            (root / ".worker.env").write_text(
                "WORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0\n"
            )
            task = "TASK-BLOCKED | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: FIX] Stop blocked | VERIFY: true\n"
            (root / "tasks.txt").write_text(task)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "worker@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "worker.sh", "scripts/worker_runtime.py", ".gitignore", "tasks.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "codex"
            fake.write_text(
                "#!/bin/sh\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = --output-last-message ]; then shift; result=$1; fi\n"
                "  shift\n"
                "done\n"
                "printf '[BLOCKED] reports-not-writable\\n' > \"$result\"\n"
            )
            fake.chmod(0o755)

            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                    env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
                                    capture_output=True, text=True, timeout=30)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("[WORKER_BLOCKED]", (root / "tasks.done").read_text())
            self.assertNotIn("[DONE]", (root / "tasks.done").read_text())
            self.assertIn("Worker final response contained [BLOCKED]", (root / "progress.log").read_text())
            self.assertEqual(json.loads((root / "worker.status").read_text())["state"], "BLOCKED")

    def test_isolated_research_task_publishes_only_its_new_report_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            shutil.copy2(RUNTIME, root / "scripts/worker_runtime.py")
            (root / ".worker.env").write_text(
                "WORKER_ISOLATION=1\nRUN_ONCE=1\nPOLL_INTERVAL=0\n"
            )
            (root / "tasks.txt").write_text(
                "TASK-REPORT | LEVEL: 1 | TARGET: .reports/fake/SUMMARY.md,.reports/fake/03-micro.md | "
                "ACTION: [RESEARCH] Produce fake report | VERIFY: REPORT_ONLY\n"
            )
            (root / ".reports/.archive/old").mkdir(parents=True)
            (root / ".reports/.archive/old/SUMMARY.md").write_text("# Archived\n")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "worker@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "worker.sh", "scripts/worker_runtime.py", ".gitignore", "tasks.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "codex"
            fake.write_text(
                "#!/bin/sh\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = --output-last-message ]; then shift; result=$1; fi\n"
                "  shift\n"
                "done\n"
                "mkdir -p .reports/fake\n"
                "printf '# Fresh summary\\n' > .reports/fake/SUMMARY.md\n"
                "printf '# Fresh details\\n' > .reports/fake/03-micro.md\n"
                "printf 'Attempts: 1 | Confidence: HIGH\\n' > \"$result\"\n"
            )
            fake.chmod(0o755)

            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                    env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
                                    capture_output=True, text=True, timeout=45)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("[DONE] TASK-REPORT", (root / "tasks.done").read_text())
            self.assertIn("[MECHANICAL_AUDIT] Status: PASS | Task: TASK-REPORT",
                          (root / "progress.log").read_text())
            summary = root / ".reports/fake/SUMMARY.md"
            self.assertIn("Task=TASK-REPORT", summary.read_text().splitlines()[0])
            self.assertEqual((root / ".reports/fake/03-micro.md").read_text(), "# Fresh details\n")
            self.assertFalse((root / ".worker-tree/.reports").is_symlink())
            self.assertTrue(list((root / ".reports/.archive").iterdir()))

    def test_worker_switches_to_next_registered_agent_after_quota_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            shutil.copy2(ROOT / "scripts/worker_runtime.py", root / "scripts/worker_runtime.py")
            profiles = [
                {"id": "primary", "provider": "codex", "command": "codex", "model": "gpt-6-luna"},
                {"id": "backup", "provider": "codex", "command": "codex", "model": "gpt-6.1-sol"},
            ]
            (root / ".worker.env").write_text(
                "WORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0\n"
                "AI_AGENTS_JSON='" + json.dumps(profiles) + "'\n"
            )
            (root / "tasks.txt").write_text(
                "TASK-Q | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: EXPAND] "
                "Write output | VERIFY: test -f output.txt\n"
            )
            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "codex"
            fake.write_text(
                "#!/bin/sh\n"
                "model=\nwhile [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = --model ]; then shift; model=$1; fi\n"
                "  if [ \"$1\" = --output-last-message ]; then shift; result=$1; fi\n"
                "  shift\ndone\n"
                "printf '%s\\n' \"$model\" >> \"$AGENT_CALLS\"\n"
                "if [ \"$model\" = gpt-6-luna ]; then echo 'Error: insufficient_quota'; exit 1; fi\n"
                "printf 'Attempts: 1 | Confidence: HIGH\\n' > \"$result\"\n"
                "printf 'hello\\n' > output.txt\n"
            )
            fake.chmod(0o755)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "worker@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "worker.sh", "scripts/worker_runtime.py", ".gitignore", "tasks.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            calls = Path(directory) / "agent-calls.log"
            env = os.environ.copy()
            env.update(PATH=f"{bin_dir}{os.pathsep}{env['PATH']}", AGENT_CALLS=str(calls))

            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=45)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(calls.read_text().splitlines(), ["gpt-6-luna", "gpt-6.1-sol"])
            self.assertIn("[DONE]", (root / "tasks.done").read_text(),
                          (root / "progress.log").read_text())
            self.assertEqual((root / "output.txt").read_text(), "hello\n")
            state = json.loads((root / ".worker-agent-state.default.json").read_text())
            self.assertEqual(state["exhausted"]["primary"]["reason"], "quota")

    def test_worker_requeues_task_and_stops_when_all_registered_agents_are_exhausted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            shutil.copy2(ROOT / "scripts/worker_runtime.py", root / "scripts/worker_runtime.py")
            task = ("TASK-Q | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: EXPAND] "
                    "Write output | VERIFY: test -f output.txt\n")
            profiles = [{"id": "one", "provider": "codex", "command": "codex"},
                        {"id": "two", "provider": "codex", "command": "codex"}]
            (root / ".worker.env").write_text(
                "WORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0\n"
                "AI_AGENTS_JSON='" + json.dumps(profiles) + "'\n"
            )
            (root / "tasks.txt").write_text(task)
            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "codex"
            fake.write_text("#!/bin/sh\necho 'rate limit exceeded'; exit 1\n")
            fake.chmod(0o755)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "worker@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "worker.sh", "scripts/worker_runtime.py", ".gitignore", "tasks.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                    env={**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"},
                                    capture_output=True, text=True, timeout=45)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((root / "tasks.txt").read_text(), task)
            self.assertEqual((root / "tasks.done").read_text(), "")
            self.assertIn("QUOTA_EXHAUSTED", result.stdout)
            self.assertEqual(json.loads((root / "worker.status").read_text())["state"], "QUOTA_EXHAUSTED")
            self.assertEqual(set(json.loads((root / ".worker-agent-state.default.json").read_text())["exhausted"]), {"one", "two"})

    def test_worker_does_not_switch_agents_for_non_quota_cli_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            shutil.copy2(ROOT / "scripts/worker_runtime.py", root / "scripts/worker_runtime.py")
            profiles = [{"id": "primary", "provider": "codex", "command": "codex"},
                        {"id": "backup", "provider": "codex", "command": "codex"}]
            (root / ".worker.env").write_text(
                "WORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0\n"
                "AI_AGENTS_JSON='" + json.dumps(profiles) + "'\n"
            )
            (root / "tasks.txt").write_text("TASK-E | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: EXPAND] Fail | VERIFY: true\n")
            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "codex"
            fake.write_text("#!/bin/sh\necho 'network unavailable'; exit 1\n")
            fake.chmod(0o755)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "worker@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "worker.sh", "scripts/worker_runtime.py", ".gitignore", "tasks.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            calls = Path(directory) / "calls.log"
            env = {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "AGENT_CALLS": str(calls)}
            fake.write_text("#!/bin/sh\necho called >> \"$AGENT_CALLS\"\necho 'network unavailable'; exit 1\n")

            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=45)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(calls.read_text().splitlines(), ["called"])
            self.assertFalse((root / ".worker-agent-state.default.json").exists())

    def test_status_dashboard_uses_project_paths_from_an_external_cwd(self):
        with tempfile.TemporaryDirectory() as directory:
            external = Path(directory)
            root = external / "repo"
            (root / "scripts").mkdir(parents=True)
            shutil.copy2(ROOT / "scripts/status.sh", root / "scripts/status.sh")
            (root / "scripts").mkdir(exist_ok=True)
            shutil.copy2(ROOT / "scripts/worker_runtime.py", root / "scripts/worker_runtime.py")
            (root / ".worker.env").write_text(
                "STATUS_FILE=state/worker.json\nTASKS_FILE=queue/tasks.txt\n"
                "TASKS_DONE_FILE=queue/tasks.done\nPROGRESS_FILE=queue/progress.log\n"
            )
            (root / "state").mkdir()
            (root / "queue").mkdir()
            (root / "state/worker.json").write_text(json.dumps({
                "state": "IDLE", "pid": -1, "elapsed_seconds": 0,
                "progress": {"bar": "[###]"}, "isolation": False,
            }))
            (root / "queue/tasks.txt").write_text("TASK-1\n")
            (root / "queue/tasks.done").write_text("[DONE] TASK-0\n[DONE] TASK-9\n")
            (root / "queue/progress.log").write_text("latest verified entry\n")
            (root / ".preview").mkdir()
            (root / ".preview/version.json").write_text(json.dumps({
                "task_id": "TASK-0", "commit": "abc123", "updated_at": "now",
            }))
            subprocess.run(["git", "init", "-q", str(root)], check=True)

            result = subprocess.run(["bash", str(root / "scripts/status.sh")], cwd=external,
                                    capture_output=True, text=True, timeout=10)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Worker State   : IDLE", result.stdout)
            self.assertIn("Completed: 2 | Remaining in Queue: 1", result.stdout)
            self.assertIn("TASK-0 (abc123) updated at now", result.stdout)

    def test_sentinel_does_not_treat_historical_pass_as_new_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            external = Path(directory)
            root = external / "repo"
            (root / "scripts").mkdir(parents=True)
            shutil.copy2(ROOT / "scripts/watch_worker.sh", root / "scripts/watch_worker.sh")
            (root / ".worker.env").write_text(
                "TASKS_FILE=queue/tasks.txt\n"
                "TASKS_DONE_FILE=queue/tasks.done\n"
                "STATUS_FILE=queue/worker.json\nPROGRESS_FILE=queue/progress.log\n"
            )
            (root / "queue").mkdir()
            (root / "queue/tasks.txt").write_text("")
            (root / "queue/tasks.done").write_text("[DONE] TASK-0\n")
            (root / "queue/progress.log").write_text("[MECHANICAL_AUDIT] Status: PASS\n")
            (root / "queue/worker.json").write_text(json.dumps({"state": "STOPPED"}))

            result = subprocess.run(["bash", str(root / "scripts/watch_worker.sh"), "1", "0.01"],
                                    cwd=external, capture_output=True, text=True, timeout=5)

            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("[SENTINEL_TIMEOUT]", result.stdout)
            self.assertNotIn("[SENTINEL_COMPLETED]", result.stdout)

    def test_sentinel_requires_a_fresh_task_scoped_audit_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            (root / "scripts").mkdir(parents=True)
            (root / "queue").mkdir()
            shutil.copy2(ROOT / "scripts/watch_worker.sh", root / "scripts/watch_worker.sh")
            (root / ".worker.env").write_text(
                "TASKS_FILE=queue/tasks.txt\nTASKS_DONE_FILE=queue/tasks.done\n"
                "STATUS_FILE=queue/worker.json\nPROGRESS_FILE=queue/progress.log\n"
            )
            (root / "queue/tasks.txt").write_text("")
            (root / "queue/tasks.done").write_text("[DONE] TASK-OLD\n")
            (root / "queue/progress.log").write_text(
                "[MECHANICAL_AUDIT] Status: PASS | Task: TASK-OLD |\n"
            )
            (root / "queue/worker.json").write_text(json.dumps({"state": "STOPPED"}))
            completion = (
                "sleep 0.05; printf 'TASK-NEW | LEVEL: 1\\n' > queue/tasks.txt; "
                "sleep 0.10; : > queue/tasks.txt; "
                "printf '[2026-01-01] [DONE] TASK-NEW\\n' >> queue/tasks.done; "
                "printf '[MECHANICAL_AUDIT] Status: PASS | Task: TASK-NEW | Verify_Exit: 0\\n' >> queue/progress.log; "
                "printf '{\\\"state\\\":\\\"IDLE\\\"}\\n' > queue/worker.json"
            )
            completer = subprocess.Popen(["bash", "-c", completion], cwd=root,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            result = subprocess.run(
                ["bash", str(root / "scripts/watch_worker.sh"), "1", "0.01"],
                cwd=root, capture_output=True, text=True, timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("TASK-NEW", result.stdout)
            self.assertIn("[SENTINEL_COMPLETED]", result.stdout)
            completer.wait(timeout=5)

    def test_sentinel_reports_fresh_task_failure_even_when_old_pass_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            (root / "scripts").mkdir(parents=True)
            (root / "queue").mkdir()
            shutil.copy2(ROOT / "scripts/watch_worker.sh", root / "scripts/watch_worker.sh")
            (root / ".worker.env").write_text(
                "TASKS_FILE=queue/tasks.txt\nTASKS_DONE_FILE=queue/tasks.done\n"
                "STATUS_FILE=queue/worker.json\nPROGRESS_FILE=queue/progress.log\n"
            )
            (root / "queue/tasks.txt").write_text("")
            (root / "queue/tasks.done").write_text("[DONE] TASK-RETRY\n")
            (root / "queue/progress.log").write_text(
                "[MECHANICAL_AUDIT] Status: PASS | Task: TASK-RETRY | Verify_Exit: 0 | Attempts: 1\n"
            )
            (root / "queue/worker.json").write_text(json.dumps({"state": "STOPPED"}))
            completion = (
                "sleep 0.05; printf '[2026-01-01] [FAILED] TASK-RETRY [EXIT_1]\\n' >> queue/tasks.done"
            )
            completer = subprocess.Popen(["bash", "-c", completion], cwd=root,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            result = subprocess.run(
                ["bash", str(root / "scripts/watch_worker.sh"), "1", "0.01", "TASK-RETRY"],
                cwd=root, capture_output=True, text=True, timeout=10,
            )

            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("[SENTINEL_FAILED] Task TASK-RETRY", result.stdout)
            completer.wait(timeout=5)

    def test_sentinel_rejects_old_same_task_audit_for_a_new_done_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            (root / "scripts").mkdir(parents=True)
            (root / "queue").mkdir()
            shutil.copy2(ROOT / "scripts/watch_worker.sh", root / "scripts/watch_worker.sh")
            (root / ".worker.env").write_text(
                "TASKS_FILE=queue/tasks.txt\nTASKS_DONE_FILE=queue/tasks.done\n"
                "STATUS_FILE=queue/worker.json\nPROGRESS_FILE=queue/progress.log\n"
            )
            (root / "queue/tasks.txt").write_text("TASK-RETRY | LEVEL: 1\n")
            (root / "queue/tasks.done").write_text("[FAILED] TASK-RETRY [EXIT_1]\n")
            (root / "queue/progress.log").write_text(
                "[MECHANICAL_AUDIT] Status: PASS | Task: TASK-RETRY | Verify_Exit: 0 | Attempts: 1\n"
            )
            (root / "queue/worker.json").write_text(json.dumps({"state": "IDLE"}))
            completion = (
                "sleep 0.05; : > queue/tasks.txt; "
                "printf '[2026-01-01] [DONE] TASK-RETRY\\n' >> queue/tasks.done; "
                "printf '{\\\"state\\\":\\\"IDLE\\\"}\\n' > queue/worker.json"
            )
            completer = subprocess.Popen(["bash", "-c", completion], cwd=root,
                                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            result = subprocess.run(
                ["bash", str(root / "scripts/watch_worker.sh"), "1", "0.01", "TASK-RETRY"],
                cwd=root, capture_output=True, text=True, timeout=5,
            )

            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("[SENTINEL_TIMEOUT]", result.stdout)
            self.assertNotIn("[SENTINEL_COMPLETED]", result.stdout)
            completer.wait(timeout=5)

    def test_launcher_runs_python_daemon_and_cleans_pid_when_run_once_queue_is_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            shutil.copy2(ROOT / "scripts/worker_runtime.py", root / "scripts/worker_runtime.py")
            (root / ".worker.env").write_text(
                "WORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0.01\nAI_CLI=codex\n"
            )
            (root / "tasks.txt").write_text("# no tasks\n")
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "worker@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "worker.sh", "scripts/worker_runtime.py", ".gitignore", "tasks.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)

            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                    capture_output=True, text=True, timeout=30)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("RUN_ONCE", result.stdout)
            self.assertEqual(json.loads((root / "worker.status").read_text())["state"], "STOPPED")
            self.assertFalse((root / ".worker.pid").exists())

    def test_launcher_refuses_a_live_pid_without_touching_runtime_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            shutil.copy2(ROOT / "scripts/worker_runtime.py", root / "scripts/worker_runtime.py")
            (root / ".worker.env").write_text("WORKER_ISOLATION=0\n")
            pid_file = root / ".worker.pid"
            pid_file.write_text(f"{os.getpid()}\n")

            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                    capture_output=True, text=True, timeout=10)

            self.assertEqual(result.returncode, 1)
            self.assertIn("already running", result.stderr)
            self.assertEqual(pid_file.read_text(), f"{os.getpid()}\n")
            self.assertFalse((root / "tasks.txt").exists())

    def test_timed_out_task_is_recorded_and_dirty_workspace_is_preserved_then_rolled_back(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            shutil.copy2(ROOT / "scripts/worker_runtime.py", root / "scripts/worker_runtime.py")
            (root / ".worker.env").write_text(
                "AI_CLI=codex\nWORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0\nTASK_TIMEOUT=0.5\n"
                "WORKER_SCORE_FILE=.worker-score-test.json\n"
            )
            (root / "output.txt").write_text("baseline\n")
            (root / "tasks.txt").write_text(
                "TASK-T | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: FIX] Timeout test | VERIFY: true\n"
            )
            bin_dir = Path(directory) / "bin"
            bin_dir.mkdir()
            fake = bin_dir / "codex"
            fake.write_text(
                "#!/bin/sh\nprintf 'partial\\n' > output.txt\n"
                "printf 'started\\n'\n"
                "sleep 10\n"
            )
            fake.chmod(0o755)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Worker Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "worker@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "add", "worker.sh", "scripts/worker_runtime.py", ".gitignore", "output.txt", "tasks.txt"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"

            result = subprocess.run(["bash", str(root / "worker.sh")], cwd=root,
                                    env=env, capture_output=True, text=True, timeout=20)

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((root / "output.txt").read_text(), "baseline\n")
            self.assertIn("[FAILED]", (root / "tasks.done").read_text())
            self.assertIn("[TIMEOUT]", (root / "tasks.done").read_text())
            backups = list((root / ".scratch/failed_tasks").glob("TASK-T_*/changes.diff"))
            self.assertEqual(len(backups), 1)
            self.assertIn("partial", backups[0].read_text())
            self.assertFalse((root / ".worker.pid").exists())
            score = json.loads((root / ".worker-score-test.json").read_text())
            self.assertEqual(score["failures"]["TASK-T"], 1)
            self.assertEqual(score["score"], 5)

    def test_codex_task_keeps_queue_status_commit_and_guard_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for name in ("worker.sh", ".gitignore"):
                shutil.copy2(ROOT / name, root / name)
            (root / "scripts").mkdir()
            shutil.copy2(ROOT / "scripts/worker_runtime.py", root / "scripts/worker_runtime.py")
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
            git("add", "worker.sh", "scripts/worker_runtime.py", ".gitignore", "tasks.txt")
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
            (target / ".agents").mkdir()
            skills_manifest = target / ".agents/skills.json"
            skills_manifest.write_text('{"entries":[{"path":"custom/skills"}]}\n')
            result = subprocess.run(["bash", str(ROOT / "install.sh"), str(target)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(skills_manifest.read_text(), '{"entries":[{"path":"custom/skills"}]}\n')
            deployed_runtime = target / "scripts/worker_runtime.py"
            self.assertEqual(deployed_runtime.read_bytes(), (ROOT / "scripts/worker_runtime.py").read_bytes())
            operations = target / ".agents/skills/nightshift/planner/OPERATIONS.md"
            self.assertFalse(operations.exists())
            operations.parent.mkdir(parents=True, exist_ok=True)
            operations.write_text("stale planner instructions\n")
            self.assertFalse((target / "worker_runtime.py").exists())
            self.assertTrue((target / "test/nightshift_worker/test_worker_runtime.py").is_file())
            self.assertTrue((target / "test/nightshift_worker/README.md").is_file())
            self.assertTrue((target / ".worker.env").is_file())
            self.assertIn(".worker-agent-state*.json", (target / ".gitignore").read_text())
            self.assertIn(".worker-score*.json", (target / ".gitignore").read_text())
            self.assertIn(".worker-score*.json.lock/", (target / ".gitignore").read_text())
            (target / ".worker.env").write_text("AI_CLI=agy\nCUSTOM_SETTING=preserve\n")
            deployed_runtime.write_text("stale runtime\n")
            update = subprocess.run(["bash", str(ROOT / "install.sh"), str(target)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=30)
            self.assertEqual(update.returncode, 0, update.stdout + update.stderr)
            self.assertIn("Deployed scripts/worker_runtime.py", update.stdout)
            self.assertEqual(deployed_runtime.read_bytes(), (ROOT / "scripts/worker_runtime.py").read_bytes())
            self.assertFalse(operations.exists(), "updates must remove retired skill sidecars")
            planner_skill = (target / ".agents/skills/nightshift/planner/SKILL.md").read_text()
            worker_contract = (target / ".skills/universal-build-verify.md").read_text()
            self.assertNotIn("OPERATIONS.md", planner_skill + worker_contract)
            self.assertIn("full discovered graph", planner_skill)
            self.assertEqual((target / ".worker.env").read_text(), "AI_CLI=agy\nCUSTOM_SETTING=preserve\n")
            self.assertEqual(deployed_runtime.read_bytes(), (ROOT / "scripts/worker_runtime.py").read_bytes())
            installed = subprocess.run(
                [sys.executable, "-m", "unittest", "discover", "-s", "test", "-v"],
                cwd=target, capture_output=True, text=True, timeout=45,
            )
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)

    @unittest.skipUnless((ROOT / "install.sh").exists(), "source checkout only")
    def test_installer_resolves_symlink_target_before_self_install_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            alias = Path(directory) / "nightshift-alias"
            alias.symlink_to(ROOT, target_is_directory=True)
            result = subprocess.run(["bash", str(ROOT / "install.sh"), str(alias)],
                                    cwd=ROOT, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Cannot install/update NightShift into its own source directory.", result.stdout)


if __name__ == "__main__":
    unittest.main()
