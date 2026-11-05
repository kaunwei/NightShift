#!/usr/bin/env bash
set -euo pipefail

PROJECT_STATE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="$(basename "$PROJECT_STATE_DIR")"
CONFIG_FILE="$PROJECT_STATE_DIR/config.json"
NIGHTSHIFT_CORE="${NIGHTSHIFT_CORE:-/Volumes/Vault500G/workspace/NightShift}"

WORKER_SCRIPT=""
if [ -f "$NIGHTSHIFT_CORE/scripts/worker.sh" ]; then
    WORKER_SCRIPT="$NIGHTSHIFT_CORE/scripts/worker.sh"
elif [ -f "$NIGHTSHIFT_CORE/nightshift/worker.sh" ]; then
    WORKER_SCRIPT="$NIGHTSHIFT_CORE/nightshift/worker.sh"
elif [ -f "$NIGHTSHIFT_CORE/worker.sh" ]; then
    WORKER_SCRIPT="$NIGHTSHIFT_CORE/worker.sh"
else
    echo "Error: worker.sh not found in $NIGHTSHIFT_CORE" >&2
    exit 1
fi

echo "=== Starting NightShift Worker ==="
echo "Project: $PROJECT_NAME"
echo "Config:  $CONFIG_FILE"
echo "State:   $PROJECT_STATE_DIR"
echo "=================================="

export RUN_ONCE=0

cleanup() {
    echo "Stopped by operator"
    if [ -n "${WORKER_PID:-}" ] && kill -0 "$WORKER_PID" 2>/dev/null; then
        kill "$WORKER_PID" 2>/dev/null || true
        wait "$WORKER_PID" 2>/dev/null || true
    fi
    exit 0
}
trap cleanup SIGTERM SIGINT

while true; do
    bash "$WORKER_SCRIPT" --config "$CONFIG_FILE" "$@" &
    WORKER_PID=$!
    set +e
    wait "$WORKER_PID"
    status=$?
    set -e
    echo "Worker exited with status $status"
    sleep "${NIGHTSHIFT_RETRY_SECONDS:-5}"
done
