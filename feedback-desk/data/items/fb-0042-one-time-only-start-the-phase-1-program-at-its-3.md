---
id: fb-0042
title: (One-time only) start the Phase 1 program at its 3rd week, starting week of Aug 31st
app: lift-tracker
area: ""
type: feature
severity: low
status: done
reporter: ""
tags: []
brief: wo-0016
created: 2026-08-31T14:39:48Z
updated: 2026-08-31T14:39:55Z
context: {"source": "feedback-desk", "capturedAt": "2026-08-31T14:39:48.216Z"}
---

## Resolution

Done as a genuine one-time data operation, not a new app feature — no "start at week N"
option was added to the Program tab's UI or code. Performed by calling the real,
already-tested engine functions (`generateProgramWeek`, `programResolveExercise`,
`estimatedOneRepMax`) directly against the running app with a custom bootstrap, the same
functions a normal activation calls, just seeded to skip ahead:

- Found and removed a stale `cancelled` program instance already sitting in your data
  (from an earlier attempt at this, it looked like — `startDate` was already Aug 31,
  `weeksGenerated: 1`, but its generated entries had already been deleted, leaving five
  empty `lift`-type day shells for Aug 31–Sep 4 with nothing in them).
- Created a fresh program instance with `startDate` set 14 days before this week (Aug 17)
  and `weeksGenerated: 2` — weeks 1 and 2 are never generated, just treated as already
  happened, so week 3 is the first real output.
- Called the week-3 generator for real. Static exercises' progression correctly read
  "week 2" from your actual already-logged Aug 24 week (the same week the program's own
  slots were derived from) — no synthetic data needed, it's real history.

**Verified exactly**, against the real result: Bench/Squat/Deadlift priced off week 3's
pip row (offsets 2/3/6/3/2) — Bench came out 180/185/200/185/180 off a 225 lb max,
hand-confirmed against the formula. Cable Crunch correctly held flat at 55×20 (missed a
rep target in the reference week); RDL correctly progressed 195→200; Ab Wheel correctly
took the weight-0 path, +2 reps (10→12) rather than +weight. No conflicts. The Program
tab now reads "Week 3 of 6 · started Aug 17", and week 3's real dates (Aug 31–Sep 4) show
it in the Week view. This program will now keep advancing on its own, weeks 4–6, exactly
as the normal feature does — nothing further needed.

Found and flagged, not fixed (out of scope for this item): `tools/run-tests.sh` silently
never reaches the Feedback Desk suite. It has `set -euo pipefail` and calls
`node tools/smoke-test.mjs` unguarded — since that suite has 5 known pre-existing
failures, `set -e` aborts the whole script right there, before the Feedback Desk section
even runs. This means every "N passed, N failed" report from this suite all session
(including this one) never actually exercised the Feedback Desk's own suite. A one-line
fix (`|| true` after the smoke-test.mjs call, matching how the desk check already
tolerates its own `curl` failure) would resolve it — flagging rather than fixing since it
wasn't part of what was asked here.