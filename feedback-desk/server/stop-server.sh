#!/bin/bash
# Stops a server started with start-server.sh.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

PID_FILE=".server.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "Not running (no $PID_FILE)." >&2
  exit 1
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  echo "Stopped (PID $PID)."
else
  echo "PID $PID from $PID_FILE wasn't running (stale)."
fi
rm -f "$PID_FILE"
