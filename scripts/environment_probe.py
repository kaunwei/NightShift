"""Run directly, or inside the configured adapter sandbox, without model work."""
import argparse
import json
from pathlib import Path
import tempfile


def probe(project, state):
    project, state = Path(project).resolve(), Path(state).resolve()
    if not project.is_dir():
        raise ValueError(f"project directory not readable: {project}")
    list(project.iterdir())
    state.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="readiness-", dir=state) as temp:
        path = Path(temp) / "result.json"
        path.write_text('{"probe": true}\n')
        if json.loads(path.read_text()) != {"probe": True}:
            raise ValueError("runner output roundtrip failed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("state")
    args = parser.parse_args()
    probe(args.project, args.state)
