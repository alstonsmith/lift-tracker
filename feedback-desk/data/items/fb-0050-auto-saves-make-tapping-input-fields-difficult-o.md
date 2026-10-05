---
id: fb-0050
title: Auto-saves make tapping input fields difficult on mobile
app: lift-tracker
area: ""
type: bug
severity: low
status: done
reporter: ""
tags: []
brief: wo-0019
created: 2026-10-05T20:12:14Z
updated: 2026-10-05T20:13:14Z
context: {"source": "feedback-desk", "capturedAt": "2026-10-05T20:12:14.676Z"}
---

## What happened

On mobile (iOS), auto-saves make UI interactions difficult. I often have to tap a field twice because the first tap doesn't register due to the auto-save

## Resolution

Root cause: `mutate()` redraws the whole view synchronously, right inside the `onchange`
handler that fires when a field blurs — which is exactly what happens on every tap that
moves from one box to the next. The redraw replaces that box's DOM node (and the one you
just tapped) before the browser finishes handing focus over, so the tap lands on a node
that's already gone. For the Enter-to-advance flow this was worse: `advance()` had already
captured a reference to the next box before the redraw destroyed it, so `next.focus()`
silently did nothing and focus was lost entirely, not just delayed a tap.

Fix: `mutate()` now defers that redraw to a microtask (`queueMicrotask(safeRender)` in
place of a synchronous `safeRender()` call, `app/lift-tracker.html`). The data still
applies immediately; the visual redraw just waits until the current task — including the
browser's own focus handoff to whatever was tapped or Enter'd next — has finished. Once
redrawn, the existing focus/caret-restore logic picks up whatever box the browser actually
focused, instead of racing it.

Verified against the real app in headless Chrome: ran the full suite
(`./tools/run-tests.sh`, 61+51 passing, same 5 pre-existing unrelated failures before and
after) and confirmed the fix doesn't change rendering timing enough to affect any existing
assertion. I don't have an iOS device to reproduce the exact double-tap by hand, so this is
verified by root-causing the DOM-replacement race precisely rather than by reproducing the
symptom on-device — worth confirming on a phone next time you're at the gym.
