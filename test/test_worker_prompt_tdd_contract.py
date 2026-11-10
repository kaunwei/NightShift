"""Generated handoffs must explain canonical permanent-hot discovery identities."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import worker_runtime


class WorkerPromptTDDContractTests(unittest.TestCase):
    def test_fix_and_bounded_research_prompts_match_supported_contracts(self):
        prompt = worker_runtime.build_task_prompt(
            'TASK-X [CODE: FIX] | ACTION: fix behavior', 'TASK-X', '2', 'src,test',
            'test command', '', '', 40, 2, 40, 0, '/runner/progress.log')
        self.assertIn('may add or strengthen regression tests in TARGET', prompt)
        self.assertIn('preserve existing assertion strength/count', prompt)
        self.assertNotIn('[CODE: FIX] must not change tests', prompt)
        research = worker_runtime.build_task_prompt(
            'TASK-R [RESEARCH] | ACTION: bounded reproduction', 'TASK-R', '2', '.reports/r',
            'REPORT_ONLY', '', '', 100, 1, 40, 0, '/runner/progress.log')
        self.assertIn('research_conclusion=positive|negative|inconclusive', research)
        self.assertIn('Missing evidence or invalid method remains blocked', research)

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
