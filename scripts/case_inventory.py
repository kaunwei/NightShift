#!/usr/bin/env python3
"""Complete adapter inventories, independent of hot/cold scheduling."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid


class InventoryOutput(str):
    def __new__(cls, value, **metadata):
        result = super().__new__(cls, value)
        result.__dict__.update(metadata)
        return result


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)


def input_digest(root):
    names = git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard").split(b"\0")
    digest = hashlib.sha256()
    for name in sorted(set(names) - {b""}):
        path = root / os.fsdecode(name)
        digest.update(name + b"\0")
        if path.exists() or path.is_symlink():
            digest.update(str(path.lstat().st_mode & 0o7777).encode() + b"\0")
        if path.is_symlink():
            digest.update(b"link:" + os.fsencode(os.readlink(path)))
        elif path.is_file():
            digest.update(b"file:")
            with path.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        elif path.exists():
            raise ValueError("inventory does not support submodules: " + str(path))
        else:
            digest.update(b"deleted")
        digest.update(b"\0")
    return digest.hexdigest()


@contextmanager
def revision_root(root, revision):
    """Read-only Git archive; no worktree registration or source checkout edits."""
    resolved = git(root, "rev-parse", "--verify", revision + "^{commit}").decode().strip()
    if not re.fullmatch(r"[a-f0-9]{40,64}", resolved):
        raise ValueError("inventory baseline did not resolve to one commit")
    entries = git(root, "ls-tree", "-rz", resolved).split(b"\0")
    if any(entry.startswith(b"160000 ") for entry in entries):
        raise ValueError("inventory does not support submodules")
    with tempfile.TemporaryDirectory(prefix="nightshift-inventory-") as directory:
        directory = Path(directory)
        # Override archive-only transformations in isolated metadata. The original
        # repository's configuration, attributes and worktrees remain untouched.
        repository = directory / "repository.git"
        object_format = git(root, "rev-parse", "--show-object-format").decode().strip()
        subprocess.run(["git", "init", "--bare", "-q", "--object-format=" + object_format, str(repository)], check=True, capture_output=True)
        objects = Path(git(root, "rev-parse", "--git-path", "objects").decode().strip())
        if not objects.is_absolute():
            objects = root / objects
        (repository / "objects/info/alternates").write_text(str(objects.resolve()) + "\n")
        (repository / "info/attributes").write_text("* -export-ignore -export-subst\n")
        archive = directory / "source.tar"
        with archive.open("wb") as stream:
            subprocess.run(["git", "--git-dir=" + str(repository), "archive", "--format=tar", resolved], stdout=stream, stderr=subprocess.PIPE, check=True)
        checkout = directory / "checkout"
        checkout.mkdir()
        with tarfile.open(archive) as stream:
            stream.extractall(checkout, filter="data")
        subprocess.run(["git", "init", "-q", str(checkout)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(checkout), "add", "-f", "-A"], check=True, capture_output=True)
        # Git metadata is needed only for a content manifest, never as execution evidence.
        yield checkout, resolved


def validate_cases(cases):
    if not isinstance(cases, list):
        raise ValueError("inventory cases must be a list")
    found = {}
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("inventory case must be an object")
        identity, source, fingerprint = (case.get(k) for k in ("id", "source", "fingerprint"))
        if not isinstance(identity, str) or not identity or identity in found:
            raise ValueError("inventory requires unique nonempty IDs")
        if not isinstance(source, str) or not source or Path(source).is_absolute() or any(p in ("..", ".git") for p in Path(source).parts):
            raise ValueError("inventory requires safe relative sources")
        if not isinstance(fingerprint, str) or not re.fullmatch("[a-f0-9]{64}", fingerprint):
            raise ValueError("inventory requires supported fingerprints")
        found[identity] = {"id": identity, "source": source, "fingerprint": fingerprint}
    return found


def collect(root, config, revision="working", *, deadline=None):
    root = Path(root).resolve()
    if not isinstance(config, dict):
        raise ValueError("inventory config must be an object")
    command = config.get("command")
    if not isinstance(command, list) or not command or any(not isinstance(p, str) or not p for p in command):
        raise ValueError("inventory config requires command argv")
    # Run the approved candidate provider against both trees, including old revisions
    # that predate the protocol. Relative existing provider files bind to candidate.
    command = [str((root / p).resolve()) if not Path(p).is_absolute() and (root / p).is_file() else p for p in command]
    budget = config.get("timeout", 120)
    if type(budget) not in (int, float) or not math.isfinite(budget) or budget <= 0:
        raise ValueError("inventory timeout must be finite and positive")
    def provider_digest():
        digest = hashlib.sha256(json.dumps(command).encode())
        files = set()
        for arg in command:
            path = Path(arg)
            if path.is_file():
                files.add(path)
                if path.suffix == ".py":
                    files.update(path.parent.glob("*.py"))
        for path in sorted(files):
            digest.update(str(path).encode() + b"\0" + path.read_bytes())
        return digest.hexdigest()
    provider_before = provider_digest()
    def invoke(tree, resolved):
        before = input_digest(tree)
        with tempfile.TemporaryDirectory(prefix="nightshift-inventory-evidence-") as directory:
            output = Path(directory) / "inventory.json"
            nonce = uuid.uuid4().hex
            env = {**os.environ, "NIGHTSHIFT_PHASE": "inventory", "NIGHTSHIFT_RESULT": str(output),
                   "NIGHTSHIFT_RUN": nonce, "NIGHTSHIFT_BASE": "", "NIGHTSHIFT_REQUIRED": "[]",
                   "NIGHTSHIFT_ONLY_CASES": "[]", "NIGHTSHIFT_TASK": "", "NIGHTSHIFT_PROJECT_ROOT": str(tree),
                   "PROJECT_ROOT": str(tree), "NIGHTSHIFT_STATE_DIR": directory, "PYTHONDONTWRITEBYTECODE": "1"}
            import verify_process
            phase_budget = min(budget, max(0, deadline - time.monotonic())) if deadline is not None else budget
            if phase_budget <= 0:
                raise subprocess.TimeoutExpired(command, 0)
            code, output_text = verify_process.run(shlex.join(command), tree, "0", phase_budget, InventoryOutput,
                                                   environment=env, directory=Path(directory) / "command")
            if output_text.timed_out:
                raise subprocess.TimeoutExpired(command, phase_budget, output=str(output_text))
            if code:
                raise ValueError("inventory provider failed: " + str(output_text)[-4000:])
            data = json.loads(output.read_text())
            if data.get("run") != nonce or data.get("inventory_complete") is not True:
                raise ValueError("inventory provider did not attest complete discovery")
            cases = validate_cases(data.get("cases"))
            for case in cases.values():
                source = tree / case["source"]
                if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(tree):
                    raise ValueError("inventory source absent or unsafe: " + case["source"])
            if input_digest(tree) != before:
                raise ValueError("inventory inputs changed during discovery")
            if provider_digest() != provider_before:
                raise ValueError("inventory provider changed during discovery")
            return {"version": 1, "revision": resolved, "input_digest": before,
                    "provider_digest": provider_before, "complete": True,
                    "cases": sorted(cases.values(), key=lambda c: c["id"])}
    if revision == "working":
        return invoke(root, "working@" + git(root, "rev-parse", "HEAD").decode().strip())
    with revision_root(root, revision) as (tree, resolved):
        return invoke(tree, resolved)


def compare(baseline, candidate):
    if baseline["provider_digest"] != candidate["provider_digest"]:
        raise ValueError("inventory provider changed between revision collections")
    old, new = validate_cases(baseline["cases"]), validate_cases(candidate["cases"])
    return {"baseline": baseline, "candidate": candidate,
            "added": sorted(new.keys() - old.keys()), "removed": sorted(old.keys() - new.keys()),
            "modified": sorted(k for k in old.keys() & new.keys() if old[k] != new[k])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, required=True, help="JSON with command argv and optional timeout")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("list").add_argument("--revision", default="working")
    sub.add_parser("diff").add_argument("--base", required=True)
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text())
        if args.action == "list":
            result = collect(args.root, config, args.revision)
        else:
            result = compare(collect(args.root, config, args.base), collect(args.root, config))
        print(json.dumps(result, indent=2))
    except (OSError, ValueError, subprocess.SubprocessError, tarfile.TarError) as error:
        print("inventory error: " + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
