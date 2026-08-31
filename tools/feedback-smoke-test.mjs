// End-to-end smoke test for the Lift Tracker Feedback Desk, and for the capture widget embedded in
// Lift Tracker. Run via tools/run-tests.sh. Needs both servers up (8440 and 8441).
//
// It creates feedback items and one work order, then archives what it created. A crashed
// run can leave items behind; they're safe to archive by hand from the UI.
import { connect, newTab } from "./cdp.mjs";
import fs from "node:fs";
import path from "node:path";

const PORT = Number(process.env.CDP_PORT || 9222);
const DESK = process.env.DESK_URL || "http://localhost:8441/";
const APP = process.env.APP_URL || "http://localhost:8440/";
const OUT = process.env.OUT_DIR || ".";
const ITEMS = process.env.ITEMS_DIR || "feedback-desk/data/items";
const TERMINAL = new Set(["done", "closed"]);   // mirrors the app's own constant
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let pass = 0, fail = 0;
const check = (name, ok, detail = "") => {
  console.log(`${ok ? "  PASS" : "  FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
  ok ? pass++ : fail++;
};
const deskState = async () => (await (await fetch(DESK + "api/state")).json());

async function openPage(url, w, h) {
  const tab = await newTab(PORT, url);
  const p = await connect(tab.webSocketDebuggerUrl);
  await p.send("Page.enable");
  await p.send("Runtime.enable");
  await p.send("Emulation.setDeviceMetricsOverride", { width: w, height: h, deviceScaleFactor: 1, mobile: w < 700 });
  await sleep(1800);
  return p;
}

// --- 1. the desk loads ------------------------------------------------------
console.log("\n[feedback desk loads]");
const desk = await openPage(DESK + "#board", 1400, 900);
const loaded = await desk.evalJS(`
  return { pill: document.querySelector("#sync-pill").textContent,
           cards: document.querySelectorAll(".card").length,
           cols: document.querySelectorAll(".col").length };`);
check("connected to the desk server", /Connected|Saved/.test(loaded.pill), loaded.pill);
check("board shows status columns", loaded.cols === 3, loaded.cols + " open columns");
// A freshly cloned repo has an empty desk, so a card count can't be hardcoded. The
// invariant that actually matters holds either way: the board shows every open item and
// nothing else.
const openNow = (await deskState()).items.filter((i) => i.status !== "closed").length;
check("board renders one card per open item", loaded.cards === openNow,
  `${loaded.cards} cards, ${openNow} open`);

// --- 2. capture through the desk's own form ---------------------------------
console.log("\n[capture through the desk form]");
const before = (await deskState()).items.length;
await desk.evalJS(`
  document.querySelector("#capture").open = true;
  await new Promise(r => setTimeout(r, 200));
  const set = (s, v) => { const el = document.querySelector(s); el.value = v;
    el.dispatchEvent(new Event("input", { bubbles: true })); };
  set("#c-title", "SMOKE desk-form capture");
  set("#c-what", "Typed into the desk's own capture form.");
  set("#c-steps", "1. Open Inbox\\n2. Capture");
  document.querySelector("#c-sev").value = "high";
  document.querySelector("#c-save").click();
  await new Promise(r => setTimeout(r, 1200));`);
let st = await deskState();
const formItem = st.items.find((i) => i.title === "SMOKE desk-form capture");
check("item created", !!formItem, formItem?.id);
check("severity carried through", formItem?.severity === "high", formItem?.severity);
check("no priority field is stored", formItem && !("priority" in formItem),
  Object.keys(formItem || {}).filter((k) => /prio/i.test(k)).join(",") || "none");
// Ids must stay unique for the life of the repo, archived ones included -- they're
// referenced from work orders and resolutions.
const archived = fs.existsSync("feedback-desk/data/archive")
  ? fs.readdirSync("feedback-desk/data/archive").filter((f) => f.startsWith("fb-")) : [];
check("new id doesn't reuse an archived one",
  !archived.some((f) => f.startsWith(formItem.id + "-")), formItem.id);
check("body composed with headings",
  /## What happened/.test(formItem?.body || "") && /## Steps to reproduce/.test(formItem?.body || ""));
check("file written to disk", !!formItem && fs.existsSync(path.join(ITEMS, formItem.file)), formItem?.file);

// --- 3. cross-origin capture from inside Lift Tracker ----------------------
console.log("\n[capture widget inside Lift Tracker]");
const lt = await openPage(APP + "#week", 1400, 900);
const widget = await lt.evalJS(`
  document.querySelector("#btn-feedback").click();
  await new Promise(r => setTimeout(r, 400));
  const open = !document.querySelector("#fb-modal").hidden;
  const set = (s, v) => { const el = document.querySelector(s); el.value = v; };
  set("#fb-title", "SMOKE widget capture from the week view");
  set("#fb-what", "Sent from the Lift Tracker header button.");
  document.querySelector("#fb-type").value = "feature";
  document.querySelector("#fb-send").click();
  await new Promise(r => setTimeout(r, 1500));
  return { open, msg: document.querySelector("#fb-msg")?.textContent || "" };`);
check("widget opens", widget.open);
check("widget reports success", /^Captured fb-/.test(widget.msg), widget.msg);

st = await deskState();
const w = st.items.find((i) => i.title === "SMOKE widget capture from the week view");
check("item reached the desk cross-origin", !!w, w?.id);
check("  area auto-set to the current view", w?.area === "week", w?.area);
check("  type carried through", w?.type === "feature", w?.type);
check("  context has the view and viewport",
  w?.context?.view === "week" && /^\d+x\d+$/.test(w?.context?.viewport || ""),
  JSON.stringify({ view: w?.context?.view, viewport: w?.context?.viewport }));
check("  context has app revision and counts",
  typeof w?.context?.appRev === "number" && typeof w?.context?.counts?.sets === "number",
  `rev=${w?.context?.appRev} sets=${w?.context?.counts?.sets}`);
check("  context has the week being viewed",
  /^\d{4}-\d{2}-\d{2}$/.test(w?.context?.weekStart || "") && Array.isArray(w?.context?.weekTypes),
  w?.context?.weekStart);
check("  context has an errors array", Array.isArray(w?.context?.errors));

// --- 4. work order from a selection -----------------------------------------
console.log("\n[work order from a selection]");
const ids = [formItem.id, w.id];
const order = await desk.evalJS(`
  await new Promise(r => setTimeout(r, 4200));           // let the poll pick up the new items
  for (const id of ${JSON.stringify(ids)}) {
    const box = document.querySelector('[data-pick="' + id + '"]');
    if (box) box.click();
    await new Promise(r => setTimeout(r, 250));
  }
  const trayShown = !document.querySelector("#tray").hidden;
  document.querySelector("#tray-order").click();
  await new Promise(r => setTimeout(r, 400));
  document.querySelector("#o-title").value = "SMOKE work order";
  document.querySelector("#o-notes").value = "Batch instructions from the test.";
  document.querySelector("#o-create").click();
  await new Promise(r => setTimeout(r, 1500));
  return { trayShown };`);
check("selection tray appears", order.trayShown);
st = await deskState();
const brief = st.briefs.find((b) => b.title === "SMOKE work order");
check("brief created", !!brief, brief?.id);
check("brief lists both items", JSON.stringify(brief?.items) === JSON.stringify(ids), JSON.stringify(brief?.items));
const briefPath = () => path.join("feedback-desk/data/briefs", brief.file);
let briefText = brief ? fs.readFileSync(briefPath(), "utf8") : "";
check("brief points at each item's file, rather than copying its text",
  ids.every((id) => briefText.includes(`feedback-desk/data/items/`) && briefText.includes(id)) &&
  !briefText.includes("Typed into the desk's own capture form."),
  "manifest, not snapshot");
check("brief carries the reporter's instructions", briefText.includes("Batch instructions from the test."));
check("brief carries the agent protocol", briefText.includes("## How to work these items"));
check("brief body is marked generated", briefText.includes("This body is generated"));
check("items flipped to queued and point at the brief",
  st.items.filter((i) => ids.includes(i.id)).every((i) => i.status === "queued" && i.brief === brief.id));

// --- 3b. structured section editing -----------------------------------------
console.log("\n[structured section editing]");
await desk.evalJS(`
  location.hash = "#board";
  await new Promise(r => setTimeout(r, 4500));            // let the poll pick up fb items
  document.querySelector('[data-item="${formItem.id}"]').click();
  await new Promise(r => setTimeout(r, 600));`);
const boxes = await desk.evalJS(`
  return { hasRawBody: !!document.querySelector("#d-body"),
           sections: [...document.querySelectorAll("[data-section]")].map(t => t.dataset.section),
           whatValue: document.querySelector("#d-sec-what")?.value || "" };`);
check("raw body pane is gone", !boxes.hasRawBody);
check("one box per section", JSON.stringify(boxes.sections) === '["what","expected","steps","notes"]',
  JSON.stringify(boxes.sections));
check("what-happened box is populated from the file",
  boxes.whatValue.includes("Typed into the desk's own capture form."), boxes.whatValue.slice(0, 40));

await desk.evalJS(`
  const set = (s, v) => { const el = document.querySelector(s); el.focus(); el.value = v;
    el.dispatchEvent(new Event("input", { bubbles: true })); };
  set("#d-sec-expected", "EXPECTED-EDIT");
  await new Promise(r => setTimeout(r, 1600));`);
let edited = (await deskState()).items.find((i) => i.id === formItem.id);
check("editing one box writes only that section",
  edited.sections.expected === "EXPECTED-EDIT" &&
  edited.sections.what.includes("Typed into the desk's own capture form.") &&
  edited.sections.steps.includes("Open Inbox"),
  JSON.stringify(edited.sections));
let raw = fs.readFileSync(path.join(ITEMS, edited.file), "utf8");
check("  file keeps canonical heading order",
  raw.indexOf("## What happened") < raw.indexOf("## What I expected") &&
  raw.indexOf("## What I expected") < raw.indexOf("## Steps to reproduce"));

// Structure repair: mangle the file the way a rogue edit would, then save through the UI.
console.log("\n[a mangled file is repaired on the next save]");
// Keep the frontmatter, replace the body with something structurally broken: loose text
// before any heading, a lowercase heading, and a section the desk doesn't know about.
const fmEnd = raw.indexOf("\n---\n", 4) + "\n---\n".length;
fs.writeFileSync(path.join(ITEMS, edited.file), raw.slice(0, fmEnd) +
  "\nloose paragraph with no heading\n\n## steps\n\nS1\n\n## Approach\n\nagent note\n");
await desk.evalJS(`
  await new Promise(r => setTimeout(r, 4500));           // poll picks up the disk change
  const el = document.querySelector("#d-sec-notes");
  el.focus(); el.value = "REPAIRED";
  el.dispatchEvent(new Event("input", { bubbles: true }));
  await new Promise(r => setTimeout(r, 1600));`);
edited = (await deskState()).items.find((i) => i.id === formItem.id);
raw = fs.readFileSync(path.join(ITEMS, edited.file), "utf8");
check("loose text is recovered as What happened",
  edited.sections.what === "loose paragraph with no heading", edited.sections.what);
check("lowercase heading is normalised", raw.includes("## Steps to reproduce") && !raw.includes("## steps"));
check("the edit landed", edited.sections.notes === "REPAIRED");
check("an unknown section is preserved",
  (edited.extraSections || []).some((x) => x.heading === "Approach" && x.text === "agent note"),
  JSON.stringify(edited.extraSections));
await desk.evalJS(`document.querySelector("#d-close").click(); await new Promise(r=>setTimeout(r,300));`);

// --- 4b. editing work-order membership through the UI -----------------------
console.log("\n[work order membership can be edited]");
// A third item, to add to and remove from the order. Created here rather than borrowed
// from the store: on a fresh desk there is nothing to borrow, and on a used one borrowing
// means shuffling someone's real feedback through a work order mid-test.
const spare = await (await fetch(`${DESK}api/capture`, {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    title: "SMOKE spare item for membership edits", app: "lift-tracker", area: "week",
    type: "polish", severity: "low", what: "Created by the smoke test as a third item." }),
})).json().then((b) => b.item);
check("third item created for the membership test", !!spare?.id && !TERMINAL.has(spare.status),
  spare?.id);
// The desk polls for on-disk changes; the brief editor renders its candidate list from
// whatever the open page has loaded, so wait for that poll before opening it.
await sleep(4500);
await desk.evalJS(`
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
  location.hash = "#orders";
  await new Promise(r => setTimeout(r, 800));
  document.querySelector('[data-edit-brief="${brief.id}"]').click();
  await new Promise(r => setTimeout(r, 400));`);
const editorOpen = await desk.evalJS(`
  return { rows: document.querySelectorAll(".be-row").length,
           checked: document.querySelectorAll(".be-row input:checked").length };`);
check("editor lists every candidate item, including the new one", editorOpen.rows >= 3,
  editorOpen.rows + " rows");
check("current members are pre-checked", editorOpen.checked === ids.length,
  editorOpen.checked + "/" + ids.length);

// add one
await desk.evalJS(`
  document.querySelector('[data-member="${spare.id}"]').click();
  await new Promise(r => setTimeout(r, 1400));`);
st = await deskState();
let b2 = st.briefs.find((b) => b.id === brief.id);
let added = st.items.find((i) => i.id === spare.id);
check("adding an item updates the manifest", (b2.items || []).includes(spare.id), JSON.stringify(b2.items));
check("  added item becomes queued and points at the order",
  added.status === "queued" && added.brief === brief.id, `${added.status} / ${added.brief}`);
briefText = fs.readFileSync(briefPath(), "utf8");
check("  regenerated body lists it", briefText.includes(spare.id));

// remove one
await desk.evalJS(`
  await new Promise(r => setTimeout(r, 600));
  document.querySelector('[data-member="${ids[0]}"]').click();
  await new Promise(r => setTimeout(r, 1400));`);
st = await deskState();
b2 = st.briefs.find((b) => b.id === brief.id);
const removed = st.items.find((i) => i.id === ids[0]);
check("removing an item updates the manifest", !(b2.items || []).includes(ids[0]), JSON.stringify(b2.items));
check("  removed item goes back to backlog with no order",
  removed.status === "backlog" && !removed.brief, `${removed.status} / ${removed.brief || "-"}`);
briefText = fs.readFileSync(briefPath(), "utf8");
check("  regenerated body drops it", !briefText.includes("| " + ids[0] + " |"));

// title edit
await desk.evalJS(`
  const t = document.querySelector("#be-title");
  t.focus(); t.value = "SMOKE work order renamed";
  t.dispatchEvent(new Event("input", { bubbles: true }));
  await new Promise(r => setTimeout(r, 1600));`);
st = await deskState();
b2 = st.briefs.find((b) => b.id === brief.id);
check("title edit persists", b2.title === "SMOKE work order renamed", b2.title);
const focusKept = await desk.evalJS(`
  return { focused: document.activeElement?.id === "be-title",
           value: document.querySelector("#be-title")?.value };`);
check("editor keeps focus through the re-render", focusKept.focused, "value=" + focusKept.value);

// put the removed one back for the archive check below
await fetch(`${DESK}api/briefs/${brief.id}`, { method: "POST",
  headers: { "Content-Type": "application/json" }, body: JSON.stringify({ add: [ids[0]] }) });

// --- 4c. archiving an order releases its items ------------------------------
console.log("\n[archiving an order releases its items]");
await fetch(`${DESK}api/briefs/${brief.id}/archive`, { method: "POST",
  headers: { "Content-Type": "application/json" }, body: "{}" });
st = await deskState();
check("order is gone from the list", !st.briefs.some((b) => b.id === brief.id));
check("its items are back to backlog with no order",
  [...ids, spare.id].every((id) => {
    const it = st.items.find((x) => x.id === id);
    return it && it.status === "backlog" && !it.brief;
  }));

// --- 5. an agent editing a file on disk shows up live ------------------------
console.log("\n[agent edits a file on disk; the open browser follows]");
const target = st.items.find((i) => i.id === formItem.id);
const file = path.join(ITEMS, target.file);
let text = fs.readFileSync(file, "utf8");
text = text.replace(/^status: .*$/m, "status: done") +
  "\n## Resolution\n\nFixed by the smoke test, editing this file directly.\n";
fs.writeFileSync(file, text);
const followed = await desk.evalJS(`
  // Creating a work order deliberately lands you on the Work orders tab (and may leave a
  // copy-fallback modal open, since plain-http pages can't use the clipboard API). Get
  // back to the board before looking for cards.
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
  location.hash = "#board";
  await new Promise(r => setTimeout(r, 500));
  await new Promise(r => setTimeout(r, 6000));          // one poll cycle plus slack
  document.querySelector("#f-closed").click();          // reveal the Done column
  await new Promise(r => setTimeout(r, 400));
  const card = [...document.querySelectorAll(".card")]
    .find(c => c.dataset.item === "${target.id}");
  const col = card?.closest(".col")?.dataset.status;
  return { col, rev: !!card };`);
check("card moved to Done without a reload", followed.col === "done", "column=" + followed.col);
const reread = (await deskState()).items.find((i) => i.id === target.id);
check("resolution text read back through the API", /Fixed by the smoke test/.test(reread?.body || ""));
// QUEUE.md is generated, and an agent editing item files never touches the server -- so
// the read paths have to notice and rebuild it. Without that it silently lists work that
// is already finished.
const queue = fs.readFileSync("feedback-desk/data/QUEUE.md", "utf8");
check("QUEUE.md dropped the closed item without an API write",
  !queue.includes("| " + target.id + " |"),
  queue.split("\n").find((l) => /^\d+ open/.test(l)) || "");

// --- 6. screenshot + cleanup ------------------------------------------------
const shot = await desk.send("Page.captureScreenshot", { format: "png" });
fs.writeFileSync(`${OUT}/feedback-desk.png`, Buffer.from(shot.data, "base64"));

for (const id of ids) {
  await fetch(`${DESK}api/items/${id}/archive`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
}
await fetch(`${DESK}api/items/${spare.id}/archive`, { method: "POST",
  headers: { "Content-Type": "application/json" }, body: "{}" });
// The work order was archived in step 4c; nothing left to clean up for it.

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
