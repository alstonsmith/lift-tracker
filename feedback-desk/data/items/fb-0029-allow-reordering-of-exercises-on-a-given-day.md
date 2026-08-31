---
id: fb-0029
title: Allow reordering of exercises on a given day
app: lift-tracker
area: week
type: polish
severity: low
status: done
reporter: ""
tags: []
brief: wo-0010
created: 2026-08-25T02:30:54Z
updated: 2026-08-25T02:41:55Z
context: {"source": "lift-tracker", "capturedAt": "2026-08-25T02:29:37.846Z", "url": "http://192.168.4.44:8440/#week", "view": "week", "weekStart": "2026-08-24", "weekTypes": ["2026-08-24:lift", "2026-08-25:rest", "2026-08-26:rest", "2026-08-27:rest", "2026-08-28:rest", "2026-08-29:rest", "2026-08-30:rest"], "expandedEntries": [], "viewport": "1920x849", "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36", "appRev": 293, "counts": {"exercises": 11, "days": 1, "entries": 4, "sets": 18}, "errors": []}
---

## What happened

Allow exercises in a given day to be reordered. Also, when adding new exercises to a day, let's add them in order. (Right now the sequencing is all over the place; sometimes a new exercises is added to the top of the day's list, sometimes to the bottom)

## Resolution

Two changes in `app/lift-tracker.html`:

- **Reordering.** Each exercise row now has a small ▲▼ control (`.entry-move`) in its
  header. Clicking either calls a new `moveEntry(entryId, dir)`, which swaps the entry
  with its neighbour and renumbers the whole day's entries 0..n-1 in one batched `patch`
  mutation, so `order` can never drift out of sync with what's on screen. Top/bottom
  buttons disable themselves rather than being no-ops. Click handlers `stopPropagation()`
  so pressing them doesn't also toggle the entry open/closed (they sit inside the same
  clickable header).

- **The append bug.** Found the actual cause while testing against the real data file:
  `addExercise()` was assigning a new entry's `order` as `entriesFor(day.id).length` — a
  count. Once any exercise had ever been removed from a day, the count under-shoots the
  highest `order` still in use, so a newly added exercise could collide with an existing
  one's order value and sort unpredictably instead of landing at the bottom. Replaced with
  `nextEntryOrder(dayId)`, which takes `max(existing orders) + 1`. This isn't hypothetical:
  the live data file (`data/lift-tracker.json`) had exactly this collision on today's lift
  day (two entries both at `order: 3`) before this fix, from before `order` was renumbered
  by any move; fixed by the renormalization above.

Verified in-browser end to end: reordering two exercises persists after a full page
reload, and the fix was confirmed against the real data file's pre-existing order
collision (see above) rather than just synthetic test data.
