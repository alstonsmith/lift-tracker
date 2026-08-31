---
id: fb-0041
title: Rename this feedback desk to "Lift Tracker Feedback Desk
app: lift-tracker
area: ""
type: polish
severity: low
status: done
reporter: ""
tags: []
brief: wo-0016
created: 2026-08-31T04:10:43Z
updated: 2026-08-31T04:13:40Z
context: {"source": "feedback-desk", "capturedAt": "2026-08-31T04:10:43.240Z"}
---

## Resolution

Renamed everywhere it appears as a display name (not the internal `feedback-desk`
directory/path or the `"server": "feedback-desk"` API identifier, both left alone —
this was about the name people see, not the plumbing):

- `feedback-desk/app/feedback-desk.html`: `<title>`, `<h1>`, the intro comment, the
  "Work on this feedback item..." copy-prompt string, and the "can't reach the server"
  error message.
- `feedback-desk/server/serve_feedback_desk.py`: the module docstring, the argparse
  description, the startup banner, and — notably — the strings baked into every
  generated `QUEUE.md` and work-order body (`data/QUEUE.md`, `data/briefs/*.md` all
  pick this up automatically next time the server writes them; regenerated once already
  to confirm).
- `feedback-desk/README.md`, the top-level `README.md`, `app/lift-tracker.html` (the
  Feedback button's modal copy and its own error message), `tools/run-tests.sh`,
  `tools/feedback-smoke-test.mjs`, and the `feedback-desk/autorun/` scripts + README
  built for wo-0013's scheduler.

Restarted the Feedback Desk server to pick up the Python change. Verified in-browser at
both desktop and iPhone-13 mobile widths: title bar and header both read "Lift Tracker
Feedback Desk", wraps cleanly to a second line on mobile, no horizontal scroll, no
console errors.