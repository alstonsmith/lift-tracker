#!/bin/bash
# Starts the Lift Tracker server detached, so it keeps running after this terminal
# closes -- the same manual start/stop pair House Tracker uses, on the same reasoning:
# you start it once and it stays up until you explicitly stop it.
# Pair: stop-server.sh.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

PID_FILE=".server.pid"
LOG_FILE="server.log"
PORT="${1:-8440}"

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Already running (PID $(cat "$PID_FILE")). Run ./stop-server.sh first to restart it." >&2
  exit 1
fi

# -u: unbuffered stdout. Without it Python buffers print() when stdout isn't a terminal,
# so the startup banner (the URLs to open) would sit in memory and never reach the log.
nohup python3 -u serve_lift_tracker.py --port "$PORT" >> "$LOG_FILE" 2>&1 &
echo $! > "$PID_FILE"
sleep 0.5

if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  echo "Server failed to start -- check $LOG_FILE" >&2
  rm -f "$PID_FILE"
  exit 1
fi

echo "Started (PID $(cat "$PID_FILE")). Logs: $(pwd)/$LOG_FILE"
tail -n 6 "$LOG_FILE"
