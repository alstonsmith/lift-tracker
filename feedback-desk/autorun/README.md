# Unattended queue runner

Runs the Lift Tracker Feedback Desk queue on a schedule so work orders don't sit waiting for someone
to paste `Work on feedback-desk/data/briefs/wo-NNNN.md` into a session. Once a day at
**22:00 local time (10pm)**, a launchd agent fires `lift-tracker-feedback-queue.sh`, which:

1. makes sure both local servers are up (Lift Tracker `:8440`, Feedback Desk `:8441`),
   so a run can actually load the app and click through a fix, the way an interactive
   session would;
2. asks `scan.py` which work orders are still **open** — one with at least one item not
   yet `done`/`closed`; an order that's fully finished is skipped so Claude is never
   woken for nothing;
3. runs `claude -p "Work on feedback-desk/data/briefs/wo-NNNN-*.md ..."` headless
   against each open order, in order, one at a time;
4. rebuilds `DIGEST.md` from the `needs-clarification` tags a run adds to any item it
   had to stop on, and raises a macOS notification.

It **never commits and never pushes.** A run leaves the working tree dirty — edited item
files, edited app `.html`. The Lift Tracker Feedback Desk board shows the `done` cards immediately (it
reads the files live); `git status` shows what's there for you to review and commit.

## Enable / disable

```sh
feedback-desk/autorun/install.sh      # write the plist, load it
feedback-desk/autorun/uninstall.sh    # stop and remove it
```

`install.sh` is safe to re-run — it's also the update path. Edit
`com.lift-tracker.feedback-queue.plist` (change the time, the PATH) and re-run it.

## Run it now, by hand

```sh
feedback-desk/autorun/lift-tracker-feedback-queue.sh                  # exactly what launchd runs
launchctl kickstart -k gui/$(id -u)/com.lift-tracker.feedback-queue   # via launchd instead
```

## How "needs clarification" surfaces

The scheduled run is told, inline in its prompt (see `lift-tracker-feedback-queue.sh`), that it's
unattended: nobody is reading its reply in real time, so a question left only in the
reply is a question that gets lost. Instead, for any item it must stop on — a design
decision the report doesn't specify, or an action with real consequences it shouldn't
take without sign-off — it:

- adds `needs-clarification` to the item's `tags`,
- appends a `## Open question` section to the item file,
- leaves the item's `status` untouched (it isn't `done`).

After the run, `scan.py digest` gathers every flagged item into `DIGEST.md` and the
notification says how many. Answer the question in the item file (or in chat, then
re-run), and the tag clears when the item is next finished.

## Files

| file | |
|---|---|
| `lift-tracker-feedback-queue.sh` | what launchd runs; also the by-hand entry point. Named for the Login Items panel, not just style — see the .plist's comment |
| `scan.py` | read-only: `open-orders` and `digest` (stdlib only) |
| `com.lift-tracker.feedback-queue.plist` | canonical launchd agent, with `__PLACEHOLDER__` paths |
| `install.sh` / `uninstall.sh` | load / unload the agent |
| `logs/` | `<timestamp>-run.log` + one `<timestamp>-woNNNN.log` per work order (gitignored) |
| `DIGEST.md` | generated each run — the "waiting on Alston" list (gitignored) |

## Knobs

Environment variables `lift-tracker-feedback-queue.sh` reads (set them in the plist's
`EnvironmentVariables`, or export before a by-hand run):

| var | default | |
|---|---|---|
| `CLAUDE_BIN` | `~/.local/bin/claude` | launchd's PATH doesn't include `~/.local/bin` |
| `MAX_MINUTES` | `45` | per-work-order wall-clock ceiling; a wedged run is killed, the next order still runs |
| `LIFT_QUEUE_MODEL` | *(account default)* | pass to pin a model |

## Caveats worth knowing

- **Permissions.** The headless run uses `--dangerously-skip-permissions` — it can't
  stop to ask you to approve an edit or a command. It's scoped to the Lift Tracker
  Feedback Desk flow
  by what it's told to do (edit the item files, edit the app `.html`, run the local
  servers), but that instruction is the only fence there is, and that's the tradeoff
  you're accepting by automating it.
- **Browser verification is weaker.** The runner can start a server and `curl` it, but a
  real click-through needs a headless browser driver, which it may or may not reach for.
  Expect the occasional Resolution that says "not verified in a browser" — spot-check
  those.
- **Asleep at 22:00?** launchd runs the job once on the next wake.
- **Persists across reboots** — unlike a cloud-routine schedule, this is a local launchd
  agent; it keeps firing until `uninstall.sh` removes it, with no expiry.
- **Re-running an order is safe** — items already `done` are skipped, and an all-done
  order is a no-op. `Closed` it in the Lift Tracker Feedback Desk once you've signed off, so the
  runner (and you) have less to look at next time.
