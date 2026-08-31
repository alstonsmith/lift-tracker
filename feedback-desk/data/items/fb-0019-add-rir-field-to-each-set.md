---
id: fb-0019
title: Add "RIR" field to each set
app: lift-tracker
area: week
type: feature
severity: high
status: done
reporter: ""
tags: []
brief: wo-0006
created: 2026-08-24T21:58:31Z
updated: 2026-08-24T22:22:03Z
context: {"source": "lift-tracker", "capturedAt": "2026-08-24T21:57:35.443Z", "url": "http://192.168.4.44:8440/#week", "view": "week", "weekStart": "2026-08-24", "weekTypes": ["2026-08-24:lift", "2026-08-25:rest", "2026-08-26:rest", "2026-08-27:rest", "2026-08-28:rest", "2026-08-29:rest", "2026-08-30:rest"], "expandedEntries": [], "viewport": "1920x849", "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36", "appRev": 104, "counts": {"exercises": 11, "days": 1, "entries": 4, "sets": 12}, "errors": []}
---

## What happened

For each set being tracked, add a field called "RIR" which is a single digit integer representing Reps In Reserve (how many more reps I think I could have hit before hitting failure)

## Resolution

Every set now carries an **RIR** box — one digit, right of the rep count.

`app/lift-tracker.html`:

- Stored as `sets[].rir`, a string like `reps` is. The server merges unknown fields, so
  nothing there needed changing.
- `setHTML()` renders it after the reps box with a faint `RIR` label; `maxlength="1"`,
  `inputmode="numeric"`, and non-digits are dropped as you type rather than rejected on
  save — the same treatment the rep box already got, so the two are now wired by one
  `digitBox()` helper instead of two near-copies.
- **`0` is a real answer** and is stored as `"0"`, not as blank. It means you had nothing
  left, which is the most informative thing RIR can say, so it had to be distinguishable
  from "didn't record it".
- RIR does **not** gate the green "logged" state — that still means "reps are in". An
  optional field that turned a logged set grey by being empty would be worse than useless.
  It gets its own quieter colour (the `--info` blue) once filled.

**Enter now walks reps → that set's RIR → the next set's reps**, rather than reps → reps.
Logging a session is still one run down the card; RIR is on that run rather than a second
pass because you know how many you had left when you rack the bar, not ten minutes later.
If that turns out to be one keystroke too many for sets you don't score, it is a one-line
change back to reps-only.

Covered in `tools/smoke-test.mjs`: the box takes one digit, `"9x7"` becomes `9`, `0`
round-trips to the server as `"0"`, and the boxes start empty.
