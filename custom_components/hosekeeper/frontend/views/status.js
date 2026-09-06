/**
 * How the lawn looks, in the reader's own words.
 *
 * This is the one thing the engine cannot measure and cannot do without. Every sensor on the
 * property says what the weather did and what the soil holds; none of them says whether the
 * grass is any good. The adaptation loop moves a lawn's water and feed factors on the trend
 * of these ratings after advice was followed, so a lawn nobody ever rates is a lawn the
 * engine never learns anything about.
 *
 * It asks where the answer is known — beside the lawn, on the day being lived — and it asks
 * with four buttons rather than a form, because the difference between a good lawn and a fair
 * one is a glance out of the window and not a measurement.
 */

import { el, icon } from "../dom.js";
import { strings } from "../i18n.js";
import { zoneBadge } from "./events.js";

// Best to worst, and drawn that way: the scale reads left to right like a thermometer.
export const RATINGS = ["excellent", "good", "fair", "poor"];

const TONE = { excellent: "reserve", good: "reserve", fair: "warn", poor: "error" };

/** The rating a lawn carries today, if it was given one. */
function ratedToday(snapshot, todayIso) {
  const day = (snapshot.days || []).find((d) => d.date === todayIso);
  return day?.status || null;
}

/**
 * One row per lawn: its name, and the four answers.
 *
 * The rating already given today is marked, and pressing it again is not an error — a lawn
 * looked at twice in a day can be judged differently the second time.
 */
export function renderStatus(snapshots, { lang, zoneColour, zoneName, todayIso, onRate }) {
  const s = strings(lang);
  if (!onRate || !snapshots.length) return null;
  return el(
    "div",
    { class: "rate" },
    snapshots.map((snapshot) => {
      const id = snapshot.entry_id;
      const current = ratedToday(snapshot, todayIso);
      return el(
        "div",
        { class: "rate__row" },
        el(
          "span",
          { class: "rate__lawn" },
          zoneBadge(id, zoneColour, zoneName),
          el("span", { class: "rate__name" }, snapshot.field?.name || "")
        ),
        el(
          "span",
          { class: "rate__options" },
          RATINGS.map((rating) =>
            el(
              "button",
              {
                class: "rate__btn",
                "data-tone": TONE[rating],
                "aria-pressed": current === rating ? "true" : "false",
                onClick: () => onRate(id, rating),
              },
              current === rating ? icon("mdi:check", "icon--sm") : null,
              s.status[rating]
            )
          )
        )
      );
    })
  );
}
