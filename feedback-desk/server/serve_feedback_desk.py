#!/usr/bin/env python3
"""Local HTTP server for the Lift Tracker Feedback Desk.

Captures feedback about the apps in this repo and stores each item as one markdown file
with frontmatter, under data/items/. That storage choice is the whole point of the tool:
a Claude agent can read, grep and edit those files directly -- no API, no JSON parsing,
no export step -- and every change shows up as a readable git diff.

Because the files are the database, the agent and this server are peers. The server never
caches: it reads the directory on every request and derives its revision number from file
mtimes, so an item Claude edits on disk appears in an open browser within a few seconds,
and an item captured in the browser is on disk before the response is sent.

Usage:
    python3 feedback-desk/server/serve_feedback_desk.py [--port 8441]

Runs alongside the Lift Tracker server (port 8440), not instead of it. The capture widget
embedded in Lift Tracker posts here cross-origin, which is why the API sends CORS headers.

No authentication, same call as the Lift Tracker server: a household tool on a home
network. Don't run it on a network you don't trust.
"""
import argparse
import hashlib
import http.server
import json
import os
import re
import socket
import sys
import tempfile
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
APP_DIR = os.path.join(ROOT, "app")
DATA_DIR = os.path.join(ROOT, "data")
ITEMS_DIR = os.path.join(DATA_DIR, "items")
BRIEFS_DIR = os.path.join(DATA_DIR, "briefs")
ARCHIVE_DIR = os.path.join(DATA_DIR, "archive")
QUEUE_FILE = os.path.join(DATA_DIR, "QUEUE.md")

APP_FILE = "feedback-desk.html"

# Backlog is where everything lands. Queued means it's in a work order. Done is set by the
# agent when it finishes. Closed is the human's sign-off after reviewing that output --
# which is why Done is NOT hidden by default anywhere: an item sitting in Done is asking
# for review, and hiding it would strand it.
STATUSES = ["backlog", "queued", "done", "closed"]
# Finished as far as *work* goes: excluded from the queue and counted as complete on a work
# order's progress. Only "closed" is hidden from the board by default.
TERMINAL = {"done", "closed"}

TYPES = ["bug", "feature", "polish", "question"]
# Two severities on purpose: three or more lets everything settle in the middle, which is
# the same as not prioritising at all.
SEVERITIES = ["high", "low"]

# Migration map for vocabulary that existed before. Kept so a file written by an older
# version -- or by hand, from memory -- still lands somewhere sensible rather than being
# rejected or silently keeping a value nothing recognises.
LEGACY_VALUES = {
    "status": {"inbox": "backlog", "ready": "backlog", "wontfix": "closed"},
    "type": {"idea": "feature", "chore": "polish"},
    "severity": {"medium": "low", "blocker": "high"},
}

# Frontmatter key order, so every file on disk reads the same way and a diff shows a real
# change rather than a reshuffle. Keys outside this list are preserved and written after.
FIELD_ORDER = [
    "id", "title", "app", "area", "type", "severity", "status",
    "reporter", "tags", "brief", "created", "updated", "context",
    # work-order manifests share the serializer
    "instructions", "items",
]

# Fields the API will let a client set. "id" and "created" are server-owned.
WRITABLE = {
    "title", "app", "area", "type", "severity", "status",
    "reporter", "tags", "brief", "context", "body", "sections",
}


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def slugify(text, limit=48):
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (slug[:limit].rstrip("-")) or "item"


# ---------------------------------------------------------------------------
# Frontmatter: a deliberately small dialect
#
# Values are written as JSON and parsed with json.loads, falling back to the raw string
# when that fails. JSON scalars, flow arrays and flow objects are all valid YAML, so the
# files stay readable and any YAML-aware tool can still parse them -- but reading them
# here needs nothing outside the standard library, and a hand-edited plain string like
# `status: ready` round-trips untouched.
# ---------------------------------------------------------------------------
def parse_item(text):
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text
    fm, body_start = {}, len(lines)
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            body_start = i + 1
            break
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        key, sep, raw = line.partition(":")
        if not sep:
            continue
        key, raw = key.strip(), raw.strip()
        try:
            fm[key] = json.loads(raw)
        except (ValueError, TypeError):
            fm[key] = raw.strip("'\"")
    return fm, "\n".join(lines[body_start:]).lstrip("\n")


def dump_value(v):
    if isinstance(v, str):
        # A bare string is friendlier to read and to hand-edit, but anything that would
        # change meaning when re-parsed (a leading quote/bracket, a colon, a line break,
        # or a string that would come back as a number or bool) gets JSON-quoted.
        risky = (not v or v[0] in "[{\"'>|&*!%@`#-" or ": " in v or "\n" in v
                 or v.strip() != v)
        if not risky:
            try:
                json.loads(v)          # would parse as a non-string -- quote it
            except (ValueError, TypeError):
                return v
        return json.dumps(v, ensure_ascii=False)
    return json.dumps(v, ensure_ascii=False)


def serialize_item(fm, body):
    keys = [k for k in FIELD_ORDER if k in fm] + [k for k in fm if k not in FIELD_ORDER]
    head = "\n".join("%s: %s" % (k, dump_value(fm[k])) for k in keys)
    return "---\n%s\n---\n\n%s\n" % (head, (body or "").strip())


def atomic_write(path, text):
    """Temp-then-rename, so a crash mid-write can't leave a truncated item file, and an
    agent reading the directory never sees a partial one."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-", suffix=".md")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------
def item_files():
    if not os.path.isdir(ITEMS_DIR):
        return []
    return sorted(f for f in os.listdir(ITEMS_DIR)
                  if f.endswith(".md") and not f.startswith("."))


def load_items():
    items = []
    for name in item_files():
        path = os.path.join(ITEMS_DIR, name)
        try:
            with open(path, encoding="utf-8") as f:
                fm, body = parse_item(f.read())
        except OSError:
            continue
        fm["body"] = body
        sections, extras = parse_sections(body)
        fm["sections"] = {k: sections.get(k, "") for k in SECTION_KEYS}
        fm["extraSections"] = [{"heading": h, "text": t} for h, t in extras]
        fm["file"] = name
        fm.setdefault("id", name.split("-")[0] + "-" + name.split("-")[1]
                      if name.count("-") >= 1 else name[:-3])
        items.append(fm)
    return items


def load_briefs():
    if not os.path.isdir(BRIEFS_DIR):
        return []
    out = []
    for name in sorted(os.listdir(BRIEFS_DIR)):
        if not name.endswith(".md") or name.startswith("."):
            continue
        path = os.path.join(BRIEFS_DIR, name)
        try:
            with open(path, encoding="utf-8") as f:
                fm, body = parse_item(f.read())
        except OSError:
            continue
        fm["file"] = name
        fm["path"] = os.path.relpath(path, os.path.dirname(ROOT))
        fm["body"] = body
        out.append(fm)
    return out


def find_item_path(item_id):
    for name in item_files():
        if name.startswith(item_id + "-") or name == item_id + ".md":
            return os.path.join(ITEMS_DIR, name)
    return None


def next_id(prefix, directory):
    """Highest existing number + 1. Reading the directories each time (rather than keeping a
    counter file) means an item an agent adds by hand is counted too.

    The archive is scanned as well as the live directory. Ids are referenced from work
    orders, resolutions and conversations, so they have to stay unique for the life of the
    repo -- counting only live files would hand a brand new item the id of one that was
    archived last week, and silently make every existing reference to it ambiguous."""
    top = 0
    for d in (directory, ARCHIVE_DIR):
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            m = re.match(re.escape(prefix) + r"-(\d+)", name)
            if m:
                top = max(top, int(m.group(1)))
    return "%s-%04d" % (prefix, top + 1)


def revision():
    """A fingerprint of the data directory, standing in for the Lift Tracker server's
    monotonic rev counter. Derived from names, sizes and mtimes so that a file edited on
    disk -- by an agent, or by hand -- moves the number exactly like an edit made through
    the API, and every open browser notices on its next poll."""
    h = hashlib.md5()
    for directory in (ITEMS_DIR, BRIEFS_DIR):
        if not os.path.isdir(directory):
            continue
        for name in sorted(os.listdir(directory)):
            if name.startswith("."):
                continue
            try:
                st = os.stat(os.path.join(directory, name))
            except OSError:
                continue
            h.update(("%s:%d:%d" % (name, st.st_size, st.st_mtime_ns)).encode())
    return h.hexdigest()[:16]


def coerce_vocabulary(fm):
    """Map any retired status/type/severity onto the current set, in place."""
    for field, mapping in LEGACY_VALUES.items():
        value = fm.get(field)
        if value in mapping:
            fm[field] = mapping[value]
    if fm.get("status") not in STATUSES:
        fm["status"] = "backlog"
    if fm.get("type") not in TYPES:
        fm["type"] = "bug"
    if fm.get("severity") not in SEVERITIES:
        fm["severity"] = "low"
    return fm


def write_item(fm, body):
    coerce_vocabulary(fm)
    body = normalize_body(body)
    fm["updated"] = now_iso()
    path = find_item_path(fm["id"])
    if path is None:
        # The filename keeps the slug it was created with even if the title changes later:
        # a stable path means links, briefs and git history don't break on a re-title.
        path = os.path.join(ITEMS_DIR, "%s-%s.md" % (fm["id"], slugify(fm.get("title"))))
    atomic_write(path, serialize_item(fm, body))
    write_queue()
    return path


def create_item(data):
    item_id = next_id("fb", ITEMS_DIR)
    fm = {
        "id": item_id,
        "title": (data.get("title") or "Untitled").strip(),
        "app": data.get("app") or "lift-tracker",
        "area": data.get("area") or "",
        "type": data.get("type") if data.get("type") in TYPES else "bug",
        "severity": data.get("severity") if data.get("severity") in SEVERITIES else "low",
        "status": data.get("status") if data.get("status") in STATUSES else "backlog",
        "reporter": data.get("reporter") or "",
        "tags": data.get("tags") if isinstance(data.get("tags"), list) else [],
        "brief": "",
        "created": now_iso(),
        "context": data.get("context") if isinstance(data.get("context"), dict) else {},
    }
    write_item(fm, data.get("body") or "")
    return fm


# ---------------------------------------------------------------------------
# Body sections
#
# The body is not free text: it is a fixed set of `## ` sections, parsed on read and
# re-rendered on every write. That means the editor can offer one box per question instead
# of a raw markdown pane, and it means a file someone has mangled -- reordered, mis-headed,
# or written as one loose paragraph -- gets straightened out the next time it's saved
# rather than quietly degrading.
#
# Headings not in this list are preserved verbatim after the known ones, so an agent adding
# its own section doesn't lose it.
# ---------------------------------------------------------------------------
SECTION_DEFS = [
    ("what", "What happened"),
    ("expected", "What I expected"),
    ("steps", "Steps to reproduce"),
    ("notes", "Notes"),
    ("resolution", "Resolution"),
]
SECTION_KEYS = [k for k, _ in SECTION_DEFS]
SECTION_HEADINGS = {k: h for k, h in SECTION_DEFS}
_HEADING_TO_KEY = {h.lower(): k for k, h in SECTION_DEFS}
# "What you expected" is the question the form asks; "What I expected" is how the answer
# reads back in the reporter's own voice. Accept both spellings on the way in.
_HEADING_TO_KEY["what you expected"] = "expected"
_HEADING_TO_KEY["steps"] = "steps"


def parse_sections(body):
    """Split a body into {key: text} plus a list of (heading, text) for anything unknown."""
    sections, extras = {}, []
    current, buf, preamble = None, [], []
    for line in (body or "").split("\n"):
        m = re.match(r"^##\s+(.*?)\s*$", line)
        if m:
            _flush_section(sections, extras, current, buf)
            heading = m.group(1)
            current = (_HEADING_TO_KEY.get(heading.lower()), heading)
            buf = []
        elif current is None:
            preamble.append(line)
        else:
            buf.append(line)
    _flush_section(sections, extras, current, buf)
    # Loose text before any heading is almost always the description someone typed without
    # the scaffolding -- keep it as "What happened" rather than discarding it.
    lead = "\n".join(preamble).strip()
    if lead and not sections.get("what"):
        sections["what"] = lead
    elif lead:
        extras.insert(0, ("Notes", lead))
    return sections, extras


def _flush_section(sections, extras, current, buf):
    if current is None:
        return
    key, heading = current
    text = "\n".join(buf).strip()
    if not text:
        return
    if key:
        sections[key] = (sections[key] + "\n\n" + text) if sections.get(key) else text
    else:
        extras.append((heading, text))


def render_sections(sections, extras=()):
    parts = []
    for key in SECTION_KEYS:
        text = (sections.get(key) or "").strip()
        if text:
            parts.append("## %s\n\n%s" % (SECTION_HEADINGS[key], text))
    for heading, text in extras:
        if (text or "").strip():
            parts.append("## %s\n\n%s" % (heading, text.strip()))
    return "\n\n".join(parts)


def normalize_body(body):
    """Canonical section order and heading spelling, every time an item is written."""
    sections, extras = parse_sections(body)
    return render_sections(sections, extras)


def compose_body(data):
    """Build the body from the capture form's labelled fields. Anything not filled in is
    left out rather than leaving an empty heading behind."""
    return render_sections({k: data.get(k) for k in SECTION_KEYS})


# ---------------------------------------------------------------------------
# Generated files: QUEUE.md and work-order briefs
# ---------------------------------------------------------------------------
AGENT_PROTOCOL = """\
## How to work these items

1. Read each item file listed above. It holds the report, and a `context` block captured
   from the live app: the view, viewport, app revision, and any JavaScript errors at the
   time.
2. Do the work.
3. Record the outcome **in the item file itself**:
   - set `status: done` in the frontmatter,
   - append a `## Resolution` section saying what changed and where.
4. Leave `status: queued` on anything you started but didn't finish, and say so in
   `## Resolution`.

`done` is yours to set; `closed` is not. A human sets `closed` after reviewing your
output, so anything you finish stays visible until someone has actually looked at it.

The item files are the source of truth. The Lift Tracker Feedback Desk reads them from
disk on every request, so edits made here show up in the browser within seconds -- no
import step, and no need to touch the server.
"""


# The data fingerprint QUEUE.md was last written for. QUEUE.md is generated, so it has to
# be refreshed when the item files change *by any route* -- including an agent editing them
# directly on disk, which is the documented workflow and never touches this process.
# Regenerating only on API writes left it silently stale in exactly that case.
_QUEUE_FINGERPRINT = None


def refresh_queue_if_stale():
    """Cheap guard on the read paths: compare the directory fingerprint against the one
    QUEUE.md was built from, and rebuild only when it moved. QUEUE.md lives outside the
    directories revision() hashes, so rewriting it can't retrigger this."""
    if revision() != _QUEUE_FINGERPRINT:
        write_queue()


def write_queue():
    global _QUEUE_FINGERPRINT
    items = load_items()
    order = {s: i for i, s in enumerate(STATUSES)}
    sev = {s: i for i, s in enumerate(SEVERITIES)}
    live = [i for i in items if i.get("status") not in TERMINAL]
    # Severity is the only priority signal now -- a separate priority field said the same
    # thing twice, and two rankings that can disagree is worse than one that can't.
    live.sort(key=lambda i: (order.get(i.get("status"), 9),
                             sev.get(i.get("severity"), 9),
                             i.get("id", "")))
    lines = [
        "# Feedback queue",
        "",
        "Generated by the Lift Tracker Feedback Desk server on every write -- edit the item files in",
        "`data/items/`, not this file.",
        "",
        "%d open, %d finished." % (len(live), len(items) - len(live)),
        "",
    ]
    if live:
        lines += ["| id | status | type | sev | app / area | title | file |",
                  "| --- | --- | --- | --- | --- | --- | --- |"]
        for i in live:
            area = " / ".join(x for x in (i.get("app"), i.get("area")) if x)
            lines.append("| %s | %s | %s | %s | %s | %s | `data/items/%s` |" % (
                i.get("id", ""), i.get("status", ""), i.get("type", ""),
                i.get("severity", ""), area,
                str(i.get("title", "")).replace("|", "\\|"), i.get("file", "")))
    else:
        lines.append("_Nothing open._")
    lines += ["", AGENT_PROTOCOL]
    atomic_write(QUEUE_FILE, "\n".join(lines) + "\n")
    _QUEUE_FINGERPRINT = revision()


# ---------------------------------------------------------------------------
# Work orders
#
# A work order is a *manifest*: frontmatter naming the item ids, and a body that is
# entirely derived from those items and regenerated on every change. It deliberately does
# not embed each item's text. An earlier version did, and that copy went stale the moment
# anyone edited an item -- handing an agent a confidently wrong description. Pointing at
# the item files instead means there is exactly one source of truth for what an item says.
#
# Everything below therefore treats frontmatter as input and the body as output.
# ---------------------------------------------------------------------------
BRIEF_BODY_NOTE = (
    "<!-- This body is generated by the Lift Tracker Feedback Desk from the frontmatter above and the\n"
    "     item files it names. Edits to it are overwritten on the next change: put durable\n"
    "     notes in `instructions` above, or in the item files themselves. -->"
)


def find_brief_path(brief_id):
    if not os.path.isdir(BRIEFS_DIR):
        return None
    for name in os.listdir(BRIEFS_DIR):
        if name.startswith(brief_id + "-") and name.endswith(".md"):
            return os.path.join(BRIEFS_DIR, name)
    return None


def render_brief_body(fm, items_by_id):
    ids = fm.get("items") or []
    rows, missing = [], []
    for item_id in ids:
        i = items_by_id.get(item_id)
        if not i:
            missing.append(item_id)
            continue
        area = " / ".join(x for x in (i.get("app"), i.get("area")) if x)
        rows.append("| %s | %s | %s | %s | %s | `%s/%s` |" % (
            i.get("id"), i.get("type"), i.get("severity"), area or "—",
            str(i.get("title", "")).replace("|", "\\|"),
            os.path.relpath(ITEMS_DIR, os.path.dirname(ROOT)), i.get("file")))

    parts = [BRIEF_BODY_NOTE, "", "# %s" % fm.get("title", "Work order"), ""]
    parts.append("Work order **%s** — %d item%s. Created %s%s." % (
        fm.get("id"), len(ids), "" if len(ids) == 1 else "s",
        (fm.get("created") or "")[:10],
        ", updated %s" % (fm.get("updated") or "")[:10] if fm.get("updated") else ""))
    parts.append("")

    instructions = (fm.get("instructions") or "").strip()
    if instructions:
        parts += ["## Instructions from the reporter", "", instructions, ""]

    parts += ["## Items", ""]
    if rows:
        parts += ["| id | type | sev | app / area | title | file |",
                  "| --- | --- | --- | --- | --- | --- |"] + rows + [""]
        parts += ["Read each file before starting — the full report and its captured "
                  "context live there, not here.", ""]
    else:
        parts += ["_No items. Add some in the Lift Tracker Feedback Desk, or delete this work order._", ""]
    if missing:
        parts += ["> Missing from `data/items/` (archived?): %s" % ", ".join(missing), ""]

    parts += [AGENT_PROTOCOL]
    return "\n".join(parts)


def write_brief(fm):
    """Persist a work order, regenerating its derived body from the current item files."""
    fm["updated"] = now_iso()
    items_by_id = {i["id"]: i for i in load_items()}
    path = find_brief_path(fm["id"])
    if path is None:
        path = os.path.join(BRIEFS_DIR, "%s-%s.md" % (fm["id"], slugify(fm.get("title"))))
    atomic_write(path, serialize_item(fm, render_brief_body(fm, items_by_id)))
    return os.path.basename(path)


def _set_membership(item_id, brief_id):
    """Point one item at a work order (or at none) and move its status to match.

    An item belongs to at most one order: `brief` is a single field, and "which order is
    this in" should have one answer. Adding an item that already belongs elsewhere removes
    it from that other order, rather than leaving two orders each claiming it.
    """
    path = find_item_path(item_id)
    if not path:
        return None
    with open(path, encoding="utf-8") as f:
        fm, body = parse_item(f.read())
    fm["id"] = item_id
    previous = fm.get("brief") or ""
    fm["brief"] = brief_id or ""
    if brief_id:
        # Queued means "in an order, waiting to be worked". Something already finished stays
        # finished -- being added to an order shouldn't reopen it.
        if fm.get("status") == "backlog":
            fm["status"] = "queued"
    elif fm.get("status") == "queued":
        fm["status"] = "backlog"
    write_item(fm, body)
    return previous


def _detach_from_other_briefs(item_ids, keep_brief_id):
    """Drop item_ids from every other work order's manifest, enforcing single membership."""
    for name in (os.listdir(BRIEFS_DIR) if os.path.isdir(BRIEFS_DIR) else []):
        if not name.endswith(".md") or name.startswith("."):
            continue
        path = os.path.join(BRIEFS_DIR, name)
        with open(path, encoding="utf-8") as f:
            fm, _ = parse_item(f.read())
        if fm.get("id") == keep_brief_id:
            continue
        ids = fm.get("items") or []
        kept = [i for i in ids if i not in item_ids]
        if len(kept) != len(ids):
            fm["items"] = kept
            write_brief(fm)


def create_brief(ids, title, instructions):
    known = {i["id"] for i in load_items()}
    ids = [i for i in dict.fromkeys(ids) if i in known]   # de-duplicate, keep order
    if not ids:
        raise ValueError("no matching items")
    brief_id = next_id("wo", BRIEFS_DIR)
    fm = {
        "id": brief_id,
        "title": title or "Work order",
        "instructions": (instructions or "").strip(),
        "created": now_iso(),
        "items": ids,
    }
    _detach_from_other_briefs(ids, brief_id)
    for item_id in ids:
        _set_membership(item_id, brief_id)
    fm["file"] = write_brief(fm)
    write_queue()
    return fm


def update_brief(brief_id, data):
    """Patch a work order: its title, its instructions, and which items are in it."""
    path = find_brief_path(brief_id)
    if not path:
        raise ValueError("no such work order: %s" % brief_id)
    with open(path, encoding="utf-8") as f:
        fm, _ = parse_item(f.read())
    fm["id"] = brief_id
    if "title" in data:
        fm["title"] = (data["title"] or "").strip() or fm.get("title") or "Work order"
    if "instructions" in data:
        fm["instructions"] = (data["instructions"] or "").strip()

    before = list(fm.get("items") or [])
    if "items" in data or "add" in data or "remove" in data:
        known = {i["id"] for i in load_items()}
        if "items" in data:
            after = [i for i in dict.fromkeys(data["items"] or []) if i in known]
        else:
            after = list(before)
        for item_id in data.get("add") or []:
            if item_id in known and item_id not in after:
                after.append(item_id)
        for item_id in data.get("remove") or []:
            if item_id in after:
                after.remove(item_id)
        fm["items"] = after
        added = [i for i in after if i not in before]
        removed = [i for i in before if i not in after]
        _detach_from_other_briefs(added, brief_id)
        for item_id in added:
            _set_membership(item_id, brief_id)
        for item_id in removed:
            _set_membership(item_id, None)

    fm["file"] = write_brief(fm)
    write_queue()
    return fm


def archive_brief(brief_id):
    """Retire a work order, releasing its items back to `ready` first."""
    path = find_brief_path(brief_id)
    if not path:
        raise ValueError("no such work order: %s" % brief_id)
    with open(path, encoding="utf-8") as f:
        fm, _ = parse_item(f.read())
    for item_id in fm.get("items") or []:
        _set_membership(item_id, None)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    os.replace(path, os.path.join(ARCHIVE_DIR, os.path.basename(path)))
    write_queue()


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=APP_DIR, **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s [%s] %s\n" % (
            datetime.now().strftime("%H:%M:%S"), self.address_string(), fmt % args))

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        # The capture widget embedded in Lift Tracker runs on a different port, which
        # makes its POST here cross-origin. Same trust model as the rest of this tool:
        # it's already reachable unauthenticated by anyone on the LAN, so allowing the
        # browser to make the call it could make anyway costs nothing.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def _json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        return json.loads(self.rfile.read(length) or b"{}")

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def do_GET(self):
        if self.path == "/":
            self.path = "/" + APP_FILE
            return super().do_GET()
        if self.path == "/api/ping":
            return self._json(200, {"ok": True, "server": "feedback-desk"})
        if self.path == "/api/rev":
            refresh_queue_if_stale()
            return self._json(200, {"ok": True, "rev": revision()})
        if self.path == "/api/state":
            refresh_queue_if_stale()
            return self._json(200, {
                "ok": True, "rev": revision(),
                "items": load_items(), "briefs": load_briefs(),
                "meta": {"statuses": STATUSES, "types": TYPES, "severities": SEVERITIES,
                         "itemsDir": os.path.relpath(ITEMS_DIR, os.path.dirname(ROOT)),
                         "briefsDir": os.path.relpath(BRIEFS_DIR, os.path.dirname(ROOT))},
            })
        return super().do_GET()

    def do_POST(self):
        try:
            return self._route_post()
        except ValueError as e:
            return self._json(400, {"ok": False, "error": str(e)})
        except Exception as e:
            self.log_message("POST %s failed: %s", self.path, e)
            return self._json(500, {"ok": False, "error": str(e)})

    def _route_post(self):
        path = self.path
        # /api/capture is the endpoint the in-app widget posts to: labelled fields in,
        # composed markdown out. /api/items takes an already-composed body.
        if path in ("/api/capture", "/api/items"):
            data = self._read_json()
            if path == "/api/capture":
                data = dict(data, body=compose_body(data))
            if not (data.get("title") or "").strip():
                raise ValueError("title is required")
            fm = create_item(data)
            return self._json(200, {"ok": True, "rev": revision(), "item": fm})

        m = re.match(r"^/api/items/([A-Za-z0-9_-]+)$", path)
        if m:
            item_id = m.group(1)
            path_on_disk = find_item_path(item_id)
            if not path_on_disk:
                raise ValueError("no such item: %s" % item_id)
            data = self._read_json()
            with open(path_on_disk, encoding="utf-8") as f:
                fm, body = parse_item(f.read())
            fm["id"] = item_id
            for key, value in data.items():
                if key not in WRITABLE:
                    continue
                if key == "body":
                    body = value or ""
                elif key == "sections":
                    # A partial merge: the editor sends only the box that changed, so an
                    # unrelated section can't be blanked by a save it wasn't part of.
                    current, extras = parse_sections(body)
                    for section_key, text in (value or {}).items():
                        if section_key in SECTION_KEYS:
                            current[section_key] = text or ""
                    body = render_sections(current, extras)
                else:
                    fm[key] = value
            write_item(fm, body)
            return self._json(200, {"ok": True, "rev": revision()})

        m = re.match(r"^/api/items/([A-Za-z0-9_-]+)/archive$", path)
        if m:
            path_on_disk = find_item_path(m.group(1))
            if not path_on_disk:
                raise ValueError("no such item: %s" % m.group(1))
            # Archived, never deleted: a report someone took the trouble to write is worth
            # more than the directory being tidy, and it stays greppable.
            os.makedirs(ARCHIVE_DIR, exist_ok=True)
            os.replace(path_on_disk, os.path.join(ARCHIVE_DIR, os.path.basename(path_on_disk)))
            write_queue()
            return self._json(200, {"ok": True, "rev": revision()})

        if path == "/api/briefs":
            data = self._read_json()
            ids = data.get("ids") or []
            if not isinstance(ids, list) or not ids:
                raise ValueError("ids must be a non-empty list")
            brief = create_brief(ids, data.get("title"), data.get("instructions"))
            return self._json(200, {"ok": True, "rev": revision(), "brief": brief})

        m = re.match(r"^/api/briefs/([A-Za-z0-9_-]+)$", path)
        if m:
            brief = update_brief(m.group(1), self._read_json())
            return self._json(200, {"ok": True, "rev": revision(), "brief": brief})

        m = re.match(r"^/api/briefs/([A-Za-z0-9_-]+)/archive$", path)
        if m:
            archive_brief(m.group(1))
            return self._json(200, {"ok": True, "rev": revision()})

        return self._json(404, {"ok": False, "error": "not found"})


def main():
    parser = argparse.ArgumentParser(description="Lift Tracker Feedback Desk local server")
    parser.add_argument("--port", type=int, default=8441)
    args = parser.parse_args()

    for directory in (ITEMS_DIR, BRIEFS_DIR):
        os.makedirs(directory, exist_ok=True)
    write_queue()

    try:
        server = http.server.ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    except OSError as e:
        print("Couldn't start on port %d: %s" % (args.port, e), file=sys.stderr)
        sys.exit(1)

    ip = local_ip()
    print("Lift Tracker Feedback Desk server running.")
    print("  This machine:               http://localhost:%d/" % args.port)
    print("  Other devices on this WiFi: http://%s:%d/" % (ip, args.port))
    print("  Items: %s" % ITEMS_DIR)
    print("  Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping.")
        server.shutdown()


if __name__ == "__main__":
    main()
