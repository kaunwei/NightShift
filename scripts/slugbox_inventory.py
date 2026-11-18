#!/usr/bin/env python3
"""Expose SlugBox's public complete discovery without changing its live runner."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adapter", type=Path, required=True, help="Approved candidate regression.py")
    args = parser.parse_args()
    if os.environ.get("NIGHTSHIFT_PHASE") != "inventory":
        parser.error("this bridge only supports complete inventory, not test execution")
    adapter = args.adapter.resolve()
    sys.path.insert(0, str(adapter.parent))
    spec = importlib.util.spec_from_file_location("regression", adapter)
    module = importlib.util.module_from_spec(spec)
    sys.modules["regression"] = module
    spec.loader.exec_module(module)
    if module.ROOT.resolve() != Path.cwd().resolve():
        parser.error("adapter must discover the requested revision root")
    cases = module.discover()
    result = {"run": os.environ["NIGHTSHIFT_RUN"], "cases": cases, "inventory_complete": True}
    Path(os.environ["NIGHTSHIFT_RESULT"]).write_text(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
