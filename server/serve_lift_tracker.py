#!/usr/bin/env python3
"""Local HTTP server for the Lift Tracker.

Serves app/lift-tracker.html and a small JSON API over the LAN so any device on this
WiFi -- the phone in your pocket at the rack, a laptop on the kitchen table when you're
planning the week -- can view and edit the same training log, stored on THIS machine in
data/lift-tracker.json.

Modelled directly on House Tracker's server (../house-tracker/server/
serve_house_tracker.py), down to the operation-based write API. That shape matters even
more here: a set's rep field is edited a dozen times in a workout, and a whole-document
POST from a phone that had gone to sleep mid-session would roll back everything logged
after it loaded. Per-record patches can't do that.

Usage:
    python3 server/serve_lift_tracker.py [--port 8440]

Then open http://localhost:8440/ here, or the printed http://<LAN IP>:8440/ elsewhere.
Ctrl+C to stop, or use start-server.sh / stop-server.sh to run it detached.

No authentication: a household tool on a home network, the same call House Tracker makes.
Anyone on this WiFi can read and write the log while it's up. Don't run it on a network
you don't trust.
"""
import argparse
import http.server
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
APP_DIR = os.path.join(ROOT, "app")
DATA_DIR = os.path.join(ROOT, "data")
DATA_FILE = os.path.join(DATA_DIR, "lift-tracker.json")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

APP_FILE = "lift-tracker.html"

# Collections the mutation API will touch. A request naming anything outside this set is
# rejected, so a client can't invent a collection or reach into _meta.
#
#   exercises  the library -- one row per movement you do, with its defaults
#   days       one row per calendar day you've touched: rest or lift
#   entries    one exercise placed on one day (the collapsible row in the UI)
#   sets       one working set under an entry: target weight + reps performed
#   programs   one row per activated program (at most one with status "active" at a
#              time, enforced client-side) -- which built-in program, its per-slot
#              starting-weight overrides, and how many weeks it's generated so far
#
# Sets are their own collection rather than an array inside an entry on purpose. They are
# the highest-churn record in the app -- a rep field gets typed into between every set --
# and a patch to one set must not carry a stale copy of its siblings back to disk.
COLLECTIONS = {"exercises", "days", "entries", "sets", "programs"}

# A backup is a full copy of the data file, taken at most this often (seconds) on write,
# so a bad afternoon of edits is recoverable without a git commit per change.
BACKUP_MIN_INTERVAL = 600
BACKUP_KEEP = 30

# Guards the read-modify-write in apply_ops(). ThreadingHTTPServer serves each request on
# its own thread, so a phone and a laptop hitting the API at the same instant genuinely
# can interleave.
LOCK = threading.Lock()


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def local_ip():
    """Best-effort LAN IP for the "open this on another device" banner. Connecting a UDP
    socket sends nothing -- it just makes the OS choose the interface it would use, the
    usual way to ask that question without a direct API for it."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


# A first-run exercise library. Without it the app opens on an empty week with an empty
# picker, and the first thing a new user has to do is data entry rather than training.
# Everything here is editable and deletable in the Library tab; it's a starting point,
# not a fixed vocabulary.
# The group ids must match MUSCLE_GROUPS in the page; the weight is a one-rep max, which
# is the only weight the Library asks for. Both are placeholders -- nobody's real maxes
# are round numbers -- and both are edited in the Library tab.
SEED_EXERCISES = [
    ("Barbell Back Squat", "quads", 3, 135, 5),
    ("Barbell Bench Press", "chest", 3, 135, 5),
    ("Deadlift", "glutes", 3, 185, 10),
    ("Overhead Press", "delts-front", 3, 75, 5),
    ("Barbell Row", "back", 3, 95, 5),
    ("Romanian Deadlift", "hams", 3, 115, 10),
    ("Lat Pulldown", "back", 3, 100, 10),
    ("Dumbbell Curl", "biceps", 3, 25, 5),
    ("Triceps Pushdown", "triceps", 3, 40, 5),
    ("Pull-up", "back", 3, 0, 5),
]


def seed_exercises():
    stamp = now_iso()
    rows = []
    for i, (name, group, sets, weight, step) in enumerate(SEED_EXERCISES):
        rows.append({
            "id": "ex_seed%02d" % (i + 1),
            "name": name,
            "muscleGroup": group,
            "defaultSets": sets,
            "defaultWeight": weight,
            "increment": step,
            "unit": "lb",
            "order": i,
            "createdAt": stamp,
            "updatedAt": stamp,
        })
    return rows


def empty_doc():
    return {
        "_meta": {"version": 1, "rev": 0, "editedAt": now_iso()},
        "exercises": [],
        "days": [],
        "entries": [],
        "sets": [],
        "programs": [],
    }


def load_doc():
    if not os.path.isfile(DATA_FILE):
        return empty_doc()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        doc = json.load(f)
    # Tolerate a hand-edited file that's missing a collection rather than 500ing on every
    # later request -- this file is plain JSON and editing it by hand is a supported move.
    base = empty_doc()
    for key, value in base.items():
        doc.setdefault(key, value)
    doc["_meta"].setdefault("rev", 0)
    return doc


def maybe_backup():
    """Copy the current data file aside if the newest backup is older than
    BACKUP_MIN_INTERVAL. Called with LOCK held, before the file is replaced."""
    if not os.path.isfile(DATA_FILE):
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    existing = sorted(
        f for f in os.listdir(BACKUP_DIR)
        if f.startswith("lift-tracker-") and f.endswith(".json")
    )
    if existing:
        newest = os.path.join(BACKUP_DIR, existing[-1])
        if time.time() - os.path.getmtime(newest) < BACKUP_MIN_INTERVAL:
            return
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(DATA_FILE, os.path.join(BACKUP_DIR, "lift-tracker-%s.json" % stamp))
    existing = sorted(
        f for f in os.listdir(BACKUP_DIR)
        if f.startswith("lift-tracker-") and f.endswith(".json")
    )
    for stale in existing[:-BACKUP_KEEP]:
        os.remove(os.path.join(BACKUP_DIR, stale))


def write_doc(doc):
    """Temp-then-rename, so a crash mid-write can never leave a half-written log --
    os.replace is atomic on POSIX and Windows alike. mkstemp rather than a fixed
    ".lift-tracker.tmp" so overlapping writes can't collide on the temp file itself."""
    os.makedirs(DATA_DIR, exist_ok=True)
    maybe_backup()
    body = json.dumps(doc, indent=2, ensure_ascii=False).encode("utf-8")
    fd, tmp_path = tempfile.mkstemp(dir=DATA_DIR, prefix=".lift-tracker.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(body)
        os.replace(tmp_path, DATA_FILE)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def apply_ops(ops, actor):
    """Apply a list of operations to the stored document and persist it.

    Each op is one of:
        {"op": "upsert", "coll": "sets", "value": {...}}            -- create or replace
        {"op": "patch",  "coll": "sets", "id": "...", "fields": {}} -- merge fields
        {"op": "delete", "coll": "sets", "id": "..."}

    "patch" is the one that matters mid-workout: it merges only the named fields, so
    logging reps on set 3 can't overwrite the weight someone just corrected on set 1.
    Returns the new document.
    """
    with LOCK:
        doc = load_doc()
        stamp = now_iso()
        for op in ops:
            kind = op.get("op")
            coll = op.get("coll")
            if coll not in COLLECTIONS:
                raise ValueError("unknown collection: %r" % (coll,))
            rows = doc[coll]
            if kind == "upsert":
                value = op.get("value") or {}
                rid = value.get("id")
                if not rid:
                    raise ValueError("upsert needs value.id")
                value.setdefault("createdAt", stamp)
                value["updatedAt"] = stamp
                for i, row in enumerate(rows):
                    if row.get("id") == rid:
                        rows[i] = value
                        break
                else:
                    rows.append(value)
            elif kind == "patch":
                rid = op.get("id")
                fields = op.get("fields") or {}
                for row in rows:
                    if row.get("id") == rid:
                        row.update(fields)
                        row["updatedAt"] = stamp
                        break
                else:
                    raise ValueError("patch target not found: %s/%s" % (coll, rid))
            elif kind == "delete":
                rid = op.get("id")
                doc[coll] = [r for r in rows if r.get("id") != rid]
                # Deleting an entry has to take its sets with it, and deleting a day has
                # to take its entries and their sets. Left to the client this would be a
                # multi-op batch that a dropped connection could truncate halfway,
                # stranding rows nothing can reach or clean up.
                if coll == "entries":
                    doc["sets"] = [s for s in doc["sets"] if s.get("entryId") != rid]
                elif coll == "days":
                    gone = {e["id"] for e in doc["entries"] if e.get("dayId") == rid}
                    doc["entries"] = [e for e in doc["entries"] if e.get("dayId") != rid]
                    doc["sets"] = [s for s in doc["sets"] if s.get("entryId") not in gone]
            else:
                raise ValueError("unknown op: %r" % (kind,))
        doc["_meta"]["rev"] = int(doc["_meta"].get("rev", 0)) + 1
        doc["_meta"]["editedAt"] = stamp
        if actor:
            doc["_meta"]["editedBy"] = actor
        write_doc(doc)
        return doc


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=APP_DIR, **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s [%s] %s\n" % (
            datetime.now().strftime("%H:%M:%S"), self.address_string(), fmt % args))

    # Force revalidation on every response. Without it a browser's heuristic caching can
    # keep serving an old copy of the app shell indefinitely after the file changes on
    # disk, with no request reaching this server to reveal it's stale -- and this is a
    # no-build-step tool with no content hash to bust.
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/":
            # Otherwise SimpleHTTPRequestHandler renders a directory listing: app/ has no
            # index.html, the app file has a real name instead.
            self.path = "/" + APP_FILE
            return super().do_GET()
        if self.path == "/api/ping":
            return self._json(200, {"ok": True, "server": "lift-tracker"})
        if self.path == "/api/rev":
            # The polling endpoint. Deliberately tiny: every open device hits this every
            # few seconds, and only refetches /api/state when the number moved.
            with LOCK:
                doc = load_doc()
            return self._json(200, {"ok": True, "rev": doc["_meta"]["rev"]})
        if self.path == "/api/state":
            with LOCK:
                doc = load_doc()
            return self._json(200, {"ok": True, "state": doc})
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/mutate":
            return self._json(404, {"ok": False, "error": "not found"})
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            req = json.loads(raw)
        except json.JSONDecodeError as e:
            return self._json(400, {"ok": False, "error": "invalid JSON: %s" % e})
        ops = req.get("ops")
        if not isinstance(ops, list) or not ops:
            return self._json(400, {"ok": False, "error": "ops must be a non-empty list"})
        try:
            doc = apply_ops(ops, req.get("actor"))
        except ValueError as e:
            return self._json(400, {"ok": False, "error": str(e)})
        except Exception as e:  # disk full, permissions -- surface it, don't hang the client
            self.log_message("mutate failed: %s", e)
            return self._json(500, {"ok": False, "error": "server error: %s" % e})
        # Return the whole new document: it's small (one person's training log), and it
        # saves every client a follow-up GET plus any chance of showing a stale week right
        # after its own edit.
        return self._json(200, {"ok": True, "rev": doc["_meta"]["rev"], "state": doc})


def main():
    parser = argparse.ArgumentParser(description="Lift Tracker local server")
    parser.add_argument("--port", type=int, default=8440)
    args = parser.parse_args()

    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.isfile(DATA_FILE):
        doc = empty_doc()
        doc["exercises"] = seed_exercises()
        write_doc(doc)
        print("Created %s with a starter exercise library" % DATA_FILE)

    try:
        server = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    except OSError as e:
        print("Couldn't start on port %d: %s" % (args.port, e), file=sys.stderr)
        sys.exit(1)

    ip = local_ip()
    print("Lift Tracker server running.")
    print("  This machine:               http://localhost:%d/" % args.port)
    print("  Other devices on this WiFi: http://%s:%d/" % (ip, args.port))
    print("  Data file: %s" % DATA_FILE)
    print("  Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
        server.shutdown()


if __name__ == "__main__":
    main()
