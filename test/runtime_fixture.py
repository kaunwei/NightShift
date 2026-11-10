"""Deploy the declared runtime files for standalone daemon fixtures."""
import json
from pathlib import Path
import shutil


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
