import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CLI = Path(__file__).resolve().parents[1] / "nightshift" / "tools" / "index.py"


class GeneralCodeIndexPublicCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.write("src/python/tracker.py", '''import math

class Tracker:
    def advance(self):
        self.stop()

    def stop(self):
        return math.floor(1.5)

example = "Tracker.stop() is documentation, not a reference"
''')
        self.write("src/javascript/tracker.js", '''import { floor } from "math-lib";
class TrackerClient {
  advance() { new Tracker(); tracker.stop(); }
}
''')
        self.write("src/typescript/tracker.ts", '''export class TrackerTS { stop() {} }
function invoke(tracker: TrackerTS) { tracker.stop(); }
''')
        self.write("src/go/tracker.go", '''package core
import "fmt"
type TrackerGo struct{}
func invoke(tracker TrackerGo) { tracker.stop(); fmt.Println("go") }
''')
        self.write("src/rust/tracker.rs", '''use std::fmt;
struct TrackerRs;
fn invoke(tracker: TrackerRs) { tracker.stop(); let _ = fmt::Debug; }
''')
        self.write("src/c/tracker.c", '''#include <stdio.h>
int c_tracker(int value) { return value; }
''')
        self.write("src/cpp/tracker.cpp", '''#include <vector>
class CppTracker { public: int advance(int value) { return value; } };
''')
        self.write("src/java/Tracker.java", '''import java.util.List;
class JavaTracker { int advance(int value) { return value; } }
''')
        self.write("src/bash/deploy.sh", '''#!/usr/bin/env bash
function deploy_tracker() { echo ready; }
deploy_tracker
''')
        self.write("src/make/Makefile", '''all: app
app: main.c
	$(CC) main.c -o app
''')
        self.write("src/cmake/CMakeLists.txt", '''project(TrackerDemo)
add_executable(tracker main.cpp)
''')
        self.write("generated/ignored.py", "class IgnoredTracker: pass\n")
        self.write("nightshift/code-index.toml", '''[project]
include = ["src/**"]
exclude = ["src/**/vendor/**"]

[scope]
tool = ["src/javascript/**"]
project = ["src/**"]
''')
        subprocess.run(["git", "-C", str(self.root), "add", "src", "generated", "nightshift"], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"],
            check=True,
        )

    def tearDown(self):
        self.temporary.cleanup()

    def write(self, name, contents):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(CLI), "--repo", str(self.root), *args],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )

    def test_refactor_call_hints_count_callees_but_not_passed_function_values(self):
        self.write("src/python/call_usage.py", "def active():\n    pass\n\ndef dormant():\n    pass\n\ndef wrapper():\n    consume(dormant)\n\nactive()\n")
        subprocess.run(["git", "-C", str(self.root), "add", "src/python/call_usage.py"], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "call usage"], check=True)
        built = self.run_cli("build")
        self.assertEqual(built.returncode, 0, built.stderr)
        for name, expected in (("active", 1), ("dormant", 0)):
            symbol = self.run_cli("query", "symbol", name)
            self.assertEqual(symbol.returncode, 0, symbol.stderr)
            self.assertEqual(json.loads(symbol.stdout)["matches"][0]["call_sites"], expected)
        callers = self.run_cli("query", "callers", "dormant")
        self.assertEqual(json.loads(callers.stdout)["matches"], [])
        references = self.run_cli("query", "references", "dormant")
        self.assertEqual(len(json.loads(references.stdout)["matches"]), 1)
        summary = Path(json.loads(built.stdout)["summary_path"]).read_text()
        self.assertNotIn("calls=", summary)
        self.assertNotIn("call_sites", Path(json.loads(built.stdout)["index_path"]).read_text())
        self.assertEqual(json.loads(references.stdout)["reference_files"], 1)

    def test_qualified_symbols_disambiguate_same_named_methods(self):
        self.write("src/python/owners.py", "class First:\n    def reset(self):\n        pass\n\nclass Second:\n    def reset(self):\n        pass\n")
        subprocess.run(["git", "-C", str(self.root), "add", "src/python/owners.py"], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "method owners"], check=True)
        symbols = self.run_cli("query", "symbol", "reset")
        self.assertEqual(symbols.returncode, 0, symbols.stderr)
        self.assertEqual({row["qualified_name"] for row in json.loads(symbols.stdout)["matches"]}, {"First.reset", "Second.reset"})
        selected = self.run_cli("query", "symbol", "First.reset")
        self.assertEqual(selected.returncode, 0, selected.stderr)
        rows = json.loads(selected.stdout)["matches"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["qualified_name"], "First.reset")
        self.assertEqual(rows[0]["kind"], "function")
        invalid = self.run_cli("query", "callers", "First.reset")
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("simple name", json.loads(invalid.stderr)["error"])
        built = json.loads(self.run_cli("build").stdout)
        summary = Path(built["summary_path"]).read_text()
        self.assertIn("class First@", summary)
        self.assertIn("function First.reset@", summary)
        self.assertNotIn("calls=", summary)

    def test_build_publishes_bounded_navigation_map_inside_nightshift(self):
        result = self.run_cli("build")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        folder = self.root.resolve() / "nightshift" / ".scratch" / "code-index"
        self.assertEqual(Path(payload["index_path"]), folder / "index.json")
        self.assertEqual(Path(payload["summary_path"]), folder / "INDEX.md")
        summary = Path(payload["summary_path"]).read_text()
        self.assertLessEqual(len(summary.encode()), 8192)
        self.assertIn(payload["revision"], summary)
        self.assertIn("src/python/tracker.py", summary)
        self.assertIn("Tracker", summary)
        self.assertIn("syntax", summary.lower())

    def test_reference_queries_keep_cache_small_and_fetch_details_on_demand(self):
        with (self.root / "src/python/tracker.py").open("a") as output:
            output.write("tracker.stop()\n" * 1000)
        subprocess.run(["git", "-C", str(self.root), "add", "src/python/tracker.py"], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "many calls"], check=True)
        result = self.run_cli("build")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertLess(Path(payload["index_path"]).stat().st_size, 30_000)
        query = self.run_cli("query", "callers", "stop", "--scope", "project", "--limit", "2")
        self.assertEqual(query.returncode, 0, query.stderr)
        details = json.loads(query.stdout)
        self.assertEqual(len(details["matches"]), 2)
        self.assertTrue(details["truncated"])
        self.assertGreaterEqual(details["omitted"], 998)

    def test_large_navigation_map_reports_omitted_files_within_byte_budget(self):
        for number in range(120):
            self.write(f"src/python/{number:03d}_long_module_name_for_navigation_budget_abcdefghijklmno.py", f"class AdditionalTracker{number}: pass\n")
        subprocess.run(["git", "-C", str(self.root), "add", "src"], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "many modules"], check=True)
        result = self.run_cli("build")
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = Path(json.loads(result.stdout)["summary_path"]).read_text()
        self.assertLessEqual(len(summary.encode()), 8192)
        self.assertRegex(summary, r"Files: \d+/131; omitted: [1-9]\d*")
        self.assertIn("up to 3 definitions/file", summary)

    def test_clean_matching_head_reuses_cache_without_rewriting(self):
        first = json.loads(self.run_cli("build").stdout)
        index = Path(first["index_path"])
        stamp = index.stat().st_mtime_ns
        summary = Path(first["summary_path"])
        summary_stamp = summary.stat().st_mtime_ns
        for command in ("build", "ensure"):
            result = self.run_cli(command)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "current")
            self.assertEqual(index.stat().st_mtime_ns, stamp)
            self.assertEqual(summary.stat().st_mtime_ns, summary_stamp)

    def test_dirty_inputs_block_build_ensure_and_query_without_changing_cache(self):
        first = json.loads(self.run_cli("build").stdout)
        index = Path(first["index_path"])
        original = index.read_bytes()
        self.write("src/python/new tracker.py", "class PendingTracker: pass\n")
        for arguments in (("build",), ("ensure",), ("query", "symbol", "Tracker")):
            result = self.run_cli(*arguments)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("dirty", json.loads(result.stderr)["error"])
            self.assertEqual(index.read_bytes(), original)
        subprocess.run(["git", "-C", str(self.root), "add", "src/python/new tracker.py"], check=True)
        self.assertEqual(self.run_cli("build").returncode, 2)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "tracker"], check=True)
        rebuilt = self.run_cli("build")
        self.assertEqual(rebuilt.returncode, 0, rebuilt.stderr)
        payload = json.loads(rebuilt.stdout)
        self.assertEqual(payload["status"], "rebuilt")
        self.assertNotEqual(payload["revision"], first["revision"])

    def test_dirty_tracked_source_and_settings_block_build(self):
        for name in ("src/python/tracker.py", "nightshift/code-index.toml"):
            with self.subTest(path=name):
                original = (self.root / name).read_text()
                self.write(name, original + "\n# pending change\n")
                result = self.run_cli("build")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(name, json.loads(result.stderr)["error"])
                self.write(name, original)

    def test_unrelated_dirty_files_do_not_invalidate_clean_index(self):
        first = json.loads(self.run_cli("build").stdout)
        self.write("README.md", "unfinished documentation\n")
        self.write("generated/ignored.py", "class ChangedIgnored: pass\n")
        self.write("src/python/vendor/ignored.py", "class VendorChange: pass\n")
        result = self.run_cli("build")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "current")
        self.assertEqual(json.loads(result.stdout)["generation"], first["generation"])

    def test_indexes_multiple_languages_and_returns_ast_backed_evidence(self):
        built = self.run_cli("build")
        self.assertEqual(built.returncode, 0, built.stderr)
        build_result = json.loads(built.stdout)
        self.assertEqual(build_result["files"], 11)
        self.assertEqual(build_result["languages"], ["bash", "c", "cmake", "cpp", "go", "java", "javascript", "make", "python", "rust", "typescript"])
        self.assertEqual(build_result["diagnostics"], [])

        definition = self.run_cli("query", "symbol", "Tracker")
        self.assertEqual(definition.returncode, 0, definition.stderr)
        payload = json.loads(definition.stdout)
        self.assertEqual(payload["matches"][0]["path"], "src/python/tracker.py")
        self.assertEqual(payload["matches"][0]["evidence"], "ast:declaration")
        self.assertEqual(payload["matches"][0]["scope"], "project")
        for symbol in ("TrackerTS", "TrackerGo", "TrackerRs", "c_tracker", "CppTracker", "JavaTracker", "deploy_tracker"):
            result = self.run_cli("query", "symbol", symbol)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["matches"][0]["name"], symbol)

        references = self.run_cli("query", "references", "Tracker", "--scope", "tool")
        self.assertEqual(references.returncode, 0, references.stderr)
        rows = json.loads(references.stdout)["matches"]
        self.assertEqual([row["path"] for row in rows], ["src/javascript/tracker.js"])
        self.assertEqual(rows[0]["scope"], "tool")
        self.assertTrue(all(row["evidence"] == "ast:identifier-reference" for row in rows))

    def test_queries_imports_and_call_leads_across_languages(self):
        self.assertEqual(self.run_cli("build").returncode, 0)
        imported = self.run_cli("query", "module", "math")
        self.assertEqual(imported.returncode, 0, imported.stderr)
        self.assertEqual(json.loads(imported.stdout)["matches"][0]["path"], "src/python/tracker.py")
        go_import = self.run_cli("query", "module", "fmt")
        self.assertEqual(go_import.returncode, 0, go_import.stderr)
        self.assertEqual(json.loads(go_import.stdout)["matches"][0]["path"], "src/go/tracker.go")

        callers = self.run_cli("query", "callers", "stop")
        self.assertEqual(callers.returncode, 0, callers.stderr)
        rows = json.loads(callers.stdout)["matches"]
        self.assertEqual(
            {row["path"] for row in rows},
            {"src/python/tracker.py", "src/javascript/tracker.js", "src/typescript/tracker.ts", "src/go/tracker.go", "src/rust/tracker.rs"},
        )
        self.assertEqual({row["scope"] for row in rows}, {"project", "tool"})
        self.assertTrue(all(row["evidence"] == "ast:identifier-reference" for row in rows))


if __name__ == "__main__":
    unittest.main()
