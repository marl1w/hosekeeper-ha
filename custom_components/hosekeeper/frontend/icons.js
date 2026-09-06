/**
 * The panel's icons, drawn here.
 *
 * Home Assistant's `ha-icon` is only defined inside the frontend, so a panel that leans on
 * it loses every glyph in the preview and in any context that has not loaded the icon set.
 * These are a dozen shapes on a 24-unit grid, which is the whole vocabulary the calendar
 * needs, and they render the same everywhere.
 */

const P = (d, extra = {}) => ({ tag: "path", d, ...extra });
const STROKE = { fill: "none", stroke: "currentColor", "stroke-width": 1.8, "stroke-linecap": "round", "stroke-linejoin": "round" };

export const ICONS = {
  // --- categories -----------------------------------------------------------------------
  water: [P("M12 3.2c-.4 0-6.3 7.1-6.3 11a6.3 6.3 0 0 0 12.6 0c0-3.9-5.9-11-6.3-11z", { fill: "currentColor" })],
  mower: [
    P("M3 15.5h10.2l1.6-4.2H7.4L6 15.5", STROKE),
    P("M14.8 11.3h3.4a2.8 2.8 0 0 1 2.8 2.8v1.4", STROKE),
    { tag: "circle", cx: 6.2, cy: 18.2, r: 2.2, ...STROKE },
    { tag: "circle", cx: 17.6, cy: 18.2, r: 2.2, ...STROKE },
  ],
  seed: [
    { tag: "circle", cx: 8, cy: 8.4, r: 2.1, fill: "currentColor" },
    { tag: "circle", cx: 15.4, cy: 10.6, r: 2.1, fill: "currentColor" },
    { tag: "circle", cx: 10.4, cy: 15.2, r: 2.1, fill: "currentColor" },
    P("M4.5 20h15", STROKE),
  ],
  sprout: [
    P("M12 20v-7", STROKE),
    P("M12 13c0-3 2.2-5.4 5.4-5.4C17.4 10.6 15.2 13 12 13z", { fill: "currentColor" }),
    P("M12 15c-2.6 0-4.6-2-4.6-4.6C10 10.4 12 12.4 12 15z", { fill: "currentColor" }),
  ],
  weeds: [
    P("M12 20V9.5", STROKE),
    P("M12 9.5c0-2.4 1.7-4.3 4-4.3 0 2.4-1.8 4.3-4 4.3z", { fill: "currentColor" }),
    P("M12 12.5c-2.3 0-4-1.9-4-4.3 2.3 0 4 1.9 4 4.3z", { fill: "currentColor" }),
    P("M6.5 20h11", STROKE),
  ],
  disease: [
    P("M5.5 15.5a6.5 6.5 0 0 1 13 0z", { fill: "currentColor" }),
    P("M9.6 15.5v2.6a2.4 2.4 0 0 0 4.8 0v-2.6", STROKE),
  ],
  aeration: [
    ...[7, 12, 17].flatMap((x) => [7, 12, 17].map((y) => ({ tag: "circle", cx: x, cy: y, r: 1.5, fill: "currentColor" }))),
  ],
  leaf: [
    P("M5 19c0-7.7 5-13 14-13 0 8.4-5.4 13-14 13z", { fill: "currentColor" }),
    P("M5 19c2.6-3.4 5.6-5.8 9.4-7.4", { ...STROKE, stroke: "var(--hk-surface)", "stroke-width": 1.4 }),
  ],
  // --- interface ------------------------------------------------------------------------
  menu: [P("M4 7h16M4 12h16M4 17h16", STROKE)],
  refresh: [
    P("M19 12a7 7 0 1 1-2.4-5.3", STROKE),
    P("M19.5 4.5V9h-4.5", STROKE),
  ],
  "chevron-left": [P("M14.5 5.5 8 12l6.5 6.5", STROKE)],
  "chevron-right": [P("M9.5 5.5 16 12l-6.5 6.5", STROKE)],
  "chevron-down": [P("M5.5 9.5 12 16l6.5-6.5", STROKE)],
  eye: [
    P("M2.8 12S6.6 5.8 12 5.8 21.2 12 21.2 12 17.4 18.2 12 18.2 2.8 12 2.8 12z", STROKE),
    { tag: "circle", cx: 12, cy: 12, r: 2.6, fill: "currentColor" },
  ],
  clipboard: [
    P("M8.5 4.6H6.8A1.8 1.8 0 0 0 5 6.4v12.2A1.8 1.8 0 0 0 6.8 20.4h10.4a1.8 1.8 0 0 0 1.8-1.8V6.4a1.8 1.8 0 0 0-1.8-1.8h-1.7", STROKE),
    P("M9.4 3.2h5.2v3H9.4z", STROKE),
    P("M8.6 11h6.8M8.6 15h4.4", STROKE),
  ],
  alert: [
    P("M12 4.4 21 19.6H3z", STROKE),
    P("M12 10v4", STROKE),
    { tag: "circle", cx: 12, cy: 17, r: 1, fill: "currentColor" },
  ],
  check: [
    { tag: "circle", cx: 12, cy: 12, r: 8.4, ...STROKE },
    P("M8.2 12.2 11 15l5-5.4", STROKE),
  ],
  calendar: [
    P("M4.6 6.6h14.8v13H4.6z", STROKE),
    P("M4.6 10.4h14.8M8.6 4.4v3.4M15.4 4.4v3.4", STROKE),
  ],
  "calendar-today": [
    P("M4.6 6.6h14.8v13H4.6z", STROKE),
    P("M4.6 10.4h14.8M8.6 4.4v3.4M15.4 4.4v3.4", STROKE),
    { tag: "rect", x: 10.4, y: 13, width: 6, height: 4, rx: 1, fill: "currentColor" },
  ],
  chart: [
    P("M4 19h16", STROKE),
    P("M5.5 15.5 10 10.5l3.2 3 5.3-6.2", STROKE),
  ],
  "water-clock": [
    { tag: "circle", cx: 12, cy: 12, r: 8.2, ...STROKE },
    P("M12 7.4V12l3.2 1.9", STROKE),
  ],
  grass: [
    P("M4 20c0-4.6 2-7.8 4.6-9.4C8.6 15 6.9 18.4 4 20z", { fill: "currentColor" }),
    P("M12 20c-.6-6 .8-10 3.4-12.4C16.6 12.6 15.2 17 12 20z", { fill: "currentColor" }),
    P("M20 20c0-4.6-1.6-7.6-4-9.2 0 4.4 1.4 7.6 4 9.2z", { fill: "currentColor" }),
  ],
  close: [P("M6.5 6.5 17.5 17.5M17.5 6.5 6.5 17.5", STROKE)],
  info: [
    { tag: "circle", cx: 12, cy: 12, r: 8.4, ...STROKE },
    P("M12 11.2V16", STROKE),
    { tag: "circle", cx: 12, cy: 8.2, r: 1.1, fill: "currentColor" },
  ],
  drop: [P("M12 3.2c-.4 0-6.3 7.1-6.3 11a6.3 6.3 0 0 0 12.6 0c0-3.9-5.9-11-6.3-11z", { fill: "currentColor" })],

  // --- weather ---------------------------------------------------------------------------
  sunny: [
    { tag: "circle", cx: 12, cy: 12, r: 4.2, fill: "currentColor" },
    P("M12 2.6v2.2M12 19.2v2.2M2.6 12h2.2M19.2 12h2.2M5.4 5.4l1.6 1.6M17 17l1.6 1.6M18.6 5.4L17 7M7 17l-1.6 1.6", STROKE),
  ],
  cloudy: [P("M7.4 18.5a4 4 0 0 1-.4-8 5.4 5.4 0 0 1 10.3 1.3 3.4 3.4 0 0 1-.5 6.7z", { fill: "currentColor" })],
  partlycloudy: [
    { tag: "circle", cx: 9, cy: 8.4, r: 3, fill: "currentColor", opacity: 0.55 },
    P("M9.4 19.4a3.6 3.6 0 0 1-.4-7.2 4.9 4.9 0 0 1 9.3 1.2 3.1 3.1 0 0 1-.5 6z", { fill: "currentColor" }),
  ],
  rainy: [
    P("M7.6 15.4a3.6 3.6 0 0 1-.4-7.2 4.9 4.9 0 0 1 9.3 1.2 3.1 3.1 0 0 1-.5 6z", { fill: "currentColor" }),
    P("M9 18l-1 2.6M13 18l-1 2.6M17 18l-1 2.6", STROKE),
  ],
  thermometer: [
    P("M12 4.5a2 2 0 0 1 2 2v6.6a3.6 3.6 0 1 1-4 0V6.5a2 2 0 0 1 2-2z", STROKE),
    { tag: "circle", cx: 12, cy: 16.6, r: 1.7, fill: "currentColor" },
  ],
};

/** Map the names the views ask for onto the drawings above. */
export const ALIASES = {
  "mdi:water": "water",
  "mdi:water-clock": "water-clock",
  "mdi:weather-sunny": "sunny",
  "mdi:weather-cloudy": "cloudy",
  "mdi:weather-partly-cloudy": "partlycloudy",
  "mdi:weather-rainy": "rainy",
  "mdi:weather-pouring": "rainy",
  "mdi:thermometer": "thermometer",
  "mdi:mower": "mower",
  "mdi:robot-mower": "mower",
  "mdi:seed": "seed",
  "mdi:sprout": "sprout",
  "mdi:flower-tulip-outline": "weeds",
  "mdi:bacteria-outline": "disease",
  "mdi:dots-grid": "aeration",
  "mdi:leaf": "leaf",
  "mdi:grass": "grass",
  "mdi:menu": "menu",
  "mdi:refresh": "refresh",
  "mdi:chevron-left": "chevron-left",
  "mdi:chevron-right": "chevron-right",
  "mdi:chevron-down": "chevron-down",
  "mdi:eye-outline": "eye",
  "mdi:clipboard-text-clock": "clipboard",
  "mdi:alert-outline": "alert",
  "mdi:check-circle-outline": "check",
  "mdi:calendar-today": "calendar-today",
  "mdi:calendar-month": "calendar",
  "mdi:calendar-week": "calendar",
  "mdi:chart-timeline-variant": "chart",
  "mdi:chart-line": "chart",
  "mdi:information-outline": "info",
  "mdi:notebook-outline": "clipboard",
  "mdi:clock-outline": "water-clock",
  "mdi:timer-outline": "water-clock",
  "mdi:school-outline": "info",
  "mdi:close": "close",
};
