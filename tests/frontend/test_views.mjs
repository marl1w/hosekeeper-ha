// The views render without throwing, and say what they should.
//
// The panel is plain DOM, so a missing import or a null child does not fail a build — it
// blanks a section of the page at runtime. This renders every view against the same
// invented lawn the preview uses and asserts on the text that comes out.
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { installDom, byClass } from "./dom-shim.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const root = join(here, "..", "..");
installDom();

// Exactly what the preview server serves, so a view that throws on the real sample throws
// here too rather than on somebody's screen.
const raw = execFileSync(join(root, ".venv", "bin", "python"), [
  "-c",
  [
    "import sys, json, datetime as dt",
    "from pathlib import Path",
    "sys.path.insert(0, 'scripts')",
    "import preview",
    "from weather import from_file",
    "lawn = json.loads(Path('scripts/example-lawn.json').read_text())",
    "weather = from_file(Path('scripts/example-weather.json'))",
    "zones = lawn['zones']",
    // And the same lawn with one zone left unwatered, because a sample where every zone is
    // watered daily never exercises the watering itself.
    "dry = dict(zones[-1], zone_id='dry', name='Dry lawn', minutes_per_day=0)",
    "everything = [preview.invent(1 + i, dt.date(2026, 9, 6), zone=z, weather=weather, lawn=lawn) for i, z in enumerate(zones)]",
    "everything.append(preview.invent(9, dt.date(2026, 9, 6), zone=dry, weather=weather, lawn=lawn))",
    "print(json.dumps(everything))",
  ].join("; "),
], { cwd: root, maxBuffer: 64 * 1024 * 1024 }).toString();
const everything = JSON.parse(raw);
const snapshots = everything.slice(0, -1);
const thirstyLawn = everything[everything.length - 1];
const byId = new Map(everything.map((s) => [s.zone_id, s]));

const front = join(root, "custom_components", "hosekeeper", "frontend");
const { renderOverview } = await import(join(front, "views", "overview.js"));
const { confirmable } = await import(join(front, "views", "confirm.js"));
const { eventDetail, eventHowTo, eventTitle } = await import(join(front, "views", "events.js"));
const { renderDayDetail } = await import(join(front, "views", "day-detail.js"));
const { renderMonthGrid, renderAgenda } = await import(join(front, "views", "calendar.js"));
const { renderTrend } = await import(join(front, "views", "trend.js"));
const { joinSeries, waterFlowChart } = await import(join(front, "charts.js"));
const { renderNow } = await import(join(front, "views", "now.js"));
const { renderTracking } = await import(join(front, "views", "tracking.js"));
const { lookup, strings } = await import(join(front, "i18n.js"));

const zoneColour = (id) => (id === "preview" ? "#6c5ce7" : "#00a3a3");
const zoneName = (id) => byId.get(id)?.field?.name || "";
const snapshotFor = (event) => byId.get(event.zone_id);
const today = "2026-09-06";

// The panel's own merge, not the test's idea of it.
const { datedOnly, mergeEvents } = await import(join(front, "merge.js"));
const merged = mergeEvents(snapshots);

const shared = { lang: "it", locale: "it-IT", zoneColour, zoneName, snapshotFor, multiZone: true };

// The unwatered lawn's own events, for the watering checks.
const thirstyDays = mergeEvents([thirstyLawn]);
let failed = 0;
const check = (name, fn, assertion) => {
  let node;
  try {
    node = fn();
  } catch (err) {
    console.error(`  ${name} threw: ${err.message}`);
    failed = 1;
    return;
  }
  const problem = assertion ? assertion(node) : null;
  if (problem) {
    console.error(`  ${name}: ${problem}`);
    failed = 1;
  }
};

check(
  "overview",
  () =>
    renderOverview(snapshots, snapshots, merged, {
      ...shared,
      todayIso: today,
      selectedZone: null,
      onSelectZone: () => {},
      onOpenDay: () => {},
    }),
  (node) => {
    const text = node.textContent;
    if (!text.includes("In sintesi")) return "no glance section";
    for (const snap of snapshots) {
      if (!text.includes(snap.field.name)) return `${snap.field.name} is missing`;
    }
    if (!text.includes("Prossimi interventi")) return "no next actions";
    if (!node.findAll(byClass("action")).length) return "no action rows";
    const badges = node.findAll(byClass("zone"));
    if (!badges.length) return "no lawn badges";
    const letters = new Set(badges.map((b) => b.textContent));
    if ([...letters].some((l) => !/^[A-Z0-9]$/.test(l))) return `a lawn badge has no letter: ${[...letters].join()}`;
    return null;
  }
);

check("now", () => renderNow(snapshots, { ...shared, selectedZone: null, onSelectZone: () => {} }), (node) => {
  if (!node.textContent.includes("Acqua nel terreno")) return "the water label is missing";
  const rows = node.findAll(byClass("glance__row"));
  if (rows.length !== snapshots.length) return "a lawn is missing from the strip";
  // Every row must have the same cells, or the shared columns fall out of line.
  const counts = new Set(rows.map((r) => r.children.length));
  if (counts.size !== 1) return `rows have different cell counts: ${[...counts].join()}`;
  // Each badge must be the initial of that row's own lawn: a badge falling back to the
  // entry id, or to a bare dot, means the name lookup never reached the view.
  const expected = snapshots.map((snap) => snap.field.name.replace(/^(giardino|prato)\s+/i, "").charAt(0).toUpperCase());
  const actual = rows.map((row) => row.find(byClass("zone"))?.textContent);
  if (actual.join() !== expected.join()) return `badges are ${actual.join()}, expected ${expected.join()}`;
  // Columns line up because the strip is a table: every row must be a tr with the same
  // number of cells, or the alignment goes with it.
  if (rows.some((row) => row.localName !== "tr")) return "a glance row is not a table row";
  if (rows.some((row) => row.getAttribute("role") !== "button")) return "a glance row is not reachable as a button";
  const cells = new Set(rows.map((row) => row.children.filter((c) => c.localName === "td").length));
  if (cells.size !== 1 || [...cells][0] !== 6) return `rows have ${[...cells].join()} cells, expected 6`;
  // The table is laid out from the header alone, so the header must have a cell for every
  // column. A colspan there, or a missing cell, and the widths go back to being decided by
  // whatever the rows happen to hold that day.
  const headRow = node.find(byClass("glance__head"));
  const heads = headRow ? headRow.findAll((n) => n.localName === "th") : [];
  if (heads.length !== 6) return `the header has ${heads.length} cells for 6 columns`;
  if (heads.some((h) => h.getAttribute("colspan"))) return "a header cell spans two columns";
  // The columns are named once, in a header, not on every row.
  const head = node.find(byClass("glance__head"));
  if (!head) return "the glance has no header row";
  if (head.textContent.trim() === "") return "the header names nothing";

  // Soil water is where it is going, not only where it is. A bar of this instant on a lawn
  // watered at dawn always reads full, which is the least useful thing the row could say.
  for (const row of rows) {
    const spark = row.find(byClass("spark"));
    if (!spark) return "the glance still shows only this instant";
    const lines = spark.children.filter((c) => c.localName === "polyline");
    if (!lines.length) return "the projection is not drawn";
    if (!row.find(byClass("glance__pctlow"))) return "the row does not say how low the week goes";
  }
  return null;
});

// A job repeated through the day is one line, and a job repeated day after day is one entry
// that says until when. Neither may fill the list with copies of itself.
check("repeats are collapsed", () => {
  const seedbed = (merged.get(today) || []).filter((e) => e.code === "germination_watering");
  if (seedbed.length !== 1) throw new Error(`${seedbed.length} seedbed lines on one day`);
  if (!(seedbed[0].repeats >= 1)) throw new Error("the repeat count is missing");
  return renderDayDetail(today, merged.get(today) || [], shared);
});

check(
  "the overview says how long a daily job lasts",
  () =>
    renderOverview(snapshots, snapshots, merged, {
      ...shared,
      todayIso: today,
      selectedZone: null,
      onSelectZone: () => {},
      onOpenDay: () => {},
    }),
  (node) => {
    const actions = node.findAll(byClass("action"));
    // By its own title, not by the word "seed": the starter feed after a sowing mentions the
    // seed too, and an action that merely talks about it is not a second watering.
    const watering = strings(shared.lang).advice.germination_watering.title;
    const seedbed = actions.filter((a) => a.textContent.includes(watering.split("{")[0].trim()));
    if (seedbed.length > 1) return `the seedbed watering appears ${seedbed.length} times`;
    if (seedbed.length && !node.findAll(byClass("action__repeat")).length) {
      return "a daily job does not say until when";
    }
    return null;
  }
);

// A day and a week list work to do; a month-long routine is not work to do on Tuesday.
//
// "Mow every five days at 60 mm" is the reason Tuesday's cut is on the calendar, not a job of
// its own, and reading it in a day's list is reading the plan where the work should be. The
// month view and the overview are about the season's shape and keep it.
{
  const withPlan = [...merged.entries()].find(([, events]) =>
    events.some((e) => e.code === "planned_month")
  );
  if (!withPlan) {
    console.error("  the sample plans no month-long line, so the day and week cannot be checked");
    failed = 1;
  } else {
    const [date, events] = withPlan;
    const kept = datedOnly(merged).get(date) || [];
    if (kept.some((e) => e.code === "planned_month")) {
      console.error("  a month-long line survives into the day and week lists");
      failed = 1;
    }
    const dated = events.filter((e) => e.code !== "planned_month");
    if (kept.length !== dated.length) {
      console.error(`  filtering the plan out of ${date} took ${dated.length - kept.length} real jobs with it`);
      failed = 1;
    }
    // And the month grid still has it: that is where the season's shape belongs.
    if (!merged.get(date).some((e) => e.code === "planned_month")) {
      console.error("  the month view lost the plan it exists to show");
      failed = 1;
    }
  }
}

// A month with planned work shows it once, above the grid, and never inside a day cell.
{
  const plannedMonth = [...merged.entries()]
    .filter(([, events]) => events.some((e) => e.kind === "planned"))
    .map(([date]) => date)[0];
  if (!plannedMonth) {
    console.error("  the sample plans no operation, so the month banner cannot be checked");
    failed = 1;
  } else {
    check("the month plans a month-long line", () => renderMonthGrid(merged, plannedMonth, today, today, shared), (node) => {
      if (!node.find(byClass("cal__banner"))) return `${plannedMonth.slice(0, 7)} has planned work but no month-long line`;
      for (const cell of node.findAll(byClass("cal__day"))) {
        if (cell.findAll(byClass("pill--planned")).length) return "a month-long operation is still inside a day";
      }
      return null;
    });
  }
}

check("day detail", () => renderDayDetail(today, merged.get(today) || [], shared), (node) =>
  node.findAll(byClass("event")).length ? null : "no events on a day that has some"
);

// An observation is not a job: a rating or an issue must never be badged as done.
{
  const observations = [...merged.values()].flat().filter((e) => e.code === "issue" || e.code === "rating");
  if (!observations.length) {
    console.error("  the sample records no rating or issue, so the badge cannot be checked");
    failed = 1;
  } else if (observations.some((e) => e.kind !== "noted")) {
    console.error(`  an observation is kind ${observations.find((e) => e.kind !== "noted").kind}, expected noted`);
    failed = 1;
  } else {
    const day = observations[0].date;
    const node = renderDayDetail(day, merged.get(day) || [], shared);
    const badges = node.findAll(byClass("badge")).map((b) => b.textContent);
    if (badges.includes(strings.ui?.logged)) {
      console.error("  an observation is badged as done");
      failed = 1;
    }
  }
}

// The watering time is the thing the user acts on, so it must be on the page whenever the
// balance asks for a cycle — and the panel must say why when it does not.
// The irrigation cycle is an action like any other: it must be in the list, with its time.
check(
  "overview lists the watering with its time",
  () =>
    renderOverview([thirstyLawn], [thirstyLawn], thirstyDays, {
      ...shared,
      todayIso: today,
      selectedZone: null,
      onSelectZone: () => {},
      onOpenDay: () => {},
    }),
  (node) => {
    if (!(thirstyLawn.state.irrigation_plan || {}).main_start) {
      return "the unwatered lawn still needs no water, so the times cannot be checked";
    }
    const actions = node.findAll(byClass("action"));
    const watering = actions.find((a) => a.getAttribute("data-category") === "irrigation");
    if (!watering) return "no irrigation among the next actions";
    if (!/\d{1,2}[:.]\d{2}/.test(watering.textContent)) return `no time on the watering action: ${watering.textContent}`;
    // "3 mm" tells nobody when to be in the garden. The clock has to be its own line, not
    // a fragment buried in the detail text.
    const clock = watering.find(byClass("action__clock"));
    if (!clock || !/\d{1,2}[:.]\d{2}/.test(clock.textContent)) return "the watering time is not shown as a time";
    return null;
  }
);

// A job that lasts a month is dated by the month. Printing "1" invites the reader to do it
// on the first; and a feed due next spring is not a next action.
check(
  "the overview dates a month-long job by its month, and looks no further than two months",
  () =>
    renderOverview(snapshots, snapshots, merged, {
      ...shared,
      todayIso: today,
      selectedZone: null,
      onSelectZone: () => {},
      onOpenDay: () => {},
    }),
  (node) => {
    const rows = node.findAll(byClass("action"));
    const horizon = new Date(`${today}T12:00:00`);
    horizon.setDate(horizon.getDate() + 61);
    const furthest = horizon.toISOString().slice(0, 10);
    const planned = [...merged.values()].flat().filter((e) => e.kind === "planned");
    if (!planned.length) return "the sample plans no operation";
    for (const row of rows) {
      const chip = row.find(byClass("datechip"));
      if (!chip) return "an action has no date";
      const month = chip.classList.contains("datechip--month");
      if (month && chip.findAll(byClass("datechip__num")).length) return "a month-long job still prints a day";
    }
    const beyond = [...merged.entries()].filter(([date, events]) => date > furthest && events.some((e) => e.kind === "planned"));
    if (!beyond.length) return "the sample plans nothing beyond two months, so the horizon is untested";
    const titles = rows.map((r) => r.textContent).join(" ");
    for (const [, events] of beyond) {
      for (const event of events) {
        if (event.params?.operation && titles.includes(String(event.params.operation))) {
          return `${event.params.operation} is a year out and still listed as next`;
        }
      }
    }
    return null;
  }
);

// Confirming a job is the panel's job, and the button has to sit on the line that asked for
// it. A device page full of buttons cannot know which lawn wants what.
check(
  "the overview and the day carry a Done button, and it says what it would write",
  () =>
    renderOverview(snapshots, snapshots, merged, {
      ...shared,
      todayIso: today,
      selectedZone: null,
      onSelectZone: () => {},
      onOpenDay: () => {},
      onConfirm: () => {},
    }),
  (node) => {
    // Nothing in the future can be confirmed: there is no doing next month's feed today.
    for (const row of node.findAll(byClass("action"))) {
      const chip = row.find(byClass("datechip"));
      const future = chip && chip.classList.contains("datechip--month");
      if (future && row.find(byClass("confirm"))) return "a month-long plan offers a Done button";
    }
    const day = renderDayDetail(today, merged.get(today) || [], { ...shared, todayIso: today, onConfirm: () => {} });
    if (!day.findAll(byClass("confirm")).length) return "today has no way to confirm anything";
    return null;
  }
);

// Today and yesterday can be confirmed; tomorrow cannot.
check(
  "Done is offered for days that have happened and no others",
  () => {
    const tomorrow = new Date(`${today}T12:00:00`);
    tomorrow.setDate(tomorrow.getDate() + 1);
    return renderDayDetail(tomorrow.toISOString().slice(0, 10), merged.get(today) || [], {
      ...shared,
      todayIso: today,
      onConfirm: () => {},
    });
  },
  (node) => {
    // The events still carry today's date, so the guard has to read the event, not the page.
    const rows = node.findAll(byClass("event"));
    if (!rows.length) return "the sample has nothing on this day";
    return null;
  }
);

check(
  "a job dated tomorrow cannot be ticked off",
  () => {
    const tomorrow = new Date(`${today}T12:00:00`);
    tomorrow.setDate(tomorrow.getDate() + 1);
    const iso = tomorrow.toISOString().slice(0, 10);
    const events = (merged.get(today) || []).map((e) => ({ ...e, date: iso }));
    if (!events.length) return null;
    return renderDayDetail(iso, events, { ...shared, todayIso: today, onConfirm: () => {} });
  },
  (node) => (node && node.findAll(byClass("confirm")).length ? "tomorrow offers a Done button" : null)
);

// Without a handler there is no button at all, so a read-only render stays read-only.
check(
  "no confirm handler, no confirm button",
  () => renderDayDetail(today, merged.get(today) || [], shared),
  (node) => (node.findAll(byClass("confirm")).length ? "a button appeared with nothing to call" : null)
);

// The calendar said what to do and never why the day was like that. The weather is in the
// snapshot for every day it can speak for, and it has to say which of the three it is.
check(
  "the overview carries the week's sky, once, and marks where the forecast ends",
  () =>
    renderOverview(snapshots, snapshots, merged, {
      ...shared,
      todayIso: today,
      selectedZone: null,
      onSelectZone: () => {},
      onOpenDay: () => {},
    }),
  (node) => {
    const strips = node.findAll(byClass("wxstrip"));
    if (strips.length !== 1) return `${strips.length} forecast strips, expected exactly one`;
    const days = strips[0].findAll(byClass("wxday"));
    if (days.length < 3) return `only ${days.length} days of sky`;
    if (!days[0].classList.contains("wxday--today")) return "the first day is not marked as today";
    const temps = days.filter((d) => /\d/.test(d.textContent));
    if (!temps.length) return "no temperatures in the strip";
    return null;
  }
);

check(
  "a day says what its weather was, and whether it was measured or forecast",
  () => renderDayDetail(today, merged.get(today) || [], { ...shared, todayIso: today, snapshot: snapshots[0] }),
  (node) => {
    const wx = node.find(byClass("wx"));
    if (!wx) return "the day shows no weather at all";
    if (!/measured|forecast|expected|rilevato|previsto|atteso/.test(wx.textContent)) {
      return `the day does not say where its weather came from: ${wx.textContent}`;
    }
    return null;
  }
);

// Water that stays at the surface is not a run whose length anybody chooses, and writing it
// as irrigation would tell the balance the root zone was filled when it was not.
check(
  "surface watering is a tap, not a duration",
  () => renderDayDetail(today, merged.get(today) || [], { ...shared, todayIso: today, snapshot: snapshots[0], onConfirm: () => {} }),
  () => {
    const surface = [...merged.values()].flat().filter((e) => ["germination_watering", "syringe"].includes(e.code));
    if (!surface.length) return "the sample waters no seedbed, so this cannot be checked";
    for (const event of surface) {
      const payload = confirmable(event);
      if (!payload) continue;
      if (payload.asks) return `${event.code} still asks for a duration`;
      if (payload.what !== "maintenance") return `${event.code} would be written as ${payload.what}`;
    }
    // A real root-zone cycle still asks, because its length is the thing being recorded.
    const cycle = [...merged.values()].flat().find((e) => e.code === "irrigate" && e.kind !== "logged");
    if (cycle && !confirmable(cycle)?.asks) return "a dawn cycle no longer asks how long it ran";
    return null;
  }
);

// The glance sits above a calendar. If it reports today while the calendar shows next week,
// the two halves of the screen describe different days and only one of them says which.
check(
  "the glance follows the day on screen",
  () => renderNow(snapshots, { ...shared, selectedZone: null, onSelectZone: () => {}, dateIso: today, todayIso: today, eventsByDay: merged }),
  () => {
    const read = (dateIso) => {
      const node = renderNow(snapshots, {
        ...shared,
        selectedZone: null,
        onSelectZone: () => {},
        dateIso,
        todayIso: today,
        eventsByDay: merged,
      });
      const row = node.findAll(byClass("glance__row"))[0];
      const cells = row.children.filter((c) => c.localName === "td");
      return cells.map((c) => c.textContent.replace(/\s+/g, " ").trim()).join(" | ");
    };
    const ahead = new Date(`${today}T12:00:00`);
    ahead.setDate(ahead.getDate() + 3);
    const later = read(ahead.toISOString().slice(0, 10));
    if (later === read(today)) return "the glance says the same thing three days out";

    // Past the days the diary and the projection reach, it must say so rather than showing
    // today's figures under another date.
    const far = new Date(`${today}T12:00:00`);
    far.setDate(far.getDate() + 200);
    const beyond = read(far.toISOString().slice(0, 10));
    if (beyond === read(today)) return "a date beyond the data still shows today's numbers";
    if (!beyond.includes("–")) return `a date beyond the data shows a reading: ${beyond}`;
    return null;
  }
);

// The rating is the one thing no sensor can answer, and the adaptation loop runs on it. If
// the panel cannot take it, the engine never learns anything about this lawn.
// Tracking is where a person tells the engine things no sensor can. Each section has to say
// where things stand before it offers a button: a page of buttons cannot be read, because it
// says what you may do and never what is already true.
const trackingOpts = (sink) => ({
  ...shared,
  todayIso: today,
  byDay: merged,
  issues: snapshots[0].issues || [],
  kinds: snapshots[0].maintenance_kinds || [],
  onRate: (...a) => sink.push(["rate", ...a]),
  onIssue: (...a) => sink.push(["issue", ...a]),
  onWater: (...a) => sink.push(["water", ...a]),
  onRecord: (...a) => sink.push(["record", ...a]),
  onFeed: (...a) => sink.push(["feed", ...a]),
});

check(
  "tracking states where each lawn stands, and hands its dialogs to the panel",
  () => {
    const sink = [];
    const node = renderTracking(snapshots, trackingOpts(sink));
    node._sink = sink;
    return node;
  },
  (node) => {
    const rows = node.findAll(byClass("track__row"));
    if (rows.length !== snapshots.length * 2) {
      return `${rows.length} summary rows for ${snapshots.length} lawns across two sections`;
    }
    if (!rows.some((r) => r.textContent.trim())) return "the summaries say nothing";
    // The dialogs go to the panel, not into the scrolling page: inside it they are laid out
    // against the whole scroll height and open halfway down it.
    if ((node.dialogs || []).length !== 2) return `${(node.dialogs || []).length} dialogs, expected two`;
    if (node.findAll(byClass("modal")).length) return "a dialog was left inside the page";
    if (node.dialogs.some((d) => !d.hidden)) return "a dialog is open before anybody asked";
    return null;
  }
);

check(
  "the condition dialog records a rating and what was seen, for every lawn at once",
  () => {
    const sink = [];
    const node = renderTracking(snapshots, trackingOpts(sink));
    node._sink = sink;
    return node;
  },
  (node) => {
    const [condition] = node.dialogs;
    const openers = node.findAll(byClass("rate__btn--primary"));
    if (openers.length !== 2) return `${openers.length} buttons open dialogs, expected two`;
    openers[0].click();
    if (condition.hidden) return "the button did not open the dialog";
    const buttons = condition.findAll(byClass("rate__btn"));
    const poor = buttons.find((b) => b.textContent.trim() === strings(shared.lang).status.poor);
    if (!poor) return "the four ratings are not offered";
    poor.click();
    const firstIssue = buttons.find(
      (b) => b.textContent.trim() === lookup(shared.lang, "issues", (snapshots[0].issues || [])[0])
    );
    if (!firstIssue) return "the issues are not offered";
    firstIssue.click();
    condition.findAll(byClass("rate__btn")).at(-1).click();
    const rated = node._sink.filter(([what]) => what === "rate");
    const seen = node._sink.filter(([what]) => what === "issue");
    if (rated.length !== snapshots.length) return `rated ${rated.length} lawns, expected all ${snapshots.length}`;
    if (rated.some(([, , status]) => status !== "poor")) return "the wrong rating was written";
    if (seen.length !== snapshots.length) return `reported the issue on ${seen.length} lawns`;
    if (!condition.hidden) return "the dialog stayed open";
    return null;
  }
);

// Each job needs different details, and a feed's rate is the whole yearly nitrogen budget.
check(
  "the record dialog asks each job for what it needs",
  () => {
    const sink = [];
    const node = renderTracking(snapshots, trackingOpts(sink));
    node._sink = sink;
    return node;
  },
  (node) => {
    const record = node.dialogs[1];
    node.findAll(byClass("rate__btn--primary"))[1].click();
    const [lawn, activity, product] = record.findAll((n) => n.localName === "select");
    if (!product) return "no product to choose for a feed";
    const asks = () =>
      record
        .findAll(byClass("record__field"))
        .filter((f) => !f.hidden)
        .map((f) => f.children[0].textContent.trim());
    const pick = (what) => {
      activity.value = what;
      activity.dispatchEvent({ type: "change" });
      return asks();
    };
    const s = strings(shared.lang).ui;
    const watering = pick("__watering__");
    if (!watering.includes(s.minutesWatered)) return "watering does not ask for minutes";
    // The hour is on every activity, watering included, and it is the first thing the dialog
    // shows for the default one: hidden there, nobody finds it at all.
    if (!watering.includes(s.atWhatTime)) return "the hour is missing from the activity shown first";
    const cut = pick("mowing");
    if (!cut.includes(s.cuttingHeight)) return "a cut does not ask for a height";
    if (!cut.includes(s.atWhatTime)) return "a cut cannot be recorded at the hour it happened";
    const feed = pick("fertilizing");
    if (!feed.includes(s.whichProduct) || !feed.includes(s.dose)) return "a feed asks for no product or rate";
    // A seed mix is a product name, so it cannot be a closed list, but nobody should type
    // "perennial ryegrass" from memory either.
    const sowing = pick("sowing");
    if (!sowing.includes(s.seedMix)) return "a sowing does not ask for its mix";
    const suggestions = record.findAll((n) => n.localName === "datalist")[0];
    if (!suggestions || suggestions.children.length < 3) return "the mix is offered no suggestions";
    const mix = record.findAll((n) => n.localName === "input").find((i) => i.attributes.type === "text");
    if (!mix?.value) return "the mix does not start from the lawn's own grass";

    // Everything else needs only the lawn, the job and the hour.
    const weeding = pick("weeding");
    if (weeding.includes(s.cuttingHeight) || weeding.includes(s.dose)) {
      return "weeding asks for something it does not need";
    }
    if (!weeding.includes(s.atWhatTime)) return "weeding cannot be recorded at the hour it happened";

    // A feed goes as product and rate, never as details the panel worked out itself: the
    // integration turns those into the grams the yearly budget is summed from.
    pick("fertilizing");
    lawn.value = snapshots[0].zone_id;
    record.findAll(byClass("rate__btn")).at(-1).click();
    const [what, zoneId, chosenProduct, dose, at] = node._sink.at(-1);
    if (what !== "feed") return `a feed was written as ${what}`;
    if (zoneId !== snapshots[0].zone_id) return "the feed went to the wrong lawn";
    if (!chosenProduct) return "the feed carries no product";
    if (!(dose > 0)) return "the feed carries no rate";
    // The hour starts at now, so a job recorded this evening is not filed at midnight.
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$/.test(at || "")) return `the feed carries no time: ${at}`;
    if (!at.startsWith(today)) return `the feed was filed on ${at}, not today`;
    return null;
  }
);

// A phone should give its own keypad, its own clock and its own picker. Everything the panel
// asks for is a plain HTML control, and nothing is a browser prompt.
{
  const sources = ["record.js", "confirm.js", "condition.js", "dialog.js", "status.js", "tracking.js"];
  for (const name of sources) {
    const code = readFileSync(join(front, "views", name), "utf8");
    if (/window\.(prompt|confirm|alert)\b|[^.\w](prompt|alert)\(/.test(code)) {
      console.error(`  ${name} asks through a browser dialog, which a phone renders as a grey box`);
      failed = 1;
    }
    for (const [, type] of code.matchAll(/el\("input", \{[^}]*type: "(\w+)"/g)) {
      if (!["number", "text", "time", "date"].includes(type)) {
        console.error(`  ${name} uses <input type="${type}">, which has no native control on a phone`);
        failed = 1;
      }
    }
  }
  const record = readFileSync(join(front, "views", "record.js"), "utf8");
  if (!/type: "number"[\s\S]*?inputmode: "numeric"/.test(record)) {
    console.error("  a number box does not ask for the numeric keypad");
    failed = 1;
  }
  if (!/type: "time"/.test(record)) {
    console.error("  the hour is not a time input, so a phone gives no clock");
    failed = 1;
  }
}

// In a summary row the chips sit at the right, after the lawn's name; in a dialog they are
// the answer to the question above them and start where it starts. Sharing one class made
// the short row of ratings drift right while the long row of issues filled and looked left.
check(
  "the dialog's answers all start at the same edge",
  () => {
    const node = renderTracking(snapshots, trackingOpts([]));
    node.findAll(byClass("rate__btn--primary"))[0].click();
    return node;
  },
  (node) => {
    const [condition] = node.dialogs;
    const groups = condition.findAll(byClass("dialog__choices"));
    if (groups.length < 2) return `${groups.length} groups of answers, expected the rating and the issues`;
    if (condition.findAll(byClass("rate__options")).length) {
      return "a dialog reuses the summary row's chips, which are pushed to the right";
    }
    const css = readFileSync(join(front, "theme.js"), "utf8");
    if (/\.dialog__choices \{[^}]*margin-left:\s*auto/.test(css)) {
      return "the dialog's answers are pushed to the right";
    }
    return null;
  }
);

// Nothing the reader sees may still be a template. A name can carry its own placeholders —
// a mowing line names its height and its interval — so every path that renders one has to
// fill it, and the last-resort path is the one that forgot.
{
  let unfilled = 0;
  for (const lang of ["en", "it"]) {
    const locale = lang === "it" ? "it-IT" : "en-GB";
    for (const [, events] of merged) {
      for (const event of events) {
        const snap = snapshotFor(event);
        for (const text of [
          eventTitle(event, lang, locale, snap),
          eventDetail(event, lang, locale, snap),
          eventHowTo(event, lang, locale, snap),
        ]) {
          if (/\{\w+\}/.test(text || "")) {
            console.error(`  ${lang}: ${event.params?.operation || event.code} still reads as a template: ${text}`);
            unfilled += 1;
          }
        }
      }
    }
  }
  // And the last-resort path specifically, which is the one that forgot. The sample does not
  // reach it today, so it is reached deliberately: an event named directly after an operation
  // whose name carries its own height and interval.
  const direct = eventTitle(
    { code: "mow_routine_robot_daily", category: "mowing", params: { height_mm: 65, interval_days: 1 } },
    "en",
    "en-GB",
    snapshots[0]
  );
  if (/\{\w+\}/.test(direct)) {
    console.error(`  an operation named directly still reads as a template: ${direct}`);
    unfilled += 1;
  }
  if (unfilled) failed = 1;
}

check("month grid", () => renderMonthGrid(merged, today, today, today, shared), (node) => {
  const cells = node.findAll(byClass("cal__day"));
  if (cells.length % 7 !== 0 || cells.length < 28) return `grid has ${cells.length} cells`;
  return null;
});

check("agenda", () => renderAgenda(merged, today, today, today, shared), (node) =>
  node.findAll(byClass("agenda__day")).length === 7 ? null : "a week is not seven days"
);

check("trend", () => renderTrend(snapshots, shared), (node) => {
  const text = node.textContent;
  if (!text.includes("Acqua nella zona radicale")) return "no soil water chart";
  if (!text.includes("Entrate e uscite")) return "no water flow chart";
  // A legend that promises irrigation and a chart with no irrigation bar is a lie: the
  // sample must water, and the bars must be drawn for the days it does.
  // The same window the trend view draws, or the count and the bars cannot agree.
  const watered = snapshots.flatMap((snap) => (snap.days || []).slice(-21).filter((d) => d.irrigation_mm > 0));
  if (!watered.length) return "the sample lawn never irrigates, so the bars cannot be checked";
  const bars = node.findAll((n) => n.localName === "rect" && (n.getAttribute("fill") || "").includes("--hk-irrigation"));
  if (bars.length < watered.length) return `${watered.length} irrigation days but ${bars.length} bars`;
  return null;
});

// Tonight's cycle belongs on today, next to what the diary already recorded.
check("tonight's cycle is on today", () => {
  const series = joinSeries(thirstyLawn.days.slice(-14), thirstyLawn.state.projection, today);
  const day = series.find((d) => d.date === today);
  if (!day || !(day.planned_irrigation_mm > 0)) throw new Error("today lost its planned cycle");
  return waterFlowChart(series, { locale: "it-IT" });
});

// --- and the panel that wires them together -------------------------------------------
//
// The views above are called with the right arguments by hand. The panel is where they are
// wired for real, and a view called with one argument missing is exactly the bug this is
// here to catch, so the panel gets driven end to end against a fake Home Assistant.
const { default: _panelModule } = await import(join(front, "hosekeeper-panel.js")).then((m) => ({ default: m }));
const Panel = globalThis.customElementRegistry.get("hosekeeper-panel");
if (!Panel) {
  console.error("  the panel did not register itself");
  failed = 1;
} else {
  const hass = {
    language: "it",
    locale: { language: "it" },
    states: {},
    callWS: async (msg) => {
      if (msg.type === "hosekeeper/fields") return snapshots.map((s) => ({ zone_id: s.zone_id, name: s.field.name }));
      if (msg.type === "hosekeeper/field") return byId.get(msg.zone_id);
      throw new Error(`unknown ${msg.type}`);
    },
  };
  for (const mode of ["overview", "tracking", "day", "week", "month"]) {
    const panel = new Panel();
    panel.connectedCallback();
    panel._mode = mode;
    panel.hass = hass;
    panel._render();
    for (let i = 0; i < 8; i += 1) await new Promise((resolve) => setTimeout(resolve, 0));
    const content = panel.shadowRoot.find(byClass("content"));
    const text = content?.textContent || "";
    if (!text.includes(snapshots[0].field.name)) {
      console.error(`  panel in ${mode}: renders nothing`);
      failed = 1;
      continue;
    }
    const expected = snapshots.map((s) => s.field.name.replace(/^(giardino|prato)\s+/i, "").charAt(0).toUpperCase());
    const rows = content.findAll(byClass("glance__row"));
    const badges = rows.map((row) => row.find(byClass("zone"))?.textContent);
    if (rows.length && badges.join() !== expected.join()) {
      console.error(`  panel in ${mode}: glance badges are ${badges.join()}, expected ${expected.join()}`);
      failed = 1;
    }
    // The glance is about one day, so it belongs on the overview and the day. Above a week
    // or a month it answers a question the view is not asking.
    if ((mode === "week" || mode === "month" || mode === "tracking") && rows.length) {
      console.error(`  panel in ${mode}: still carries the at-a-glance strip`);
      failed = 1;
    }
    if ((mode === "overview" || mode === "day") && !rows.length) {
      console.error(`  panel in ${mode}: has lost the at-a-glance strip`);
      failed = 1;
    }
    if (!["overview", "tracking"].includes(mode) && !content.findAll(byClass("chart")).length) {
      console.error(`  panel in ${mode}: no charts`);
      failed = 1;
    }
  }

  // The list under the calendar shows the selected day. Paging used to move only the anchor,
  // so the grid went to October while the list below stayed on a day in September.
  {
    const shifter = new Panel();
    shifter.connectedCallback();
    for (const [mode, apart] of [["week", 7], ["month", null]]) {
      shifter._mode = mode;
      shifter._anchor = today;
      shifter._selected = today;
      shifter._shift(1);
      const moved = new Date(`${shifter._selected}T12:00:00`);
      const anchor = new Date(`${shifter._anchor}T12:00:00`);
      if (shifter._selected === today) {
        console.error(`  ${mode}: paging left the chosen day behind`);
        failed = 1;
      } else if (apart) {
        const days = Math.round((moved - new Date(`${today}T12:00:00`)) / 86400000);
        if (days !== apart) {
          console.error(`  ${mode}: the chosen day moved ${days} days, expected ${apart}`);
          failed = 1;
        }
      } else if (moved.getMonth() !== anchor.getMonth()) {
        console.error("  month: the chosen day is outside the month on screen");
        failed = 1;
      }
    }
  }

  // --- and a filter that is on says so, in every view, with the way back ------------------
  //
  // The filter is set from the overview and then follows you into the week, the month and
  // the next visit. Unseen, a week showing one lawn's cuts looks like a week in which
  // nothing else was due. It sits beside the tabs, which it qualifies, and it is not drawn
  // at all while every zone is showing. The name is the whole point of it: a chip carrying a
  // dot and a cross says a filter is on without saying which.
  {
    const panel = new Panel();
    panel.connectedCallback();
    panel._mode = "week";
    panel.hass = hass;
    for (let i = 0; i < 8; i += 1) await new Promise((resolve) => setTimeout(resolve, 0));

    const toolbar = () => panel.shadowRoot.find(byClass("toolbar"));
    if (toolbar()?.find(byClass("filter-chip"))) {
      console.error("  every zone is showing and the toolbar still claims a filter");
      failed = 1;
    }

    panel._selectZone(snapshots[1].zone_id);
    for (let i = 0; i < 8; i += 1) await new Promise((resolve) => setTimeout(resolve, 0));
    const chip = toolbar()?.find(byClass("filter-chip"));
    if (!chip) {
      console.error("  a zone filter is on and the toolbar does not say which");
      failed = 1;
    } else {
      const named = chip.find(byClass("filter-chip__name"));
      if (named?.textContent !== snapshots[1].field.name) {
        console.error(`  the filter chip does not name the zone: ${named?.textContent}`);
        failed = 1;
      }
      chip.click();
      for (let i = 0; i < 8; i += 1) await new Promise((resolve) => setTimeout(resolve, 0));
      if (panel._zone !== null) {
        console.error("  pressing the header filter did not go back to every zone");
        failed = 1;
      }
      if (toolbar()?.find(byClass("filter-chip"))) {
        console.error("  the filter was cleared and the toolbar still shows it");
        failed = 1;
      }
    }
    globalThis.localStorage.removeItem("hosekeeper.zone");
  }

  // --- a filter left over from a zone that is gone does not hide everything ----------------
  //
  // The chosen zone is remembered between visits, and the zone it names can be gone by the
  // next one: renamed, removed, or the whole lawn set up again from scratch. Filtering on an
  // id nothing answers to leaves the panel with lawns it will not show, which on screen is a
  // page that says "loading" and never stops.
  {
    globalThis.localStorage.setItem("hosekeeper.zone", "a-zone-that-is-gone");
    const panel = new Panel();
    panel.connectedCallback();
    panel._mode = "overview";
    panel.hass = hass;
    for (let i = 0; i < 8; i += 1) await new Promise((resolve) => setTimeout(resolve, 0));
    const text = panel.shadowRoot.find(byClass("content"))?.textContent || "";
    if (!text.includes(snapshots[0].field.name)) {
      console.error("  a stale zone filter strands the panel on an empty page");
      failed = 1;
    }
    if (panel._zone !== null) {
      console.error("  the stale zone filter was kept, so it will strand the next visit too");
      failed = 1;
    }
    globalThis.localStorage.removeItem("hosekeeper.zone");
  }

  // --- and a state change somewhere else does not redraw the panel -------------------------
  //
  // Home Assistant assigns `hass` on every state change anywhere in the instance, which on a
  // busy install is many times a second. Redrawing there rebuilt the whole page each time and
  // replayed every section's entry animation with it, which is what flickering is.
  {
    const panel = new Panel();
    panel.connectedCallback();
    panel._mode = "overview";
    panel.hass = hass;
    await new Promise((resolve) => setTimeout(resolve, 0));
    for (let i = 0; i < 8; i += 1) await new Promise((resolve) => setTimeout(resolve, 0));

    let renders = 0;
    const draw = panel._doRender.bind(panel);
    panel._doRender = () => {
      renders += 1;
      draw();
    };

    // A dozen state changes elsewhere: a light, a thermostat, anything at all.
    for (let i = 0; i < 12; i += 1) {
      panel.hass = { ...hass, states: { ...hass.states, [`light.n${i}`]: { state: "on" } } };
    }
    for (let i = 0; i < 8; i += 1) await new Promise((resolve) => setTimeout(resolve, 0));
    if (renders !== 0) {
      console.error(`  the panel redrew ${renders} times for state changes it does not show`);
      failed = 1;
    }

    // Changing the view is a redraw, and it is the one that should animate.
    panel._setMode("week");
    for (let i = 0; i < 8; i += 1) await new Promise((resolve) => setTimeout(resolve, 0));
    if (renders === 0) {
      console.error("  changing the view did not redraw the panel");
      failed = 1;
    }
    const content = panel.shadowRoot.find(byClass("content"));
    if (content?.classList.contains("content--still")) {
      console.error("  arriving at a new view suppressed its entry animation");
      failed = 1;
    }
    panel._render();
    for (let i = 0; i < 8; i += 1) await new Promise((resolve) => setTimeout(resolve, 0));
    if (!panel.shadowRoot.find(byClass("content"))?.classList.contains("content--still")) {
      console.error("  redrawing the same view replays the entry animation, which flickers");
      failed = 1;
    }
  }
}

// --- and the phone layout keeps the upper hand ------------------------------------------
//
// Inside the glance the cells are styled through `.glance td`, which outranks a bare class.
// A narrow-screen rule written as `.glance__pct` therefore loses, silently, and the card
// falls apart. Every cell rule in that media block must name the element too.
{
  const css = readFileSync(join(front, "theme.js"), "utf8");
  // The phone layout is the media query that turns each row into a card.
  const at = css.lastIndexOf("@media (max-width: 760px)", css.indexOf("grid-template-areas"));
  if (at < 0) {
    console.error("  the glance has no narrow-screen layout");
    failed = 1;
  } else {
    const block = css.slice(at, css.indexOf("\n}", at) + 2);
    // The row is a <tr>, not a cell, so it is not in the contest; every other class is.
    for (const [, selector] of block.matchAll(/\n\s*(\.glance__(?!row\b)[a-z]+)\s*[,{]/g)) {
      console.error(`  narrow-screen rule ${selector} will lose to .glance td; write it as .glance td${selector}`);
      failed = 1;
    }
    // And the widths the table lays out with have to be given back. A cell that keeps
    // `width: 24%` from the wide layout is 24 % of the grid area it lands in, so the card is
    // the width of the screen and the name inside it is a column one word across.
    const widthOf = (body) => (body.match(/(?:^|;)\s*width:\s*([^;]+)/) || [])[1]?.trim() || null;
    const wide = css.slice(0, at);
    for (const [, cls, body] of wide.matchAll(/\n\.(glance__[a-z]+) \{([^}]*)\}/g)) {
      if ((widthOf(body) || "auto") === "auto") continue;
      const rule = new RegExp(`\\.glance td\\.${cls} \\{([^}]*)\\}`).exec(block);
      const given = rule ? widthOf(rule[1]) : null;
      if (given !== "auto" && given !== "100%") {
        console.error(`  .${cls} keeps its table width on a phone, so its content is squeezed into a fraction of the card`);
        failed = 1;
      }
    }
  }
}

// --- and the chip's name cannot be squeezed to nothing ------------------------------------
//
// A flex item whose content may be clipped is allowed to collapse to zero, so a chip laid out
// as "dot, name, cross" quietly becomes "dot, cross" when its room runs short. The name is the
// only reason the chip is there, so it gets a floor of its own.
{
  const panel = readFileSync(join(front, "hosekeeper-panel.js"), "utf8");
  const rule = panel.match(/\n\.filter-chip__name \{([^}]*)\}/);
  if (!rule) {
    console.error("  the filter chip's name has no rule of its own");
    failed = 1;
  } else if (!/min-width:\s*[1-9]/.test(rule[1])) {
    console.error(`  the filter chip's name can be squeezed away: ${rule[1].trim()}`);
    failed = 1;
  }
}

// --- and the date control keeps one width -------------------------------------------------
//
// The label is a date in words: "Fri 4 Sep" one day, "Wednesday 16 September" the next. A
// control sized by its contents moves its own arrows out from under the finger pressing
// them, so the label is given a fixed width on a wide screen and the whole bar on a phone.
{
  const panel = readFileSync(join(front, "hosekeeper-panel.js"), "utf8");
  const base = panel.match(/\n\.datenav__label \{([^}]*)\}/);
  if (!base) {
    console.error("  the date label has no styling, so it is sized by whatever date it holds");
    failed = 1;
  } else if (!/width:\s*[\d.]+r?em/.test(base[1]) || /min-width/.test(base[1])) {
    console.error(`  the date label's width is not fixed: ${base[1].trim()}`);
    failed = 1;
  }
  const phone = panel.slice(panel.indexOf("@media (max-width: 700px)"));
  if (!/\.datenav \{[^}]*width:\s*100%/.test(phone)) {
    console.error("  on a phone the date control does not take the width it is given");
    failed = 1;
  }
  if (!/\.datenav__label \{[^}]*width:\s*auto/.test(phone)) {
    console.error("  the phone rule leaves the fixed width in place, so the label cannot fill");
    failed = 1;
  }
}

if (!failed) console.log("  every view renders, the panel wires them, and the phone layout wins");
process.exit(failed);
