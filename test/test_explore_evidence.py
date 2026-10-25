import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = next(parent for parent in Path(__file__).resolve().parents
            if (parent / "scripts" / "adapters").is_dir())
sys.path.insert(0, str(ROOT / "scripts" / "adapters"))

from explore_evidence import append_ledger, build_static_evidence, render_static_report
from aider_explore import normalize_source_paths, source_pointers


class StaticEvidenceTests(unittest.TestCase):
    def test_indexes_imports_and_unique_local_callers_with_exact_lines(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "pkg").mkdir()
            (root / "pkg" / "worker.py").write_text(
                "from pkg.adapter import start\n\n"
                "def dispatch():\n"
                "    return start()\n", encoding="utf-8")
            (root / "pkg" / "adapter.py").write_text(
                "def start():\n"
                "    return 1\n", encoding="utf-8")

            evidence = build_static_evidence(
                root, ["pkg/worker.py", "pkg/adapter.py"], "worker adapter dispatch")

        self.assertEqual(evidence["imports"], [
            {"source": "pkg/worker.py", "line": 1, "target": "pkg/adapter.py"}
        ])
        self.assertEqual(evidence["calls"], [
            {"source": "pkg/worker.py", "line": 4, "caller": "dispatch",
             "callee": "start", "target": "pkg/adapter.py", "target_line": 1,
             "resolution": "unique-name-match"}
        ])
        self.assertIn("pkg/worker.py", evidence["selected"])
        self.assertIn("pkg/adapter.py", evidence["selected"])

    def test_ambiguous_function_names_are_not_reported_as_resolved_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "one.py").write_text("def run():\n    return 1\n", encoding="utf-8")
            (root / "two.py").write_text("def run():\n    return 2\n", encoding="utf-8")
            (root / "main.py").write_text(
                "def launch():\n    return run()\n", encoding="utf-8")

            evidence = build_static_evidence(root, ["one.py", "two.py", "main.py"], "launch run")

        self.assertEqual(evidence["calls"], [])
        self.assertEqual(evidence["unresolved_calls"], [
            {"source": "main.py", "line": 2, "caller": "launch", "callee": "run",
             "reason": "ambiguous-name", "candidates": ["one.py", "two.py"]}
        ])

    def test_evidence_records_survive_later_appends(self):
        with tempfile.TemporaryDirectory() as temp:
            ledger = Path(temp) / "trace" / "evidence.jsonl"
            append_ledger(ledger, {"path": "a.py", "sha256": "first"})
            append_ledger(ledger, {"path": "b.py", "sha256": "second"})

            records = [json.loads(line) for line in ledger.read_text().splitlines()]

        self.assertEqual(records, [
            {"path": "a.py", "sha256": "first"},
            {"path": "b.py", "sha256": "second"},
        ])

    def test_report_citations_must_land_inside_an_inspected_source_span(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "src.py").write_text("one\ntwo\nthree\nfour\n", encoding="utf-8")

            valid = source_pointers("Fact `src.py#L2`.", root, {"src.py": [(1, 2)]})
            with self.assertRaisesRegex(RuntimeError, "uninspected source line"):
                source_pointers("Fact `src.py#L4`.", root, {"src.py": [(1, 2)]})

        self.assertEqual(valid, [("src.py", 2)])

    def test_path_normalization_does_not_prefix_existing_full_citations(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            nested = root / "scripts" / "adapters"
            nested.mkdir(parents=True)
            (nested / "aider_explore.py").write_text("line\n", encoding="utf-8")
            report = "`aider_explore.py#L1` and `scripts/adapters/aider_explore.py#L1`"

            normalized = normalize_source_paths(report, root)

        self.assertEqual(normalized,
                         "`scripts/adapters/aider_explore.py#L1` and "
                         "`scripts/adapters/aider_explore.py#L1`")

    def test_static_report_is_repeatable_and_cites_only_observed_edges(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "pkg").mkdir()
            (root / "pkg" / "worker.py").write_text(
                "from pkg.adapter import start\n\n"
                "def dispatch():\n"
                "    return start()\n", encoding="utf-8")
            (root / "pkg" / "adapter.py").write_text(
                "def start():\n"
                "    return 1\n", encoding="utf-8")
            evidence = build_static_evidence(
                root, ["pkg/worker.py", "pkg/adapter.py"], "worker adapter dispatch")
            spans = {"pkg/worker.py": [(1, 4)], "pkg/adapter.py": [(1, 2)]}
            summaries = {path: "Draft model note; source-check before use." for path in spans}

            first = render_static_report(
                "TASK-1", "abc123", "Trace worker dispatch", evidence, summaries, spans)
            second = render_static_report(
                "TASK-1", "abc123", "Trace worker dispatch", evidence, summaries, spans)
            pointers = source_pointers(first, root, spans)

        self.assertEqual(first, second)
        self.assertIn("`pkg/worker.py#L1` imports `pkg/adapter.py`", first)
        self.assertIn("unique-name match only; binding is unproven", first)
        self.assertIn("model notes remain unverified", first)
        self.assertIn("Expand–Migrate–Contract Matrix", first)
        self.assertIn("Static Caller Leads", first)
        self.assertNotIn("Verified Callers", first)
        self.assertLess(len(first.encode("utf-8")), 5000)
        self.assertTrue(pointers)


if __name__ == "__main__":
    unittest.main()
