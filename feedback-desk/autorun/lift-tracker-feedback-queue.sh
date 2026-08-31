#!/bin/bash
# Unattended Lift Tracker Feedback Desk work-order runner.
#
# launchd fires this once a day (see com.lift-tracker.feedback-queue.plist). It:
#   1. makes sure both local servers are up (Lift Tracker :8440, Feedback Desk :8441)
#      so a run can actually load the app and click through a fix, the way an
#      interactive session would
#   2. finds every open work order -- one with at least one item not yet done/closed
#   3. runs `claude -p "Work on feedback-desk/data/briefs/wo-NNNN-*.md ..."` headless
#      against each, in order, one at a time
#   4. rebuilds autorun/DIGEST.md from the `needs-clarification` tags a run adds to
#      any item it had to stop on, and raises a macOS notification
#
# It never commits and never pushes -- that stays Alston's call. A run leaves the
# working tree dirty (edited item files, edited app .html); the Lift Tracker Feedback
# Desk board
# picks the changes up live, and `git status` shows what's there to review.
#
# Enable / disable:  autorun/install.sh  /  autorun/uninstall.sh
# Run by hand:       autorun/lift-tracker-feedback-queue.sh   (same thing, right now)
# Logs:              autorun/logs/<timestamp>-woNNNN.log  and  -run.log
#
# Named lift-tracker-feedback-queue.sh, not the more generic run-queue.sh, because the
# launchd agent's ProgramArguments points straight at this file (see the .plist) --
# macOS's Login Items & Extensions panel names an agent after its executable's own
# filename, not its Label, so a generic name here would be indistinguishable from any
# other Feedback-Desk-style runner (PXL's included) in that list.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
DESK="$(cd "$HERE/.." && pwd)"
LOG_DIR="$HERE/logs"
LOCK="$HERE/.run.lock"
STAMP="$(date +%Y-%m-%d-%H%M%S)"
RUN_LOG="$LOG_DIR/$STAMP-run.log"

# claude lives in ~/.local/bin, which launchd's minimal PATH does not include.
CLAUDE_BIN="${CLAUDE_BIN:-$HOME/.local/bin/claude}"
# Per-order wall-clock ceiling, so one wedged run can't block the rest forever.
MAX_MINUTES="${MAX_MINUTES:-45}"
# Pin a model with LIFT_QUEUE_MODEL=... if you want; empty = account default.
MODEL_ARG=()
[[ -n "${LIFT_QUEUE_MODEL:-}" ]] && MODEL_ARG=(--model "$LIFT_QUEUE_MODEL")

mkdir -p "$LOG_DIR"
exec > >(tee -a "$RUN_LOG") 2>&1

log() { printf '%s  %s\n' "$(date +%H:%M:%S)" "$*"; }

# --- one run at a time -------------------------------------------------------
# A lock older than 3h is stale (a run this size can't legitimately last that
# long) -- a previous run was killed -9 before its trap fired. Break it.
if [[ -d "$LOCK" ]] && [[ -z "$(find "$LOCK" -maxdepth 0 -mmin -180 2>/dev/null)" ]]; then
  rmdir "$LOCK" 2>/dev/null || true
fi
if ! mkdir "$LOCK" 2>/dev/null; then
  log "another run holds $LOCK -- exiting"
  exit 0
fi
trap 'rmdir "$LOCK" 2>/dev/null' EXIT

cd "$REPO_ROOT" || { log "cannot cd to repo root $REPO_ROOT"; exit 1; }

if [[ ! -x "$CLAUDE_BIN" ]]; then
  log "claude CLI not found at $CLAUDE_BIN (set CLAUDE_BIN=) -- exiting"
  exit 1
fi

log "repo: $REPO_ROOT"
log "claude: $CLAUDE_BIN  ($("$CLAUDE_BIN" --version 2>/dev/null))"

# --- make sure both servers are up ------------------------------------------
# start-server.sh exits 1 if a server is already running -- that's fine, it just
# means there's nothing to do here. Either way, the run needs both up: the app
# server so a fix can actually be loaded and clicked through, the desk server so
# item edits are picked up the way Alston's own open browser would see them.
"$REPO_ROOT/server/start-server.sh" >/dev/null 2>&1 || true
"$DESK/server/start-server.sh" >/dev/null 2>&1 || true

# --- what's open -----------------------------------------------------------
# bash 3.2 (macOS default) has no `mapfile`, so read the lines the old way.
OPEN=()
while IFS= read -r wo; do
  [[ -n "$wo" ]] && OPEN+=("$wo")
done < <(python3 "$HERE/scan.py" open-orders | awk '{print $1}')
if [[ ${#OPEN[@]} -eq 0 ]]; then
  log "no open work orders -- nothing to do"
  python3 "$HERE/scan.py" digest >/dev/null
  exit 0
fi
log "open work orders: ${OPEN[*]}"

# --- work each one --------------------------------------------------------
# Mirrors, in one inline instruction (lift-tracker has no separate playbook doc
# the way PXL does), the same shape as the brief file's own embedded "How to work
# these items" section, plus the one thing that section can't say: how to behave
# when nobody's there to answer a question.
read -r -d '' UNATTENDED_CLAUSE <<'EOF' || true
This is an unattended scheduled run, not an interactive session -- nobody is reading a
reply in real time, so a question left only in your reply is a question that gets lost.
Work every item in the order normally (read it, do the work, verify what you can against
the running local servers, set status: done and add a ## Resolution section -- or leave
status: queued and explain why in ## Resolution if you can't finish). Two changes from the
normal flow:
1. If an item genuinely needs Alston's input before you can proceed -- a design decision
   the report doesn't specify, an action with real consequences (deleting real logged
   data, anything destructive or hard to reverse), or anything else you'd normally stop
   and ask about -- do not guess and do not proceed. For that item only: add
   "needs-clarification" to its frontmatter tags array (keep any existing tags), append a
   "## Open question" section to the item file stating exactly what you need decided, with
   enough context that Alston can answer without reloading the whole report, and leave
   status untouched. Keep working every other unblocked item in the order.
2. Skip anything already done or closed -- note it and move on. If every item in the order
   is already finished, say so and stop.
Never git commit or push -- leave the working tree for Alston to review. If you use a
throwaway exercise/entry to test something in the running app, delete it again before
you finish, the same way you would in an interactive session.
EOF

declare -a RESULTS
for wo in "${OPEN[@]}"; do
  batch_log="$LOG_DIR/$STAMP-$wo.log"
  log "=== $wo -> $batch_log"
  brief_glob=$(ls "$DESK"/data/briefs/"$wo"-*.md 2>/dev/null | head -1)
  brief_path="${brief_glob:-feedback-desk/data/briefs/$wo.md}"
  brief_rel="${brief_path#$REPO_ROOT/}"
  prompt="Work on $brief_rel

$UNATTENDED_CLAUSE"
  # perl gives us a portable alarm(); macOS has no coreutils `timeout`.
  # ${arr[@]+...} guard: bash 3.2 + `set -u` treats an empty array expansion
  # as an unbound variable without it.
  perl -e 'alarm shift; exec @ARGV' $((MAX_MINUTES * 60)) \
    "$CLAUDE_BIN" -p "$prompt" \
      ${MODEL_ARG[@]+"${MODEL_ARG[@]}"} \
      --dangerously-skip-permissions \
      --output-format text \
    >"$batch_log" 2>&1
  rc=$?
  if [[ $rc -eq 0 ]]; then
    log "$wo finished (rc=0)"
    RESULTS+=("$wo ok")
  elif [[ $rc -eq 142 ]]; then
    log "$wo TIMED OUT after ${MAX_MINUTES}m"
    RESULTS+=("$wo timeout")
  else
    log "$wo exited rc=$rc -- see $batch_log"
    RESULTS+=("$wo rc=$rc")
  fi
done

# --- collect what needs Alston ------------------------------------------
python3 "$HERE/scan.py" digest
FLAGGED=$?
log "digest: $FLAGGED item(s) flagged needs-clarification"

DONE_COUNT=$(grep -rlE '^status:[[:space:]]*"?done"?[[:space:]]*$' "$DESK/data/items" 2>/dev/null | wc -l | tr -d ' ')

SUMMARY="Feedback queue: ran ${#OPEN[@]} work order(s) [${RESULTS[*]}]. \
$FLAGGED flagged for clarification. $DONE_COUNT item(s) now marked done -- review & commit."
log "$SUMMARY"

# --- notify --------------------------------------------------------------
if command -v osascript >/dev/null 2>&1; then
  title="Lift Tracker feedback queue"
  [[ $FLAGGED -gt 0 ]] && title="Lift Tracker feedback queue - $FLAGGED need clarification"
  osascript -e "display notification \"$SUMMARY\" with title \"$title\"" >/dev/null 2>&1 || true
fi

log "done. Full logs in $LOG_DIR"
