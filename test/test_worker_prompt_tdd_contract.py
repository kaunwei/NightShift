"""Generated handoffs must explain canonical permanent-hot discovery identities."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import worker_runtime


class WorkerPromptTDDContractTests(unittest.TestCase):
    def test_prompt_requires_discovered_case_identity_and_changed_behavior(self):
        prompt = worker_runtime.build_task_prompt(
            'TASK-X | ACTION: fix behavior', 'TASK-X', '2', 'src,test',
            'python3 -m unittest discover -s test', '', '', 40, 2, 40, 0, '/runner/progress.log')
        self.assertIn('unittest.TestLoader().discover("test")', prompt)
        self.assertIn('test.id()', prompt)
        self.assertIn('inspect.getfile(type(test))', prompt)
        self.assertIn('Do not prepend `test.`', prompt)
        self.assertIn('Only new or meaningfully modified behavior cases', prompt)
        self.assertIn('nonempty `tdd_cases`', prompt)
