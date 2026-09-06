/**
 * The weather behind the work, for any day the panel can show.
 *
 * The calendar said what to do and never why the day was like that, so a watering on
 * Thursday and none on Friday looked arbitrary. The numbers were all in the snapshot
 * already: measured in the diary for the days gone, forecast for the week ahead, and the
 * season's own rate for the days past the forecast.
 *
 * Which of the three a number came from matters more than the number, so it is never
 * dropped: a measured 34 °C and a guessed one are not the same fact, and a reader deciding
 * whether to water tonight needs to know which they are looking at.
 */

import { el, icon } from "../dom.js";
import { fmtNumber } from "../format.js";
import { strings } from "../i18n.js";

const ICON_FOR = {
  sunny: "mdi:weather-sunny",
  clear: "mdi:weather-sunny",
  "clear-night": "mdi:weather-sunny",
  cloudy: "mdi:weather-cloudy",
  partlycloudy: "mdi:weather-partly-cloudy",
  rainy: "mdi:weather-rainy",
  pouring: "mdi:weather-pouring",
  lightning: "mdi:weather-pouring",
  "lightning-rainy": "mdi:weather-pouring",
};

/** The icon a day deserves: what fell decides it, and the sky's own word breaks the tie. */
function conditionIcon(rain, condition) {
  if (rain >= 4) return "mdi:weather-pouring";
  if (rain > 0.2) return "mdi:weather-rainy";
  return ICON_FOR[condition] || (condition ? "mdi:weather-partly-cloudy" : "mdi:weather-sunny");
}

/**
 * One day's weather, wherever in time it falls.
 *
 * `source` is "measured" for a day the station lived through, "forecast" for one the model
 * still covers, and "expected" past that, where the numbers are the season's rate with no
 * rain in them and are a projection rather than a prediction.
 */
export function dayWeather(dateIso, snapshot) {
  const st = snapshot?.state || {};
  const logged = (snapshot?.days || []).find((d) => d.date === dateIso);
  if (logged && (logged.tmax !== undefined || logged.rain_mm !== undefined)) {
    return {
      source: "measured",
      tmax: logged.tmax ?? null,
      tmin: logged.tmin ?? null,
      rain: logged.rain_mm ?? 0,
      etc: logged.etc_mm ?? null,
    };
  }
  const ahead = (st.forecast_days || []).find((f) => String(f.datetime || "").slice(0, 10) === dateIso);
  const projected = (st.projection || []).find((d) => d.date === dateIso);
  if (!ahead && !projected) return null;
  return {
    source: ahead ? "forecast" : "expected",
    tmax: ahead?.temperature ?? null,
    tmin: ahead?.templow ?? null,
    // The projection's rain is the forecast already discounted by how often this place's
    // forecast has been right, which is the number the watering decision was actually made
    // on. Showing the raw forecast instead would not explain the plan beside it.
    rain: projected?.rain_mm ?? ahead?.precipitation ?? 0,
    etc: projected?.etc_mm ?? null,
    condition: ahead?.condition,
  };
}

/** The weather as one line: an icon, the two temperatures, the rain and what the lawn used. */
export function weatherLine(dateIso, snapshot, { lang, locale, compact = false } = {}) {
  const w = dayWeather(dateIso, snapshot);
  if (!w) return null;
  const s = strings(lang);
  const bits = [];
  if (w.tmax !== null) {
    bits.push(
      el(
        "span",
        { class: "wx__temps" },
        el("span", { class: "wx__hi tabular" }, `${fmtNumber(w.tmax, locale, 0)}°`),
        w.tmin === null ? null : el("span", { class: "wx__lo tabular" }, `${fmtNumber(w.tmin, locale, 0)}°`)
      )
    );
  }
  if (w.rain > 0.05) {
    bits.push(
      el("span", { class: "wx__rain tabular" }, icon("mdi:water", "icon--sm"), `${fmtNumber(w.rain, locale, 1)} mm`)
    );
  }
  if (!compact && w.etc) {
    bits.push(el("span", { class: "wx__et tabular" }, `${s.ui.waterOut} ${fmtNumber(w.etc, locale, 1)} mm`));
  }
  if (!bits.length) return null;
  return el(
    "div",
    { class: `wx wx--${w.source}`, title: s.ui[`wx_${w.source}`] || "" },
    icon(conditionIcon(w.rain, w.condition), "icon--sm"),
    ...bits,
    compact ? null : el("span", { class: "wx__source" }, s.ui[`wx_${w.source}`] || "")
  );
}

/**
 * The week ahead, once, above the lawns.
 *
 * Every lawn on the property shares a sky, so this is drawn a single time rather than
 * repeated down a column of a table that already has enough columns.
 */
export function forecastStrip(snapshot, { lang, locale, todayIso, days = 7 }) {
  const s = strings(lang);
  const start = new Date(`${todayIso}T12:00:00`);
  const cells = [];
  for (let i = 0; i < days; i += 1) {
    const date = new Date(start);
    date.setDate(date.getDate() + i);
    const iso = date.toISOString().slice(0, 10);
    const w = dayWeather(iso, snapshot);
    if (!w) continue;
    cells.push(
      el(
        "div",
        { class: `wxday wxday--${w.source}${i === 0 ? " wxday--today" : ""}` },
        el("div", { class: "wxday__dow" }, i === 0 ? s.ui.today : new Intl.DateTimeFormat(locale, { weekday: "short" }).format(date)),
        icon(conditionIcon(w.rain, w.condition), "icon--sm"),
        el(
          "div",
          { class: "wxday__temps tabular" },
          el("span", { class: "wx__hi" }, w.tmax === null ? "–" : `${fmtNumber(w.tmax, locale, 0)}°`),
          el("span", { class: "wx__lo" }, w.tmin === null ? "" : `${fmtNumber(w.tmin, locale, 0)}°`)
        ),
        el("div", { class: "wxday__rain tabular" }, w.rain > 0.05 ? `${fmtNumber(w.rain, locale, 1)} mm` : "")
      )
    );
  }
  if (!cells.length) return null;
  return el(
    "div",
    { class: "wxstrip" },
    ...cells,
    el("div", { class: "wxstrip__note" }, s.ui.forecastNote)
  );
}
