#!/bin/bash
# Runs the end-to-end smoke tests against a running Lift Tracker server.
# Starts its own headless Chrome, runs tools/smoke-test.mjs, tears Chrome down.
#
#   ./tools/run-tests.sh              # assumes the server is up on :8440
#   PORT=8440 ./tools/run-tests.sh
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

PORT="${PORT:-8440}"
CDP_PORT="${CDP_PORT:-9223}"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
OUT_DIR="${OUT_DIR:-$(mktemp -d)}"

if ! curl -sf "http://localhost:$PORT/api/ping" >/dev/null; then
  echo "No Lift Tracker server on port $PORT — run ./server/start-server.sh first." >&2
  exit 1
fi
if [[ ! -x "$CHROME" ]]; then
  echo "Chrome not found at $CHROME (override with CHROME=...)." >&2
  exit 1
fi

# Two suites against one server corrupt each other's fixtures: both build the same test
# week, both look it up by date, and one deletes the day the other was using. One run at
# a time.
LOCK_DIR="${TMPDIR:-/tmp}/lift-tracker-tests.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "Another test run is in progress (lock: $LOCK_DIR)." >&2
  echo "If that's stale, remove it: rmdir '$LOCK_DIR'" >&2
  exit 1
fi

PROFILE="$(mktemp -d)"
"$CHROME" --headless=new --disable-gpu --remote-debugging-port="$CDP_PORT" \
  --user-data-dir="$PROFILE" --no-first-run about:blank >/dev/null 2>&1 &
CHROME_PID=$!
cleanup() {
  kill "$CHROME_PID" 2>/dev/null || true
  rm -rf "$PROFILE" 2>/dev/null || true
  rmdir "$LOCK_DIR" 2>/dev/null || true
}
trap cleanup EXIT

for _ in $(seq 1 40); do
  curl -sf "http://127.0.0.1:$CDP_PORT/json/version" >/dev/null 2>&1 && break
  perl -e 'select(undef,undef,undef,0.25)'
done

DESK_PORT="${DESK_PORT:-8441}"
echo "Screenshots: $OUT_DIR"
export CDP_PORT APP_URL="http://localhost:$PORT/" OUT_DIR
# Both suites run regardless of whether the first one has failures -- under `set -e`, an
# unguarded `node tools/smoke-test.mjs` would abort the whole script the moment it exits
# non-zero (which it does whenever any test fails), and the Feedback Desk suite below
# would silently never run. The `cmd && rc=0 || rc=$?` form is the standard way to capture
# a command's exit status without tripping `-e`: a command isn't subject to `-e` when it's
# not the last element of an `&&`/`||` list.
echo "=== Lift Tracker ==="
node tools/smoke-test.mjs && LT_RC=0 || LT_RC=$?
DESK_RC=0
if curl -sf "http://localhost:$DESK_PORT/api/ping" >/dev/null; then
  echo
  echo "=== Lift Tracker Feedback Desk ==="
  DESK_URL="http://localhost:$DESK_PORT/" node tools/feedback-smoke-test.mjs && DESK_RC=0 || DESK_RC=$?
else
  echo
  echo "(Lift Tracker Feedback Desk not running on :$DESK_PORT — skipping its suite.)"
fi

# The script's own exit status still reflects either suite failing, so a caller (CI, an
# agent checking $?) can't mistake "we ran both suites" for "everything passed".
[[ $LT_RC -eq 0 && $DESK_RC -eq 0 ]]
