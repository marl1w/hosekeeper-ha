/**
 * How the lawn is: the rating, and anything seen on it.
 *
 * The two belong in one dialog because they are one act of looking. You walk out, you form a
 * judgement, and you notice the moss under the tree at the same moment; asking for them in
 * two places asks the reader to make the same trip twice.
 *
 * It is the one thing the engine cannot measure and cannot do without. The rating is the
 * trend the adaptation loop moves on, and each issue changes a decision rather than merely
 * describing the lawn — weeds and moss make their pass compulsory, thin or bare turf brings
 * the overseeding forward, fungus holds the nitrogen back.
 */

import { el, icon } from "../dom.js";
import { lookup, strings } from "../i18n.js";
import { ALL, chosen, dialog, field, lawnChoice } from "./dialog.js";

// Best to worst, and drawn that way: the scale reads left to right like a thermometer.
export const RATINGS = ["excellent", "good", "fair", "poor"];

const TONE = { excellent: "reserve", good: "reserve", fair: "warn", poor: "error" };

/** What a lawn was rated today, if anything. */
function ratedToday(snapshot, todayIso) {
  return (snapshot.days || []).find((d) => d.date === todayIso)?.status || null;
}

/** What was reported on a lawn today, so re-opening the dialog shows what was just said. */
function reportedToday(snapshot, todayIso) {
  return new Set((snapshot.days || []).find((d) => d.date === todayIso)?.issues || []);
}

export function conditionDialog(snapshots, { lang, issues, todayIso, zoneName, onRate, onIssue }) {
  const s = strings(lang);
  const byId = new Map(snapshots.map((snapshot) => [snapshot.zone_id, snapshot]));
  const lawn = lawnChoice(snapshots, { lang, zoneName, id: "hk-condition-lawn" });

  let rating = null;
  const ratingButtons = RATINGS.map((value) =>
    el(
      "button",
      {
        class: "rate__btn",
        "data-tone": TONE[value],
        "aria-pressed": "false",
        onClick: (event) => {
          rating = rating === value ? null : value;
          for (const button of ratingButtons) {
            button.setAttribute("aria-pressed", button === event.currentTarget && rating ? "true" : "false");
          }
        },
      },
      s.status[value]
    )
  );

  const picked = new Set();
  const issueButtons = (issues || []).map((issue) =>
    el(
      "button",
      {
        class: "rate__btn",
        "data-tone": "warn",
        "aria-pressed": "false",
        onClick: (event) => {
          if (picked.has(issue)) picked.delete(issue);
          else picked.add(issue);
          event.currentTarget.setAttribute("aria-pressed", picked.has(issue) ? "true" : "false");
        },
      },
      lookup(lang, "issues", issue)
    )
  );

  /** Show what this lawn already says today, so the dialog is never stale. */
  const sync = () => {
    const first = lawn.value === ALL ? snapshots[0] : byId.get(lawn.value);
    rating = first ? ratedToday(first, todayIso) : null;
    RATINGS.forEach((value, i) =>
      ratingButtons[i].setAttribute("aria-pressed", rating === value ? "true" : "false")
    );
    const already = first ? reportedToday(first, todayIso) : new Set();
    picked.clear();
    (issues || []).forEach((issue, i) => {
      if (already.has(issue)) picked.add(issue);
      issueButtons[i].setAttribute("aria-pressed", picked.has(issue) ? "true" : "false");
    });
  };
  lawn.addEventListener("change", sync);

  const body = [
    snapshots.length > 1 ? field(s.ui.colZone, lawn) : lawn,
    el("div", { class: "track__sub" }, s.ui.howDoesItLook),
    el("div", { class: "dialog__choices" }, ratingButtons),
    onIssue && issueButtons.length ? el("div", { class: "track__sub" }, s.ui.anythingSeen) : null,
    onIssue && issueButtons.length
      ? el("div", { class: "dialog__choices" }, issueButtons)
      : null,
    el("div", { class: "section__hint" }, s.ui.ratingHint),
  ].filter(Boolean);

  return dialog({
    lang,
    title: s.ui.howTheLawnIs,
    openLabel: s.ui.reportCondition,
    openIcon: "mdi:emoticon-outline",
    submitLabel: s.ui.save,
    body,
    onOpen: sync,
    onSubmit: () => {
      for (const zoneId of chosen(snapshots, lawn)) {
        if (rating && onRate) onRate(zoneId, rating);
        for (const issue of picked) onIssue?.(zoneId, issue);
      }
    },
  });
}

export { icon };
