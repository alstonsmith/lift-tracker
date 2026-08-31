---
id: fb-0031
title: Floor weights to the nearest 5lb
app: lift-tracker
area: week
type: polish
severity: low
status: done
reporter: ""
tags: []
brief: wo-0010
created: 2026-08-25T02:33:55Z
updated: 2026-08-25T02:41:55Z
context: {"source": "lift-tracker", "capturedAt": "2026-08-25T02:32:30.463Z", "url": "http://192.168.4.44:8440/#week", "view": "week", "weekStart": "2026-08-24", "weekTypes": ["2026-08-24:lift", "2026-08-25:rest", "2026-08-26:rest", "2026-08-27:rest", "2026-08-28:rest", "2026-08-29:rest", "2026-08-30:rest"], "expandedEntries": ["en_mt7t4p3bdy4g"], "viewport": "1920x849", "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36", "appRev": 293, "counts": {"exercises": 11, "days": 1, "entries": 4, "sets": 18}, "errors": []}
---

## What happened

Instead of displaying fractional weights (e.g. when selecting the Peak rep scheme), round weights down to the nearest 5lb (e.g. everything between 65 and 70 (not-inclusive) get rounded down to 65)

## Resolution

Added a `floorWeight(w)` helper in `app/lift-tracker.html` (`Math.floor(w / 5) * 5`) and
applied it at the two places the app computes a fractional weight from the pip model:

- `peakWeight()` — the per-rung weight for the Peak scheme (used in the add-exercise
  preview and in the sets it actually creates).
- `repMaxWeight()` — the Library's rep-max expander (the 2..12 rep table under a movement).

Weights you type yourself (a set's weight box, the Library's one-rep max, the new Static
weight field from fb-0030) are left untouched — this only rounds numbers the app derives,
not numbers you chose. Verified in-browser: a Peak-scheme preview off a 280 lb max now
shows 210/220/245/220/210 lb (previously fractional), and the Library rep-max table shows
only multiples of 5. Existing sets already logged before this change keep whatever weight
they were created with.
