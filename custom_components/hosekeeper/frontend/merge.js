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

function signature(event) {
  const params = event.params || {};
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
  ].join("|");
}

export function mergeEvents(snapshots) {
  const byDay = new Map();
  for (const snapshot of snapshots) {
    for (const event of snapshot.events || []) {
      if (!byDay.has(event.date)) byDay.set(event.date, new Map());
      const bucket = byDay.get(event.date);
      const key = signature(event);
      const merged = bucket.get(key);
      if (!merged) {
        bucket.set(key, { ...event, params: { ...(event.params || {}) }, zones: [event.entry_id], repeats: 1 });
        continue;
      }
      if (!merged.zones.includes(event.entry_id)) merged.zones.push(event.entry_id);
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
