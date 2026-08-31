---
id: fb-0007
title: Show "Max Weight" instead of "Weight
app: lift-tracker
area: library
type: feature
severity: high
status: done
reporter: ""
tags: []
brief: wo-0003
created: 2026-08-24T20:57:47Z
updated: 2026-08-24T21:28:32Z
context: {"source": "lift-tracker", "capturedAt": "2026-08-24T20:55:56.599Z", "url": "http://192.168.4.44:8440/#library", "view": "library", "weekStart": "2026-08-24", "weekTypes": ["2026-08-24:lift", "2026-08-25:rest", "2026-08-26:rest", "2026-08-27:rest", "2026-08-28:rest", "2026-08-29:rest", "2026-08-30:rest"], "expandedEntries": [], "viewport": "1920x849", "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36", "appRev": 67, "counts": {"exercises": 11, "days": 1, "entries": 4, "sets": 12}, "errors": []}
---

## What happened

The current exercise library shows Sets and Weight for that set, but I instead want to see "Max Weight" for a specific number of reps. By default, show 1 rep max weights

## Resolution

The Library's weight column is now **Max Weight** — a one-rep max — and it is the only
weight on the tab you type. Everything else on the row is derived from it.

- `app/lift-tracker.html`, `renderLibrary()` / `libRowHTML()`: the column header reads
  `Max Weight`, the input is `data-ex-max`, and its tooltip says what the number is:
  "One-rep max — the weight every other number on this row comes from".
- The stored field is unchanged (`exercises[].defaultWeight`), so no migration was needed
  and nothing about how a day is logged moved.
- `server/serve_lift_tracker.py`: the seed's comment now says the number is a one-rep max.
- `README.md`: "The library" and "Where the expected weight comes from" rewritten to match.

**One thing worth a decision.** That same number is still what pre-fills the sets of a
movement with *no history yet* (`suggestWeight()`), which used to be a working weight and
is now your max. Add a brand-new movement to a day and its three sets come up at your
single. Once the movement has been logged once, history takes over and the library is
never consulted again, so this only bites on the first session. It was left as-is
deliberately: seeding at some fraction of the max means picking a target rep count on
your behalf, and there was nothing in the report saying which. Say the word and it can
seed at any rep max you like — the 5-rep (87.5% of the single) is the usual pick.
