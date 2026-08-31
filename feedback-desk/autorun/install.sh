#!/bin/bash
# Install (or re-install) the daily Lift Tracker Feedback Desk queue runner as a launchd agent.
# Safe to run repeatedly -- it bootout/bootstraps, so editing the .plist here and
# re-running is the update path. Pair: uninstall.sh.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="com.lift-tracker.feedback-queue"
SRC="$HERE/$LABEL.plist"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
RUN_QUEUE_SH="$HERE/lift-tracker-feedback-queue.sh"
LOG_DIR="$HERE/logs"

[[ -f "$SRC" ]] || { echo "missing $SRC" >&2; exit 1; }
chmod +x "$RUN_QUEUE_SH" "$HERE/scan.py" "$HERE/uninstall.sh" 2>/dev/null || true
mkdir -p "$LOG_DIR" "$HOME/Library/LaunchAgents"

sed -e "s#__RUN_QUEUE_SH__#$RUN_QUEUE_SH#g" \
    -e "s#__LOG_DIR__#$LOG_DIR#g" \
    -e "s#__HOME__#$HOME#g" \
    "$SRC" > "$DEST"
echo "wrote $DEST"

# launchctl bootstrap is the modern load; bootout first so a re-run replaces cleanly.
DOMAIN="gui/$(id -u)"
launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true
launchctl bootstrap "$DOMAIN" "$DEST"
launchctl enable "$DOMAIN/$LABEL"
echo "loaded $LABEL into $DOMAIN -- fires daily at 22:00 local (10pm)"
echo
launchctl print "$DOMAIN/$LABEL" | grep -E "state|program|next" || true
echo
echo "Run it once now:   $RUN_QUEUE_SH"
echo "Or force via launchd: launchctl kickstart -k $DOMAIN/$LABEL"
