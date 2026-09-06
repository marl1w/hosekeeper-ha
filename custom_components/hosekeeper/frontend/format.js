/** Formatting helpers that follow the frontend's locale. */

export function fmtNumber(value, locale, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "–";
  return new Intl.NumberFormat(locale, { maximumFractionDigits: digits, minimumFractionDigits: 0 }).format(Number(value));
}

export function fmtDate(iso, locale, opts = { weekday: "short", day: "numeric", month: "short" }) {
  if (!iso) return "–";
  const date = iso.length === 10 ? new Date(`${iso}T12:00:00`) : new Date(iso);
  return new Intl.DateTimeFormat(locale, opts).format(date);
}

export function fmtTime(iso, locale) {
  if (!iso) return "–";
  return new Intl.DateTimeFormat(locale, { hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
}

export function fmtMonth(key, locale) {
  // key is YYYY-MM
  const [year, month] = key.split("-").map(Number);
  return new Intl.DateTimeFormat(locale, { month: "long", year: "numeric" }).format(new Date(year, month - 1, 1));
}

export function todayKey() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

export function monthKey(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

export function addMonths(key, count) {
  const [year, month] = key.split("-").map(Number);
  const date = new Date(year, month - 1 + count, 1);
  return monthKey(date);
}

/** Fill {placeholders} in a template from params, formatting numbers. */
export function fill(template, params, locale) {
  return template.replace(/\{(\w+)\}/g, (_, key) => {
    const value = params[key];
    if (value === null || value === undefined) return "…";
    if (typeof value === "number") return fmtNumber(value, locale, Number.isInteger(value) ? 0 : 1);
    return String(value);
  });
}

/** The locale to format numbers and dates with, following the frontend's own. */
export function pickLocale(hass, fallback = "en") {
  return (hass && (hass.locale?.language || hass.language)) || fallback;
}
