# Lift Tracker

Two small apps in this repo, each a single HTML file served by a stdlib Python server on
the LAN — the same shape as [House Tracker](../house-tracker), and deliberately so:

- **Lift Tracker** (port 8440) — one week of training at a time. Documented below.
- **[Lift Tracker Feedback Desk](feedback-desk/README.md)** (port 8441) — capture feedback about these
  apps and hand batches of it to a Claude agent. Every item is a markdown file, so the
  agent reads and edits the queue directly.

---

A week of training on one screen. Each day is either a **rest day** or a **lift day**; a
lift day holds exercises, and each exercise expands to the sets underneath it — the weight
already filled in from the last time you did that movement, and an empty two-digit box for
the reps you actually hit.

The server runs on one machine and holds the data. Any device on the same WiFi opens the
same page: the phone in your pocket at the rack, a laptop on the kitchen table when you're
planning the week.

> **This is a first prototype.** It does the loop described above, plus one pre-built
> [program](#programs) — and nothing more: no charts, no personal records, no plate maths,
> no history view beyond paging back through weeks. Those are all reachable from here;
> none of them are here yet. See [What's deliberately missing](#whats-deliberately-missing).

---

## Running it

On the machine that should hold the data:

```bash
./server/start-server.sh                     # detached; survives closing the terminal
./feedback-desk/server/start-server.sh       # optional, for the Feedback button
./server/stop-server.sh                      # when you're done
```

It prints two addresses — `http://localhost:8440/` for this machine, and
`http://<LAN IP>:8440/` for everything else on the WiFi. Open either in a browser. No
install, no build step, no app to sideload; it's a web page. On a phone, "Add to Home
Screen" gives it an icon and a full-screen window.

To run it in the foreground instead (Ctrl+C to stop):

```bash
python3 server/serve_lift_tracker.py --port 8440
```

Logs go to `server/server.log`. Python 3 is the only requirement — standard library only,
no pip packages.

**There is no authentication.** Anyone on the WiFi can read and edit the log while the
server is up. That's the same call House Tracker makes for the same reason: it's a
household tool on a home network. Don't run it on a network you don't trust.

---

## Using it

Two tabs, each a bookmarkable URL — `#week` and `#library`.

### The week

Seven day cards, Monday to Sunday. `←` and `→` (or `[` and `]`) move a week at a time;
**This week** comes back. Today's card is outlined.

Every day starts as a **rest day** — a day with no record at all *is* a rest day, which is
why most of a week costs nothing to store. **＋ Lift day**, or the `REST`/`LIFT` badge,
flips it. Turning a lift day back into a rest day removes its exercises and sets, so it
asks first if there's anything to lose.

### A lift day

Pick from **＋ Add exercise…** at the bottom of the card. The last option, **＋ New
movement…**, adds something that isn't in the library yet and puts it straight on the day.
Adding an exercise to a rest day makes it a lift day — you don't have to flip it first.

Picking a movement opens a short dialog asking for its **rep scheme** — see
[Rep schemes](#rep-schemes) below. It previews the exact sets it is about to create;
**Add** makes them, Escape or **Cancel** backs out.

Each exercise is then one collapsed row showing `logged/total · weight`, with a `PEAK`
badge if it's a wave. Click it to expand the sets beneath:

```
  1   135 lb ×  8 /8   reps   2  RIR
  2   135 lb × 12 /8   reps   0  RIR
  3   145 lb × __ /8   reps   _  RIR   ← the empty boxes are where the set goes
      ＋ Set                          Remove exercise
```

- **Weight** is pre-filled and fully editable. Overwrite it and it stays overwritten.
- **Reps** starts empty. It takes two digits, and only digits — anything else is dropped as
  you type.
- The faint **`/8`** next to it is the scheme's target for that set: what you meant to do,
  next to what you did. It isn't editable — it's a note on the box, not a second number to
  keep in step. Sets logged before schemes existed simply don't have one.
- **RIR** is reps in reserve: how many more you reckon you had before failure. One digit,
  and `0` is a real answer — it means you had nothing left. Optional; leaving it blank
  doesn't stop a set counting as logged.
- **Enter** walks the boxes in the order they sit on screen — this set's reps, its RIR,
  then the next set — so logging a session is one run down the card. RIR is on that run
  rather than a second pass because you know how many you had left when you rack the bar,
  not ten minutes later.
- A set turns green once its reps are in, and the collapsed row counts them.

### Rep schemes

Five sets waving up to a heavy double is a different session from three sets of eight, and
that isn't something the library row can say. So it's asked at the moment you add the
movement, and recorded on the entry.

**Static** — the default. You give it a number of sets (one digit) and a rep target, and
it makes that many sets, all at the same weight and all with the same target. The weight is
the first set of the last session you did that movement, falling back to the library's max
weight for something you've never logged. The rep target defaults the same way: whatever
you aimed for last time, or 8.

**Peak** — a fixed wave of five sets at **5 · 4 · 2 · 4 · 5** reps, with every rung priced
off the library's one-rep max in [pips](#the-library):

| reps | weight |
| --- | --- |
| 5 | one-rep max − 10 pips (75% of it) |
| 4 | one-rep max − 8 pips (80%) |
| 2 | one-rep max − 5 pips (87.5%) |

Peak consults no history at all: the point of a wave is that it's pinned to the max you
have now. Change the max in the library and the next one you add rescales with it.

Those offsets are deliberately *not* the library's own rep-max table, where a five is five
pips down. A rep max is the most you could do for those reps; a working set inside a wave
isn't meant to be, and the extra discount is what leaves the last set of five still there
after the double.

Either way the sets are ordinary sets once created — every weight and target is just a
number on a row, and nothing recalculates behind you afterwards. The scheme is a label on
what the entry was built as, not a rule that keeps enforcing itself. (A [program](#programs)
is the one exception: its own slots *do* keep enforcing a rule, week over week — but only
for the days it filled in, and only until you edit them, at which point they're exactly as
ordinary as anything you typed yourself.)

### Programs

A program is a pre-built, six-week plan — not something you author, the same relationship
the library has to a rep scheme. Activate one from the **Program** tab and it fills in one
week of days/exercises/sets at a time, in the shape it defines: which movements, which
days, Static or Peak. **Phase 1: Volume** is the one built in — six weeks pushing 2-rep-max
weights on the big lifts (Peak, Mon/Wed/Fri) while accumulating volume there and in
accessories (Static, Tue/Thu), deloading week 5 and testing week 6.

Only one program is active at a time. Starting one lets you adjust each slot's starting
weight — inherited from the library by default — before anything's written. From there:

- **One week at a time.** The next week is generated once the current one's last lift day
  is behind you — the calendar's moved past it, or every set on it has both reps and RIR
  filled in. Nothing is ever generated in advance, because a static slot's progression
  reads the *previous week's logged results*, which don't exist yet for a week nobody's
  lifted.
- **Never overwrites.** If a day the program wants to fill already has an entry for that
  exercise — most often because week 1 lands on a week you'd already logged by hand — the
  program leaves it alone. Past week 1 that's flagged as a conflict, shown on the Program
  tab, and nothing else is skipped because of it.
- **What it writes is ordinary.** A program-generated set is stored exactly like a
  hand-typed one — same collections, no ownership flag. Edit it, delete it, log it: the
  program doesn't know or care, and reads whatever's actually there (or isn't) when it
  next needs to progress from that day.
- **Cancelling** stops future weeks from being generated. Weeks already written stay in
  your log.

Programs are hardcoded in `PROGRAMS` in `app/lift-tracker.html`, the same way `PEAK_REPS`
and `MUSCLE_GROUPS` are — adding a second program is a new entry there, not a new feature.

### Where the expected weight comes from

Whatever you last did for that exercise. Squat 135 on Monday, add squats on Thursday, and
Thursday starts at 135. An exercise with no history yet starts from its library **max
weight**; after that, the library is never consulted again — except by a Peak scheme,
which is pinned to the max by definition.

A **Static** scheme puts that one weight on every set it creates, which is what makes it
static. **＋ Set** on an existing exercise still carries the *previous set's* weight
forward rather than re-deriving it, so dropping from 135 to 115 mid-session means set four
starts at 115 and not back at 135.

The rule is deliberately dumb. An auto-progression that guesses wrong is worse than a
number you can see is stale and change — and every suggestion is written into the set as a
real value the moment it appears, so nothing moves on its own once it's on screen.

### The library

One row per movement: its muscle group, how many sets to create when you add it to a day,
and its **max weight** — the one-rep max. Edits save as you type.

The max weight is the only weight on the tab you type. Everything else is derived from it:

- A **pip** is 2.5% of the one-rep max, shown to one decimal in its own column. It's the
  unit of progress on that lift, which is why it's a percentage — 5 lb is a rounding error
  on a 405 deadlift and a third of a set of curls.
- Opening a row (the `▸`) shows what that max implies for **2 through 12 reps**, one pip
  lighter per rep: a 200 lb single is 200 − 3 × 5 = 185 for a triple. None of those are
  inputs. A rep max that can be typed is a rep max that can drift out of step with the
  single it came from, and there is nothing eleven extra boxes per movement could say that
  the arithmetic doesn't.

The model is linear on purpose, the same call as the weight suggestion above: it is easy to
hold in your head and easy to see is wrong. Epley and Brzycki are more accurate about a
population and no more accurate about you.

**Muscle groups** are a fixed list of twelve — Quads, Hams, Glutes, Chest, Delts (R/F/S),
Back, Abs, Neck, Biceps, Triceps — and each one has a hue, so the group column reads as a
colour before it reads as a word. Movements filed under an older, coarser group ("legs",
"arms") show as unset rather than being auto-filed under a guess, since this list splits
legs three ways and arms two.

Deleting a movement here doesn't touch sessions that already used it: the name is **copied**
onto each entry when it's added to a day, so renaming "Barbell Row" or deleting it later
can't retitle six months of finished workouts.

### Feedback

The **Feedback** button in the header (or press `f`) files a report to the Lift Tracker
Feedback Desk on port 8441, with the week you were looking at, each day's rest/lift state,
which rows were expanded, the app's data revision and any JavaScript errors attached
automatically. If the
desk isn't running, the report is handed back as markdown to paste rather than lost.

---

## How it works

### Why operations instead of whole-file saves

The write API takes **per-entity operations**, not a whole-document POST:

```json
{"ops": [{"op": "patch", "coll": "sets", "id": "st_...", "fields": {"reps": "8"}}]}
```

A rep box is edited a dozen times in a workout. A phone that had been asleep since the
warm-up, posting the whole document, would roll back everything logged after it loaded.
A patch to one set can't do that — it merges only the named fields, so the laptop
correcting set 1's weight and the phone logging set 3's reps both land.

Three ops: `upsert`, `patch`, `delete`. `apply_ops()` in the server and `applyOpsLocal()`
in the page are deliberate twins, so the optimistic redraw matches what gets stored.

### The collections

| | |
| --- | --- |
| `exercises` | the library — one row per movement, with its defaults |
| `days` | one row per day you've *touched*. No row means a rest day |
| `entries` | one exercise placed on one day — the collapsible row |
| `sets` | one set: target weight, unit, rep target, reps performed, reps in reserve |
| `programs` | one row per activated [program](#programs) — which one, its per-slot weight overrides, how many weeks it's generated so far |

Sets are their own collection rather than an array inside an entry, for the reason above:
they're the highest-churn record in the app, and a patch to one must not carry a stale copy
of its siblings back to disk. Deleting an entry cascades to its sets, and deleting a day to
its entries and their sets — done **server-side**, so a dropped connection can't truncate a
multi-op batch halfway and strand rows nothing can reach.

### Everything else

- **Storage** is one JSON file, `data/lift-tracker.json`. Hand-editable; the server tolerates
  a file missing a collection rather than 500ing forever after. Written temp-then-rename so a
  crash can't leave it half-written, with a rolling backup in `data/backups/` at most every
  ten minutes.
- **Sync** is polling. Every open device hits `/api/rev` (a few bytes) every four seconds and
  only refetches the document when the number moved. It holds off while a save is in flight,
  while a debounced save is armed, and while any field has focus — a redraw under your thumb
  mid-set is worse than four seconds of staleness.
- **Dates** are plain `YYYY-MM-DD` strings end to end, never `Date` objects in storage. A
  workout happens on a calendar day, not at an instant. Arithmetic converts at UTC noon so a
  DST shift can't move a date across midnight.
- **Focus survives redraws.** The page redraws whole views with `innerHTML`, and every one of
  those redraws happens while someone is typing a rep count — so each field carries a stable
  key and focus plus caret is restored onto the matching field afterwards. There's a test for
  it.

### API

| endpoint | |
| --- | --- |
| `GET /api/ping` | health check |
| `GET /api/rev` | the revision number, for polling |
| `GET /api/state` | the whole document |
| `POST /api/mutate` | `{"ops": [...]}` → the whole new document |

---

## Tests

An end-to-end smoke test that drives the real app in a real headless Chrome over the
DevTools protocol — no test dependencies, node's global `WebSocket` is enough.

```bash
./server/start-server.sh
./tools/run-tests.sh
```

It works on a week in 2031 so it can never touch real training data, and deletes what it
created at the end — the last assertion is that the store is left exactly as it was found.
It covers the phone layout, flipping rest↔lift, the scheme dialog (both schemes, and that
Peak's five rungs come out at the right pips off the current max), the auto-populated
weights, the two-digit rep box and the one-digit RIR box (including `"1234"`, `"6x"` and
`"9x7"`), rep targets, carry-forward to the next session, a second device picking up a
change by polling, expand/collapse, the caret surviving a redraw, and the Library's pip
and rep-max columns.

It runs against the real store, so anything that depends on the user's own history — what
a movement's max is, how many sets its library row asks for, what was logged last week —
is asserted as a property (*every Static set matches its neighbours*) rather than as a
fixed number. If the Lift Tracker Feedback Desk is up on 8441 its own suite runs too.
Screenshots land in `$OUT_DIR`.

## What's deliberately missing

Named so nobody has to rediscover them:

- **No progression outside a program.** An exercise you add by hand still just repeats the
  weight; it never adds 5 lb for you. [Programs](#programs) are the one place progression
  exists, and only for the days they fill in.
- **No history view** beyond paging back a week at a time, and no charts or PRs.
- **No user-authored programs** — no editor for your own, no "copy last week" outside one.
  The one built-in program is hardcoded; a second one is code, not a form.
- **No units per user.** Everything says `lb`; the field exists on every set and exercise,
  but nothing switches it yet.
- **No RPE, tempo, rest timer, warm-up sets, supersets, or notes on a set.** RIR is the
  one exception, and it's a bare digit — nothing reads it back yet.
- **No scheme beyond Static and Peak**, and no way to define your own. Adding one is a
  row in `PEAK_REPS`-shaped data and a button in the dialog; nothing else knows the list.
- **No one to attribute an edit to.** House Tracker has people; this assumes one lifter.

## Layout

```
app/lift-tracker.html           the UI — single file, no build step
server/serve_lift_tracker.py    stdlib server, JSON store
server/start-server.sh          detached start / stop
data/lift-tracker.json          the data (created on first run, with a starter library)
data/backups/                   rolling copies, gitignored
tools/run-tests.sh              the smoke suite
feedback-desk/                  the second app — see its own README
```
