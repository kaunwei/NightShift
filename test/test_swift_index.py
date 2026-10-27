import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


CLI = Path(__file__).resolve().parents[1] / "nightshift" / "tools" / "index.py"


class SwiftIndexPublicCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        self.write("Package.swift", '''// swift-tools-version: 5.9
import PackageDescription
let package = Package(name: "Fixture", targets: [
    .target(name: "Core", path: "Sources/Core"),
    .target(name: "App", dependencies: ["Core"], path: "Sources/App"),
    .testTarget(name: "CoreTests", dependencies: ["Core"], path: "Tests/CoreTests")
])
''')
        self.write("Sources/Core/PracticeTracker.swift", '''import Foundation
public final class PracticeTracker {
    public init() {}
    public func record() {}
    @MainActor
    public func markedMethod() {}
    @available(macOS 14, *)
    public static func availableMethod() {}
    private(set) var cachedState = false
}
''')
        self.write("Sources/App/MetronomeViewModel.swift", '''import Core
final class MetronomeViewModel {
    private let practiceTracker = PracticeTracker()
    func tick() { practiceTracker.record() }
    let documentation = "PracticeTracker() is only an example // not a comment"
    /* PracticeTracker() is not executable code */
    // PracticeTracker() is not executable code either
}
''')
        self.write("tests/CoreTests/PracticeTrackerTests.swift", '''@testable import Core
func testTracker() { PracticeTracker().record() }
''')
        self.write(".build/generated/Noise.swift", "struct MustNotAppear {}\n")
        subprocess.run(["git", "-C", str(self.root), "add", "Package.swift", "Sources", "tests"], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "fixture"], check=True)

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
        )

    def test_build_and_queries_return_source_backed_definitions_and_reference_leads(self):
        built = self.run_cli("build")
        self.assertEqual(built.returncode, 0, built.stderr)
        build_result = json.loads(built.stdout)
        self.assertEqual(build_result["files"], 4)
        self.assertEqual(build_result["modules"], ["App", "Core", "CoreTests"])
        self.assertTrue(build_result["index_path"])
        self.assertTrue(build_result["source_sha256"])

        definition = self.run_cli("query", "symbol", "PracticeTracker")
        self.assertEqual(definition.returncode, 0, definition.stderr)
        definition_result = json.loads(definition.stdout)
        self.assertEqual(definition_result["matches"][0]["path"], "Sources/Core/PracticeTracker.swift")
        self.assertEqual(definition_result["matches"][0]["line"], 2)
        self.assertIsInstance(definition_result["matches"][0]["column"], int)
        self.assertEqual(definition_result["matches"][0]["evidence"], "ast:declaration")
        for symbol in ("markedMethod", "availableMethod", "cachedState"):
            indexed = self.run_cli("query", "symbol", symbol)
            self.assertEqual(indexed.returncode, 0, indexed.stderr)
            self.assertEqual(json.loads(indexed.stdout)["matches"][0]["name"], symbol)

        method = self.run_cli("query", "symbol", "PracticeTracker.record")
        self.assertEqual(method.returncode, 0, method.stderr)
        self.assertEqual(json.loads(method.stdout)["matches"][0]["qualified_name"], "PracticeTracker.record")
        self.assertEqual(json.loads(method.stdout)["matches"][0]["kind"], "function")

        references = self.run_cli("query", "references", "PracticeTracker")
        self.assertEqual(references.returncode, 0, references.stderr)
        reference_result = json.loads(references.stdout)
        self.assertEqual(
            {row["path"] for row in reference_result["matches"]},
            {"Sources/App/MetronomeViewModel.swift", "tests/CoreTests/PracticeTrackerTests.swift"},
        )
        self.assertTrue(all(row["evidence"] == "ast:identifier-reference" for row in reference_result["matches"]))
        self.assertIn("semantic", reference_result["unresolved"])
        self.assertEqual(len(reference_result["matches"]), 2)
        self.assertTrue(all(row["column"] > 0 for row in reference_result["matches"]))

    def test_module_query_reports_import_relationship_and_bounded_truncation(self):
        self.assertEqual(self.run_cli("build").returncode, 0)
        result = self.run_cli("query", "module", "Core", "--limit", "1")
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(len(payload["matches"]), 1)
        self.assertTrue(payload["truncated"])
        self.assertGreater(payload["omitted"], 0)
        self.assertEqual(payload["matches"][0]["evidence"], "ast:import")

        all_core_imports = self.run_cli("query", "module", "Core", "--limit", "50")
        self.assertEqual(all_core_imports.returncode, 0, all_core_imports.stderr)
        self.assertTrue(any(
            row["path"] == "tests/CoreTests/PracticeTrackerTests.swift"
            for row in json.loads(all_core_imports.stdout)["matches"]
        ))

        compact = self.run_cli("query", "module", "Core", "--limit", "1", "--format", "compact")
        self.assertEqual(compact.returncode, 0, compact.stderr)
        self.assertIn("matches: 1/2", compact.stdout)
        self.assertIn("truncated: true", compact.stdout)
        self.assertIn("Sources/App/MetronomeViewModel.swift", compact.stdout)
        self.assertLess(len(compact.stdout), len(result.stdout))

    def test_stale_query_refreshes_automatically_and_reuses_single_index_location(self):
        first = json.loads(self.run_cli("build").stdout)
        self.write("Sources/Core/NewTracker.swift", "struct NewTracker {}\n")
        subprocess.run(["git", "-C", str(self.root), "add", "Sources/Core/NewTracker.swift"], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "new tracker"], check=True)
        refreshed = self.run_cli("query", "symbol", "NewTracker")
        self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
        payload = json.loads(refreshed.stdout)
        self.assertTrue(any(row["name"] == "NewTracker" for row in payload["matches"]))
        self.assertNotEqual(payload["generation"], first["generation"])

        rebuilt = json.loads(self.run_cli("build").stdout)
        self.assertEqual(rebuilt["index_path"], first["index_path"])
        self.assertEqual(rebuilt["generation"], payload["generation"])
        self.assertEqual(rebuilt["files"], 5)

    def test_missing_index_and_invalid_limit_have_actionable_errors(self):
        missing = self.run_cli("query", "symbol", "PracticeTracker")
        self.assertEqual(missing.returncode, 0, missing.stderr)
        self.assertTrue(json.loads(missing.stdout)["generation"])
        self.assertEqual(self.run_cli("build").returncode, 0)
        invalid = self.run_cli("query", "symbol", "PracticeTracker", "--limit", "-1")
        self.assertEqual(invalid.returncode, 2)
        self.assertIn("limit", json.loads(invalid.stderr)["error"])

    def test_query_refreshes_index_after_head_moves_even_when_sources_do_not(self):
        self.assertEqual(self.run_cli("build").returncode, 0)
        self.write("README.md", "metadata-only revision\n")
        subprocess.run(["git", "-C", str(self.root), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "metadata"], check=True)
        refreshed = self.run_cli("query", "symbol", "PracticeTracker")
        self.assertEqual(refreshed.returncode, 0, refreshed.stderr)
        self.assertTrue(json.loads(refreshed.stdout)["generation"])

    def test_linked_worktree_keeps_its_index_inside_its_own_checkout(self):
        first = json.loads(self.run_cli("build").stdout)
        linked = self.root.parent / f"linked-worktree-{self.root.name}"
        subprocess.run(["git", "-C", str(self.root), "worktree", "add", "-q", "--detach", str(linked), "HEAD"], check=True)
        try:
            second = subprocess.run(
                [sys.executable, str(CLI), "--repo", str(linked), "build"],
                capture_output=True, text=True,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            payload = json.loads(second.stdout)
            self.assertNotEqual(payload["index_path"], first["index_path"])
            self.assertEqual(Path(payload["index_path"]), linked.resolve() / "nightshift/.scratch/code-index/index.json")
        finally:
            subprocess.run(["git", "-C", str(self.root), "worktree", "remove", "--force", str(linked)], check=True)

    def test_concurrent_builds_leave_one_valid_generation(self):
        commands = [
            subprocess.Popen(
                [sys.executable, str(CLI), "--repo", str(self.root), "build"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
            for _ in range(2)
        ]
        results = [process.communicate(timeout=10) + (process.returncode,) for process in commands]
        self.assertTrue(all(code == 0 for _, stderr, code in results), results)
        query = self.run_cli("query", "callers", "record")
        self.assertEqual(query.returncode, 0, query.stderr)
        payload = json.loads(query.stdout)
        self.assertEqual(payload["matches"][0]["evidence"], "ast:identifier-reference")
        self.assertIn("unresolved", payload)

    def test_query_works_with_a_read_only_cached_generation(self):
        built = json.loads(self.run_cli("build").stdout)
        lock = Path(built["index_path"]).with_suffix(".lock")
        lock.chmod(0o444)
        try:
            result = self.run_cli("query", "symbol", "PracticeTracker")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["matches"][0]["name"], "PracticeTracker")
        finally:
            lock.chmod(0o644)


if __name__ == "__main__":
    unittest.main()
