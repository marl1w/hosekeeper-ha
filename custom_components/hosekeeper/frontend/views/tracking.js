/**
 * Tracking: everything the engine needs from a person, in one place.
 *
 * The other views answer "what should I do". This one answers the question going the other
 * way, which is the half the engine cannot get from any instrument on the property. The
 * sensors know what the weather did and what the soil holds. They do not know whether the
 * grass is any good, whether there is moss under the tree, or whether the cut the calendar
 * asked for actually happened, and every one of those changes what the plan says next.
 *
 * Each section says where things stand before it offers a button. A page of buttons and
 * nothing else cannot be read: it says what you may do and never what is already true, so
 * there is no way to tell whether pressing anything is needed.
 */

import { el, icon } from "../dom.js";
import { lookup, strings } from "../i18n.js";
import { categoryIcon, eventTitle, zoneBadge } from "./events.js";
import { confirmButton, confirmable } from "./confirm.js";
import { conditionDialog } from "./condition.js";
import { recordDialog } from "./record.js";

const ISSUE_DAYS = 30;

/** One lawn's line in a summary: its badge, its name, and what it currently says. */
function summaryRow(snapshot, { zoneColour, zoneName, multiZone }, ...content) {
  return el(
    "div",
    { class: "track__row" },
    multiZone
      ? el(
          "span",
          { class: "rate__lawn" },
          zoneBadge(snapshot.zone_id, zoneColour, zoneName),
          el("span", { class: "rate__name" }, snapshot.field?.name || "")
        )
      : null,
    el("span", { class: "track__facts" }, ...content)
  );
}

/** What a lawn says about itself today: the rating given, and the issues on record. */
function conditionOf(snapshot, todayIso) {
  const today = (snapshot.days || []).find((d) => d.date === todayIso);
  const from = new Date(`${todayIso}T12:00:00`);
  from.setDate(from.getDate() - ISSUE_DAYS);
  const cutoff = from.toISOString().slice(0, 10);
  const issues = new Set();
  for (const day of snapshot.days || []) {
    if (day.date < cutoff) continue;
    for (const issue of day.issues || []) issues.add(issue);
  }
  return { rating: today?.status || null, issues: [...issues] };
}

export function renderTracking(snapshots, opts) {
  const { lang, locale, zoneColour, zoneName, todayIso, byDay, issues, kinds } = opts;
  const { onRate, onIssue, onWater, onRecord, onFeed, onConfirm, snapshotFor } = opts;
  const s = strings(lang);
  const multiZone = snapshots.length > 1;
  const shared = { zoneColour, zoneName, multiZone };

  // Both dialogs ask a handful of short questions about one lawn or all of them, now and
  // then rather than on every visit, which is why they are behind a button.
  const condition =
    onRate || onIssue
      ? conditionDialog(snapshots, { lang, issues, todayIso, zoneName, onRate, onIssue })
      : null;
  const manual =
    onWater || onRecord
      ? recordDialog(snapshots, { lang, kinds, todayIso, zoneName, onWater, onRecord, onFeed })
      : null;

  const today = byDay?.get(todayIso) || [];
  const outstanding = today.filter(
    (e) => e.kind !== "logged" && e.kind !== "noted" && confirmable(e)
  );
  const doneToday = today.filter((e) => e.kind === "logged" || e.kind === "noted");

  const page = el(
    "div",
    { class: "page" },
    el(
      "section",
      { class: "section enter" },
      el("div", { class: "section__label" }, icon("mdi:clipboard-text-clock"), s.ui.todaysWork),
      outstanding.length
        ? el(
            "div",
            { class: "actions" },
            outstanding.map((event) =>
              el(
                "div",
                { class: "action action--static", "data-category": event.category },
                el(
                  "span",
                  { class: "action__body" },
                  el(
                    "span",
                    { class: "action__head" },
                    categoryIcon(event.category),
                    el("span", { class: "action__title" }, eventTitle(event, lang, locale, snapshotFor(event))),
                    el("span", { class: "spacer" }),
                    confirmButton(event, { lang, onConfirm, todayIso })
                  )
                )
              )
            )
          )
        : el("div", { class: "section__hint" }, s.ui.nothingToday)
    ),
    condition
      ? el(
          "section",
          { class: "section enter" },
          el("div", { class: "section__label" }, icon("mdi:emoticon-outline"), s.ui.howTheLawnIs),
          el(
            "div",
            { class: "track" },
            snapshots.map((snapshot) => {
              const { rating, issues: seen } = conditionOf(snapshot, todayIso);
              return summaryRow(
                snapshot,
                shared,
                rating
                  ? el("span", { class: "chip", "data-tone": "reserve" }, s.status[rating])
                  : el("span", { class: "track__none" }, s.ui.notRatedToday),
                seen.map((issue) =>
                  el("span", { class: "chip", "data-tone": "warn" }, lookup(lang, "issues", issue))
                )
              );
            })
          ),
          el("div", { class: "track__act" }, condition.button),
          el("div", { class: "section__hint" }, s.ui.ratingHint)
        )
      : null,
    manual
      ? el(
          "section",
          { class: "section enter" },
          el("div", { class: "section__label" }, icon("mdi:clipboard-check-outline"), s.ui.workYouDid),
          el(
            "div",
            { class: "track" },
            snapshots.map((snapshot) => {
              const mine = doneToday.filter((e) =>
                (e.zones || [e.zone_id]).includes(snapshot.zone_id)
              );
              return summaryRow(
                snapshot,
                shared,
                mine.length
                  ? mine.map((e) =>
                      el(
                        "span",
                        { class: "pill pill--logged", "data-category": e.category },
                        categoryIcon(e.category),
                        el("span", { class: "pill__text" }, eventTitle(e, lang, locale, snapshotFor(e)))
                      )
                    )
                  : el("span", { class: "track__none" }, s.ui.nothingLogged)
              );
            })
          ),
          el("div", { class: "track__act" }, manual.button),
          el("div", { class: "section__hint" }, s.ui.workYouDidHint)
        )
      : null
  );
  // The dialogs are handed to the panel rather than left in the page. Inside a scrolling
  // column they are positioned against the whole scroll height, so they open halfway down it
  // and run off the bottom of the window.
  page.dialogs = [condition?.overlay, manual?.overlay].filter(Boolean);
  return page;
}
