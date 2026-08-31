---
id: fb-0037
title: Prevent screen from zooming in when typing on mobile (iOS)
app: lift-tracker
area: week
type: polish
severity: low
status: done
reporter: ""
tags: []
brief: wo-0014
created: 2026-08-27T22:28:45Z
updated: 2026-08-31T03:06:43Z
context: {"source": "lift-tracker", "capturedAt": "2026-08-27T22:28:24.417Z", "url": "http://192.168.4.44:8440/#week", "view": "week", "weekStart": "2026-08-24", "weekTypes": ["2026-08-24:lift", "2026-08-25:lift", "2026-08-26:lift", "2026-08-27:lift", "2026-08-28:rest", "2026-08-29:rest", "2026-08-30:rest"], "expandedEntries": ["en_mtc2lyvjnoq9", "en_mtc2mjrjch9o"], "viewport": "390x797", "userAgent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/27.0 Mobile/15E148 Safari/604.1", "appRev": 532, "counts": {"exercises": 29, "days": 4, "entries": 22, "sets": 65}, "errors": []}
---

## Resolution

iOS Safari auto-zooms the page whenever a focused form control has a computed
`font-size` below 16px. Every input in Lift Tracker is deliberately smaller than that
— the two-digit rep box, the RIR box, the weight box and the library fields are all
around 13px, and shrinking the layout to fit an iPhone 13 has been the subject of its
own work (fb-0034, wo-0012). Bumping the inputs to 16px to dodge the zoom would undo
that, so the fix is on the viewport meta instead.

**Changed:** `app/lift-tracker.html` line 5 — the viewport meta went from

```
<meta name="viewport" content="width=device-width, initial-scale=1">
```

to

```
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
```

with a comment explaining why. `maximum-scale=1` tells Safari not to scale past 1×,
which suppresses the focus-zoom jump. iOS still honours the pinch-to-zoom
accessibility gesture regardless of `maximum-scale`/`user-scalable` (Apple has
overridden those for zoom-in since iOS 10), so this only removes the unwanted
automatic zoom, not the user's ability to zoom deliberately. `user-scalable=no` was
not added — it buys nothing extra on iOS and would needlessly block pinch-zoom on
Android.

**Verified:** `curl http://localhost:8440/` serves the updated meta tag. The full
smoke suite (`./tools/run-tests.sh`) was run before and after the change — identical
result both times (61 passed, 5 failed), so this change affects nothing the tests
cover, and "no JavaScript errors were thrown all run" still passes. The 5 failures are
pre-existing and unrelated (library "Max Wt" column label and rep-max rounding, from
other in-flight work). The actual iOS zoom behaviour can't be exercised by the
headless-Chrome test harness and was not device-tested here.
