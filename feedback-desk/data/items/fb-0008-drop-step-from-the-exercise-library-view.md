---
id: fb-0008
title: Drop "step" from the exercise library view
app: lift-tracker
area: library
type: polish
severity: low
status: done
reporter: ""
tags: []
brief: wo-0003
created: 2026-08-24T20:58:07Z
updated: 2026-08-24T21:28:32Z
context: {"source": "lift-tracker", "capturedAt": "2026-08-24T20:57:50.810Z", "url": "http://192.168.4.44:8440/#library", "view": "library", "weekStart": "2026-08-24", "weekTypes": ["2026-08-24:lift", "2026-08-25:rest", "2026-08-26:rest", "2026-08-27:rest", "2026-08-28:rest", "2026-08-29:rest", "2026-08-30:rest"], "expandedEntries": [], "viewport": "1920x849", "userAgent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36", "appRev": 67, "counts": {"exercises": 11, "days": 1, "entries": 4, "sets": 12}, "errors": []}
---

## What happened

Drop the "step" column

## Resolution

The **Step** column is gone from the Library.

- `app/lift-tracker.html`, `renderLibrary()`: the header cell and the per-row `increment`
  input are removed, and `wireLibrary()` no longer binds them.
- The stored `exercises[].increment` field is left alone rather than migrated away. It is
  now read by nothing, but deleting it would rewrite every exercise in the file for a
  cosmetic gain, and the pip (see fb-0011) has taken over as this app's answer to "how big
  is one jump on this lift".
- `tools/smoke-test.mjs` asserts the column stays gone.
