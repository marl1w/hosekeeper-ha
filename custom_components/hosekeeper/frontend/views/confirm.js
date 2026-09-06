/**
 * "Done": the button that closes the loop, next to the job it closes.
 *
 * Recording what was done used to be a row of buttons on a device page, one per kind of
 * work, with no idea which lawn wanted what. That is the wrong place. A confirmation is
 * only ever made about a job somebody is looking at, so it belongs on the line that names
 * that job, on the two views where the day's work is read: the overview and the day.
 *
 * Done is one tap, everywhere. It confirms the row exactly as the row is written: the cut at
 * the height asked for, the watering for the minutes planned. It used to stop and ask how
 * long the watering ran, through a browser prompt, which is an ugly box on a phone and the
 * wrong question anyway — the row says what was asked for, and Done means "that happened".
 * A figure that came out differently is corrected in Tracking, which has a proper field for
 * it and knows the day's total.
 *
 * The seedbed's light passes and a midday syringing ask nothing. They are a fixed routine of
 * two millimetres, not a run whose length anybody chooses, and they must never be written as
 * irrigation: that total feeds the water balance, and telling it the roots were filled by
 * water that wet the top centimetre would cancel the deep cycle the turf around the seed
 * still needs.
 */

import { el, icon } from "../dom.js";
import { todayKey } from "../format.js";
import { strings } from "../i18n.js";

/**
 * Month-long lines that are not a job you finish in an afternoon.
 *
 * "Mow every six days at 65 mm" is how the month is to be worked, not a task with a tick
 * box; the cut it asks for is a separate line on the day it falls due, and that is what gets
 * confirmed. Raising the cutting height is a setting, and recording it as a cut would put a
 * mow in the diary that never happened.
 */
const NOT_A_JOB = new Set([
  "mow_routine",
  "mow_routine_robot",
  "mow_routine_robot_daily",
  "raise_mowing_height",
  "irrigation_deep_infrequent",
  "summer_watch",
  "summer_rest",
  "winter_rest",
]);

// The diary's name for the work each category records, and whether a tap is enough.
const RECORDS = {
  mowing: { kind: "mowing" },
  weeds: { kind: "weeding" },
  aeration: { kind: "aeration" },
  fertilizing: { kind: "fertilizing" },
  seeding: { kind: "sowing" },
  disease: { kind: "treatment" },
  general: { kind: "leaf_clearing", only: ["clear_leaves", "leaf_clearing"] },
  irrigation: { asks: "minutes" },
};

/**
 * Operations the diary records under a different name from their category's default.
 *
 * Three jobs share the soil category and the diary keeps them apart: writing all three as
 * "aeration" would leave days_since_scarifying at never, so the plan would go on asking for
 * a scarifying done last week. And preparing for an overseeding is a low cut and a light
 * scarify, not a sowing — recording it as one would start the germination regime, with three
 * light waterings a day, over ground that has no seed in it.
 */
const RECORDED_AS = {
  aeration_spring: "aeration",
  aeration_autumn: "aeration",
  scarify_dethatch: "scarifying",
  top_dressing: "top_dressing",
  prepare_overseeding: "scarifying",
};

// Watering that stays at the surface: a tap is the whole answer, and it is recorded as work
// done rather than as water the root zone received.
const SURFACE_WATER = {
  germination_watering: "seedbed_watering",
  syringe: "syringing",
};

/** What confirming this event would write, or nothing when the event is not a job. */
export function confirmable(event) {
  if (event.kind === "logged" || event.kind === "noted") return null;
  const record = RECORDS[event.category];
  if (!record) return null;
  const code = event.params?.operation || event.code;
  if (NOT_A_JOB.has(code)) return null;
  if (record.only && !record.only.includes(code)) return null;
  if (SURFACE_WATER[code]) {
    return { what: "maintenance", kind: SURFACE_WATER[code], details: {} };
  }
  if (record.asks === "minutes") {
    // Only ask about watering the lawn actually has to be given by hand. A run the valve
    // makes is already in the diary by the time anybody reads the line.
    const minutes = Math.max(1, Math.round(event.params?.minutes || 0));
    return { what: "irrigation", minutes, asks: true };
  }
  const p = event.params || {};
  const details = {};
  if (p.height_mm && event.code === "mow") details.height_mm = p.height_mm;
  if (p.preset) details.product = p.preset;
  // The yearly nitrogen budget is summed from this number and nothing else. A feed confirmed
  // without it counts as a feed that put no nitrogen down, so the engine would go on calling
  // the lawn under-fed however often it was actually fed.
  for (const key of ["n_g_m2", "dose_g_m2", "npk_class", "role"]) {
    if (p[key] !== undefined && p[key] !== null) details[key] = p[key];
  }
  return { what: "maintenance", kind: RECORDED_AS[code] || record.kind, details };
}

/**
 * The button, or nothing at all.
 *
 * Nothing for an event that records nothing, and nothing for a day that has not happened:
 * there is no confirming next month's feed in September. Yesterday still gets one, because
 * a job done and not written down is the common case the diary exists for.
 */
export function confirmButton(event, { lang, onConfirm, compact = false, todayIso }) {
  if (!onConfirm) return null;
  if (event.date > (todayIso || todayKey())) return null;
  const payload = confirmable(event);
  if (!payload) return null;
  const s = strings(lang);
  const { asks: _asks, ...write } = payload;
  return el(
    "button",
    {
      class: `confirm${compact ? " confirm--compact" : ""}`,
      title: s.ui.markDone,
      onClick: (ev) => {
        // The row underneath is a button too, and opens the day. Confirming is not opening.
        ev.stopPropagation();
        onConfirm(event, write);
      },
    },
    icon("mdi:check", "icon--sm"),
    compact ? null : el("span", {}, s.ui.markDone)
  );
}
