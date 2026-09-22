/**
 * Every lawn's events, by day, with the copies taken out.
 *
 * Three things count as one line. The same job on several lawns is one job with several
 * lawns against it. The same job repeated through a day — three light waterings, four
 * irrigation runs — is one line that says how many. Only genuinely different work, a
 * different depth or a different product, stays apart.
 *
 * It lives here, and not in the panel, because the tests and the panel must merge the same
 * way: a test that merges by its own rules tests its own rules.
 */

import { confirmable } from "./views/confirm.js";

export const CATEGORY_ORDER = [
  "irrigation",
  "mowing",
  "fertilizing",
  "seeding",
  "weeds",
  "disease",
  "aeration",
  "general",
];

/**
 * Yesterday's lines, minus the ones there is nothing left to say about.
 *
 * The day keeps every line it carried, because the coordinator writing them has no idea
 * which of them anybody will want back. Two kinds are dropped on the way in. A line that is
 * not a job — an alert, a standing routine — cannot be confirmed, so offering it yesterday
 * would be offering a tick box that does nothing. And a line the day already records was
 * done and written down: the diary's own entry is beside it, and a second row asking for the
 * same cut reads as the engine not having noticed.
 *
 * Both tests come from `confirmable`, which is where confirming is defined. A copy of that
 * list here would be a copy to keep in step, and the one it drifted from would be the one
 * deciding what the reader sees.
 */
function stillOpen(event, recorded) {
  if (event.kind !== "unrecorded") return true;
  const payload = confirmable(event);
  if (!payload) return false;
  return !recorded.has(payload.what === "irrigation" ? "irrigation" : payload.kind);
}

/** The diary's names for the work one lawn recorded on each day. */
function recordedByDay(snapshot) {
  const out = new Map();
  for (const event of snapshot.events || []) {
    if (event.kind !== "logged") continue;
    if (!out.has(event.date)) out.set(event.date, new Set());
    // A watering is kept as the day's total rather than as a job, so it comes back under a
    // name of its own; everything else is filed under the diary kind it was written as.
    out.get(event.date).add(event.code === "irrigation_done" ? "irrigation" : event.code);
  }
  return out;
}

/**
 * What makes two lines the same line.
 *
 * The rule the merge is for is that the same job on several lawns is one job with several
 * lawns against it — and the test of "the same job" is that a reader following the line
 * would do the same thing on every lawn under it. So the shape of the work belongs in the
 * key, not just its name: a zone wetted six times from half past ten is not doing the same
 * job as one wetted five times from eleven, however alike the two read.
 *
 * This used to stop at the code and the product. Nothing showed, because every zone of a
 * lawn was given identical passes and identical depths; the first zone to shade differently
 * from its neighbours put five hours on a line that four zones were standing under, three of
 * which were on six. A merge that hides the difference is worse than no merge, because the
 * reader has no way to tell it happened.
 *
 * The depths stay out of the key for a split run. A watering divided into cycles is several
 * parts of one job whose mm and minutes are meant to be added back together below, and
 * keying on them would leave the parts sitting apart as though they were different work.
 */
function signature(event) {
  const params = event.params || {};
  const split = params.of !== undefined;
  return [
    event.code,
    event.category,
    event.kind,
    params.operation ?? "",
    params.height_mm ?? "",
    params.preset ?? "",
    params.dose_g_m2 ?? "",
    params.status ?? "",
    params.issue ?? "",
    // The shape of the work: when it runs, how often, and how much each time.
    (params.at || []).join(","),
    params.times ?? "",
    split ? "" : (params.mm ?? ""),
    split ? "" : (params.minutes ?? ""),
  ].join("|");
}

export function mergeEvents(snapshots) {
  const byDay = new Map();
  for (const snapshot of snapshots) {
    const recorded = recordedByDay(snapshot);
    for (const event of snapshot.events || []) {
      // Per lawn, before anything is merged: one lawn's cut being written down says nothing
      // about the lawn next to it, and after merging there is no telling the two apart.
      if (!stillOpen(event, recorded.get(event.date) || new Set())) continue;
      if (!byDay.has(event.date)) byDay.set(event.date, new Map());
      const bucket = byDay.get(event.date);
      const key = signature(event);
      const merged = bucket.get(key);
      if (!merged) {
        bucket.set(key, { ...event, params: { ...(event.params || {}) }, zones: [event.zone_id], repeats: 1 });
        continue;
      }
      if (!merged.zones.includes(event.zone_id)) merged.zones.push(event.zone_id);
      else merged.repeats += 1;
      if (event.start && (!merged.start || event.start < merged.start)) merged.start = event.start;
      if (event.end && (!merged.end || event.end > merged.end)) merged.end = event.end;
      // A split job's parts add up to the whole; its run numbers stop meaning anything.
      if (event.params?.of) {
        merged.params.mm = Math.round(((merged.params.mm || 0) + (event.params.mm || 0)) * 10) / 10;
        merged.params.minutes = (merged.params.minutes || 0) + (event.params.minutes || 0);
        delete merged.params.cycle;
        delete merged.params.of;
      }
    }
  }
  const out = new Map();
  for (const [date, bucket] of byDay) {
    const list = [...bucket.values()];
    list.sort(
      (a, b) =>
        (a.start || "").localeCompare(b.start || "") ||
        CATEGORY_ORDER.indexOf(a.category) - CATEGORY_ORDER.indexOf(b.category)
    );
    out.set(date, list);
  }
  return out;
}

/**
 * The same days with the month's standing lines taken out.
 *
 * The plan carries jobs that run all month rather than happening on a day — "mow every five
 * days at 60 mm" — and they are filed on the first of their month so the month view and the
 * overview can show what the season asks for. A day and a week are lists of work to do, and
 * a standing routine is not work to do on Tuesday: it is the reason Tuesday's cut is there.
 * Anything actually due inside the week has been dated by the agenda already, so nothing
 * that can be acted on is lost by leaving these out.
 */
export function datedOnly(byDay) {
  const out = new Map();
  for (const [date, list] of byDay) {
    const kept = list.filter((event) => event.code !== "planned_month");
    if (kept.length) out.set(date, kept);
  }
  return out;
}
