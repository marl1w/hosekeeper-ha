/**
 * The lawn calendar: a month grid and an agenda, over every lawn at once.
 *
 * A day's cell carries a coloured dot per lawn and a pill per thing to do, so a month is
 * read at a glance and a day is opened for the detail. The agenda is the same events as a
 * list, which is what a phone wants and what a week is actually planned from.
 */

import { el, icon } from "../dom.js";
import { fmtDate, fmtNumber } from "../format.js";
import { strings } from "../i18n.js";
import { categoryIcon, eventDetail, eventTime, eventTitle, zoneBadge, zoneDots } from "./events.js";

const DAY = 86400000;

export function isoDay(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

export function parseDay(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d);
}

/** Monday of the week that contains `date`. */
function weekStart(date) {
  const copy = new Date(date);
  const shift = (copy.getDay() + 6) % 7;
  copy.setDate(copy.getDate() - shift);
  return copy;
}

export function monthGridDays(anchorIso) {
  const anchor = parseDay(anchorIso);
  const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1);
  const start = weekStart(first);
  const days = [];
  for (let i = 0; i < 42; i += 1) {
    const day = new Date(start.getTime() + i * DAY);
    days.push({ iso: isoDay(day), inMonth: day.getMonth() === anchor.getMonth() });
    if (i >= 34 && day.getMonth() !== anchor.getMonth() && (i + 1) % 7 === 0) break;
  }
  return days;
}

/** The seven days of the week that contains `anchorIso`, Monday first. */
export function weekDays(anchorIso) {
  const start = weekStart(parseDay(anchorIso));
  return Array.from({ length: 7 }, (_, i) => isoDay(new Date(start.getTime() + i * DAY)));
}

export function weekLabel(anchorIso, locale) {
  const days = weekDays(anchorIso);
  const fmt = new Intl.DateTimeFormat(locale, { day: "numeric", month: "short" });
  return `${fmt.format(parseDay(days[0]))} – ${fmt.format(parseDay(days[6]))}`;
}

export function renderMonthGrid(byDay, anchorIso, selectedIso, todayIso, { lang, locale, zoneColour, zoneName, snapshotFor, onSelectDay }) {
  const s = strings(lang);
  // What the month plans belongs to the month, not to its first day: a banner above the
  // grid, the way a calendar shows an all-month event.
  const month = anchorIso.slice(0, 7);
  const monthly = [...byDay.entries()]
    .filter(([date]) => date.slice(0, 7) === month)
    .flatMap(([, events]) => events.filter((event) => event.kind === "planned"));
  const banner = monthly.length
    ? el(
        "div",
        { class: "cal__banner" },
        el("span", { class: "cal__banner-label" }, s.ui.thisMonthLong),
        el(
          "span",
          { class: "cal__banner-items" },
          monthly.map((event) =>
            el(
              "span",
              { class: `pill pill--planned`, "data-category": event.category },
              categoryIcon(event.category),
              el("span", { class: "pill__text" }, eventTitle(event, lang, locale, snapshotFor(event))),
              zoneDots(event, zoneColour, zoneName)
            )
          )
        )
      )
    : null;
  const head = el(
    "div",
    { class: "cal__head" },
    ...s.ui.weekdays.split(",").map((label) => el("span", { class: "cal__dow" }, label))
  );
  const cells = monthGridDays(anchorIso).map(({ iso, inMonth }) => {
    const events = (byDay.get(iso) || []).filter((event) => event.kind !== "planned");
    const shown = events.slice(0, 3);
    const zones = [...new Set(events.flatMap((e) => e.zones || [e.zone_id]))];
    return el(
      "button",
      {
        class: `cal__day${inMonth ? "" : " cal__day--outside"}${iso === selectedIso ? " cal__day--selected" : ""}${iso === todayIso ? " cal__day--today" : ""}`,
        onClick: () => onSelectDay(iso),
      },
      el(
        "span",
        { class: "cal__num" },
        String(Number(iso.slice(8))),
        el("span", { class: "cal__dots" }, zones.map((id) => zoneBadge(id, zoneColour, zoneName)))
      ),
      el(
        "span",
        { class: "cal__events" },
        shown.map((event) =>
          el(
            "span",
            { class: `pill pill--${event.kind}`, "data-category": event.category },
            categoryIcon(event.category),
            el("span", { class: "pill__text" }, eventTitle(event, lang, locale, snapshotFor(event)))
          )
        ),
        events.length > shown.length ? el("span", { class: "cal__more" }, fmtNumber(events.length - shown.length, locale, 0), "+") : null
      )
    );
  });
  return el("div", { class: "cal" }, banner, head, el("div", { class: "cal__grid" }, ...cells));
}

export function renderAgenda(byDay, anchorIso, selectedIso, todayIso, opts) {
  const { lang, locale, zoneColour, zoneName, snapshotFor, onSelectDay, multiZone } = opts;
  const s = strings(lang);
  const rows = weekDays(anchorIso).map((iso) => {
    const events = byDay.get(iso) || [];
    const isToday = iso === todayIso;
    return el(
      "button",
      {
        class: `agenda__day${iso === selectedIso ? " agenda__day--selected" : ""}${isToday ? " agenda__day--today" : ""}${iso < todayIso ? " agenda__day--past" : ""}`,
        onClick: () => onSelectDay(iso),
      },
      el(
        "span",
        { class: "agenda__date" },
        el("span", { class: "agenda__dow" }, fmtDate(iso, locale, { weekday: "short" })),
        el("span", { class: "agenda__num" }, String(Number(iso.slice(8)))),
        isToday ? el("span", { class: "agenda__today" }, s.ui.today) : null
      ),
      el(
        "span",
        { class: "agenda__events" },
        events.length
          ? events.map((event) =>
              el(
                "span",
                { class: `agenda__event pill pill--${event.kind}`, "data-category": event.category },
                multiZone ? zoneDots(event, zoneColour, zoneName) : null,
                categoryIcon(event.category),
                el("span", { class: "pill__text" }, eventTitle(event, lang, locale, snapshotFor(event))),
                eventTime(event, locale) ? el("span", { class: "pill__time tabular" }, eventTime(event, locale)) : null,
                eventDetail(event, lang, locale, snapshotFor(event)) ? el("span", { class: "pill__detail" }, eventDetail(event, lang, locale, snapshotFor(event))) : null
              )
            )
          : el("span", { class: "agenda__empty" }, "—")
      )
    );
  });
  return el("div", { class: "agenda" }, ...rows);
}

export { icon };
