import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] if (Path(__file__).resolve().parents[1] / "worker.sh").exists() else Path(__file__).resolve().parents[2]


class StickyFailoverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        for name in ("worker.sh", ".gitignore"):
            shutil.copy2(ROOT / name, self.root / name)
        (self.root / "scripts").mkdir()
        shutil.copy2(ROOT / "scripts/worker_runtime.py", self.root / "scripts/worker_runtime.py")
        shutil.copytree(ROOT / "scripts/adapters", self.root / "scripts/adapters")

        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "Worker Test"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "worker@example.invalid"], check=True)
        (self.root / "tasks.txt").write_text("")
        subprocess.run(["git", "-C", str(self.root), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "initial"], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_sticky_agent_failover_and_reset(self):
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        calls_file = Path(self.tmp.name) / "calls.log"

        # Create fake-agent script
        fake_agent = bin_dir / "fake-agent"
        fake_agent.write_text(f"""#!/usr/bin/env python3
import json, os, sys
from pathlib import Path

agent_name = os.environ.get("AGENT_NAME", "unknown")
with open("{calls_file}", "a") as f:
    f.write(agent_name + "\\n")

# Check if this agent should fail with no_response
fail_agents = os.environ.get("FAIL_AGENTS", "").split(",")
if agent_name in fail_agents:
    # Exit with code 1 and 0 actions -> no_response
    sys.exit(1)

# Otherwise succeed
result_path = None
for i, arg in enumerate(sys.argv):
    if arg == "--output-last-message" and i + 1 < len(sys.argv):
        result_path = sys.argv[i + 1]

if result_path:
    payload = {{
        "outcome": "complete",
        "changed": True,
        "commit_message": f"feat: completed by {{agent_name}}"
    }}
    Path(result_path).write_text(json.dumps(payload))

# Make a small change to a target file
target = Path("output.txt")
target.write_text(f"done by {{agent_name}}\\n")
sys.exit(0)
""")
        fake_agent.chmod(0o755)

        # 3 registered agents: A (default), B, C
        agents_dict = {
            "agent-a": {
                "default": True,
                "agent": {
                    "adapter": "codex", "command": str(fake_agent), "args": [],
                    "env": {"AGENT_NAME": "agent-a"}, "config": {"command": str(fake_agent)}
                }
            },
            "agent-b": {
                "default": False,
                "agent": {
                    "adapter": "codex", "command": str(fake_agent), "args": [],
                    "env": {"AGENT_NAME": "agent-b"}, "config": {"command": str(fake_agent)}
                }
            },
            "agent-c": {
                "default": False,
                "agent": {
                    "adapter": "codex", "command": str(fake_agent), "args": [],
                    "env": {"AGENT_NAME": "agent-c"}, "config": {"command": str(fake_agent)}
                }
            }
        }
        (self.root / "scripts/adapters/agents.json").write_text(json.dumps(agents_dict, indent=2))

        (self.root / ".worker.env").write_text(
            "WORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0\n"
        )

        # --- Task 1: Agent A fails with no_response, Agent B succeeds ---
        (self.root / "tasks.txt").write_text(
            "TASK-001 | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: EXPAND] Write output | VERIFY: test -f output.txt\n"
        )
        env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "RUN_ONCE": "1",
            "POLL_INTERVAL": "0",
            "FAIL_AGENTS": "agent-a"
        }
        res = subprocess.run(["bash", str(self.root / "worker.sh")], cwd=self.root, env=env,
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

        # Calls should have been: agent-a (failed), then agent-b (succeeded)
        calls = calls_file.read_text().splitlines()
        self.assertEqual(calls, ["agent-a", "agent-b"])

        # Check state: active_agent_id should be agent-b, consecutive_no_response == 0
        state_file = self.root / ".worker-agent-state.default.json"
        self.assertTrue(state_file.exists())
        state = json.loads(state_file.read_text())
        self.assertEqual(state["active_agent_id"], "agent-b")
        self.assertEqual(state["consecutive_no_response"], 0)

        # --- Task 2: Starts with Agent B directly (sticky!) ---
        calls_file.unlink()
        (self.root / "tasks.txt").write_text(
            "TASK-002 | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: EXPAND] Write output | VERIFY: test -f output.txt\n"
        )
        # Note: even if agent-a is no longer failing, it should still start with agent-b!
        env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "RUN_ONCE": "1",
            "POLL_INTERVAL": "0",
            "FAIL_AGENTS": ""
        }
        res = subprocess.run(["bash", str(self.root / "worker.sh")], cwd=self.root, env=env,
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

        calls = calls_file.read_text().splitlines()
        self.assertEqual(calls, ["agent-b"])  # Agent B used directly, sticky!
        state = json.loads(state_file.read_text())
        self.assertEqual(state["active_agent_id"], "agent-b")
        self.assertEqual(state["consecutive_no_response"], 0)

        # --- Task 3: Agent B fails, switches to Agent C ---
        calls_file.unlink()
        (self.root / "tasks.txt").write_text(
            "TASK-003 | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: EXPAND] Write output | VERIFY: test -f output.txt\n"
        )
        env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "RUN_ONCE": "1",
            "POLL_INTERVAL": "0",
            "FAIL_AGENTS": "agent-b"
        }
        res = subprocess.run(["bash", str(self.root / "worker.sh")], cwd=self.root, env=env,
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

        calls = calls_file.read_text().splitlines()
        self.assertEqual(calls, ["agent-b", "agent-c"])
        state = json.loads(state_file.read_text())
        self.assertEqual(state["active_agent_id"], "agent-c")
        self.assertEqual(state["consecutive_no_response"], 0)

    def test_three_consecutive_no_response_reports_to_planner(self):
        bin_dir = Path(self.tmp.name) / "bin"
        bin_dir.mkdir()
        calls_file = Path(self.tmp.name) / "calls.log"

        fake_agent = bin_dir / "fake-agent"
        fake_agent.write_text(f"""#!/usr/bin/env python3
import os, sys
with open("{calls_file}", "a") as f:
    f.write(os.environ.get("AGENT_NAME", "unknown") + "\\n")
# All agents fail without action -> no_response
sys.exit(1)
""")
        fake_agent.chmod(0o755)

        agents_dict = {
            "agent-a": {
                "default": True,
                "agent": {
                    "adapter": "codex", "command": str(fake_agent), "args": [],
                    "env": {"AGENT_NAME": "agent-a"}, "config": {"command": str(fake_agent)}
                }
            },
            "agent-b": {
                "default": False,
                "agent": {
                    "adapter": "codex", "command": str(fake_agent), "args": [],
                    "env": {"AGENT_NAME": "agent-b"}, "config": {"command": str(fake_agent)}
                }
            },
            "agent-c": {
                "default": False,
                "agent": {
                    "adapter": "codex", "command": str(fake_agent), "args": [],
                    "env": {"AGENT_NAME": "agent-c"}, "config": {"command": str(fake_agent)}
                }
            }
        }
        (self.root / "scripts/adapters/agents.json").write_text(json.dumps(agents_dict, indent=2))

        (self.root / ".worker.env").write_text(
            "WORKER_ISOLATION=0\nRUN_ONCE=1\nPOLL_INTERVAL=0\n"
        )
        (self.root / "tasks.txt").write_text(
            "TASK-FAIL | LEVEL: 1 | TARGET: output.txt | ACTION: [CODE: EXPAND] Write output | VERIFY: test -f output.txt\n"
        )

        env = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "RUN_ONCE": "1",
            "POLL_INTERVAL": "0"
        }
        res = subprocess.run(["bash", str(self.root / "worker.sh")], cwd=self.root, env=env,
                             capture_output=True, text=True, timeout=30)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

        calls = calls_file.read_text().splitlines()
        # Exactly 3 attempts: agent-a, agent-b, agent-c
        self.assertEqual(calls, ["agent-a", "agent-b", "agent-c"])

        # Progress log should report [AGENT_NO_RESPONSE]
        progress = (self.root / "progress.log").read_text()
        self.assertIn("[AGENT_NO_RESPONSE]", progress)
        self.assertIn("agent no response", progress)

        # Worker status should show AGENT_NO_RESPONSE
        status = json.loads((self.root / "worker.status").read_text())
        self.assertEqual(status["state"], "AGENT_NO_RESPONSE")

        # Task should remain queued in tasks.txt
        self.assertIn("TASK-FAIL", (self.root / "tasks.txt").read_text())


if __name__ == "__main__":
    unittest.main()
