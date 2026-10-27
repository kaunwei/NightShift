#!/bin/sh
set -eu

TOOL_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PYTHON_BIN=${PYTHON_BIN:-python3}
VENV="$TOOL_DIR/.venv"
STAMP="$VENV/.requirements.sha256"
REQUIREMENTS_HASH=$("$PYTHON_BIN" - "$TOOL_DIR/requirements.txt" <<'PY'
import hashlib
from pathlib import Path
import sys
print(hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest())
PY
)

if [ -x "$VENV/bin/python" ] && [ -f "$STAMP" ] \
  && [ "$(cat "$STAMP")" = "$REQUIREMENTS_HASH" ] \
  && "$VENV/bin/python" -m pip check >/dev/null 2>&1; then
  echo "NightShift parser dependencies are already installed."
  exit 0
fi

if [ ! -x "$VENV/bin/python" ]; then "$PYTHON_BIN" -m venv "$VENV"; fi
"$VENV/bin/python" -m pip install -r "$TOOL_DIR/requirements.txt"
"$VENV/bin/python" -m pip check
printf '%s\n' "$REQUIREMENTS_HASH" > "$STAMP"
