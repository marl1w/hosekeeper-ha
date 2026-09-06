/**
 * "I did this": one button and one small dialog, rather than a wall of controls.
 *
 * Recording work nobody asked for needs three answers — which lawn, what, and for watering
 * how long — and laid out inline that is two rows per lawn before anything has been done.
 * Six rows of controls on a property of three lawns, for the rarest thing anyone comes here
 * to do. So it collapses to a button, and the questions are asked once, in order, when the
 * button is pressed.
 *
 * The dialog is part of the page it belongs to rather than something bolted onto the
 * document: the panel lives in a shadow root, and a dialog appended anywhere else would lose
 * every style it has.
 */

import { el } from "../dom.js";
import { lookup, strings } from "../i18n.js";
import { ALL, chosen, dialog, field, lawnChoice } from "./dialog.js";

// Watering is not a maintenance kind: it goes in as minutes and lands in the water balance,
// so it is offered alongside them and written differently.
export const WATERING = "__watering__";

/** A small number box: the dialog asks for four of these and they should all look alike. */
function numberBox(id, max) {
  return el("input", {
    class: "water__input tabular",
    id,
    type: "number",
    min: "0",
    max: String(max),
    step: "1",
    inputmode: "numeric",
    value: "0",
  });
}

export function recordDialog(
  snapshots,
  { lang, kinds, todayIso, zoneName, onWater, onRecord, onFeed }
) {
  const s = strings(lang);
  const byId = new Map(snapshots.map((snapshot) => [snapshot.entry_id, snapshot]));
  const lawn = lawnChoice(snapshots, { lang, zoneName, id: "hk-record-lawn" });
  const activity = el(
    "select",
    { class: "record__select", id: "hk-record-what" },
    onWater ? el("option", { value: WATERING }, s.ui.wateredByHand) : null,
    (kinds || []).map((kind) => el("option", { value: kind }, lookup(lang, "maintenance", kind)))
  );
  const minutes = numberBox("hk-record-minutes", 1440);
  const minutesRow = field(
    s.ui.minutesWatered,
    el("span", { class: "record__inline" }, minutes, el("span", { class: "water__unit" }, s.ui.minutes))
  );

  // What each job needs beyond its name. A cut is a height, a feed is a product and a rate,
  // a sowing is a mix and a rate; the rest need nothing but the fact that they happened.
  const height = numberBox("hk-record-height", 150);
  const heightRow = field(
    s.ui.cuttingHeight,
    el("span", { class: "record__inline" }, height, el("span", { class: "water__unit" }, "mm"))
  );
  const presets = Object.entries(snapshots[0]?.fertilizers || {});
  const product = el(
    "select",
    { class: "record__select", id: "hk-record-product" },
    presets.map(([key, f]) => el("option", { value: key }, f.name))
  );
  const productRow = field(s.ui.whichProduct, product);
  const dose = numberBox("hk-record-dose", 500);
  const doseRow = field(
    s.ui.dose,
    el("span", { class: "record__inline" }, dose, el("span", { class: "water__unit" }, "g/m²"))
  );
  // A mix is a product name, so it cannot be a closed list — but nobody should have to type
  // "perennial ryegrass" from memory either. A datalist is the native answer to exactly that:
  // the grasses the integration knows are offered, and anything else can still be written.
  const mixes = el(
    "datalist",
    { id: "hk-record-mixes" },
    Object.keys(strings(lang).grasses || {}).map((grass) =>
      el("option", { value: lookup(lang, "grasses", grass) })
    )
  );
  const mix = el("input", {
    class: "record__text",
    id: "hk-record-mix",
    type: "text",
    list: "hk-record-mixes",
    autocomplete: "off",
  });
  const mixRow = field(s.ui.seedMix, el("span", { class: "record__inline" }, mix, mixes));
  // When it happened. A person opens the panel in the evening to record the cut they made at
  // five, so the hour is theirs to set, and it starts at now because that is the common case.
  const when = el("input", { class: "record__text record__time", id: "hk-record-when", type: "time" });
  const whenRow = field(s.ui.atWhatTime, when);
  const rate = numberBox("hk-record-rate", 200);
  const rateRow = field(
    s.ui.seedRate,
    el("span", { class: "record__inline" }, rate, el("span", { class: "water__unit" }, "g/m²"))
  );

  /** The month's planned feed for a lawn, which is what a feed is most likely to be. */
  const plannedFeed = (entryId) =>
    (byId.get(entryId)?.state?.plan || []).find(
      (op) => op.month === todayIso.slice(0, 7) && op.category === "fertilizing"
    );

  /** Show the fields the chosen job needs, and fill them with what the lawn already says. */
  const sync = () => {
    const what = activity.value;
    const first = lawn.value === ALL ? snapshots[0] : byId.get(lawn.value);
    minutesRow.hidden = what !== WATERING;
    heightRow.hidden = what !== "mowing";
    productRow.hidden = doseRow.hidden = what !== "fertilizing";
    mixRow.hidden = rateRow.hidden = what !== "sowing";
    if (what === WATERING) {
      minutes.value = String(Math.round(first?.state?.irrigation_today_min || 0));
    }
    if (what === "mowing") {
      const asked = (first?.state?.advice || []).find((a) => a.params?.height_mm)?.params?.height_mm;
      height.value = String(asked || first?.field?.mow_height_mm || 40);
    }
    if (what === "sowing" && !mix.value) {
      // The lawn's own grass is the likeliest answer, so it is the one already there.
      mix.value = lookup(lang, "grasses", first?.field?.grass_type || "");
    }
    if (what === "fertilizing") {
      const planned = first ? plannedFeed(first.entry_id) : null;
      if (planned?.params?.preset && snapshots[0]?.fertilizers?.[planned.params.preset]) {
        product.value = planned.params.preset;
      } else if (!product.value && presets.length) {
        product.value = presets[0][0];
      }
      const preset = snapshots[0]?.fertilizers?.[product.value];
      dose.value = String(Math.round(planned?.params?.dose_g_m2 || preset?.dose_g_m2 || 25));
    }
  };
  product.addEventListener("change", () => {
    const preset = snapshots[0]?.fertilizers?.[product.value];
    if (preset?.dose_g_m2) dose.value = String(Math.round(preset.dose_g_m2));
  });
  activity.addEventListener("change", sync);
  lawn.addEventListener("change", sync);

  /** What goes in the diary beside the fact that the job happened. */
  const detailsFor = (what) => {
    if (what === "mowing") return height.value ? { height_mm: Number(height.value) } : {};
    if (what === "sowing") {
      const out = {};
      if (mix.value) out.seed_mix = mix.value;
      if (rate.value) out.rate_g_m2 = Number(rate.value);
      return out;
    }
    return {};
  };

  return dialog({
    lang,
    title: s.ui.recordSomething,
    openLabel: s.ui.recordSomething,
    openIcon: "mdi:clipboard-check-outline",
    submitLabel: s.ui.record,
    body: [
      snapshots.length > 1 ? field(s.ui.colLawn, lawn) : lawn,
      field(s.ui.whatWasDone, activity),
      minutesRow,
      whenRow,
      heightRow,
      productRow,
      doseRow,
      mixRow,
      rateRow,
      el("div", { class: "section__hint" }, s.ui.recordHint),
    ],
    onOpen: () => {
      activity.value = onWater ? WATERING : (kinds || [])[0];
      const now = new Date();
      when.value = `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
      sync();
    },
    onSubmit: () => {
      const what = activity.value;
      const value = Number(String(minutes.value ?? "").replace(",", "."));
      if (what === WATERING && (!Number.isFinite(value) || value < 0)) return false;
      // The hour applies to everything: it is when the job happened, and for a watering it
      // is when the hose was on, even though the balance only cares about the day's total.
      const at = when.value ? `${todayIso}T${when.value}:00` : undefined;
      for (const entryId of chosen(snapshots, lawn)) {
        if (what === WATERING) {
          onWater(entryId, value, at);
          continue;
        }
        if (what === "fertilizing") {
          // Never as free details: the integration works the nitrogen out from the product
          // and the rate, so the panel sends those and nothing it has computed itself.
          onFeed(entryId, product.value, Number(dose.value) || undefined, at);
          continue;
        }
        onRecord(entryId, what, detailsFor(what), at);
      }
      return true;
    },
  });
}
