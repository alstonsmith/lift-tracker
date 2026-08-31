---
id: fb-0010
title: Pre-built set/weight schemes
app: lift-tracker
area: week
type: feature
severity: high
status: done
reporter: ""
tags: []
brief: wo-0006
created: 2026-08-24T21:06:26Z
updated: 2026-08-24T22:22:03Z
context: {"source": "lift-tracker", "capturedAt": "2026-08-24T21:00:36.852Z", "url": "http://192.168.4.44:8440/#week", "view": "week", "weekStart": "2026-08-24", "weekTypes": ["2026-08-24:lift", "2026-08-25:rest", "2026-08-26:rest", "2026-08-27:rest", "2026-08-28:rest", "2026-08-29:rest", "2026-08-30:rest"], "expandedEntries": [], "viewport": "1920x849", "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36", "appRev": 67, "counts": {"exercises": 11, "days": 1, "entries": 4, "sets": 12}, "errors": []}
---

## What happened

Right now, when adding an exercise, it follows a pre-build scheme of Sets x Weight based on pulling data from the Library

## What I expected

When an exercise is added, the user selects the "Rep scheme" which can be "Static" (default; each set has the same number of reps at the same weight) and "Peak". If "Peak" is selected, then Sets is automatically set to 5, Reps are automatically set to 5, 4, 2, 4, 5, and weights are automatically populated based on %s of the Library's recorded 1 rep max (5 reps = 1RM minus 10 pips; 4 reps is 1RPM minus 8 pips; 2 reps is 1RM minus 5 pips). If "Static" is chosen as the rep scheme, then the user can enter the number of sets (single-digit integer) and each rep will have the same number of reps (also user-provided) with the same weight per set (pulled from the Library)

## Resolution

Adding an exercise now asks for a **rep scheme** first, in a small dialog that previews the
exact sets it is about to create.

`app/lift-tracker.html`:

- Picking a movement from **＋ Add exercise…** opens the dialog instead of creating sets
  immediately. **＋ New movement…** creates the movement and then opens the same dialog.
  Escape or **Cancel** backs out; the day is untouched until **Add**.
- `planSets(ex, date, plan)` is the whole of what a scheme is — it returns
  `{weight, targetReps}` pairs, and the dialog previews a scheme by calling the same
  function that will build it. There is no second description of a scheme to drift out of
  step with the first.
- The choice is recorded as `entries[].scheme`. A Peak entry wears a `PEAK` badge on its
  collapsed row; Static is the default and wears nothing, since a badge on every row
  carries one bit of information at the cost of reading like a label.
- Rep targets are stored per set as `sets[].targetReps` and shown as the faint `/8` beside
  the rep box: what the scheme asked for, next to what you did. **Not editable** — it is a
  note on the box, not a second number to keep in step. Sets from before this exists have
  no target and simply don't show one.

**Peak** — `PEAK_REPS = [5, 4, 2, 4, 5]`, priced off the library one-rep max exactly as the
report specifies: `PEAK_PIPS_OFF = {5: 10, 4: 8, 2: 5}`, so five reps at ten pips down (75%
of the max), four at eight (80%), the double at five (87.5%). It consults no history at
all — a wave is pinned to the max you have now, so changing the max in the Library
rescales the next one you add. If the movement has no max yet, the dialog says so rather
than silently offering five sets of zero.

Those offsets are deliberately not the Library's own rep-max table from wo-0003, where a
five is five pips down. Both live in the file with a comment saying why they differ: a rep
max is the most you could do; a working set inside a wave isn't meant to be.

**Static** — sets (one digit) and reps, both typed, both defaulting to what you did last
time: the library's set count for that movement, and the rep target of its most recent
session (falling back to 8). `suggestTargetReps()` walks history the same way
`suggestWeight()` does; the shared walk is now `priorSessions()`.

**One behaviour changed that's worth flagging.** The report says a Static scheme gives
"the same weight per set", and it now does — one weight across every set it creates. That
replaces the old set-for-set carry-forward, where squatting 135/135/145 on Monday made
Thursday start 135/135/145. Thursday now starts 135/135/135: the weight is still taken from
history (the *first* set of the last session), but the shape of that session no longer
comes with it. **＋ Set** on an existing exercise is unchanged and still carries the
previous set's weight forward, so dropping mid-session still works. I followed the report's
wording here because "the same weight per set" is explicit and is the contrast it draws
with Peak — but the old behaviour is one argument to `suggestWeight()` away if you'd rather
keep it.

`README.md` has a new **Rep schemes** section, and "Where the expected weight comes from"
was corrected — it still described the set-for-set rule.

`tools/smoke-test.mjs` drives the dialog: that it opens, that Static asks for sets and
reps, that Peak's five rungs come out at the right pips off the *current* max, that the
preview matches what gets created, that every Static set shares one weight, that targets
are stored and carried forward by ＋ Set, and that the entry records its scheme. The
history-dependent assertions are written as properties rather than fixed numbers, because
the suite runs against the real store and your maxes and past sessions move.
