/** Turning one calendar event into a title, an icon and a colour. */

import { el, icon } from "../dom.js";
import { fill, fmtNumber, fmtTime } from "../format.js";
import { lookup, strings } from "../i18n.js";

export const CATEGORY_ICONS = {
  irrigation: "mdi:water",
  mowing: "mdi:mower",
  fertilizing: "mdi:seed",
  seeding: "mdi:sprout",
  weeds: "mdi:flower-tulip-outline",
  disease: "mdi:bacteria-outline",
  aeration: "mdi:dots-grid",
  general: "mdi:leaf",
};

/** The event's one-line title, in the viewer's language. */
export function eventTitle(event, lang, locale, snapshot) {
  const s = strings(lang);
  const params = { ...(event.params || {}) };
  if (params.status) params.status = (s.status[params.status] || params.status).toLowerCase();
  if (params.issue) params.issue = lookup(lang, "issues", params.issue);
  // An operation's name may carry placeholders of its own: a mowing line names its height
  // and how often it wants doing. They are filled from the same parameters.
  if (params.operation) params.operation = fill(lookup(lang, "operations", params.operation), params, locale);
  if (params.preset && snapshot?.fertilizers?.[params.preset]) params.preset = snapshot.fertilizers[params.preset].name;
  for (const [key, value] of Object.entries(params)) {
    if (typeof value === "number") params[key] = fmtNumber(value, locale, Number.isInteger(value) ? 0 : 1);
  }
  // A split watering names its run, so three entries in one morning are not three waterings.
  const code = event.code === "irrigate" && params.of ? "irrigate_cycle" : event.code;
  const fromEvents = s.events[code];
  if (fromEvents) {
    const title = fill(fromEvents, params, locale);
    // "three times today", rather than the same line three times.
    return event.repeats > 1 ? `${title} · ${fill(s.ui.timesToday, { n: event.repeats }, locale)}` : title;
  }
  const asMaintenance = s.maintenance[event.code];
  if (asMaintenance) return asMaintenance;
  const asAdvice = s.advice[event.code];
  if (asAdvice) return fill(asAdvice.title, params, locale);
  return lookup(lang, "operations", event.code);
}

/** What to do, in a sentence, when the event is a planned or projected operation. */
export function eventHowTo(event, lang, locale, snapshot) {
  const code = event.params?.operation || event.code;
  const text = lookup(lang, "howto", code);
  if (text === code) return "";
  const presetName = (key) => (key && snapshot?.fertilizers?.[key] ? snapshot.fertilizers[key].name : key || "…");
  return fill(text, { ...(event.params || {}), preset: presetName(event.params?.preset), starter: presetName(event.params?.starter_feed?.preset) }, locale);
}

/** The detail line: product, dose, run time. */
export function eventDetail(event, lang, locale, snapshot) {
  const s = strings(lang);
  const p = event.params || {};
  const bits = [];
  if (p.minutes) bits.push(`${fmtNumber(p.minutes, locale, 0)} ${s.ui.minutes}`);
  if (p.preset && snapshot?.fertilizers?.[p.preset]) bits.push(snapshot.fertilizers[p.preset].name);
  if (p.npk_class) bits.push(p.npk_class);
  if (p.dose_g_m2) bits.push(`${fmtNumber(p.dose_g_m2, locale, 0)} g/m²`);
  if (p.n_g_m2 && !p.dose_g_m2) bits.push(`${fmtNumber(p.n_g_m2, locale)} g N/m²`);
  // A robot's run time says nothing useful: one machine covers several lawns, and the
  // minutes it spent are not the minutes any one lawn got. That it mowed is the fact.
  if (p.height_mm && event.code !== "mow") bits.push(`${p.height_mm} mm`);
  return bits.join(" · ");
}

/**
 * When to do it, as the reader would write it down.
 *
 * A job done three times in a day is three hours, not the six-hour span between the first
 * and the last: "11:00–17:00" for three two-minute waterings says the sprinkler runs all
 * afternoon, which is the opposite of what is being asked for.
 */
export function eventTime(event, locale) {
  const at = event.params?.at;
  if (at?.length > 1) return at.join(" · ");
  if (event.all_day || !event.start) return "";
  return event.end ? `${fmtTime(event.start, locale)}–${fmtTime(event.end, locale)}` : fmtTime(event.start, locale);
}

export function categoryIcon(category) {
  return icon(CATEGORY_ICONS[category] || CATEGORY_ICONS.general, "icon--sm");
}

/**
 * A lawn, as a lettered circle.
 *
 * A bare coloured dot next to a coloured pill reads as one more category; a circle with the
 * lawn's initial in it cannot be mistaken for anything else.
 */
export function zoneBadge(entryId, zoneColour, zoneName) {
  const name = (zoneName ? zoneName(entryId) : "") || "";
  // "North lawn" and "New lawn" share their first letter, so a leading word every lawn on
  // the property has is dropped before the initial is taken.
  const distinctive = name.replace(/\s*(giardino|prato|lawn|garden|zona|zone)\s*/i, " ").trim() || name;
  const initial = distinctive.charAt(0).toUpperCase() || entryId.charAt(0).toUpperCase();
  return el("span", { class: "zone", style: { background: zoneColour(entryId) }, title: name }, initial);
}

/** The lawns an event applies to. */
export function zoneDots(event, zoneColour, zoneName) {
  const zones = event.zones || [event.entry_id];
  return el("span", { class: "zones" }, zones.map((id) => zoneBadge(id, zoneColour, zoneName)));
}


