// End-to-end smoke test: drives the real app in a real Chrome over the DevTools
// protocol (no test dependencies -- node 24 ships a global WebSocket). Run it with
// tools/run-tests.sh, which starts Chrome, points it at a running Lift Tracker server,
// and cleans up after itself.
//
// It works on a week far in the future ("2031") so it can never touch real training
// data, and deletes the day it created at the end. A crashed run can leave that one day
// behind; it is safe to delete by hand from data/lift-tracker.json.
import { connect, newTab } from "./cdp.mjs";
const CDP = Number(process.env.CDP_PORT || 9222);
const APP = process.env.APP_URL || "http://localhost:8440/";
const API = APP.replace(/\/$/, "");
const OUT = process.env.OUT_DIR || ".";
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let pass = 0, fail = 0;
const check = (name, ok, detail = "") => {
  console.log(`${ok ? "  PASS" : "  FAIL"}  ${name}${detail ? "  — " + detail : ""}`);
  ok ? pass++ : fail++;
};
const getState = async () => (await (await fetch(API + "/api/state")).json()).state;

// A Monday well past anything real. The app navigates by whole weeks from today, so the
// test drives the same #-less UI a person would, then jumps by setting the week directly.
const TEST_MONDAY = "2031-03-03";
const TEST_DAY_ID = "day_2031-03-05";     // the Wednesday of that week

async function openPage(url, w, h) {
  const tab = await newTab(CDP, url);
  const p = await connect(tab.webSocketDebuggerUrl);
  await p.send("Page.enable");
  await p.send("Runtime.enable");
  await p.send("Emulation.setDeviceMetricsOverride", {
    width: w, height: h, deviceScaleFactor: 1, mobile: w < 700,
  });
  await sleep(1500);
  return p;
}
// Park a page on the test week. state.weekStart is the app's own navigation state, so
// setting it and re-rendering is exactly what the ← / → buttons do.
const gotoTestWeek = (p) => p.evalJS(
  `state.weekStart = "${TEST_MONDAY}"; render(); await new Promise(r => setTimeout(r, 300));`);

// --- 1. phone layout --------------------------------------------------------
console.log("\n[phone layout @ 390x844]");
const phone = await openPage(APP + "#week", 390, 844);
const layout = await phone.evalJS(`
  const over = [...document.querySelectorAll("header, #weekbar, main, .day, .entry, .set-row")]
    .filter(el => el.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
    .map(el => el.tagName + "." + el.className);
  return { vw: document.documentElement.clientWidth,
           days: document.querySelectorAll(".day").length,
           cols: new Set([...document.querySelectorAll(".day")]
             .map(d => Math.round(d.getBoundingClientRect().left))).size,
           tabsVisible: [...document.querySelectorAll("#tabs button")]
             .filter(b => b.getBoundingClientRect().right <= document.documentElement.clientWidth + 1).length,
           overflowing: over };`);
check("viewport is 390px", layout.vw === 390, "vw=" + layout.vw);
check("no element overflows the viewport", layout.overflowing.length === 0, layout.overflowing.join("; "));
check("all seven days of the week are shown", layout.days === 7, layout.days + " day cards");
check("phone stacks them into one column", layout.cols === 1, layout.cols + " column(s)");
check("all tabs fit on screen", layout.tabsVisible === 3, layout.tabsVisible + "/3");

const before = await getState();
check("every day starts as a rest day",
  !before.days.some((d) => d.id === TEST_DAY_ID), "no record for " + TEST_DAY_ID);

// --- 2. rest day -> lift day, through the UI --------------------------------
console.log("\n[flip a rest day to a lift day]");
const desk = await openPage(APP + "#week", 1400, 950);
await gotoTestWeek(desk);
const flipped = await desk.evalJS(`
  const card = document.querySelector('[data-day="2031-03-05"]');
  const wasRest = card.classList.contains("rest");
  card.querySelector("[data-make-lift]").click();
  await new Promise(r => setTimeout(r, 900));
  const now = document.querySelector('[data-day="2031-03-05"]');
  return { wasRest, badge: now.querySelector(".badge").textContent,
           hasPicker: !!now.querySelector("[data-add-to]"),
           pill: document.querySelector("#sync-pill").textContent };`);
check("day started as rest", flipped.wasRest);
check("badge now reads lift", flipped.badge === "lift", flipped.badge);
check("an exercise picker appeared", flipped.hasPicker);
check("save pill shows saved", /^Saved/.test(flipped.pill), flipped.pill);

// --- 3. add an exercise; the scheme dialog, then the sets it promised -------
console.log("\n[add an exercise -- the scheme dialog builds the sets]");
const squat = before.exercises.find((e) => e.name === "Barbell Back Squat");
const squatId = squat?.id;
check("seed library has Barbell Back Squat", !!squatId, squatId);
// Read the expected numbers off the live library rather than hard-coding them: this runs
// against the user's real store, where the maxes, the set counts and the history of a
// movement all move between runs. Anything history-dependent is asserted as a property
// (every Static set matches its neighbours) rather than as a number.
const squatMax = Number(squat?.defaultWeight || 0);
const squatPip = squatMax * 0.025;
const fmtW = (w) => (Math.round(w * 100) / 100).toString();
const allSame = (xs) => xs.length > 0 && xs.every((x) => x === xs[0]);

const dialog = await desk.evalJS(`
  const sel = document.querySelector('[data-day="2031-03-05"] [data-add-to]');
  sel.value = "${squatId}";
  sel.dispatchEvent(new Event("change", { bubbles: true }));
  await new Promise(r => setTimeout(r, 400));
  const m = document.querySelector("#add-modal");
  const peakPreview = () => {
    document.querySelector('[data-scheme="peak"]').click();
    return [...m.querySelectorAll(".add-preview li")]
      .map(li => li.querySelector(".wt").textContent.trim() + " x " + li.querySelector(".rp").textContent.trim());
  };
  const out = { shown: !m.hidden, title: m.querySelector("h3").textContent,
                fields: [...m.querySelectorAll("[data-add-field]")].map(e => e.dataset.addField),
                peak: peakPreview() };
  // back to Static, and ask for a known 3 x 8 rather than whatever the library defaults to
  document.querySelector('[data-scheme="static"]').click();
  await new Promise(r => setTimeout(r, 100));
  const type = (name, v) => { const el = document.querySelector('[data-add-field="' + name + '"]');
    el.focus(); el.value = v; el.dispatchEvent(new Event("input", { bubbles: true })); };
  type("sets", "3"); await new Promise(r => setTimeout(r, 80));
  type("reps", "8"); await new Promise(r => setTimeout(r, 80));
  const rows = [...m.querySelectorAll(".add-preview li")];
  out.staticPreview = rows.length;
  out.staticWeights = rows.map(li => li.querySelector(".wt").textContent.trim());
  document.querySelector("#add-go").click();
  await new Promise(r => setTimeout(r, 1000));
  out.closed = document.querySelector("#add-modal").hidden;
  return out;`);
check("picking a movement opens the scheme dialog", dialog.shown && /Barbell Back Squat/.test(dialog.title),
  dialog.title);
check("Static asks for sets and reps", dialog.fields.join() === "sets,reps", dialog.fields.join());
// 5 . 4 . 2 . 4 . 5, priced at 10 / 8 / 5 pips off the one-rep max.
const wantPeak = [5, 4, 2, 4, 5].map((r) =>
  `${fmtW(squatMax - ({ 5: 10, 4: 8, 2: 5 })[r] * squatPip)} lb x × ${r} reps`);
check("Peak previews the 5·4·2·4·5 wave off the max",
  dialog.peak.join(" | ") === wantPeak.join(" | "), dialog.peak.join(" | "));
check("Static previews the sets it will make", dialog.staticPreview === 3, dialog.staticPreview + " rows");
check("Static previews one weight for all of them", allSame(dialog.staticWeights),
  dialog.staticWeights.join(" | "));
check("the dialog closes on Add", dialog.closed);

const added = await desk.evalJS(`
  const entry = document.querySelector('[data-day="2031-03-05"] .entry');
  return { open: entry.classList.contains("open"),
           name: entry.querySelector(".ex-name").textContent,
           setRows: entry.querySelectorAll(".set-row").length,
           weights: [...entry.querySelectorAll("input.w")].map(i => i.value),
           targets: [...entry.querySelectorAll(".tgt")].map(e => e.textContent),
           reps: [...entry.querySelectorAll("input.r")].map(i => i.value),
           rir: [...entry.querySelectorAll("input.rir")].map(i => i.value),
           rirMax: entry.querySelector("input.rir").maxLength,
           badge: !!entry.querySelector(".entry-head .scheme"),
           repMax: entry.querySelector("input.r").maxLength };`);
check("exercise row appears with its name", added.name === "Barbell Back Squat", added.name);
check("the row you just added is expanded", added.open);
check("three sets created, as the dialog asked", added.setRows === 3, added.setRows + " sets");
// Static means one weight across the whole thing -- last session's opener where there is
// one, the library max where there isn't. Which of those it was is history's business;
// that all three agree, and agree with what the dialog promised, is the scheme's.
check("every Static set gets the same weight", allSame(added.weights), added.weights.join());
check("the sets match the weight the dialog previewed",
  added.weights[0] === dialog.staticWeights[0].replace(/ .*$/, ""),
  added.weights[0] + " vs " + dialog.staticWeights[0]);
check("every set carries the rep target", added.targets.join() === "/8,/8,/8", added.targets.join());
check("Static gets no scheme badge", !added.badge);
check("rep boxes start empty", added.reps.every((r) => r === ""), JSON.stringify(added.reps));
check("RIR boxes start empty", added.rir.every((r) => r === ""), JSON.stringify(added.rir));
check("rep box accepts two digits only", added.repMax === 2, "maxlength=" + added.repMax);
check("RIR box accepts one digit only", added.rirMax === 1, "maxlength=" + added.rirMax);

// --- 4. log reps; the two-digit cap and non-digit stripping hold ------------
console.log("\n[log reps into the empty boxes]");
const logged = await desk.evalJS(`
  const type = (el, v) => { el.focus(); el.value = v; el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true })); el.blur(); };
  const rows = [...document.querySelectorAll('[data-day="2031-03-05"] .set-row')];
  type(rows[0].querySelector("input.r"), "8");
  await new Promise(r => setTimeout(r, 700));
  type(rows[1].querySelector("input.r"), "1234");        // over two digits
  await new Promise(r => setTimeout(r, 700));
  type(rows[2].querySelector("input.r"), "6x");          // stray character
  await new Promise(r => setTimeout(r, 700));
  // and overwrite the auto-populated weight on the last set
  type(rows[2].querySelector("input.w"), "145");
  await new Promise(r => setTimeout(r, 900));
  // RIR: one digit, and 0 is a real answer rather than an empty one
  type(rows[0].querySelector("input.rir"), "2");
  await new Promise(r => setTimeout(r, 700));
  type(rows[1].querySelector("input.rir"), "0");
  await new Promise(r => setTimeout(r, 700));
  type(rows[2].querySelector("input.rir"), "9x7");     // stray characters, over one digit
  await new Promise(r => setTimeout(r, 900));
  const now = [...document.querySelectorAll('[data-day="2031-03-05"] .set-row')];
  return { shown: now.map(r => r.querySelector("input.r").value),
           rir: now.map(r => r.querySelector("input.rir").value),
           loggedClass: now.filter(r => r.classList.contains("logged")).length,
           summary: document.querySelector('[data-day="2031-03-05"] .ex-sum').textContent };`);
// "1234" keeps its first two digits and "6x" drops the stray character: the box is a
// two-digit rep count, and sanitising as you type beats rejecting on save.
check("typed reps stay in the boxes, cleaned", logged.shown.join() === "8,12,6",
  logged.shown.join());
check("all three rows marked logged", logged.loggedClass === 3, logged.loggedClass + "/3");
check("collapsed summary counts them", /3\/3/.test(logged.summary), logged.summary);
check("RIR keeps one digit and drops the rest", logged.rir.join() === "2,0,9", logged.rir.join());

const after = await getState();
const day = after.days.find((d) => d.id === TEST_DAY_ID);
const entry = after.entries.find((e) => e.dayId === TEST_DAY_ID);
const sets = after.sets.filter((s) => s.entryId === entry?.id).sort((a, b) => a.index - b.index);
check("day reached the server file", day?.type === "lift", day?.type);
check("  entry stored with a copied name", entry?.name === "Barbell Back Squat", entry?.name);
check("  three sets stored", sets.length === 3, sets.length + " sets");
check("  reps clamped to two digits", sets.map((s) => s.reps).join() === "8,12,6",
  sets.map((s) => s.reps).join());
check("  overwritten weight stored", sets[2]?.weight === 145, String(sets[2]?.weight));
check("  rep targets stored", sets.map((s) => s.targetReps).join() === "8,8,8",
  sets.map((s) => s.targetReps).join());
check("  RIR stored, 0 included", sets.map((s) => s.rir).join() === "2,0,9",
  sets.map((s) => s.rir).join());
check("  entry records its scheme", entry?.scheme === "static", entry?.scheme);

// --- 5. next week's suggestion comes from this week's weights ---------------
console.log("\n[expected weight is carried forward to the next session]");
const carried = await desk.evalJS(`
  state.weekStart = "2031-03-10"; render();
  await new Promise(r => setTimeout(r, 300));
  document.querySelector('[data-day="2031-03-12"] [data-make-lift]').click();
  await new Promise(r => setTimeout(r, 800));
  const add = document.querySelector('[data-day="2031-03-12"] [data-add-to]');
  add.value = "${squatId}";
  add.dispatchEvent(new Event("change", { bubbles: true }));
  await new Promise(r => setTimeout(r, 400));
  // The dialog defaults are themselves the carry-forward: last session's rep target, and
  // a preview built from last session's weight. Take them as offered.
  const offered = { sets: document.querySelector('[data-add-field="sets"]').value,
                    reps: document.querySelector('[data-add-field="reps"]').value };
  // Ask for three, so the count doesn't ride on the library's current default.
  const setsEl = document.querySelector('[data-add-field="sets"]');
  setsEl.focus(); setsEl.value = "3"; setsEl.dispatchEvent(new Event("input", { bubbles: true }));
  await new Promise(r => setTimeout(r, 100));
  document.querySelector("#add-go").click();
  await new Promise(r => setTimeout(r, 1000));
  // and one more set on the end, which carries the *previous set's* weight forward
  document.querySelector('[data-day="2031-03-12"] [data-add-set]').click();
  await new Promise(r => setTimeout(r, 900));
  return { offered,
           weights: [...document.querySelectorAll('[data-day="2031-03-12"] input.w')].map(i => i.value),
           targets: [...document.querySelectorAll('[data-day="2031-03-12"] .tgt')].map(e => e.textContent) };`);
check("the dialog offers last session's rep target", carried.offered.reps === "8",
  JSON.stringify(carried.offered));
// Static repeats one weight, so the 145 typed into set 3 last week does not come back as
// set 3's start this week -- every set opens on what set 1 opened on.
check("a Static session opens every set on one weight", allSame(carried.weights),
  carried.weights.join());
check("＋ Set adds a fourth", carried.weights.length === 4, carried.weights.length + " sets");
check("＋ Set carries the previous set's weight forward",
  carried.weights[3] === carried.weights[2], carried.weights.slice(2).join(" -> "));
check("＋ Set carries the target forward too", carried.targets.join() === "/8,/8,/8,/8",
  carried.targets.join());

// --- 6. the other device sees it (polling) ----------------------------------
console.log("\n[second device picks up the change by polling]");
await gotoTestWeek(phone);
await sleep(5000);
const seen = await phone.evalJS(`
  state.weekStart = "${TEST_MONDAY}"; render();
  await new Promise(r => setTimeout(r, 200));
  return { text: document.querySelector("#week").textContent.includes("Barbell Back Squat"),
           pill: document.querySelector("#sync-pill").textContent };`);
check("phone tab shows the exercise without a reload", seen.text, "pill: " + seen.pill);

// --- 7. expand/collapse and focus survival ----------------------------------
console.log("\n[expand/collapse, and the caret survives a redraw]");
const focusTest = await desk.evalJS(`
  state.weekStart = "${TEST_MONDAY}"; render();
  await new Promise(r => setTimeout(r, 300));
  const head = document.querySelector('[data-day="2031-03-05"] .entry-head');
  head.click();                                     // collapse
  await new Promise(r => setTimeout(r, 250));
  const collapsed = !document.querySelector('[data-day="2031-03-05"] .entry').classList.contains("open");
  const hiddenSets = getComputedStyle(document.querySelector('[data-day="2031-03-05"] .entry-sets')).display === "none";
  head.click();                                     // expand again
  await new Promise(r => setTimeout(r, 250));
  const reopened = document.querySelector('[data-day="2031-03-05"] .entry').classList.contains("open");
  // now type into a weight box and let the debounced save redraw underneath the caret
  const w = document.querySelector('[data-day="2031-03-05"] input.w');
  w.focus(); w.value = "155"; w.setSelectionRange(2, 2);
  w.dispatchEvent(new Event("input", { bubbles: true }));
  await new Promise(r => setTimeout(r, 1600));
  const now = document.querySelector('[data-day="2031-03-05"] input.w');
  return { collapsed, hiddenSets, reopened,
           focused: document.activeElement === now, caret: now.selectionStart, value: now.value };`);
check("clicking the row collapses it", focusTest.collapsed && focusTest.hiddenSets);
check("clicking again expands it", focusTest.reopened);
check("weight box keeps focus through the redraw", focusTest.focused);
check("caret position preserved", focusTest.caret === 2, "caret=" + focusTest.caret);
check("typed value preserved", focusTest.value === "155", focusTest.value);

// --- 7b. the Library tab ----------------------------------------------------
console.log("\n[library tab]");
const lib = await desk.evalJS(`
  location.hash = "#library";
  await new Promise(r => setTimeout(r, 500));
  const bar = document.querySelector("#weekbar");
  const row = document.querySelector('.lib-row[data-ex="ex_seed01"]');
  return { rows: document.querySelectorAll(".lib-row[data-ex]").length,
           headers: [...document.querySelectorAll(".lib-row .cap")].map(e => e.textContent),
           squat: !!row,
           // The chip's hue comes from MUSCLE_GROUPS, so a coloured group is one the
           // page recognised -- an unknown or legacy value comes out grey at --g-s:0%.
           squatGroup: row.querySelector("[data-ex-group]").value,
           squatChip: row.querySelector("[data-ex-group]").getAttribute("style"),
           squatMax: row.querySelector("[data-ex-max]").value,
           squatPip: row.querySelector("[data-ex-pip]").textContent,
           // hidden alone isn't enough: #weekbar is display:flex, which outranks it.
           barShown: getComputedStyle(bar).display !== "none",
           errors: recentErrors.length };`);
// The library is editable, so its length is whatever the user has made it -- assert the
// seeded rows are there, not that nobody has ever added a movement.
check("library lists the seeded movements", lib.rows >= 10 && lib.squat, lib.rows + " rows");
check("weight column is labelled as a max", lib.headers.includes("Max Weight"),
  lib.headers.join("/"));
check("step column is gone", !lib.headers.includes("Step"), lib.headers.join("/"));
check("muscle group is colour-coded", /--g-h:\d+;--g-s:62%/.test(lib.squatChip || ""),
  lib.squatGroup + " → " + lib.squatChip);
// A pip is 2.5% of the max weight, to one decimal: 135 → 3.4.
check("pip column is 2.5% of the max weight",
  lib.squatPip === (Number(lib.squatMax) * 0.025).toFixed(1),
  `${lib.squatMax} → ${lib.squatPip}`);

// Expanding a row derives 2..12 rep maxes from that one number, one pip lighter per rep.
const reps = await desk.evalJS(`
  document.querySelector('[data-ex-toggle="ex_seed01"]').click();
  await new Promise(r => setTimeout(r, 200));
  const cells = [...document.querySelectorAll('[data-ex-reps="ex_seed01"] .rm')];
  const open = { count: cells.length,
                 first: cells[0]?.querySelector(".w").textContent,
                 last: cells[cells.length - 1]?.querySelector(".w").textContent,
                 inputs: document.querySelectorAll('[data-ex-reps="ex_seed01"] input').length };
  document.querySelector('[data-ex-toggle="ex_seed01"]').click();
  await new Promise(r => setTimeout(r, 200));
  open.closed = !document.querySelector('[data-ex-reps="ex_seed01"]');
  return open;`);
const max = Number(lib.squatMax), pip = max * 0.025;
const fmt = (w) => (Math.round(w * 100) / 100).toString();
check("expanding a row shows the 2..12 rep maxes", reps.count === 11, reps.count + " rows");
check("two-rep max is one pip per rep off the single",
  reps.first === fmt(max - 2 * pip), `${reps.first} vs ${fmt(max - 2 * pip)}`);
check("twelve-rep max is one pip per rep off the single",
  reps.last === fmt(max - 12 * pip), `${reps.last} vs ${fmt(max - 12 * pip)}`);
check("derived rep maxes are not editable", reps.inputs === 0, reps.inputs + " inputs");
check("the row collapses again", reps.closed);

check("week nav is hidden away from the week view", !lib.barShown);
check("no JavaScript errors were thrown all run", lib.errors === 0, lib.errors + " errors");
await desk.evalJS(`location.hash = "#week"; await new Promise(r => setTimeout(r, 400));`);

// --- 8. screenshots ---------------------------------------------------------
for (const [pg, name] of [[phone, "phone-week"], [desk, "desk-week"]]) {
  const shot = await pg.send("Page.captureScreenshot", { format: "png" });
  const fs = await import("node:fs");
  fs.writeFileSync(`${OUT}/${name}.png`, Buffer.from(shot.data, "base64"));
}

// --- 9. clean up ------------------------------------------------------------
// Deleting the day cascades its entries and sets away on the server, which is also the
// last thing this suite asserts: two deletes must leave the store exactly as found.
await fetch(API + "/api/mutate", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ ops: [
    { op: "delete", coll: "days", id: TEST_DAY_ID },
    { op: "delete", coll: "days", id: "day_2031-03-12" },
  ] }),
});
const end = await getState();
check("test days removed", !end.days.some((d) => d.id.startsWith("day_2031-")));
check("their entries went with them",
  !end.entries.some((e) => e.dayId.startsWith("day_2031-")));
check("data left exactly as found",
  end.days.length === before.days.length && end.entries.length === before.entries.length &&
  end.sets.length === before.sets.length,
  `days ${before.days.length}->${end.days.length}, entries ${before.entries.length}->${end.entries.length}, sets ${before.sets.length}->${end.sets.length}`);

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail ? 1 : 0);
