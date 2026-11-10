#!/usr/bin/env python3
"""unittest discovery and execution evidence for the hot hook protocol."""

import argparse
import ast
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest


def methods(source):
    tree = ast.parse(source)
    found = {}
    for cls in tree.body:
        if isinstance(cls, ast.ClassDef):
            for node in cls.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Docstrings/comments are not a substantive test change.
                    if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                        node.body = node.body[1:]
                    found[(cls.name, node.name)] = hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest()
    return found


def flatten(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from flatten(item)
        else:
            yield item


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", default="test")
    parser.add_argument("--pattern", default="test*.py")
    parser.add_argument("--cold-only-file", type=Path,
                        help="Case IDs to omit from hot unless new, changed, or required")
    args = parser.parse_args()
    cold_only = set()
    if args.cold_only_file is not None:
        cold_only = {line.strip() for line in args.cold_only_file.read_text(encoding="utf-8").splitlines()
                     if line.strip() and not line.lstrip().startswith("#")}
    phase = os.environ["NIGHTSHIFT_PHASE"]
    required = set(json.loads(os.environ.get("NIGHTSHIFT_REQUIRED", "[]"))) if phase == "run" else set()
    only = set(json.loads(os.environ.get("NIGHTSHIFT_ONLY_CASES", "[]"))) if phase == "run" else set()
    root = Path.cwd().resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    loader = unittest.TestLoader()
    suite = loader.discover(args.start, pattern=args.pattern)
    if loader.errors:
        raise RuntimeError("\n".join(loader.errors))
    tests, cases = [], []
    fingerprints = {}
    for test in flatten(suite):
        source = Path(inspect.getfile(type(test))).resolve().relative_to(root).as_posix()
        if source not in fingerprints:
            baseline = subprocess.run(["git", "show", f"{os.environ['NIGHTSHIFT_BASE']}:{source}"], capture_output=True)
            fingerprints[source] = (methods((root / source).read_text()),
                                    methods(baseline.stdout.decode()) if baseline.returncode == 0 else {})
        identity = (type(test).__name__, test._testMethodName)
        current_methods, baseline_methods = fingerprints[source]
        current, previous = current_methods[identity], baseline_methods.get(identity)
        case_id = test.id()
        if only and case_id not in only:
            continue
        if case_id in cold_only and case_id not in required and previous == current:
            continue
        tests.append(test)
        cases.append({"id": case_id, "source": source, "fingerprint": current,
                      "baseline_fingerprint": previous})
    if phase == "run":
        class Result(unittest.TextTestResult):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.outcomes = {}

            def addSuccess(self, test):
                super().addSuccess(test)
                self.outcomes[test.id()] = "passed"

            def addFailure(self, test, err):
                super().addFailure(test, err)
                self.outcomes[test.id()] = "failed"

            def addError(self, test, err):
                super().addError(test, err)
                self.outcomes[test.id()] = "error"

            def addSubTest(self, test, subtest, err):
                super().addSubTest(test, subtest, err)
                if err:
                    status = "failed" if issubclass(err[0], test.failureException) else "error"
                    if self.outcomes.get(test.id()) != "error":
                        self.outcomes[test.id()] = status

        result = unittest.TextTestRunner(resultclass=Result, verbosity=1).run(unittest.TestSuite(tests))
        for case in cases:
            case["status"] = result.outcomes.get(case["id"], "failed_or_skipped")
        code = 0 if result.wasSuccessful() and tests else 1
    else:
        code = 0
    Path(os.environ["NIGHTSHIFT_RESULT"]).write_text(json.dumps({"run": os.environ["NIGHTSHIFT_RUN"], "cases": cases, "supports_case_selection": True}))
    return code


if __name__ == "__main__":
    sys.exit(main())
