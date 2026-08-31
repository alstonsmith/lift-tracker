---
id: fb-0040
title: "Program: \"Phase 1: Volume\""
app: lift-tracker
area: ""
type: feature
severity: low
status: done
reporter: ""
tags: []
brief: wo-0015
created: 2026-08-31T03:06:09Z
updated: 2026-09-01T00:00:00Z
context: {"source": "feedback-desk", "capturedAt": "2026-08-31T03:06:09.064Z"}
---

## What happened

Add a new program called "Phase 1: Volume". 6 week program that focuses on pushing 2-rep max weights on big lifts, while accumulating volume in those lifts & in accessory lifts.
This program runs Mon to Fri, with Sat and Sun as rest days. Week 1-4 focus on progression; week 5 focuses on deloading & recovering; week 6 tests heavy lifts.
Mon, Wed, Thurs are 'big lift' days; Tues and Thurs are 'accessory' days.
You can derive the Mon to Fri exercises from the existing logs under week of Aug 24th.
For the Peak exercises, the progression should look like:
- week 1 is 75% of 1RM base with set 1 = +0 pips, set 2 = +1 pip, set 3 = +2 pips, set 4 = +1 pip, set 5 = +0 pips
- week 2 is 75% of 1RM base with +1 pip / +2 pips / +4 pips / +2 pips / +1 pip
- week 3 is 75% of 1RM base with +2 pips / +3 pips / +6 pips / +3 pips / +2 pips
- week 4 is 75% of 1RM base with +2 pips / +4 pips / +7 pips / +4 pips / +2 pips
- week 5 is 75% of 1RM base with +0 pips across all sets
- week 6 is 75% of 1RM base with +0 pips / +1 pip / +9 pips / +1 pip / +0 pips

For the static exercises, progression will be: for any exercise where no set has RIR 0 AND all reps were at least met AND weight is not set to 0, then add +5lbs to the next week's weight. And if no set has RIR 0 AND at least all reps were met but weight is 0, then add 2 reps next week instead. Else, just port over the prior week's weights & rep target

## Open question

This program depends on the program engine in [[fb-0039]], which isn't built yet and has
its own open questions — so this item is blocked on that first. Beyond that, the
program's own definition has gaps I can't fill without guessing:

**1. Day roles — likely typo.** "Mon, Wed, Thurs are 'big lift' days; Tues and Thurs are
'accessory' days" lists Thursday twice. The logs for the week of Aug 24 have Peak lifts
on **Mon / Wed / Fri** and pure accessory work on **Tue / Thu**. Confirm the intent is
**Mon/Wed/Fri = big-lift days, Tue/Thu = accessory days**.

**2. Exercise lists derived from week of Aug 24.** From the store, that week was:
- **Mon:** Barbell Bench Press, Barbell Back Squat, Deadlift (Peak) + Cable Crunch
- **Tue:** Pendlay Row, OH Triceps Xt, Seated Leg Curl, Seated Neutral Row, Pause Bench
  Press, Seated Alt Curl, Face Pull
- **Wed:** RDL, Incline Bench Press (Peak), Front Squat (Peak), Ab Wheel
- **Thu:** Lat Pulldown, BB Hip Thrust, DB Shoulder Press, Preacher Curls, Dips, EZ Bar
  Curl, Lateral Raise
- **Fri:** Deadlift, Barbell Bench Press, Barbell Back Squat (Peak) + Sit Up

  So the "Peak / big lifts" are Bench, Squat, Deadlift (Mon & Fri) and Incline Bench +
  Front Squat (Wed); everything else including Wed's RDL is a "static" exercise. Confirm
  that's the slot list, and whether the user can swap movements per slot (per fb-0039) or
  these are fixed for this program.

**3. Peak progression specifics.**
   - The "+N pips" schedule you gave sets the *weight* per set. What are the **rep
     targets** for the 5 sets? The app's existing Peak scheme is 5·4·2·4·5. Your
     description ("pushing 2-rep max", set 3 gets the biggest bump) fits set 3 = the
     heavy double, so I'd reuse **5·4·2·4·5** unless you want different targets, and
     hold them constant across all 6 weeks.
   - "75% of 1RM base" = 10 pips below the one-rep max, which is exactly what the app's
     `peakWeight` already uses for a 5. Confirm **"1RM base" = the library's estimated
     one-rep max** for that movement (the number `estimatedOneRepMax()` derives from Max
     Weight + Reps), fixed at program start, not re-read each week.
   - So each set's weight = floor5( 1RM − (10 − weekPips[set]) × pip ). Week 3 set 3 is
     1RM − (10 − 6) = 1RM − 4 pips = 90%. Week 6 set 3 is 1RM − 1 pip = 97.5%. Is that
     the intent (week 6 "tests heavy lifts" at ~97.5% for a double)?

**4. Static progression rule details.**
   - "+5lbs" — literal flat 5 lb, or the exercise's own `increment` field (the library
     stores one per movement; some are 10)? I'll use a flat +5 unless told otherwise.
   - "all reps were at least met" = every set's logged `reps` ≥ its `targetReps`.
   - "no set has RIR 0" — a set with a **blank** RIR counts as *not* 0 (RIR is optional
     in the app). Confirm.
   - "add 2 reps" when weight is 0: applied to every set's `targetReps` (+2)?
   - What does week 1 seed from? Presumably the same Aug-24-week logged weights/targets
     as the starting point, then the rule runs week-over-week from there.

**5. Deload (wk5) and test (wk6) — accessories.** The pip schedule covers the Peak lifts.
On the accessory days, does week 5 also back off (e.g. hold weight, don't progress), and
does week 6 change anything for accessories, or do the static rules just keep running
through weeks 5–6 unchanged?

**6. Start week.** Which calendar Monday is week 1 — is that chosen at program-start time
in the fb-0039 setup UI, or fixed?

## Resolution

All six questions answered interactively; implemented as the `"phase1-volume"` entry in
`PROGRAMS` (`app/lift-tracker.html`), on top of the engine built for fb-0039.

1. **Day roles** confirmed Mon/Wed/Fri Peak, Tue/Thu accessory, as guessed from your logs.
2. **Slots** confirmed as derived, resolved by movement name at generation time
   (`programResolveExercise()` — prefers the most-recently-added Library row when a name
   is ambiguous; your store actually has two "Lat Pulldown" rows from a re-add, and this
   correctly picks the one your Thursday entries use). Fixed per slot, not swappable, per
   fb-0039's answer that only starting weight is user-adjustable.
3. **Peak progression:** your exact pip schedule went into `PROGRAM_PEAK_PIPS`, a 6×5
   table — not the guessed-at 5·4·2·4·5-rep-target version, the literal per-set-per-week
   numbers from your report. `estimatedOneRepMax()` locked at activation is the "1RM base."
   Hand-verified: week 2, 225 lb max, comes out 170/180/190/180/170 for the five sets,
   which is `floorWeight(225 - (10-offset)×5.625)` for offsets `[1,2,4,2,1]` — exact.
4. **Static progression** uses each exercise's own `increment` field (discovered it exists
   on every exercise, unused anywhere in the app until now — evidently built for exactly
   this) rather than a flat +5. "Reps met" = every set's reps ≥ target; blank RIR counts
   as not-0; the weight-0 case adds +2 reps instead. Week 1 seeds from whatever's already
   logged (or the library default, for a movement with none) — never a hardcoded copy of
   your specific numbers, so a different week or a different user's library still work.
5. **Deload (week 5) / test (week 6) for accessories** — this needed real back-and-forth,
   not a guess: week 5 drops a set, cuts the previous week's weight by 25% (**rounded up**
   to the nearest 5 lb — a deliberate exception to the app's usual floor-to-5, since
   erring heavy on a deload is the safe side), and holds reps flat. Week 6 resumes from
   week 4 (skipping over week 5 entirely) + one increment, unconditionally, sets back to
   normal.
6. **Start week** = the calendar week the program is activated in (per fb-0039).

**Verified** as part of fb-0039's end-to-end test against the real store (same session,
same activation): week 1 correctly produced zero new rows against your already-logged
Aug 24 week; week 2 correctly generated fresh with the Peak formula confirmed exactly and
both static branches (progress / hold-flat) confirmed against your actual logged
performance that week (Cable Crunch held at 55×20 after missing a rep target on set 3;
RDL progressed 195→200 after clearing every set). All test data deleted afterward and the
store confirmed to match a pre-test snapshot exactly.

Weeks 5 and 6's formulas were verified separately, in-browser but against fabricated
in-memory data rather than your real store (calling `programPlanSlot()` directly with a
synthetic "week 4" of 120 lb x 3 sets, never touching `mutate()`), since reaching week 5
for real needs either five real weeks to pass or hand-editing `weeksGenerated` against
your actual program -- the wrong tradeoff for this pass. Confirmed exact: week 5 gives 90 lb x 2 sets off 120 lb (120 x 0.75 = 90 exactly), and
gives 95 lb -- not 90 -- off 122 lb (122 x 0.75 = 91.5, and the round-*up* takes it to 95),
confirming the deliberate away-from-the-app's-usual-floor rounding actually behaves that
way rather than only looking right on a number that didn't need rounding. Week 6 gives
125 lb x 3 sets off a 120 lb week 4 (120 + the 5 lb increment, sets back to normal). A
live check once the program's actually run six real weeks is still worth doing, or a
dedicated test fixture if this becomes permanent.
