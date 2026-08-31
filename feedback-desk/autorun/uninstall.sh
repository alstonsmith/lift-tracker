#!/bin/bash
# Stop and remove the daily Lift Tracker Feedback Desk queue runner. Leaves logs/ alone.
set -euo pipefail
LABEL="com.lift-tracker.feedback-queue"
DEST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null && echo "booted out $LABEL" || echo "$LABEL was not loaded"
rm -f "$DEST" && echo "removed $DEST" || true
