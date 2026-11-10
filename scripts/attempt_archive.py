"""Self-contained, restore-verified evidence before destructive Git recovery."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True).stdout


def paths(root):
    return sorted(set(os.fsdecode(p) for p in git(
        root, "ls-files", "--cached", "--others", "--exclude-standard", "-z").split(b"\0") if p))


def entry(root, name):
    p = root / name
    if p.is_symlink():
        return {"kind": "symlink", "target": os.readlink(p)}
    if not p.exists():
        return {"kind": "missing"}
    if not p.is_file():
        raise ValueError(f"attempt archive cannot preserve non-file entry: {name}")
    return {"kind": "file", "mode": p.stat().st_mode & 0o777,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}


def copy_file(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        target.symlink_to(os.readlink(source))
    else:
        shutil.copy2(source, target)


def capture(root, destination, *, context=None):
    """Stop on any capture/restore error; never modify the source checkout."""
    root, destination = Path(root).resolve(), Path(destination).resolve()
    if destination.exists():
        raise FileExistsError(destination)
    names = paths(root)
    head = git(root, "rev-parse", "HEAD").decode().strip()
    index = git(root, "write-tree").decode().strip()
    entries = {name: entry(root, name) for name in names}
    destination.mkdir(parents=True, mode=0o700)
    try:
        git(root, "bundle", "create", str(destination / "head.bundle"), "HEAD")
        (destination / "index.diff").write_bytes(git(root, "diff", "--cached", "--binary", "HEAD"))
        (destination / "worktree.diff").write_bytes(git(root, "diff", "--binary"))
        untracked = [os.fsdecode(p) for p in git(root, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0") if p]
        # The package may live in the project's ignored scratch area. Never
        # recursively copy a newly created archive into itself.
        untracked = [n for n in untracked if n in entries]
        for name in untracked:
            copy_file(root / name, destination / "untracked" / name)
        manifest = {"version": 1, "root": str(root), "head": head, "index": index,
                    "entries": entries, "untracked": untracked,
                    "context": context or {},
                    "exclusions": "Git-ignored files are not captured"}
        manifest["checksums"] = {n: hashlib.sha256((destination / n).read_bytes()).hexdigest()
                                 for n in ("head.bundle", "index.diff", "worktree.diff")}
        (destination / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=True, indent=2) + "\n")
        verify(destination)
        # Catch a source writer racing capture. A changed scene must remain live.
        if (head != git(root, "rev-parse", "HEAD").decode().strip()
                or index != git(root, "write-tree").decode().strip()
                or any(entry(root, n) != value for n, value in entries.items())
                or set(names) != {n for n in paths(root) if not (root / n).is_relative_to(destination)}):
            raise RuntimeError("attempt changed while being archived; cleanup refused")
        (destination / "verified.json").write_text('{"restoration_verified": true}\n')
    except Exception:
        # Retain partial evidence for diagnosis; no cleanup authorization exists.
        raise
    return destination


def verify(destination):
    destination = Path(destination).resolve()
    data = json.loads((destination / "manifest.json").read_text())
    for name, checksum in data["checksums"].items():
        if name not in ("head.bundle", "index.diff", "worktree.diff"):
            raise ValueError("invalid archive member")
        if hashlib.sha256((destination / name).read_bytes()).hexdigest() != checksum:
            raise ValueError(f"attempt archive checksum mismatch: {name}")
    for name in data["entries"]:
        if Path(name).is_absolute() or ".." in Path(name).parts or ".git" in Path(name).parts:
            raise ValueError("unsafe archive path")
    with tempfile.TemporaryDirectory(prefix="nightshift-restore-check-") as temp:
        root = Path(temp) / "checkout"
        subprocess.run(["git", "clone", "--quiet", str(destination / "head.bundle"), str(root)],
                       check=True, capture_output=True)
        for name, options in (("index.diff", ["--index"]), ("worktree.diff", [])):
            if (destination / name).stat().st_size:
                git(root, "apply", *options, str(destination / name))
        for name in data["untracked"]:
            if name not in data["entries"]:
                raise ValueError("invalid untracked archive member")
            copy_file(destination / "untracked" / name, root / name)
        for name, value in data["entries"].items():
            if value["kind"] == "file":
                (root / name).chmod(value["mode"])
        if (git(root, "rev-parse", "HEAD").decode().strip() != data["head"]
                or git(root, "write-tree").decode().strip() != data["index"]
                or any(entry(root, n) != value for n, value in data["entries"].items())):
            raise ValueError("attempt archive could not restore exact head/index/files")
    return data


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    manifest = verify(args.archive)
    print(json.dumps({"restoration_verified": True, "head": manifest["head"],
                      "files": len(manifest["entries"])}))
