---
id: fb-0011
title: Compute "pips" based on 1 rep max weights
app: lift-tracker
area: library
type: feature
severity: high
status: done
reporter: ""
tags: []
brief: wo-0003
created: 2026-08-24T21:08:42Z
updated: 2026-08-24T21:28:32Z
context: {"source": "lift-tracker", "capturedAt": "2026-08-24T21:06:37.414Z", "url": "http://192.168.4.44:8440/#library", "view": "library", "weekStart": "2026-08-24", "weekTypes": ["2026-08-24:lift", "2026-08-25:rest", "2026-08-26:rest", "2026-08-27:rest", "2026-08-28:rest", "2026-08-29:rest", "2026-08-30:rest"], "expandedEntries": [], "viewport": "1920x849", "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36", "appRev": 67, "counts": {"exercises": 11, "days": 1, "entries": 4, "sets": 12}, "errors": []}
---

## What happened

A "pip" is just 2.5% of a given 1 rep max weight (so if 1 rep max is 200lbs, then 1 pip = 5 lbs). Show what 1 pip is (to 1 decimal place) as a separate column to the right of the max weight

## Resolution

There is now a **Pip** column immediately to the right of Max Weight, showing 2.5% of that
movement's one-rep max to one decimal place. A 200 lb max reads `5.0`; a 25 lb curl reads
`0.6`.

`app/lift-tracker.html`:

- `PIP_FRACTION = 0.025`, with `pipFor()` and `fmtPip()` next to the other formatters.
  `fmtPip` always pads to one decimal, so a column of pips reads as one kind of number
  rather than a mix of `5` and `0.63`.
- The cell is text, not an input — it is derived, and a box would invite an edit with
  nowhere to go. It gets the same right-aligned tabular width as the number inputs beside
  it so the columns line up.
- It updates on the keystroke, not on the save. The library's saves are debounced 600ms,
  which is long enough for the pip to sit visibly wrong next to the box you are typing in,
  so `wireLibrary()` recomputes the cell (and the open rep-max table) straight into the DOM
  and lets the round trip catch up.
- `tools/smoke-test.mjs` asserts the displayed pip is 2.5% of the displayed max.
