---
id: fb-0035
title: Allow users to set  >12 reps in the Library
app: lift-tracker
area: library
type: bug
severity: low
status: done
reporter: ""
tags: []
brief: wo-0013
created: 2026-08-25T03:27:23Z
updated: 2026-08-25T03:28:05Z
context: {"source": "lift-tracker", "capturedAt": "2026-08-25T03:25:56.657Z", "url": "http://192.168.4.44:8440/#library", "view": "library", "weekStart": "2026-08-24", "weekTypes": ["2026-08-24:lift", "2026-08-25:rest", "2026-08-26:rest", "2026-08-27:rest", "2026-08-28:rest", "2026-08-29:rest", "2026-08-30:rest"], "expandedEntries": [], "viewport": "1920x849", "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36", "appRev": 309, "counts": {"exercises": 11, "days": 1, "entries": 4, "sets": 18}, "errors": [{"kind": "unhandledrejection", "detail": "Failed to set the 'innerHTML' property on 'Element': The node to be removed is no longer a child of this node. Perhaps it was moved in a 'blur' event handler?", "at": "2026-08-25T03:25:48.749Z"}]}
---

## What happened

Now really a bug, but right now, >12 reps entered snaps back to 12 reps in order to calculate the max weight. Let's let users enter some number greater than 12 reps, but we'll keep the max weight the same (so the weight at 12 reps covers 13+ reps as well)

## Resolution

The snap-back was in `wireLibrary()` in `app/lift-tracker.html`: the Reps field's commit
and its live-preview refresh both clamped the value itself to `REP_MAX_MAX` (12) before
storing it, so 20 got saved (and echoed back on the next render) as 12. Both now clamp to
`MAX_REPS` (99, the same ceiling the Week view's own rep box uses) instead — the number
you type is the number that's kept.

The "keep the max weight the same" half of the ask was already correct and needed no
change: `estimatedOneRepMax()` separately clamps the reps it feeds into the pip formula
to `REP_MAX_MAX`, so a 20-rep entry prices identically to a 12-rep one rather than the
linear discount running out past 12 reps and eventually going negative. Confirmed by
testing: Max Weight 400 at Reps 20 estimates "571.43 lb one-rep max" — exactly
400 / (1 − 12×2.5%), i.e. priced at 12 reps' worth of discount, not 20's — and 20 (not
12) is what's still in the box after a reload.

Added a note to the rep-max expander ("priced as a 12-rep max — 20 isn't modeled
further") and to the input's title and the panel's hint text, so this cap is visible
rather than a silent behavior.

Also fixed, as a related finding rather than something separately asked for: both this
item's and fb-0036's captured context included the same JS error
(`unhandledrejection: Failed to set the 'innerHTML' property on 'Element'...`). Traced it
to `mutate()` in `app/lift-tracker.html`: it calls `render()` outside any try/catch, and
since `mutate()` is `async`, a throw there becomes a rejected promise that nothing awaits
or catches — Chrome has a known quirk where a synchronous full-page `innerHTML` replace
that happens to run mid-blur (exactly what an `onchange` handler firing while tabbing off
a field does) can throw this way. Wrapped both of `mutate()`'s `render()` calls in a
`safeRender()` helper that catches and logs instead of throwing, so this self-healing
race (the next render repaints correctly regardless) can't surface as an unhandled
rejection again.
