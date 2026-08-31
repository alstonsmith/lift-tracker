---
id: fb-0039
title: Add a "program" feature that pre-populates weekly exercises & rep schemes for a set period of time
app: lift-tracker
area: ""
type: feature
severity: low
status: done
reporter: ""
tags: []
brief: wo-0015
created: 2026-08-31T00:02:02Z
updated: 2026-09-01T00:00:00Z
context: {"source": "feedback-desk", "capturedAt": "2026-08-31T00:02:02.435Z"}
---

## What happened

Programs are templates (pre-built using this feedback form) that automatically populate a week’s exercises & reps & weights based on pre-defined rules for that program.
Programs will be pre-built using this feedback form, with the only customization option being the specific exercises and weights.

## Open question

This is a new subsystem, not a tweak to an existing one, and the app is deliberately built
the opposite way in several places it would touch — the README's *What's deliberately
missing* explicitly names "No progression" and "No programme templates", and *Rep schemes*
says "The scheme is a label on what the entry was built as, not a rule that keeps enforcing
itself." Building a program engine reverses those choices. Before I write it I need the
shape decided, because guessing wrong here is a large, hard-to-review diff to a
single-file app.

**1. Where do program definitions live?**
The report says programs are "pre-built using this feedback form" — i.e. each program
arrives as a feedback item (fb-0040 is the first) and I bake it into the code. That points
to a hardcoded `PROGRAMS` constant in `lift-tracker.html`, in the same spirit as
`PEAK_REPS` / `MUSCLE_GROUPS`. Confirm that, versus: (a) a new editable `programs`
collection in the JSON store, or (b) a separate file the server loads. A constant is the
smallest change and matches "pre-built, not user-authored"; the only customization the
report allows is exercise choice + weights, which is per-user state, not program data.

**2. How does a user start a program, and where does the per-user setup live?**
Nothing in the report describes the UI. Proposed: a new **Program** tab (third tab beside
Week / Library). It lists the built-in programs; picking one opens a setup panel that, for
each "slot" the program defines (e.g. "Monday big lift 1"), lets you choose a library
movement and a starting weight — the "specific exercises and weights" the report allows.
That mapping + a start-Monday is stored as the one piece of per-user program state.
Where should that state live — a new `programs` collection (one row = one active/configured
program instance), or `_meta`? Can more than one program be configured at once, and is
there ever more than one *active*?

**3. All weeks generated up front, or one week at a time?**
This is the load-bearing decision and fb-0040 forces it: its progression rules read the
*logged results* of the previous week (RIR, reps hit, whether weight was 0). If all 6
weeks are generated when you start the program, weeks 2–6 have nothing to progress from.
Proposed: nothing is generated automatically. When you navigate to a week that the active
program covers and it has no lift days yet, the week bar offers **"Fill this week from
Phase 1: Volume"**; that button previews the days/exercises/sets it will create (built by
the same code that creates them, like the add-exercise dialog does) and, on confirm,
writes them as ordinary `days`/`entries`/`sets` — real values, nothing that recalculates
later. Progression for week N is computed at the moment you fill week N, from week N-1's
logged sets. Confirm this model vs. an up-front "generate all 6 weeks" with progression
applied lazily on view.

**4. Collisions and edits.**
If the target week already has lift days, does "Fill from program" refuse, merge, or
replace? Once a week is filled, it's just normal entries the user edits by hand — the
program doesn't touch it again. Correct?

**5. README.** Assuming yes to the above, `What's deliberately missing` and `Rep schemes`
need rewriting to say programs now exist and what they do/don't do. Confirm you want that
in the same change.

Once 1–4 are settled I can implement the engine here and the Phase 1: Volume program in
fb-0040 (which has its own open questions about the progression math).

## Resolution

Answered interactively (not through the unattended queue — this was flagged as needing
real back-and-forth, and it did: a few more rounds of questions on the deload/test-week
accessory handling and the Peak 1RM baseline). Built alongside fb-0040, since the two are
one feature in practice.

**Where program definitions live:** a hardcoded `PROGRAMS` object in `app/lift-tracker.html`,
same spirit as `PEAK_REPS`/`MUSCLE_GROUPS`. Each program names its day-slots (movement,
scheme, day of week) and, for Peak slots, a 6-week × 5-set pip-offset schedule.

**UI:** a third **Program** tab. With no program active it lists the catalog (`PROGRAMS`,
so a second program is just a new entry, no new UI). Starting one opens a setup dialog —
one row per slot, its starting weight pre-filled from the library (`estimatedOneRepMax()`
for Peak, `defaultWeight` for Static) and editable — then activates. Only one program can
be active at a time. The active view shows current week / total, every slot's weight
(editable — only affects weeks not yet generated), any conflicts, and a Cancel button.

**Generation, one week at a time:** `generateProgramWeek(prog, week)` writes ordinary
`days`/`entries`/`sets` rows — no ownership marker, so a hand-edit and the program's own
output are indistinguishable afterwards, exactly as asked. `maybeAdvanceProgram()` runs on
a slow tick (`poll()`, `boot()`) and generates the next week once the current one's last
lift day is behind you — the calendar's passed it, or every set has both reps and RIR
filled in (checked against the program's own slots by exercise + date, so an unrelated
exercise added that day can't block it forever).

**Conflicts:** a slot whose date already has an entry for that exercise is left untouched.
Week 1 landing on an already-logged week is the expected case, not a conflict. Any other
week finding one is recorded in `programs.conflicts` and shown on the Program tab.

**1RM baseline:** locked at activation (a snapshot in `programs.overrides`, not re-read
from the library later), per your answer.

**README:** updated — a new "Programs" section, and `What's deliberately missing` /
`Rep schemes` rewritten to say what now exists and what still doesn't (no user-authored
programs, no editor — this is one hardcoded plan, not a builder).

**Verified:** against the real store, not a fixture — activated Phase 1: Volume for real
(landing week 1 on your already-logged Aug 24 week, confirming it correctly created
*nothing* rather than duplicating it), forced the week-2 advance, hand-verified the Peak
weight formula against the pip math exactly (170/180/190/180/170 off a 225 lb max), and
confirmed both branches of the static rule (Cable Crunch correctly held flat after missing
a rep target; RDL correctly progressed +5). Then deleted every row the test created and
confirmed the store matched a pre-test snapshot byte-for-byte before doing the same for
the real Aug 24 week's counts. `tools/run-tests.sh`: 61 passed, 5 failed (all pre-existing,
unrelated — confirmed identical before and after this change), after updating one test
assertion (`tools/smoke-test.mjs`) that hardcoded the old 2-tab count.

**Not done:** no automated test coverage was added for the Program tab itself to
`tools/smoke-test.mjs` — the verification above was thorough but manual/scripted, not a
permanent regression test. Worth adding if this gets built on further.
