---
id: fb-0036
title: Add + incrementing button to reps and RIR
app: lift-tracker
area: week
type: feature
severity: low
status: done
reporter: ""
tags: []
brief: wo-0013
created: 2026-08-25T03:30:22Z
updated: 2026-08-25T03:30:46Z
context: {"source": "lift-tracker", "capturedAt": "2026-08-25T03:29:08.976Z", "url": "http://192.168.4.44:8440/#week", "view": "week", "weekStart": "2026-08-24", "weekTypes": ["2026-08-24:lift", "2026-08-25:rest", "2026-08-26:rest", "2026-08-27:rest", "2026-08-28:rest", "2026-08-29:rest", "2026-08-30:rest"], "expandedEntries": ["en_mt7t4kzsmrt0"], "viewport": "1920x849", "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36", "appRev": 309, "counts": {"exercises": 11, "days": 1, "entries": 4, "sets": 18}, "errors": [{"kind": "unhandledrejection", "detail": "Failed to set the 'innerHTML' property on 'Element': The node to be removed is no longer a child of this node. Perhaps it was moved in a 'blur' event handler?", "at": "2026-08-25T03:25:48.749Z"}]}
---

## What happened

Add a convenience + button that can be tapped to increment the Reps value by 1, and ditto for RIR. (When tapped, if the field is empty, enter '0' instead for the first tap and then increment by 1 for each subsequent tap)

## Resolution

Added a small "+" button next to each set's Reps box and next to its RIR box in
`app/lift-tracker.html` (`setHTML()`), wired in `wireWeek()`. Tapping reads the set's
current value straight from `state.doc` (not the input's possibly-still-typing DOM
value), treats empty as the start-at-0 case, otherwise adds 1, and caps at the same
limits typing already respects (`MAX_REPS` 99, `MAX_RIR` 9) — then patches it, so it
saves and re-renders exactly like typing would. Unlike the existing delete button
(`.del`), these are always visible rather than hover-gated: this app's primary surface is
a phone at the rack, where hover doesn't exist, and a tap target that only appears on
hover is one a touchscreen can never reach.

Fitting two more elements into the set-row, which was already tight enough to carry a
container query hiding the word "reps" under 278px, took some adjusting: that threshold
moved up to 320px (the label needs to give way sooner now), and a second one was added
that also hides the "RIR" label under 250px. Tested at the narrowest realistic width (a
~282px-wide set-row container, from forcing 7 day-cards across a 2200px-wide desktop
viewport) and at an iPhone 13 viewport — both stay on one line, no horizontal scroll, no
console errors.

Also flushes any pending debounced save for that set before applying the bump, so tapping
+1 right after typing into the same box can't have its result overwritten when that
stale save lands 600ms later — the same flush-before-commit pattern the app already uses
for onchange/blur elsewhere.

See fb-0035's resolution for a related JS error fix (an unhandled promise rejection from
`mutate()`'s `render()`) found in this item's own captured error context and fixed in the
same pass.
