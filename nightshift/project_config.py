"""Read the project's single persistent NightShift configuration."""
import json
from pathlib import Path


def read(path):
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"invalid NightShift configuration {path}: {error}") from error
    if not isinstance(value, dict):
        raise ValueError(f"NightShift configuration {path} must be an object")
    if value.get("version") != 1:
        raise ValueError(f"NightShift configuration {path} requires version 1")
    return value
