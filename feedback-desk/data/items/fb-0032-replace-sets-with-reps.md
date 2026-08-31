---
id: fb-0032
title: Replace "sets" with "reps
app: lift-tracker
area: library
type: feature
severity: low
status: done
reporter: ""
tags: []
brief: wo-0011
created: 2026-08-25T02:39:55Z
updated: 2026-08-25T03:00:14Z
context: {"source": "lift-tracker", "capturedAt": "2026-08-25T02:37:11.936Z", "url": "http://192.168.4.44:8440/#library", "view": "library", "weekStart": "2026-08-24", "weekTypes": ["2026-08-24:lift", "2026-08-25:rest", "2026-08-26:rest", "2026-08-27:rest", "2026-08-28:rest", "2026-08-29:rest", "2026-08-30:rest"], "expandedEntries": ["en_mt7t4p3bdy4g"], "viewport": "1920x849", "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36", "appRev": 293, "counts": {"exercises": 11, "days": 1, "entries": 4, "sets": 18}, "errors": []}
---

## What happened

Instead of showing "sets" in the Library, show "reps" so that "Max Weight" represents the maximum weight that could be lifted with a given rep scheme. Then, when the exercise row is expanded (to show max weight at other rep ranges), you can compute from the given details by reverse-engineering a 1RM (every additional rep you're able to perform reduces your max weight by 2.5%, starting at 95% of 1RM for 2 reps)

## Resolution

The Library's "Sets" column is now "Reps" (`app/lift-tracker.html`), a new `maxReps`
field on each exercise (1..12, defaulting to 1) meaning "Max Weight is good for this many
reps." Added `estimatedOneRepMax(ex)`, which inverts the existing rep-max formula to
recover a true one-rep max from that pair: `reps <= 1 ? weight : weight / (1 -
reps*PIP_FRACTION)`. That existing formula (`repMaxWeight`) is exactly "95% of 1RM at 2
reps, 2.5% lighter per rep after," so this is its literal inverse, not a new model.

Every place that used to read `ex.defaultWeight` as a literal one-rep max now goes
through `estimatedOneRepMax(ex)` instead: the Pip column, the rep-max expander (2..12
reps), and the Peak scheme's rung pricing in `planSets()` and its add-dialog preview. The
raw Max Weight input itself still stores and edits the literal number you type (the
weight for Reps reps) — only the derived numbers change.

**Backward compatible by construction:** `maxReps` defaults to 1 wherever it's missing
(`num(ex?.maxReps, 1)`), and at reps=1 `estimatedOneRepMax` returns the typed weight
unchanged (no division). So every exercise already in your library — none of which have
`maxReps` set — computes exactly as before; nothing needs migrating.

Verified in-browser on a throwaway test exercise: Max Weight 300 lb at 5 reps produced
"1 pip = 8.6 lb ... off an estimated 342.86 lb one-rep max" (300 / 0.875 = 342.86, and
inverting back through `repMaxWeight` at 5 reps reproduces ~300), with the rest of the
2..12 table falling out correctly and floored to 5 lb per fb-0031.

Note: the old "Sets" number (how many sets get created when a movement is added to a
day) still exists internally as `defaultSets` — it just isn't shown in the Library
anymore, since the report asked for that slot to become Reps. It's frozen at whatever it
was last set to (3 for most movements) and still feeds the add-exercise dialog's default
Sets count there.
