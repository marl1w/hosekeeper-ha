/** Render a list of advice items with their reasons spelled out. */

import { el, icon } from "../dom.js";
import { fill, fmtNumber } from "../format.js";
import { lookup, strings } from "../i18n.js";

const ICONS = {
  irrigation: "mdi:water",
  mowing: "mdi:mower",
  fertilizing: "mdi:seed",
  seeding: "mdi:sprout",
  weeds: "mdi:flower-tulip-outline",
  disease: "mdi:bacteria-outline",
  aeration: "mdi:dots-grid",
  general: "mdi:information-outline",
};

function decorate(params, lang, snapshot) {
  const s = strings(lang);
  const out = { ...params };
  if (params.preset && snapshot?.fertilizers?.[params.preset]) {
    out.preset = snapshot.fertilizers[params.preset].name;
  }
  if (params.role && s.npk[params.role]) out.role = s.npk[params.role];
  if (params.seed_mix) out.seed_mix = lookup(lang, "seedMix", params.seed_mix);
  if (Array.isArray(params.gdd_window)) out.gdd_window = params.gdd_window.join("–");
  return out;
}

export function adviceItem(item, lang, locale, snapshot) {
  const text = lookup(lang, "advice", item.code);
  const params = decorate(item.params || {}, lang, snapshot);
  const title = typeof text === "object" ? fill(text.title, params, locale) : item.code;
  const body = typeof text === "object" && text.body ? fill(text.body, params, locale) : "";
  const reasons = (item.reasons || []).map((code) => lookup(lang, "reasons", code)).filter((r) => r);
  const info = item.priority >= 4;
  return el(
    "div",
    { class: `advice__item${info ? " advice__item--info" : ""}`, "data-category": item.category },
    el("div", { class: "advice__bar" }),
    el(
      "div",
      {},
      el(
        "div",
        { class: "advice__title" },
        icon(ICONS[item.category] || ICONS.general, "icon--sm"),
        title,
        item.params?.optional ? el("span", { class: "badge" }, strings(lang).ui.optional) : null
      ),
      body ? el("div", { class: "advice__body" }, body) : null,
      reasons.length && !info
        ? el("ul", { class: "advice__why" }, reasons.map((r) => el("li", {}, r)))
        : null
    )
  );
}

export function adviceList(items, lang, locale, snapshot, emptyText) {
  if (!items.length) return el("div", { class: "dim small" }, emptyText || "");
  return el("div", { class: "advice" }, items.map((item) => adviceItem(item, lang, locale, snapshot)));
}

export function section(label, iconName, ...children) {
  return el(
    "section",
    { class: "section enter" },
    el("div", { class: "section__label" }, iconName ? icon(iconName) : null, label),
    ...children
  );
}

export function stat(label, value, unit, note) {
  return el(
    "div",
    { class: "stat" },
    el("div", { class: "stat__label" }, label),
    el("div", { class: "stat__value" }, value, unit ? el("small", {}, unit) : null),
    note ? el("div", { class: "stat__note" }, note) : null
  );
}

export { fmtNumber };
