/**
 * At a glance: one line per lawn, the whole property read in a couple of seconds.
 *
 * It is a table, and deliberately so. Columns that line up across rows are exactly what a
 * table does, in every engine, without subgrid and without a row's contents ever being able
 * to land on top of each other — which is what the grid versions of this kept doing.
 *
 * And it has a header, because a table's columns are named once. The words "Soil water" used
 * to be printed on every row, taking a column's width to say the same thing three times.
 *
 * It follows the day being looked at. Sitting above a calendar showing the twentieth while
 * reporting the dry spell as it stands today is not a glance at anything: the two halves of
 * the screen described different days and only one of them said which. Where the diary and
 * the projection can speak for the day, every figure is that day's; where they cannot, the
 * row says so rather than quietly showing today's numbers under another date.
 */

import { el, icon } from "../dom.js";
import { fill, fmtNumber, fmtTime } from "../format.js";
import { lookup, strings } from "../i18n.js";
import { soilWaterSpark, waterGauge } from "../charts.js";
import { eventTitle, zoneBadge } from "./events.js";

/** Every day the snapshot can speak for, diary then projection, oldest first. */
function series(snapshot) {
  const st = snapshot.state || {};
  const seen = new Set((snapshot.days || []).map((d) => d.date));
  return [...(snapshot.days || []), ...(st.projection || []).filter((d) => !seen.has(d.date))];
}

/** Consecutive days without meaningful rain, counted back from a date. */
function drySpell(rows, dateIso) {
  let days = 0;
  for (let i = rows.length - 1; i >= 0; i -= 1) {
    if (rows[i].date > dateIso) continue;
    if ((rows[i].rain_mm || 0) >= 1) break;
    days += 1;
  }
  return days;
}

export function renderNow(snapshots, { lang, locale, zoneColour, zoneName, selectedZone, onSelectZone, dateIso, todayIso, eventsByDay }) {
  const s = strings(lang);
  const day = dateIso || todayIso || null;
  const isNow = !day || !todayIso || day === todayIso;
  const rows = snapshots.map((snapshot) => {
    const st = snapshot.state || {};
    const id = snapshot.zone_id;
    const all = series(snapshot);
    const onDay = isNow ? null : all.find((d) => d.date === day);
    // A day the diary and the projection cannot reach: say so, rather than showing today's
    // figures under someone else's date.
    const unknown = !isNow && !onDay;
    const available = unknown
      ? null
      : Math.round((isNow ? (st.available_fraction ?? 0) : Math.max(0, 1 - (onDay.deficit_mm || 0) / (st.taw_mm || 1))) * 100);
    // The days the balance can speak for from here on, with the plan followed.
    const ahead = isNow ? st.projection || [] : all.filter((d) => d.date >= day).slice(0, 14);
    const lowest = ahead.length
      ? Math.round(Math.min(...ahead.map((d) => Math.max(0, 1 - (d.deficit_mm || 0) / (st.taw_mm || 1)))) * 100)
      : null;
    // What is next: today the rules say it, another day the calendar does.
    const onThisDay = (eventsByDay?.get(day) || []).filter(
      (e) => e.kind !== "logged" && e.kind !== "noted" && (e.zones || [e.zone_id]).includes(id)
    );
    const next = isNow ? (st.advice || []).find((a) => a.priority <= 2) : onThisDay[0] || null;
    const plan = st.irrigation_plan || {};
    const alerts = [];
    const start = isNow ? plan.main_start : onThisDay.find((e) => e.category === "irrigation" && e.start)?.start;
    if (start) {
      alerts.push(el("span", { class: "chip", "data-tone": "irrigation" }, icon("mdi:water-clock", "icon--sm"), fmtTime(start, locale)));
    }
    const hot = isNow ? st.heat_stress : (onDay?.tmax ?? null) !== null && onDay.tmax >= 30;
    if (hot) alerts.push(el("span", { class: "chip", "data-tone": "error" }, s.ui.heatStress));
    const disease = isNow
      ? (st.advice || []).some((a) => a.category === "disease" && a.priority <= 2)
      : onThisDay.some((e) => e.category === "disease" && e.kind === "alert");
    if (disease) {
      alerts.push(el("span", { class: "chip", "data-tone": "error" }, icon("mdi:bacteria-outline", "icon--sm"), s.categories.disease));
    }
    const dry = isNow ? st.dry_spell_days || 0 : unknown ? 0 : drySpell(all, day);
    if (dry > 7) alerts.push(el("span", { class: "chip", "data-tone": "warn" }, fill(s.ui.dryDays, { days: dry }, locale)));

    const toggle = () => onSelectZone(selectedZone === id ? null : id);
    return el(
      "tr",
      {
        class: "glance__row",
        role: "button",
        tabindex: "0",
        "aria-pressed": selectedZone === id ? "true" : "false",
        onClick: toggle,
        onKeydown: (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault?.();
            toggle();
          }
        },
      },
      el("td", { class: "glance__badge" }, zoneBadge(id, zoneColour, zoneName)),
      el(
        "td",
        { class: "glance__name" },
        el("div", { class: "glance__title" }, snapshot.field?.name || ""),
        el(
          "div",
          { class: "glance__sub" },
          [
            snapshot.field?.area_m2 ? `${fmtNumber(snapshot.field.area_m2, locale, 0)} m²` : null,
            lookup(lang, "exposures", snapshot.field?.exposure),
            lookup(lang, "phases", st.season_phase),
          ]
            .filter(Boolean)
            .join(" · ")
        )
      ),
      el(
        "td",
        { class: "glance__meter" },
        // Where the water is going, not only where it is. A bar showing this instant on a
        // lawn watered at dawn always reads full, which is the least useful thing the row
        // could say.
        //
        // Past the days the balance can speak for there is nothing to draw. The bar used to
        // appear there instead, filled from today's deficit, which put today's reading under
        // somebody else's date — the very thing the rest of this row refuses to do.
        ahead.length > 1 || !isNow
          ? soilWaterSpark(ahead, { rawMm: st.raw_mm, tawMm: st.taw_mm, label: s.ui.soilWater })
          : waterGauge({ deficit: st.deficit_mm || 0, taw: st.taw_mm || 1, raw: st.raw_mm || 0 })
      ),
      el(
        "td",
        { class: "glance__pct" },
        el("div", { class: "glance__pctnow tabular" }, available === null ? "–" : `${available} %`),
        lowest === null || available === null || lowest >= available
          ? null
          : el("div", { class: "glance__pctlow tabular" }, `↓ ${lowest} %`)
      ),
      el(
        "td",
        { class: "glance__next" },
        unknown
          ? s.ui.noDataForDay
          : next
            ? eventTitle({ code: next.code, category: next.category, params: next.params }, lang, locale, snapshot)
            : isNow
              ? s.ui.nothingToday
              : s.ui.nothingPlanned
      ),
      el("td", { class: "glance__when" }, el("div", { class: "glance__chips" }, ...alerts))
    );
  });
  return el(
    "table",
    { class: "glance" },
    el(
      "thead",
      { class: "glance__head" },
      el(
        "tr",
        {},
        // The widths live here, and the table is laid out from this row alone. A lawn with
        // no dry spell to report and one with a watering time are otherwise different
        // shapes, and the columns moved under the reader as the date changed.
        el("th", { class: "glance__badge", scope: "col" }, ""),
        el("th", { class: "glance__name", scope: "col" }, s.ui.colZone),
        el("th", { class: "glance__meter", scope: "col" }, s.ui.soilWater),
        el("th", { class: "glance__pct", scope: "col" }, ""),
        el("th", { class: "glance__next", scope: "col" }, s.ui.colNext),
        el("th", { class: "glance__when", scope: "col" }, "")
      )
    ),
    el("tbody", {}, ...rows)
  );
}
