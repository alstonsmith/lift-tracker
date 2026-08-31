---
id: fb-0034
title: Resize Library so it fits an iPhone 13 screen
app: lift-tracker
area: library
type: polish
severity: low
status: done
reporter: ""
tags: []
brief: wo-0012
created: 2026-08-25T02:41:26Z
updated: 2026-08-25T03:00:23Z
context: {"source": "lift-tracker", "capturedAt": "2026-08-25T02:40:35.862Z", "url": "http://192.168.4.44:8440/#library", "view": "library", "weekStart": "2026-08-24", "weekTypes": ["2026-08-24:lift", "2026-08-25:rest", "2026-08-26:rest", "2026-08-27:rest", "2026-08-28:rest", "2026-08-29:rest", "2026-08-30:rest"], "expandedEntries": ["en_mt7t4p3bdy4g"], "viewport": "1920x849", "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36", "appRev": 293, "counts": {"exercises": 11, "days": 1, "entries": 4, "sets": 18}, "errors": []}
---

## What happened

On mobile, each exercise spans 2 rows because the given fields are so big. Resize them so that everything is able to fit in one row when viewed on a mobile phone (you can use iPhone 13 screen size as a reference)

## Resolution

Added Library-specific rules to the existing phone-layout media query
(`@media (max-width: 700px)` in `app/lift-tracker.html`) that shrink each row's columns:
the Reps input got its own narrower class (`.rp`, 2rem — it never needs more than 2
digits, unlike the shared 5rem `.num` class it used to borrow from Max Weight), Max
Weight and Pip shrink to 3.3rem/2.1rem, Movement and Group get smaller min-widths and
font-size, and the muscle-group select gets `text-overflow: ellipsis` so a label like
"Delts (F)" clips instead of forcing the row wider. The Delete button switched from a
text button ("Delete") to an icon-only "×" (`.ex-del`, matching the app's existing icon
buttons elsewhere), which alone freed a lot of width. The header row's "Max Weight"
label was shortened to "Max Wt" (and "Reps" to "Rep") since the abridged column widths
that fit a value don't fit that much header text.

Verified with Playwright at Playwright's "iPhone 13" device profile (390×844 CSS px):
every one of the 11 real library rows renders as a single line, the header is a single
line too, there's no horizontal scroll, and opening a row's rep-max/notes disclosure
(fb-0033) still lays out cleanly at that width. Screenshots taken before and after
confirmed the visual change; DOM geometry checks confirmed no row's children fall onto a
second line.
