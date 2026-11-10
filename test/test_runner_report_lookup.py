import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from worker_runtime import first_report

class RunnerReportLookupTests(unittest.TestCase):
    def test_only_selected_runner_reports_and_local_reports_are_allowed(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp); root=base/'project'; root.mkdir()
            runner=base/'runner'; selected=runner/'reports'/'probe'; selected.mkdir(parents=True)
            summary=selected/'SUMMARY.md'; summary.write_text('# Research\n')
            outside=base/'outside'; outside.mkdir(); (outside/'SUMMARY.md').write_text('# Outside\n')
            local=root/'.reports'/'local'; local.mkdir(parents=True); (local/'SUMMARY.md').write_text('# Local\n')
            with patch.dict(os.environ, {'NIGHTSHIFT_STATE_DIR':str(runner)}):
                self.assertEqual(first_report(root,str(selected)),summary.resolve())
                self.assertEqual(first_report(root,str(summary)),summary.resolve())
                self.assertEqual(first_report(root,'.reports/local'),(local/'SUMMARY.md').resolve())
                self.assertIsNone(first_report(root,str(outside)))
                indirect=runner/'reports'/'indirect'; indirect.mkdir()
                (indirect/'SUMMARY.md').symlink_to(outside/'SUMMARY.md')
                self.assertIsNone(first_report(root,str(indirect)))
                (runner/'reports'/'escape').symlink_to(outside,target_is_directory=True)
                self.assertIsNone(first_report(root,str(runner/'reports'/'escape')))
            with patch.dict(os.environ,{},clear=True):
                self.assertIsNone(first_report(root,str(selected)))
