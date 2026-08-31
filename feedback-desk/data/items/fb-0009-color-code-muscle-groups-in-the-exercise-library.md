---
id: fb-0009
title: Color-code muscle groups in the exercise library
app: lift-tracker
area: library
type: polish
severity: low
status: done
reporter: ""
tags: []
brief: wo-0003
created: 2026-08-24T20:59:20Z
updated: 2026-08-24T21:28:32Z
context: {"source": "lift-tracker", "capturedAt": "2026-08-24T20:58:15.218Z", "url": "http://192.168.4.44:8440/#library", "view": "library", "weekStart": "2026-08-24", "weekTypes": ["2026-08-24:lift", "2026-08-25:rest", "2026-08-26:rest", "2026-08-27:rest", "2026-08-28:rest", "2026-08-29:rest", "2026-08-30:rest"], "expandedEntries": [], "viewport": "1920x849", "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36", "appRev": 67, "counts": {"exercises": 11, "days": 1, "entries": 4, "sets": 12}, "errors": []}
---

## What happened

Muscle groups should be color coded and should capture the following: Quads, Hams, Glutes, Chest, Delts (R), Delts (F), Delts (S), Back, Abs, Neck, Biceps, Triceps

## Resolution

Muscle groups are now the twelve you listed, in your order, each with its own colour.

`app/lift-tracker.html`:

- `MUSCLE_GROUPS` is now a list of `{ id, label, hue }` — Quads, Hams, Glutes, Chest,
  Delts (R), Delts (F), Delts (S), Back, Abs, Neck, Biceps, Triceps.
- The group cell is a coloured chip. The row carries the group's hue as a `--g-h` custom
  property and one CSS rule (`.mg`) turns it into background, text and border, with three
  different lightnesses under `prefers-color-scheme: dark`. That is what keeps it to one
  rule instead of twelve colours restated per theme, and it stays a real `<select>` — the
  chip is the editor.
- Hues are assigned so that anatomical families sit next to each other: the three delt
  heads on adjacent oranges, the legs on adjacent greens/teals, biceps and triceps on
  adjacent violets. Everything else is spread wide enough to tell apart at a glance.
- "No group" is a real state and comes out grey from the same rule.

**Older groups.** The previous vocabulary was coarser (`legs`, `arms`, `shoulders`,
`core`). `LEGACY_GROUPS` translates only what is unambiguous — anything this list splits
(legs three ways, arms two) shows as unset rather than being auto-filed under a guess,
because "Triceps Pushdown → Biceps" is worse than a blank asking to be filled in.

Your existing eleven movements were migrated by name through the API, since the movement
name settles it where the old group didn't: Barbell Back Squat → Quads, Overhead Press →
Delts (F), Romanian Deadlift → Hams, Dumbbell Curl → Biceps, Triceps Pushdown → Triceps,
Cable Crunch → Abs. Deadlift, Barbell Row, Lat Pulldown and Pull-up were already on `back`,
which is still a group in the new list, so they were left exactly as they were.
`server/serve_lift_tracker.py`'s seed uses the new ids too, for a fresh install.
