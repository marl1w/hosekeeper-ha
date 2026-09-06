/**
 * Two charts, drawn by hand, that answer the two questions the diary is kept for.
 *
 * The first is the state of the lawn: how much of the water the roots can reach is still
 * there, day by day, against the line below which the grass starts to suffer. The second is
 * why it moved: what came in as rain and irrigation, drawn upward, and what the lawn used,
 * drawn downward. Two pictures beat one crowded one — the earlier chart put millimetres a
 * day and a running total on the same axis, which made both unreadable.
 */

import { el, svg } from "./dom.js";
import { fmtDate } from "./format.js";

const W = 640;
const PAD = { top: 12, right: 10, bottom: 22, left: 34 };

function axisDates(days, count = 6) {
  const step = Math.max(1, Math.ceil(days.length / count));
  return days.map((d, i) => (i % step === 0 ? d.date : null));
}

/**
 * Past and future in one series.
 *
 * The diary ends today; the projection carries on from it. Charts that stopped at today
 * answered "what happened" and never "what is about to", which is the half a plan is made
 * from — so both halves are drawn, split by a line on today and the future drawn lighter.
 */
export function joinSeries(days, projection = [], todayKey) {
  const past = days.filter((d) => !todayKey || d.date <= todayKey);
  const planned = new Map(projection.map((d) => [d.date, d]));
  const merged = past.map((day) => {
    // Today is in both: the diary holds what has already fallen and been given, the
    // projection holds tonight's cycle, which has not run yet. Both belong on the day.
    const ahead = planned.get(day.date);
    const still = ahead ? (ahead.irrigation_mm || 0) - (day.irrigation_mm || 0) : 0;
    return still > 0 ? { ...day, planned_irrigation_mm: still } : day;
  });
  const seen = new Set(past.map((d) => d.date));
  const future = projection.filter((d) => !seen.has(d.date)).map((d) => ({ ...d, projected: true }));
  return [...merged, ...future];
}

/** How full the root zone was, and is about to be, as a percentage of what the roots reach. */
export function soilWaterChart(days, { locale, rawMm, tawMm, labels } = {}) {
  const H = 132;
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;
  const taw = tawMm || 1;
  const threshold = Math.max(0, Math.min(1, 1 - (rawMm || 0) / taw));
  const value = (day) => (day.deficit_mm === undefined || day.deficit_mm === null ? null : Math.max(0, Math.min(1, 1 - day.deficit_mm / taw)));
  const x = (i) => PAD.left + (days.length <= 1 ? innerW / 2 : (i * innerW) / (days.length - 1));
  const y = (v) => PAD.top + innerH - v * innerH;

  const root = svg("svg", { class: "chart", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": labels?.title || "" });
  // The band the grass is comfortable in, and the one it is not.
  root.append(svg("rect", { x: PAD.left, y: PAD.top, width: innerW, height: y(threshold) - PAD.top, fill: "var(--hk-reserve)", opacity: 0.07 }));
  root.append(svg("rect", { x: PAD.left, y: y(threshold), width: innerW, height: PAD.top + innerH - y(threshold), fill: "var(--hk-warn)", opacity: 0.1 }));
  root.append(svg("line", { x1: PAD.left, x2: W - PAD.right, y1: y(threshold), y2: y(threshold), stroke: "var(--hk-warn)", "stroke-dasharray": "4 4", "stroke-width": 1.2 }));
  for (const frac of [0, 0.5, 1]) {
    root.append(svg("text", { x: PAD.left - 6, y: y(frac) + 3, "text-anchor": "end" }, `${Math.round(frac * 100)}%`));
  }

  // The days ahead get a lighter ground. That alone says where measurement stops, so there
  // is no line on today: a second marker for the same boundary is one too many. Beyond the
  // forecast the ground is lighter again: those days are not a forecast at all, but the
  // season's own rate with no rain in it, and the picture must not pass them off as one.
  const firstFuture = days.findIndex((d) => d.projected);
  if (firstFuture > 0) {
    root.append(svg("rect", { x: x(firstFuture - 0.5), y: PAD.top, width: W - PAD.right - x(firstFuture - 0.5), height: innerH, fill: "var(--hk-text)", opacity: 0.04 }));
  }
  const firstBlind = days.findIndex((d) => d.projected && d.forecast === false);
  if (firstBlind > 0) {
    root.append(svg("rect", { x: x(firstBlind - 0.5), y: PAD.top, width: W - PAD.right - x(firstBlind - 0.5), height: innerH, fill: "var(--hk-text)", opacity: 0.05 }));
    root.append(svg("line", { x1: x(firstBlind - 0.5), x2: x(firstBlind - 0.5), y1: PAD.top, y2: PAD.top + innerH, stroke: "var(--hk-text-dim)", "stroke-dasharray": "2 3", "stroke-width": 1 }));
  }

  const segment = (subset, dashed) => {
    const points = subset.map(([px, v]) => `${px},${y(v)}`).join(" ");
    if (subset.length < 2) return;
    if (!dashed) {
      root.append(svg("polygon", { points: `${subset[0][0]},${y(0)} ${points} ${subset[subset.length - 1][0]},${y(0)}`, fill: "var(--hk-reserve)", opacity: 0.18 }));
    }
    root.append(
      svg("polyline", {
        points,
        fill: "none",
        stroke: "var(--hk-reserve)",
        "stroke-width": 2,
        "stroke-linejoin": "round",
        "stroke-dasharray": dashed ? "5 4" : null,
        opacity: dashed ? 0.85 : 1,
      })
    );
  };
  const all = days.map((d, i) => [x(i), value(d), Boolean(d.projected)]).filter(([, v]) => v !== null);
  segment(all.filter(([, , future]) => !future), false);
  const bridge = all.filter(([, , future]) => future);
  const lastPast = [...all].reverse().find(([, , future]) => !future);
  segment(lastPast ? [lastPast, ...bridge] : bridge, true);

  axisDates(days).forEach((date, i) => {
    if (date) root.append(svg("text", { x: x(i), y: H - 6, "text-anchor": "middle" }, fmtDate(date, locale, { day: "numeric", month: "short" })));
  });
  return root;
}

/** What came in and what the lawn used, each day. */
export function waterFlowChart(days, { locale } = {}) {
  const H = 150;
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;
  const slot = innerW / Math.max(days.length, 1);
  const maxIn = Math.max(
    6,
    ...days.map(
      (d) => (d.rain_mm || 0) + (d.irrigation_mm || 0) + (d.planned_irrigation_mm || 0) + (d.seedbed_mm || 0)
    )
  );
  const maxOut = Math.max(4, ...days.map((d) => d.etc_mm || 0));
  const scale = Math.max(maxIn, maxOut * 1.6);
  const zero = PAD.top + (innerH * maxIn) / (maxIn + Math.max(maxOut, scale - maxIn) || 1);
  const upH = zero - PAD.top;
  const downH = PAD.top + innerH - zero;
  const up = (mm) => (mm / (maxIn || 1)) * upH;
  const down = (mm) => (mm / (maxOut || 1)) * downH;
  const x = (i) => PAD.left + i * slot;

  const root = svg("svg", { class: "chart", viewBox: `0 0 ${W} ${H}`, role: "img" });
  root.append(svg("line", { x1: PAD.left, x2: W - PAD.right, y1: zero, y2: zero, stroke: "var(--hk-line)" }));
  root.append(svg("text", { x: PAD.left - 6, y: PAD.top + 8, "text-anchor": "end" }, `${Math.round(maxIn)}`));
  root.append(svg("text", { x: PAD.left - 6, y: PAD.top + innerH, "text-anchor": "end" }, `${Math.round(maxOut)}`));

  const firstFuture = days.findIndex((d) => d.projected);
  if (firstFuture > 0) {
    root.append(svg("rect", { x: x(firstFuture), y: PAD.top, width: W - PAD.right - x(firstFuture), height: innerH, fill: "var(--hk-text)", opacity: 0.04 }));
  }
  days.forEach((day, i) => {
    const bw = Math.max(2, slot * 0.6);
    const bx = x(i) + (slot - bw) / 2;
    const soon = day.projected ? 0.55 : 1;
    const rain = day.rain_mm || 0;
    const irrigation = day.irrigation_mm || 0;
    if (rain > 0) root.append(svg("rect", { x: bx, y: zero - up(rain), width: bw, height: up(rain), rx: 1.5, fill: "var(--hk-rain)", opacity: soon }));
    if (irrigation > 0) root.append(svg("rect", { x: bx, y: zero - up(rain + irrigation), width: bw, height: up(irrigation), rx: 1.5, fill: "var(--hk-irrigation)", opacity: soon }));
    const planned = day.planned_irrigation_mm || 0;
    if (planned > 0) {
      // Tonight's cycle: the same blue, hollowed out, because it has not run yet.
      root.append(
        svg("rect", {
          x: bx,
          y: zero - up(rain + irrigation + planned),
          width: bw,
          height: up(planned),
          rx: 1.5,
          fill: "var(--hk-irrigation)",
          opacity: 0.35,
          stroke: "var(--hk-irrigation)",
          "stroke-dasharray": "3 2",
        })
      );
    }
    // The seedbed's light waterings sit on top, hatched: water that goes on the lawn but
    // stays in the top centimetre, which is why the line below does not rise with them.
    const seedbed = day.seedbed_mm || 0;
    if (seedbed > 0) {
      const base = rain + irrigation + planned;
      root.append(
        svg("rect", {
          x: bx,
          y: zero - up(base + seedbed),
          width: bw,
          height: up(seedbed),
          rx: 1.5,
          fill: "var(--hk-irrigation)",
          opacity: 0.28 * soon,
        })
      );
    }
    const etc = day.etc_mm || 0;
    if (etc > 0) root.append(svg("rect", { x: bx, y: zero, width: bw, height: down(etc), rx: 1.5, fill: "var(--hk-et)", opacity: 0.85 * soon }));
  });
  axisDates(days).forEach((date, i) => {
    if (date) root.append(svg("text", { x: x(i) + slot / 2, y: H - 6, "text-anchor": "middle" }, fmtDate(date, locale, { day: "numeric", month: "short" })));
  });
  return root;
}

export function legend(items) {
  return el(
    "div",
    { class: "legend" },
    items.map(([color, label]) => el("span", { class: "legend__item" }, el("span", { class: "legend__swatch", style: { background: color } }), label))
  );
}

/**
 * The glance's soil water: where it is, and where it is going.
 *
 * A bar showing this instant answers "is the lawn short of water now", which on a lawn that
 * was watered at dawn is always no, and is therefore the least useful thing the row could
 * say. What a glance is for is the next few days: the line the balance projects, the mark it
 * must not fall below, and a tick on every day the plan waters. Read left to right it says
 * "full now, watering Tuesday and Thursday, still fine on Friday".
 *
 * The days past the forecast are drawn dashed, as everywhere else, because they are the
 * season's rate with no rain in them rather than a prediction.
 */
export function soilWaterSpark(days, { rawMm, tawMm, label } = {}) {
  const W2 = 300;
  const H2 = 34;
  const taw = tawMm || 1;
  const pad = { top: 4, bottom: 7, left: 0, right: 0 };
  const innerH = H2 - pad.top - pad.bottom;
  const threshold = Math.max(0, Math.min(1, 1 - (rawMm || 0) / taw));
  const points = days
    .map((d, i) => ({
      i,
      value: d.deficit_mm === undefined || d.deficit_mm === null ? null : Math.max(0, Math.min(1, 1 - d.deficit_mm / taw)),
      watered: (d.irrigation_mm || 0) > 0,
      blind: d.forecast === false,
    }))
    .filter((p) => p.value !== null);
  // With nothing to draw the frame is still drawn, greyed: the row keeps its height and its
  // alignment, and an empty chart says "nothing known here" more plainly than a gap does.
  const bare = points.length < 2;
  const root = svg("svg", {
    class: `chart spark${bare ? " spark--empty" : ""}`,
    viewBox: `0 0 ${W2} ${H2}`,
    role: "img",
    "aria-label": label || "",
    preserveAspectRatio: "none",
  });
  const x = (i) => (i * W2) / Math.max(1, points.length - 1);
  const y = (v) => pad.top + innerH - v * innerH;

  // The band below the watering mark, so a dip into it is visible without reading numbers.
  root.append(svg("rect", { x: 0, y: y(threshold), width: W2, height: pad.top + innerH - y(threshold), fill: "var(--hk-warn)", opacity: 0.12 }));
  root.append(svg("line", { x1: 0, x2: W2, y1: y(threshold), y2: y(threshold), stroke: "var(--hk-warn)", "stroke-dasharray": "3 3", "stroke-width": 1 }));

  const line = (subset, dashed) => {
    if (subset.length < 2) return;
    root.append(
      svg("polyline", {
        points: subset.map((p) => `${x(p.i)},${y(p.value)}`).join(" "),
        fill: "none",
        stroke: "var(--hk-reserve)",
        "stroke-width": 2,
        "stroke-linejoin": "round",
        "stroke-dasharray": dashed ? "4 3" : null,
        opacity: dashed ? 0.8 : 1,
        "vector-effect": "non-scaling-stroke",
      })
    );
  };
  if (bare) return root;
  const solid = points.filter((p) => !p.blind);
  line(solid, false);
  const blind = points.filter((p) => p.blind);
  line(solid.length ? [solid[solid.length - 1], ...blind] : blind, true);

  // A tick under every day the plan waters: when it happens matters as much as the level.
  for (const p of points) {
    if (!p.watered) continue;
    root.append(svg("rect", { x: Math.max(0, x(p.i) - 1.5), y: H2 - 5, width: 3, height: 4, rx: 1, fill: "var(--hk-irrigation)" }));
  }
  root.append(svg("circle", { cx: x(0), cy: y(points[0].value), r: 3, fill: "var(--hk-reserve)" }));
  return root;
}

/** The horizontal meter used at a glance: how full the root zone is, with the watering mark. */
export function waterGauge({ deficit, taw, raw }) {
  const full = taw > 0 ? Math.max(0, Math.min(1, 1 - deficit / taw)) : 0;
  const mark = taw > 0 ? Math.max(0, Math.min(1, 1 - raw / taw)) : 0.5;
  const root = svg("svg", { class: "chart", viewBox: "0 0 300 20", role: "img", preserveAspectRatio: "none" });
  root.append(svg("rect", { x: 0, y: 5, width: 300, height: 10, rx: 5, fill: "var(--hk-surface-sunken)" }));
  const tone = full > mark ? "var(--hk-reserve)" : full > mark * 0.6 ? "var(--hk-warn)" : "var(--hk-error)";
  root.append(svg("rect", { x: 0, y: 5, width: 300 * full, height: 10, rx: 5, fill: tone }));
  root.append(svg("line", { x1: 300 * mark, x2: 300 * mark, y1: 1, y2: 19, stroke: "var(--hk-warn)", "stroke-width": 2 }));
  return root;
}
