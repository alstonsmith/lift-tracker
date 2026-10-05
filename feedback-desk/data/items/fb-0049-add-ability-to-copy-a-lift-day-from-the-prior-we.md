---
id: fb-0049
title: Add ability to 'copy' a Lift day from the prior week
app: lift-tracker
area: ""
type: feature
severity: low
status: done
reporter: ""
tags: []
brief: wo-0019
created: 2026-10-05T20:10:44Z
updated: 2026-10-05T20:13:14Z
context: {"source": "feedback-desk", "capturedAt": "2026-10-05T20:10:44.277Z"}
---

## What happened

When establishing Lift days, give the option to 'copy' lift days from the prior week. This should give the user the ability to select a day from the previous week and copy it into the current day, with the option to edit the specific lifts being copied. (Options to edit include: the lift itself (whether the user wants to import it or not), the rep scheme, and the settings for that rep scheme)

## Resolution

Built as a **↺ Copy last week** button next to **＋ Lift day** on a rest day's card — it
only appears when the day exactly 7 days earlier was a lift day with something on it,
since there's nothing to offer otherwise. Clicking it opens a dialog listing that day's
exercises, each as a checkbox (checked by default) with its scheme — Static rows get
editable sets/reps fields pre-filled from what that entry had, Peak rows have nothing to
configure since a Peak wave is always pinned to the library's current max. Uncheck
anything you don't want brought over; Copy commits only the checked rows.

Deliberately *not* a snapshot of last week's exact numbers. It calls the same
`addExercise()` every manual "＋ Add exercise" does, once per checked row, so weight comes
from the normal carry-forward rule (whatever you last did for that movement) rather than a
frozen copy — which for a fresh week resolves right back to the week you just copied, the
same number copying it by hand would have landed on. New sets always start unlogged, same
as adding fresh: this recreates the day's shape, not its logged results.

Scope notes, in case any of these should go a different way:
- Only reads exactly one week back (your "this" request) — not a day picker, not a
  "copy any prior week" tool.
- A day with existing exercises on it still offers the button; copying adds alongside
  whatever's already there rather than requiring an empty day first (nothing is
  overwritten — same spirit as how Programs never overwrite an existing entry).
- A movement deleted from the library since last week shows in the list (grayed, with a
  note) but can't be checked — there's no library row left to size its weight or unit
  against.

New CSS/markup: `#copy-modal` (mirrors the existing `#add-modal`/`#program-modal` dialog
shell) and `.copy-row*` rules. New JS: `openCopyDay`/`closeCopyDay`/`renderCopyDay`/
`copyRowHTML`/`commitCopyDay` and the `copyDraft` state, all in `app/lift-tracker.html`
right after the add-exercise dialog section; wired into `dayHTML()`'s rest-day branch,
`wireWeek()`, and the global Escape/shortcut-guard in `wireGlobal()`.

Verified end-to-end against the real server in headless Chrome, on a 2031 test week so it
never touched real data: built a 3-set Static entry, logged it, jumped a week forward,
confirmed the button appears only on the matching weekday, opened the dialog and checked
the pre-filled fields, committed the copy, and confirmed the new entry's scheme/set
count/rep target/weight and that its sets came back unlogged — then deleted both test days.
Also reran the full existing suite (`./tools/run-tests.sh`) — same 61+51 passing, same 5
pre-existing unrelated failures as before this work, no new ones.
