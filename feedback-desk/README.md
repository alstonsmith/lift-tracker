# Lift Tracker Feedback Desk

Capture feedback about the apps in this repo, triage it, and hand a batch of it to a Claude
agent as a work order.

Sibling to Lift Tracker: same single-file app, same stdlib Python server, same LAN
reach-it-from-any-device shape. Runs on **port 8441**, alongside Lift Tracker on 8440.

```bash
./feedback-desk/server/start-server.sh      # detached
./feedback-desk/server/stop-server.sh
```

---

## The format is the point

Every item is **one markdown file with frontmatter** in `data/items/`:

```markdown
---
id: fb-0002
title: Rep boxes are too small to tap on a phone
app: lift-tracker
area: week
type: bug
severity: high
status: backlog
reporter: Alston
tags: ["touch", "mobile"]
brief: wo-0001
created: 2026-08-24T02:39:41Z
updated: 2026-08-24T02:39:41Z
context: {"source": "lift-tracker", "view": "week", "viewport": "390x844", "appRev": 45, "errors": []}
---

## What happened
…
## What I expected
…
## Steps to reproduce
…
```

That's the whole database. It matters because of who reads it: a Claude agent can `cat`,
`grep` and edit these files directly — no API to call, no export step, no JSON to unpack —
and every change it makes lands as a readable git diff.

**The body is a fixed set of sections**, not free text: `## What happened`,
`## What I expected`, `## Steps to reproduce`, `## Notes`, and `## Resolution`. The editor
offers one box per section rather than a raw markdown pane, and the server re-renders the
whole body from those sections on every write. So a file that's been mangled — headings
reordered, mis-cased, or the whole thing typed as one loose paragraph — gets straightened
out on the next save instead of quietly degrading. Loose text before any heading is
recovered as "What happened", and headings the desk doesn't know about are preserved after
the ones it does, so an agent adding its own section never loses it.

**The frontmatter dialect is deliberately tiny.** Values are written as JSON and parsed
with `json.loads`, falling back to the raw string. JSON scalars, arrays and objects are all
valid YAML, so the files stay readable and any YAML tool can parse them, but reading them
here needs nothing outside the standard library. Hand-edit them freely — `status: ready`
round-trips untouched.

`data/QUEUE.md` is a table of everything open. It's the natural thing to point Claude at
when you don't want to build a work order — *"read QUEUE.md and fix the two high-severity bugs"*
works fine. It's generated, and it regenerates whenever the item files change — including
when an agent edits them directly, which never touches the server — so it can't sit there
listing work that's already finished.

---

## The loop

### 1. Capture

Two ways in, and the second is much better:

- **In the desk** — the Board tab's capture form. Press `c`.
- **Inside Lift Tracker** — the **Feedback** button in its header, or press `f`.

The in-app route attaches a `context` block automatically: the week on screen and each
day's rest/lift state, which exercise rows were expanded, the viewport, the browser, the
app's data revision, and any JavaScript errors that had fired. That context is usually
what turns "the weights are wrong" into something reproducible, and nobody types it by
hand.

If the desk isn't running when you press Send, Lift Tracker hands the report back as
markdown to copy rather than losing it.

### 2. Triage

Everything lands in **Backlog**. Set severity there — that's the only ranking, deliberately.
A separate priority field said the same thing twice, and two rankings that can disagree are
worse than one that can't. Pull things into a work order when you want them done.

#### The four statuses

| status | who sets it | means |
| --- | --- | --- |
| **Backlog** | capture, or removal from an order | the default bucket |
| **Queued** | adding to a work order | scheduled, waiting to be worked |
| **Done** | the agent | finished, **awaiting your review** |
| **Closed** | you | reviewed and signed off |

The split between Done and Closed is the point: an agent can say it's finished, but only a
human can say it's actually right. So **Done is never hidden** — on the board, in filters,
or anywhere else — while **Closed is hidden by default**. Nothing an agent finishes can slip
past you unreviewed. The "Mark closed" button in the selection tray signs off a batch.

### 3. Hand a batch to Claude

Tick the items, then **Create work order**. That writes one file to `data/briefs/` and flips
those items to **Queued**. Then, in a Claude Code session in this repo:

```
Work on feedback-desk/data/briefs/wo-0001-week-view-touch-fixes.md
```

**Copy prompt** on the Work orders tab puts exactly that on your clipboard. For a single
item, the editor's **Copy as prompt** does the same thing.

#### A work order is a manifest, not a snapshot

Its frontmatter is the source of truth — title, instructions, and a list of item ids — and
its body is **regenerated from those on every change**, pointing at each item's file rather
than copying its text:

```markdown
---
id: wo-0001
title: Week view touch fixes
instructions: Do the rep boxes first — I want to use it at the gym this weekend.
items: ["fb-0001", "fb-0002"]
---
```

An earlier version embedded each item's full text. That copy went stale the moment anyone
edited an item, which is worse than useless: it hands an agent a confidently wrong
description. Pointers can't drift.

#### Editing membership

Three ways in:

- **Edit** on a work order — title, instructions, and a checklist of every candidate item.
- **Add to…** in the selection tray, for a batch.
- The work-order picker in an item's own editor.

The rules: adding an item makes it **queued** and sets its `brief`; removing it sends it
back to **ready** and clears `brief`; an item already closed stays closed. An item belongs
to **at most one order** — adding it elsewhere moves it, and the previous order's manifest
is updated too. Archiving an order releases everything in it back to ready.

### 4. Watch it land

The agent records outcomes *in the item files* — `status: done` plus an appended
`## Resolution` section. This server reads the directory on every request and derives its
revision from file mtimes, so **cards move across the board on their own while the agent
works**. No refresh, no import. That's tested (`tools/run-tests.sh`, "agent edits a file on
disk; the open browser follows").

---

## Fields

| field | |
| --- | --- |
| `id` | `fb-NNNN`, assigned by the server. The filename keeps its original slug even if the title changes, so links and git history survive a re-title. |
| `app` / `area` | which app, and which view or module. `area` auto-fills from the current view on in-app capture. |
| `type` | bug · new feature · polish · question (stored as `feature`) |
| `severity` | high · low — two on purpose; three or more and everything settles in the middle. The only ranking; it orders the queue |
| `status` | backlog → queued → done → closed (see below) |
| `brief` | the work order this belongs to, once queued |
| `context` | auto-captured app state — the part that makes a report reproducible |

## API

| endpoint | |
| --- | --- |
| `GET /api/ping` `/api/rev` `/api/state` | health, mtime fingerprint, everything |
| `POST /api/capture` | labelled fields in, composed markdown out — what the widgets post to |
| `POST /api/items` | same, with a pre-composed body |
| `POST /api/items/<id>` | patch frontmatter fields and/or body |
| `POST /api/items/<id>/archive` | move to `data/archive/` — never deleted |
| `POST /api/briefs` | build a work order from a list of ids |
| `POST /api/briefs/<id>` | patch `title`, `instructions`, and membership via `items`, `add` or `remove` |
| `POST /api/briefs/<id>/archive` | retire an order, releasing its items back to `ready` |

CORS is open, because Lift Tracker posts here from a different port. Same trust model as
the rest of these tools: unauthenticated on the LAN. Don't run it on a network you don't
trust.

## Layout

```
app/feedback-desk.html          the UI — single file, no build step
server/serve_feedback_desk.py   stdlib server, markdown store
data/items/                     one .md per item — the database
data/briefs/                    generated work orders
data/QUEUE.md                   generated index of everything open
data/archive/                   archived items (gitignored)
```
