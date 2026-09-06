/** One day, in full: every event with what to do and, behind a toggle, why. */

import { el, icon } from "../dom.js";
import { fmtDate } from "../format.js";
import { lookup, strings } from "../i18n.js";
import { categoryIcon, eventDetail, eventHowTo, eventTime, eventTitle, zoneBadge, zoneDots } from "./events.js";
import { confirmButton } from "./confirm.js";
import { weatherLine } from "./weather.js";

function eventCard(event, { lang, locale, snapshot, zoneColour, multiZone, zoneName, onConfirm, todayIso }) {
  const s = strings(lang);
  const how = eventHowTo(event, lang, locale, snapshot);
  const detail = eventDetail(event, lang, locale, snapshot);
  const time = eventTime(event, locale);
  const reasons = (event.reasons || []).map((code) => lookup(lang, "reasons", code)).filter(Boolean);
  const zones = event.zones || [event.entry_id];

  // The reasoning sits between what to do and where to do it, as chips rather than a bullet
  // list: they are short, unordered and of equal weight, which is what chips are for.
  const why = reasons.length
    ? el(
        "div",
        { class: "event__why-panel", hidden: true },
        el("div", { class: "event__why-title" }, s.ui.reasonsTitle),
        el("div", { class: "event__reasons" }, reasons.map((r) => el("span", { class: "reason" }, r)))
      )
    : null;
  const toggle = why
    ? el(
        "button",
        {
          class: "event__why",
          "aria-expanded": "false",
          "aria-label": s.ui.reasonsTitle,
          title: s.ui.reasonsTitle,
          onClick: (ev) => {
            const open = why.hidden;
            why.hidden = !open;
            ev.currentTarget.setAttribute("aria-expanded", open ? "true" : "false");
          },
        },
        icon("mdi:chevron-down", "icon--sm")
      )
    : null;

  return el(
    "article",
    { class: `event event--${event.kind}`, "data-category": event.category },
    el("span", { class: "event__rail" }),
    el(
      "div",
      { class: "event__body" },
      el(
        "div",
        { class: "event__head" },
        categoryIcon(event.category),
        el("span", { class: "event__title" }, eventTitle(event, lang, locale, snapshot)),
        time ? el("span", { class: "event__time tabular" }, time) : null,
        el("span", { class: "spacer" }),
        event.params?.optional ? el("span", { class: "badge" }, s.ui.optional) : null,
        el("span", { class: `badge badge--${event.kind}` }, s.ui[event.kind] || event.kind),
        confirmButton(event, { lang, onConfirm, todayIso }),
        toggle
      ),
      detail ? el("div", { class: "event__detail" }, detail) : null,
      how ? el("p", { class: "event__how" }, how) : null,
      why,
      multiZone
        ? el(
            "footer",
            { class: "event__footer" },
            el("span", { class: "event__footer-label" }, s.ui.applyTo),
            el(
              "span",
              { class: "event__footer-zones" },
              zones.map((id) => el("span", { class: "chip", "data-tone": "general" }, zoneBadge(id, zoneColour, zoneName), zoneName(id)))
            )
          )
        : null
    )
  );
}

/**
 * One day in full.
 *
 * `snapshot` is any one lawn, and it is only read for the weather: the property shares a
 * sky, so which lawn it is does not matter.
 */
export function renderDayDetail(dayIso, events, { lang, locale, snapshotFor, zoneColour, multiZone, zoneName, onConfirm, todayIso, snapshot }) {
  const s = strings(lang);
  return el(
    "section",
    { class: "section enter" },
    el(
      "div",
      { class: "section__label" },
      icon("mdi:calendar-today"),
      fmtDate(dayIso, locale, { weekday: "long", day: "numeric", month: "long" })
    ),
    // Why the day asked for what it asked for. Measured behind, forecast ahead, and it says
    // which: a watering planned on a guessed 34 °C is not the same promise as one on a
    // measured one.
    weatherLine(dayIso, snapshot, { lang, locale }),
    events.length
      ? el(
          "div",
          { class: "events" },
          events.map((event) => eventCard(event, { lang, locale, snapshot: snapshotFor(event), zoneColour, multiZone, zoneName, onConfirm, todayIso }))
        )
      : el("div", { class: "section__hint" }, s.ui.nothingOnThisDay)
  );
}
