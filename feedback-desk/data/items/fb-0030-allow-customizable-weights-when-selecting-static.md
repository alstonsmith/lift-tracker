---
id: fb-0030
title: Allow customizable weights when selecting 'static' rep scheme
app: lift-tracker
area: week
type: polish
severity: low
status: done
reporter: ""
tags: []
brief: wo-0010
created: 2026-08-25T02:32:10Z
updated: 2026-08-25T02:41:55Z
context: {"source": "lift-tracker", "capturedAt": "2026-08-25T02:30:57.170Z", "url": "http://192.168.4.44:8440/#week", "view": "week", "weekStart": "2026-08-24", "weekTypes": ["2026-08-24:lift", "2026-08-25:rest", "2026-08-26:rest", "2026-08-27:rest", "2026-08-28:rest", "2026-08-29:rest", "2026-08-30:rest"], "expandedEntries": [], "viewport": "1920x849", "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36", "appRev": 293, "counts": {"exercises": 11, "days": 1, "entries": 4, "sets": 18}, "errors": []}
---

## What happened

In a 'static' rep scheme, the default weight provided is pulled from the Library. Let's provide the ability to set the weight, with the default being whatever's in the Library

## Resolution

Added a Weight field to the Static side of the add-exercise dialog in `app/lift-tracker.html`,
next to the existing Sets and Reps fields. It's a free-text decimal input (like the set-row
weight boxes), pre-filled with the same suggestion the app already used silently —
`suggestWeight()`: your last session's weight for that movement, or the Library's one-rep
max if you've never logged it. Editing it updates the "N sets" preview live, and the typed
value (not the suggestion) is what `planSets()` uses when you hit Add; clearing the field
back to empty falls back to the suggestion again. `planSets()` and the input-cleaning
wiring in `wireLibrary`'s dialog counterpart were both updated to plumb this through — the
Peak scheme is untouched, since it's deliberately always pinned to the Library max, not to
history. Verified in-browser: opening the dialog on a movement shows a real number in the
Weight box, typing a new value updates the preview line immediately.
