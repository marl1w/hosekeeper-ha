/**
 * The overview: how the lawns are right now, and the very next things to do.
 *
 * Nothing here needs a decision about dates. What is happening today sits at the top, the
 * next actions follow in the order they fall due, and anything alarming is called out. The
 * calendar views are for looking further.
 */

import { el, icon } from "../dom.js";
import { fill, fmtDate } from "../format.js";
import { lookup, strings } from "../i18n.js";
import { renderNow } from "./now.js";
import { forecastStrip } from "./weather.js";
import { categoryIcon, eventDetail, eventHowTo, eventTime, eventTitle, zoneDots } from "./events.js";
import { confirmButton } from "./confirm.js";

const NEXT_LIMIT = 6;

// Two months out is as far as "next" reaches. The plan runs a year ahead, and a feed due
// next June is something to look up in the month view, not something to be told about now.
const NEXT_ACTIONS_HORIZON_DAYS = 60;

/** Whole days between two ISO dates. */
function daysBetween(from, to) {
  return Math.round((new Date(`${to}T12:00:00`) - new Date(`${from}T12:00:00`)) / 86400000);
}

/**
 * A date as a calendar tear-off.
 *
 * A month-long job shows the month alone: the first of the month is where such a job is
 * filed, not a day anybody chose to do it on, and printing that day invites the reader to
 * put it in the diary.
 */
function dateBlock(dateIso, locale, isToday, monthOnly) {
  const date = new Date(`${dateIso}T12:00:00`);
  if (monthOnly) {
    return el(
      "span",
      { class: "datechip datechip--month" },
      el("span", { class: "datechip__monthname" }, new Intl.DateTimeFormat(locale, { month: "short" }).format(date)),
      el("span", { class: "datechip__year" }, String(date.getFullYear()))
    );
  }
  return el(
    "span",
    { class: `datechip${isToday ? " datechip--today" : ""}` },
    el("span", { class: "datechip__dow" }, new Intl.DateTimeFormat(locale, { weekday: "short" }).format(date)),
    el("span", { class: "datechip__num" }, String(date.getDate())),
    el("span", { class: "datechip__mon" }, new Intl.DateTimeFormat(locale, { month: "short" }).format(date))
  );
}

function actionRow(event, { lang, locale, snapshotFor, zoneColour, zoneName, multiZone, todayIso, onOpenDay, onConfirm }) {
  const s = strings(lang);
  const snapshot = snapshotFor(event);
  const how = eventHowTo(event, lang, locale, snapshot);
  const when = eventTime(event, locale);
  const detail = eventDetail(event, lang, locale, snapshot);
  return el(
    "button",
    { class: "action", "data-category": event.category, onClick: () => onOpenDay(event.date) },
    dateBlock(event.date, locale, event.date === todayIso, event.kind === "planned"),
    el(
      "span",
      { class: "action__body" },
      el(
        "span",
        { class: "action__head" },
        categoryIcon(event.category),
        el("span", { class: "action__title" }, eventTitle(event, lang, locale, snapshot)),
        el("span", { class: "spacer" }),
        multiZone ? zoneDots(event, zoneColour, zoneName) : null,
        confirmButton(event, { lang, onConfirm, compact: true, todayIso })
      ),
      when || detail
        ? el(
            "span",
            { class: "action__detail" },
            when ? el("span", { class: "action__clock" }, when) : null,
            detail ? el("span", {}, detail) : null
          )
        : null,
      event.repeatsUntil
        ? el(
            "span",
            { class: "action__repeat" },
            fill(s.ui.repeatUntil, { date: fmtDate(event.repeatsUntil, locale, { day: "numeric", month: "short" }) }, locale)
          )
        : null,
      how ? el("span", { class: "action__how" }, how) : null
    )
  );
}

/**
 * The overview.
 *
 * `snapshots` is every lawn, because the glance is also how a lawn is chosen; `visible` is
 * what the current filter leaves, and everything below the glance follows it.
 */
export function renderOverview(snapshots, visible, allByDay, opts) {
  const { lang, locale, todayIso, onSelectZone, selectedZone, zoneColour, zoneName, snapshotFor, multiZone } = opts;
  const s = strings(lang);

  // A job that comes back every day is one entry that says so, not six entries that push
  // everything else off the list.
  const upcoming = [];
  const runs = new Map();
  const horizon = new Date(`${todayIso}T12:00:00`);
  horizon.setDate(horizon.getDate() + NEXT_ACTIONS_HORIZON_DAYS);
  const furthest = horizon.toISOString().slice(0, 10);
  for (const [date, events] of [...allByDay.entries()].sort()) {
    if (date < todayIso || date > furthest) continue;
    for (const event of events) {
      if (event.kind === "logged" || event.kind === "noted") continue;
      const key = [event.code, event.category, event.params?.operation ?? "", (event.zones || []).join()].join("|");
      const seen = runs.get(key);
      if (seen && daysBetween(seen.lastDate, date) === 1) {
        seen.lastDate = date;
        seen.entry.repeatsUntil = date;
        continue;
      }
      const entry = { ...event };
      runs.set(key, { lastDate: date, entry });
      upcoming.push(entry);
    }
  }
  const alerts = upcoming.filter((e) => e.kind === "alert" && e.date === todayIso);
  const next = upcoming.filter((e) => e.kind !== "alert").slice(0, NEXT_LIMIT);
  // What was recorded today: jobs done and observations made.
  const doneToday = (allByDay.get(todayIso) || []).filter((e) => e.kind === "logged" || e.kind === "noted");

  return el(
    "div",
    { class: "page" },
    el(
      "section",
      { class: "section enter" },
      el("div", { class: "section__label" }, icon("mdi:eye-outline"), s.ui.atAGlance),
      // Every lawn on the property shares a sky, so the week is drawn once, above them all,
      // rather than repeated down a column of a table that has enough columns already.
      forecastStrip(snapshots[0], { lang, locale, todayIso }),
      renderNow(snapshots, { lang, locale, zoneColour, zoneName, selectedZone, onSelectZone })
    ),
    alerts.length
      ? el(
          "section",
          { class: "section enter" },
          el("div", { class: "section__label" }, icon("mdi:alert-outline"), s.categories.disease),
          el("div", { class: "actions" }, alerts.map((e) => actionRow(e, opts)))
        )
      : null,
    el(
      "section",
      { class: "section enter" },
      el("div", { class: "section__label" }, icon("mdi:clipboard-text-clock"), s.ui.nextActions),
      next.length
        ? el("div", { class: "actions" }, next.map((e) => actionRow(e, opts)))
        : el("div", { class: "section__hint" }, s.ui.nothingToday)
    ),
    doneToday.length
      ? el(
          "section",
          { class: "section enter" },
          el("div", { class: "section__label" }, icon("mdi:check-circle-outline"), s.ui.loggedToday),
          el(
            "div",
            { class: "row row--wrap" },
            doneToday.map((e) =>
              el(
                "span",
                { class: "pill pill--logged", "data-category": e.category },
                multiZone ? zoneDots(e, zoneColour, zoneName) : null,
                categoryIcon(e.category),
                el("span", { class: "pill__text" }, eventTitle(e, lang, locale, snapshotFor(e)))
              )
            )
          ),
          el("div", { class: "section__hint" }, s.ui.logHint)
        )
      : el(
          "section",
          { class: "section" },
          el("div", { class: "section__label" }, icon("mdi:check-circle-outline"), s.ui.loggedToday),
          el("div", { class: "section__hint" }, `${s.ui.nothingLogged} ${s.ui.logHint}`)
        )
  );
}

export { lookup };
