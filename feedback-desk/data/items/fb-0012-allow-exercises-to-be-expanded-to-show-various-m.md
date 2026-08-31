---
id: fb-0012
title: Allow exercises to be expanded to show various 'max weight' values at different reps
app: lift-tracker
area: library
type: feature
severity: high
status: done
reporter: ""
tags: []
brief: wo-0003
created: 2026-08-24T21:12:33Z
updated: 2026-08-24T21:28:32Z
context: {"source": "lift-tracker", "capturedAt": "2026-08-24T21:08:45.078Z", "url": "http://192.168.4.44:8440/#library", "view": "library", "weekStart": "2026-08-24", "weekTypes": ["2026-08-24:lift", "2026-08-25:rest", "2026-08-26:rest", "2026-08-27:rest", "2026-08-28:rest", "2026-08-29:rest", "2026-08-30:rest"], "expandedEntries": [], "viewport": "1920x849", "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36", "appRev": 67, "counts": {"exercises": 11, "days": 1, "entries": 4, "sets": 12}, "errors": []}
---

## What happened

By default, each exercise should show its 1 rep max weight in the Library. When an exercise row is expanded, beneath it we should see what weight would be lifted for 2 reps max, 3 reps max, 4 reps max, etc. down to 12+ reps. The weight shown is linear and is based on [1RM weight] - [max reps] x [pip]. Example: if an exercise's 1 rep max is 200lbs, then the 3-rep max is (200 - (3 x 2.5%*200 =)) 185lbs. In this sense, only the 1RM weight value is editable, since the other reps are direct calculations from this

## Resolution

Library rows now expand. The collapsed row shows the one-rep max; the `▸` at its left
opens a table of what that implies for **2 through 12 reps**, one pip lighter per rep.

`app/lift-tracker.html`:

- `repMaxWeight(max, reps) = max − reps × pip`, exactly the rule in the report: a 200 lb
  single gives 200 − 3 × 5 = 185 for a triple. Since a pip is a fixed 2.5%, twelve reps is
  always 70% of the single.
- `repMaxHTML()` renders reps 2..12 as chips that reflow to however many fit the width —
  twelve rows of arithmetic is more than a glance wants as a table, and it keeps the phone
  layout to two columns instead of a sideways scroll.
- **None of them are inputs**, which is the point of the report: only the one-rep max is
  stored and editable, so a three-rep max cannot drift out of step with the single it came
  from. There is a test asserting the expander contains zero `<input>`s.
- Which rows are open is client-side only (`state.libExpanded`), matching how the week
  view already treats expanded exercises: it is about the screen in your hand, not the
  training log, so the laptop can't fold up a row on the phone.
- A movement with no max yet (Pull-up, at 0) gets "Set a max weight to see the rep maxes
  it implies" instead of eleven zeroes.
- Typing in the max weight box re-derives the open table live, without waiting for the
  debounced save.

Rows are labelled by rep count and stop at 12. The report said "down to 12+ reps"; a row
labelled `12+` would be the only inexact number in a table of exact ones, so it is `12
reps` and the note above the chips states the rule.
