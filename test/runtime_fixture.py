"""Deploy the declared runtime files for standalone daemon fixtures."""
import json
import os
from pathlib import Path
import shutil
import tempfile
from contextlib import contextmanager


def deploy_runtime(destination):
    source = Path(__file__).resolve().parents[1] / "scripts"
    destination = Path(destination)
    for name in json.loads((source / "install-manifest.json").read_text())["runtime"]:
        origin = source / name
        if name == "PORTING_GUIDE.md" and not origin.exists():
            origin = source / "docs" / name
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(origin, target)


def parser_environment():
    """Explicit test environment wins; only an absent default permits skipping."""
    configured = os.environ.get("NIGHTSHIFT_TEST_PARSER_VENV")
    environment = (Path(configured).expanduser().resolve() if configured else
                   Path(__file__).resolve().parents[1] / "scripts/tools/.venv")
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if configured is not None and (not configured.strip() or not python.is_file()):
        raise RuntimeError(f"NIGHTSHIFT_TEST_PARSER_VENV has no parser Python: {environment}")
    return environment if python.is_file() else None


@contextmanager
def parser_runtime():
    """Give index tests an owned runtime using the selected parser environment."""
    environment = parser_environment()
    if environment is None:
        raise RuntimeError("parser environment required")
    with tempfile.TemporaryDirectory(prefix="nightshift-parser-runtime-") as directory:
        runtime = Path(directory) / "nightshift"
        deploy_runtime(runtime)
        (runtime / "tools/.venv").symlink_to(environment, target_is_directory=True)
        yield runtime / "worker_runtime.py"
