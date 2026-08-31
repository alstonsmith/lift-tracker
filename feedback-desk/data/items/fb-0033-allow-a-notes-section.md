---
id: fb-0033
title: Allow a 'notes' section
app: lift-tracker
area: library
type: feature
severity: low
status: done
reporter: ""
tags: []
brief: wo-0011
created: 2026-08-25T02:40:34Z
updated: 2026-08-25T03:00:14Z
context: {"source": "lift-tracker", "capturedAt": "2026-08-25T02:40:00.262Z", "url": "http://192.168.4.44:8440/#library", "view": "library", "weekStart": "2026-08-24", "weekTypes": ["2026-08-24:lift", "2026-08-25:rest", "2026-08-26:rest", "2026-08-27:rest", "2026-08-28:rest", "2026-08-29:rest", "2026-08-30:rest"], "expandedEntries": ["en_mt7t4p3bdy4g"], "viewport": "1920x849", "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36", "appRev": 293, "counts": {"exercises": 11, "days": 1, "entries": 4, "sets": 18}, "errors": []}
---

## What happened

This lets the user add details about a specific exercise, e.g. form tips or technique cues

## Resolution

Added a `notes` string field to each exercise. It shows as a textarea labeled "Notes"
inside the same disclosure the rep-max table already uses — click a movement's caret in
`app/lift-tracker.html` to reveal it — so the always-visible row stays exactly as
compact as it was (relevant for wo-0012/fb-0034, worked in the same session). Saved via
the same debounced-patch wiring every other Library field uses (`wireLibrary`'s generic
`field()` helper, which just reads `.value` and works on a textarea the same as an
input). Verified in-browser: typed a note, reloaded the page, and it was still there.
