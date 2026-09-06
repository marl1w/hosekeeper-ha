/** The numbers behind the calendar: the water in the root zone, and what moved it. */

import { el, icon } from "../dom.js";
import { fmtNumber, todayKey } from "../format.js";
import { strings } from "../i18n.js";
import { joinSeries, legend, soilWaterChart, waterFlowChart } from "../charts.js";
import { stat } from "./advice.js";
import { zoneBadge } from "./events.js";

export function renderTrend(snapshots, { lang, locale, zoneColour, zoneName, pastDays = 21 }) {
  const s = strings(lang);
  return el(
    "div",
    { class: "trend" },
    ...snapshots.map((snapshot) => {
      const st = snapshot.state || {};
      const today = todayKey();
      // The window follows the view: today sits in it, with the days behind and the days
      // the projection can speak for in front.
      const series = joinSeries((snapshot.days || []).slice(-pastDays), st.projection || [], today);
      const month = (snapshot.days || []).filter((d) => d.date.slice(0, 7) === today.slice(0, 7));
      const sum = (key) => month.reduce((a, d) => a + (d[key] || 0), 0);
      return el(
        "div",
        { class: "panel" },
        el("h3", { class: "panel__title" }, zoneBadge(snapshot.entry_id, zoneColour, zoneName), snapshot.field?.name || ""),
        el("div", { class: "chart__label" }, s.ui.chartReserve),
        soilWaterChart(series, { locale, rawMm: st.raw_mm, tawMm: st.taw_mm }),
        legend([
          ["var(--hk-reserve)", s.legend.soilWater],
          ["var(--hk-warn)", s.legend.mark],
          ["var(--hk-text-dim)", s.legend.projected],
          ...(series.some((d) => d.forecast === false) ? [["var(--hk-text-dim)", s.legend.noForecast]] : []),
        ]),
        el("div", { class: "chart__label", style: { marginTop: "16px" } }, s.ui.chartFlow),
        waterFlowChart(series, { locale }),
        legend([
          ["var(--hk-rain)", s.legend.rain],
          ["var(--hk-irrigation)", s.legend.irrigation],
          ...(series.some((d) => d.seedbed_mm) ? [["color-mix(in srgb, var(--hk-irrigation) 30%, transparent)", s.legend.seedbed]] : []),
          ["var(--hk-et)", s.legend.used],
        ]),
        el(
          "div",
          { class: "stats", style: { marginTop: "14px" } },
          stat(s.ui.rainTotal, fmtNumber(sum("rain_mm"), locale, 0), s.ui.mm),
          stat(s.ui.irrigationTotal, fmtNumber(sum("irrigation_mm"), locale, 0), s.ui.mm),
          stat(s.ui.etTotal, fmtNumber(sum("etc_mm"), locale, 0), s.ui.mm),
          stat(s.ui.nitrogenYear, fmtNumber(st.nitrogen_year_g_m2, locale), "g/m²"),
          stat(s.ui.soilTemp, fmtNumber(st.soil_temperature_c, locale), "°C"),
          stat(
            s.ui.forecastReliability,
            st.forecast_rain_reliability == null ? "–" : String(Math.round(st.forecast_rain_reliability * 100)),
            st.forecast_rain_reliability == null ? null : "%",
            st.forecast_rain_reliability == null ? s.ui.forecastUnproven : null
          )
        )
      );
    })
  );
}

export { icon };
