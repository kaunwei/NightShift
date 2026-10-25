"""Exercise no_response and failure classification through each built-in adapter's public protocol."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class AdapterDiagnosticsTests(unittest.TestCase):
    def run_adapter(self, adapter, output, exit_code):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / 'fake-agent'
            fake.write_text(
                '#!/usr/bin/env python3\nimport json,os,sys\nfrom pathlib import Path\n'
                'if "--help" in sys.argv: print("fixture help"); sys.exit(0)\n'
                'reply=json.dumps({"outcome":"complete","changed":False,"no_change_reason":"fixture"})\n'
                'if "--output-last-message" in sys.argv:\n'
                ' Path(sys.argv[sys.argv.index("--output-last-message")+1]).write_text(reply)\n'
                'print(os.environ["FIXTURE_OUTPUT"],flush=True)\n'
                'print(reply,flush=True)\n'
                'sys.exit(int(os.environ["FIXTURE_EXIT"]))\n')
            fake.chmod(0o755)
            (root / 'prompt').write_text('Protocol fixture; no project changes.')

            def callback(name, request):
                response = subprocess.run(
                    [sys.executable, str(ROOT / 'scripts/adapters' / f'{adapter}.py'), name],
                    input=json.dumps({'protocol_version': 1, **request}),
                    text=True, capture_output=True, timeout=10)
                self.assertEqual(response.returncode, 0, response.stderr)
                return json.loads(response.stdout)

            config = callback('get_config', {'overrides': {'command': str(fake)}})
            handle = callback('start', {
                'configuration': config['configuration'], 'working_directory': str(root),
                'prompt_path': str(root / 'prompt'), 'output_dir': str(root / 'output'),
                'result_path': str(root / 'result'), 'limits': {'action_limit': 100},
                'environment': {'FIXTURE_OUTPUT': output, 'FIXTURE_EXIT': str(exit_code)}})
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                status = callback('status', handle)
                if status['status'] != 'running':
                    return status, json.loads((root / 'result').read_text())
                time.sleep(.02)
            self.fail(f'{adapter} did not finish the fixture')

    def test_unexpected_stop_without_actions_is_no_response(self):
        for adapter in ('codex', 'agy'):
            for output in ('Error: connection reset', 'unexpected stop',
                           'Error: insufficient_quota', 'rate limit exceeded',
                           'RESOURCE_EXHAUSTED code 429', 'out of credits',
                           'You’ve hit your usage limit. Upgrade to Pro',
                           'You\'ve hit your usage limit.',
                           'usage limit exceeded', 'Error: usage limit reached', 'quota exceeded'):
                with self.subTest(adapter=adapter, output=output):
                    status, payload = self.run_adapter(adapter, output, 1)
                    self.assertEqual(status['status'], 'no_response')
                    self.assertEqual(payload['outcome'], 'no_response')

    def test_recovered_error_preserves_successful_final_result(self):
        for adapter in ('codex', 'agy'):
            for event in ({'type': 'error', 'message': 'rate limit exceeded'},
                          {'type': 'turn.failed', 'error': {'message': 'insufficient_quota'}}):
                with self.subTest(adapter=adapter, event=event):
                    status, payload = self.run_adapter(adapter, json.dumps(event), 0)
                    self.assertEqual(status['status'], 'complete')
                    self.assertEqual(payload['outcome'], 'complete')

    def test_command_execution_failure_is_failed_not_no_response(self):
        for adapter in ('codex', 'agy'):
            for output in (
                json.dumps({'type': 'item.completed', 'item': {
                    'type': 'command_execution', 'aggregated_output': 'Error: build failed HTTP 429'}}),
                json.dumps({'type': 'item.completed', 'item': {
                    'type': 'command_execution', 'aggregated_output': 'Expected: 4294967168'}}),
                json.dumps({'type': 'item.completed', 'item': {
                    'type': 'command_execution', 'aggregated_output': 'Test fixture mentions rate limit exceeded and error'}})):
                with self.subTest(adapter=adapter, output=output):
                    status, payload = self.run_adapter(adapter, output, 1)
                    self.assertEqual(status['status'], 'failed')
                    self.assertEqual(payload['outcome'], 'failure')


if __name__ == '__main__':
    unittest.main()
