/**
 * Shared design system for the panel.
 *
 * Everything is expressed through Home Assistant's own theme variables, so the panel
 * follows the user's theme — including custom and dark themes — instead of imposing its
 * own palette. Fallbacks are supplied for every variable so the panel still looks
 * deliberate if a theme omits one.
 */

export const TOKENS = /* css */ `
:host {
  --hk-bg: var(--primary-background-color, #f2f4f7);
  --hk-surface: var(--card-background-color, #fff);
  --hk-surface-sunken: var(--secondary-background-color, #e9ecf1);
  --hk-text: var(--primary-text-color, #1c1e21);
  --hk-text-dim: var(--secondary-text-color, #6b7280);
  --hk-text-on-accent: var(--text-primary-color, #fff);
  --hk-line: var(--divider-color, rgba(127, 127, 127, 0.22));
  --hk-accent: var(--primary-color, #03a9f4);
  --hk-error: var(--error-color, #db4437);
  --hk-warn: var(--warning-color, #ffa600);
  --hk-ok: var(--success-color, #43a047);

  /*
   * Two palettes that must never be confused. The first says what kind of job an event is,
   * the second says which lawn it belongs to — so the lawn hues are deliberately far from
   * the job hues, and a lawn is always drawn as a lettered circle rather than a bare dot.
   */
  --hk-tone-irrigation: #2f80ed;
  --hk-tone-mowing: #2f9e44;
  --hk-tone-fertilizing: #b58100;
  --hk-tone-seeding: #7cb518;
  --hk-tone-weeds: #e8730c;
  --hk-tone-disease: #d3392b;
  --hk-tone-aeration: #6b7a8f;
  --hk-tone-general: #8b93a7;

  /* Water: what came in, what went out, what is left. */
  --hk-rain: #4a90d9;
  --hk-irrigation: #1f5fbf;
  --hk-et: #e8952a;
  --hk-reserve: #2aa5a0;

  --hk-safe-top: var(--safe-area-inset-top, env(safe-area-inset-top, 0px));
  --hk-safe-bottom: var(--safe-area-inset-bottom, env(safe-area-inset-bottom, 0px));

  --hk-radius: 14px;
  --hk-radius-sm: 10px;
  --hk-radius-pill: 999px;
  --hk-gap: 12px;
  --hk-shadow: 0 1px 2px rgba(0, 0, 0, 0.06), 0 4px 14px rgba(0, 0, 0, 0.06);
  --hk-ease: cubic-bezier(0.2, 0, 0.2, 1);
}
`;

export const BASE = /* css */ `
*, *::before, *::after { box-sizing: border-box; }

:host {
  display: block;
  color: var(--hk-text);
  font-family: var(--ha-font-family-body, var(--paper-font-body1_-_font-family, Roboto, system-ui, sans-serif));
  -webkit-font-smoothing: antialiased;
}

.h1 { margin: 0; font-size: 1.4rem; font-weight: 600; letter-spacing: -0.01em; }
.h2 { margin: 0; font-size: 1.05rem; font-weight: 600; }
.h3 { margin: 0; font-size: 0.95rem; font-weight: 600; }
.dim { color: var(--hk-text-dim); }
.small { font-size: 0.82rem; }
.tabular { font-variant-numeric: tabular-nums; }

.row { display: flex; align-items: center; gap: var(--hk-gap); }
.row--wrap { flex-wrap: wrap; }
.col { display: flex; flex-direction: column; gap: var(--hk-gap); }
.spacer { flex: 1 1 auto; }

/* One centred column; sections breathe through whitespace, not boxes. */
.page { max-width: 880px; margin: 0 auto; display: flex; flex-direction: column; gap: 28px; }
.section { display: flex; flex-direction: column; gap: 10px; }
.section__label { display: flex; align-items: center; gap: 8px; font-size: 0.74rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; color: var(--hk-text-dim); }
.section__label .icon { width: 16px; height: 16px; }
.section__label .spacer { flex: 1 1 auto; }
.section__hint { font-size: 0.84rem; color: var(--hk-text-dim); line-height: 1.45; }
.pair { display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
.panel { background: var(--hk-surface); border: 1px solid var(--hk-line); border-radius: var(--hk-radius); padding: 14px 16px; }
.panel__title { font-weight: 600; margin: 0 0 8px; display: flex; align-items: center; gap: 8px; }
.hairline { border: 0; border-top: 1px solid var(--hk-line); margin: 0; }

/* The status strip at the top of a view */
.hero { display: flex; flex-direction: column; gap: 12px; padding: 4px 0 0; }
.hero__chips { display: flex; flex-wrap: wrap; gap: 8px; }
.hero__gauge { display: flex; align-items: center; gap: 14px; }
.hero__gauge svg { flex: 1 1 auto; }
.hero__gauge-label { font-size: 0.84rem; color: var(--hk-text-dim); white-space: nowrap; }
.hero__gauge-label b { color: var(--hk-text); font-weight: 600; }

.icon { width: 20px; height: 20px; flex: 0 0 auto; display: block; }
.icon--sm { width: 16px; height: 16px; }
.icon--lg { width: 28px; height: 28px; }

button { font: inherit; color: inherit; border: none; background: none; cursor: pointer; }
button:disabled { cursor: not-allowed; opacity: 0.45; }

.btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  padding: 9px 16px; border-radius: var(--hk-radius-pill);
  font-size: 0.9rem; font-weight: 500; background: var(--hk-surface-sunken);
  transition: background 140ms var(--hk-ease), transform 140ms var(--hk-ease);
}
.btn:hover:not(:disabled) { background: color-mix(in srgb, var(--hk-accent) 12%, var(--hk-surface-sunken)); }
.btn:active:not(:disabled) { transform: scale(0.97); }
.btn--primary { background: var(--hk-accent); color: var(--hk-text-on-accent); }
.btn--quiet { background: transparent; }
.btn[aria-pressed="true"] { background: color-mix(in srgb, var(--hk-accent) 20%, transparent); color: color-mix(in srgb, var(--hk-accent) 85%, var(--hk-text)); }

.icon-btn { display: inline-flex; align-items: center; justify-content: center; width: 40px; height: 40px; border-radius: 50%; }
.icon-btn:hover:not(:disabled) { background: color-mix(in srgb, currentColor 12%, transparent); }

:focus-visible { outline: 2px solid var(--hk-accent); outline-offset: 2px; }

.chip {
  display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px;
  border-radius: var(--hk-radius-pill); font-size: 0.78rem; font-weight: 600; line-height: 1.4; white-space: nowrap;
  background: color-mix(in srgb, var(--chip-tone, var(--hk-tone-general)) 16%, transparent);
  color: color-mix(in srgb, var(--chip-tone, var(--hk-tone-general)) 82%, var(--hk-text));
}
.chip .icon { width: 15px; height: 15px; }
.chip[data-tone="irrigation"] { --chip-tone: var(--hk-tone-irrigation); }
.chip[data-tone="mowing"] { --chip-tone: var(--hk-tone-mowing); }
.chip[data-tone="fertilizing"] { --chip-tone: var(--hk-tone-fertilizing); }
.chip[data-tone="seeding"] { --chip-tone: var(--hk-tone-seeding); }
.chip[data-tone="weeds"] { --chip-tone: var(--hk-tone-weeds); }
.chip[data-tone="disease"] { --chip-tone: var(--hk-tone-disease); }
.chip[data-tone="aeration"] { --chip-tone: var(--hk-tone-aeration); }
.chip[data-tone="general"] { --chip-tone: var(--hk-tone-general); }
.chip[data-tone="ok"] { --chip-tone: var(--hk-ok); }
.chip[data-tone="warn"] { --chip-tone: var(--hk-warn); }
.chip[data-tone="error"] { --chip-tone: var(--hk-error); }

.badge { display: inline-flex; align-items: center; gap: 5px; padding: 2px 8px; border-radius: 6px; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.02em; border: 1px solid var(--hk-line); color: var(--hk-text-dim); }
.badge--done { border-color: transparent; background: color-mix(in srgb, var(--hk-ok) 18%, transparent); color: color-mix(in srgb, var(--hk-ok) 80%, var(--hk-text)); }
.badge--open { border-color: transparent; background: color-mix(in srgb, var(--hk-accent) 18%, transparent); color: color-mix(in srgb, var(--hk-accent) 85%, var(--hk-text)); }
.badge--missed { border-color: transparent; background: color-mix(in srgb, var(--hk-error) 18%, transparent); color: color-mix(in srgb, var(--hk-error) 85%, var(--hk-text)); }

.empty { display: flex; flex-direction: column; align-items: center; gap: 10px; padding: 40px 24px; text-align: center; color: var(--hk-text-dim); }
.empty .icon { width: 44px; height: 44px; opacity: 0.5; }
.empty__title { font-size: 1rem; font-weight: 600; color: var(--hk-text); }
.empty__body { max-width: 42ch; line-height: 1.5; font-size: 0.88rem; }

.enter { animation: hk-enter 260ms var(--hk-ease) both; }
/* Redrawing the view you are already on is not arriving at it. */
.content--still .enter { animation: none; }
@keyframes hk-enter { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.001ms !important; transition-duration: 0.001ms !important; }
}

.scroll { overflow: auto; scrollbar-width: thin; overscroll-behavior: contain; }

/* Advice list */
.advice { display: flex; flex-direction: column; gap: 10px; }
.advice__item { display: grid; grid-template-columns: 4px 1fr; gap: 14px; padding: 12px 14px 12px 0; border-radius: var(--hk-radius); background: var(--hk-surface); border: 1px solid var(--hk-line); overflow: hidden; }
.advice__bar { background: var(--adv-tone, var(--hk-tone-general)); }
.advice__item[data-category="irrigation"] { --adv-tone: var(--hk-tone-irrigation); }
.advice__item[data-category="mowing"] { --adv-tone: var(--hk-tone-mowing); }
.advice__item[data-category="fertilizing"] { --adv-tone: var(--hk-tone-fertilizing); }
.advice__item[data-category="seeding"] { --adv-tone: var(--hk-tone-seeding); }
.advice__item[data-category="weeds"] { --adv-tone: var(--hk-tone-weeds); }
.advice__item[data-category="disease"] { --adv-tone: var(--hk-tone-disease); }
.advice__item[data-category="aeration"] { --adv-tone: var(--hk-tone-aeration); }
.advice__title { font-weight: 600; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.advice__body { margin-top: 4px; line-height: 1.45; font-size: 0.92rem; }
.advice__why { margin: 6px 0 0; padding: 0 0 0 16px; color: var(--hk-text-dim); font-size: 0.84rem; line-height: 1.45; }
.advice__why li::marker { color: var(--adv-tone, var(--hk-text-dim)); }
.advice__item--info { opacity: 0.85; }
.advice__item--info .advice__title { font-weight: 500; }

/* Plan operations */
.ops { display: flex; flex-direction: column; background: var(--hk-surface); border: 1px solid var(--hk-line); border-radius: var(--hk-radius); padding: 0 14px; }
.op { border-bottom: 1px solid var(--hk-line); }
.op:last-child { border-bottom: 0; }
.op__row { display: flex; align-items: center; gap: 12px; padding: 10px 2px; }
.op__icon { display: inline-flex; width: 28px; height: 28px; border-radius: 8px; align-items: center; justify-content: center; flex: 0 0 auto;
  background: color-mix(in srgb, var(--op-tone, var(--hk-tone-general)) 16%, transparent); color: color-mix(in srgb, var(--op-tone, var(--hk-tone-general)) 85%, var(--hk-text)); }
.op[data-category="irrigation"] { --op-tone: var(--hk-tone-irrigation); }
.op[data-category="mowing"] { --op-tone: var(--hk-tone-mowing); }
.op[data-category="fertilizing"] { --op-tone: var(--hk-tone-fertilizing); }
.op[data-category="seeding"] { --op-tone: var(--hk-tone-seeding); }
.op[data-category="weeds"] { --op-tone: var(--hk-tone-weeds); }
.op[data-category="disease"] { --op-tone: var(--hk-tone-disease); }
.op[data-category="aeration"] { --op-tone: var(--hk-tone-aeration); }
.op__main { flex: 1 1 auto; min-width: 0; }
.op__name { font-weight: 600; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.op__detail { font-size: 0.84rem; color: var(--hk-text-dim); margin-top: 2px; }
.op__how { font-size: 0.9rem; line-height: 1.45; margin-top: 6px; }
.op--done .op__name, .op--skipped .op__name { color: var(--hk-text-dim); font-weight: 500; }
.op__toggle { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: var(--hk-radius-pill); font-size: 0.78rem; font-weight: 600; color: var(--hk-text-dim); }
.op__toggle:hover { background: color-mix(in srgb, currentColor 12%, transparent); }
.op__toggle .icon { transition: transform 160ms var(--hk-ease); }
.op__toggle[aria-expanded="true"] .icon { transform: rotate(180deg); }
.op__why { padding: 0 2px 12px 40px; }
.op__why[hidden] { display: none; }
.op__why-title { font-size: 0.76rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--hk-text-dim); margin: 6px 0 2px; }
.op__why .advice__why { margin-top: 0; }

/* At a glance */
/*
 * A table, so the columns are measured once for the whole strip. Every earlier version laid
 * each row out on its own, which let a lawn carrying an alert chip set different column
 * widths from the lawn above it — and, inside a button, let the cells overlap outright.
 */
/* The week's sky, once, above the lawns. It scrolls sideways on a phone rather than
   squeezing seven days into a width that fits none of them. */
.wxstrip { display: flex; gap: 6px; overflow-x: auto; padding: 2px 0 8px; scrollbar-width: thin; }
.wxday { flex: 1 0 62px; display: flex; flex-direction: column; align-items: center; gap: 3px; padding: 8px 4px; border-radius: 12px; background: var(--hk-surface); border: 1px solid var(--hk-line); }
.wxday--today { border-color: color-mix(in srgb, var(--hk-accent) 45%, var(--hk-line)); background: color-mix(in srgb, var(--hk-accent) 8%, var(--hk-surface)); }
.wxday--expected { opacity: 0.62; border-style: dashed; }
.wxday__dow { font-size: 0.7rem; font-weight: 700; text-transform: capitalize; color: var(--hk-text-dim); }
.wxday__temps { display: flex; gap: 4px; font-size: 0.82rem; }
.wxday__rain { font-size: 0.68rem; color: var(--hk-rain); min-height: 0.9em; }
.wxstrip__note { flex: 0 0 auto; align-self: center; max-width: 150px; font-size: 0.66rem; line-height: 1.25; color: var(--hk-text-dim); padding-left: 4px; }
.wx { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin: -2px 0 10px; font-size: 0.82rem; color: var(--hk-text-dim); }
.wx__temps { display: flex; gap: 5px; }
.wx__hi { font-weight: 700; color: var(--hk-text); }
.wx__lo { color: var(--hk-text-dim); }
.wx__rain, .wx__et { display: inline-flex; align-items: center; gap: 4px; }
.wx__rain { color: var(--hk-rain); }
.wx__source { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.04em; opacity: 0.75; }
.wx--expected { font-style: italic; }

.glance {
  width: 100%;
  border-collapse: collapse;
  background: var(--hk-surface);
  border: 1px solid var(--hk-line);
  border-radius: var(--hk-radius);
  overflow: hidden;
  /*
   * Fixed, and measured from the header alone.
   *
   * With automatic layout every column was sized by whatever the rows happened to hold, so a
   * day with no dry spell to report, or a lawn with no watering time, moved every column on
   * the strip. Paging through dates made the whole thing breathe.
   */
  table-layout: fixed;
}
.section__label-note { margin-left: 6px; font-weight: 600; text-transform: none; letter-spacing: 0; color: var(--hk-accent); }
.glance__head th { padding: 9px 8px 7px; text-align: left; font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--hk-text-dim); border-bottom: 1px solid var(--hk-line); background: color-mix(in srgb, var(--hk-text) 3%, transparent); }
.glance__head th:first-child { padding-left: 14px; }
.glance__head th:last-child { padding-right: 14px; }
.glance__row { cursor: pointer; }
.glance__row:not(:last-child) > td { border-bottom: 1px solid var(--hk-line); }
/* The row carries the highlight, not its cells: painting the cells leaves grey blocks
   wherever a cell happens to sit in the grid, with gaps between them. */
.glance__row:hover { background: color-mix(in srgb, var(--hk-text) 4%, transparent); }
.glance__row[aria-pressed="true"] { background: color-mix(in srgb, var(--hk-accent) 8%, transparent); }
.glance__row:focus-visible { outline: 2px solid var(--hk-accent); outline-offset: -2px; }
.glance td { padding: 12px 8px; vertical-align: middle; line-height: 1.35; }
.glance td:first-child { padding-left: 14px; padding-right: 12px; }
.glance td:last-child { padding-right: 14px; }
/* The badge sits in the middle of its own cell, with real space before the name. */
.glance__badge { width: 46px; white-space: nowrap; text-align: center; }
.glance__badge .zone { vertical-align: middle; }
.glance__name { width: 24%; }
.glance__title { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.glance__sub { font-size: 0.76rem; color: var(--hk-text-dim); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.glance__meter { width: 26%; }
.glance__meter .chart { width: 100%; height: 14px; }
.glance__meter .spark { height: 34px; }
/* Nothing known for this day: the frame stays so the rows line up, faded so it is plainly
   not a reading. */
.spark--empty { opacity: 0.35; }
.glance__pct { width: 68px; white-space: nowrap; text-align: right; }
.glance__pctnow { font-size: 0.88rem; font-weight: 600; }
/* The floor the coming days reach, so "100 %" is not read as "nothing to do this week". */
.glance__pctlow { font-size: 0.72rem; font-weight: 600; color: var(--hk-text-dim); }
.glance__next { width: auto; font-size: 0.92rem; overflow-wrap: anywhere; }
.glance__when { width: 8.5rem; }
.glance__chips { display: flex; gap: 6px; justify-content: flex-end; flex-wrap: wrap; }

/*
 * On a narrow screen text wraps rather than being cut off.
 *
 * Truncating buys nothing on a phone: the row is already the width of the screen, so the
 * words that get an ellipsis are simply lost, and it is the lawn's own name and the job it
 * wants that get lost first. On a wide screen the ellipsis still earns its place, because a
 * long name there would push a column out of line.
 */
@media (max-width: 760px) {
  /* Inside the glance the cells are reached through a rule that names the element as well
     as the class, so a bare class loses to it and the ellipsis stays. Every one of these
     names its ancestor for that reason. */
  .glance td .glance__title,
  .glance td .glance__sub,
  .pill__text,
  .pill__detail,
  .rate__name,
  .track__facts .pill__text {
    overflow: visible;
    text-overflow: clip;
    white-space: normal;
    overflow-wrap: anywhere;
  }
  .pill,
  .pill--logged {
    align-items: flex-start;
  }
  .glance td.glance__name {
    max-width: none;
  }
}

@media (max-width: 760px) {
  /*
   * On a phone the table becomes a small grid per lawn.
   *
   * Every cell rule here names the element as well as the class. A bare class loses to the
   * rule above that selects a class and an element together, which is how the hidden label
   * reappeared at the bottom of the card, unplaced, while everything else moved.
   */
  .glance,
  .glance tbody {
    display: block;
  }
  /* A header names columns that no longer exist once the row becomes a card. */
  .glance thead.glance__head { display: none; }
  .glance__row {
    display: grid;
    /*
     * The meter spans every column, so its width does not depend on how many alert chips
     * the lawn happens to carry — sharing a row with them is what made one lawn's bar
     * shorter than the next one's.
     */
    grid-template-columns: 26px minmax(0, 1fr) auto;
    grid-template-areas:
      "badge name  pct"
      "meter meter meter"
      "next  next  next"
      "chips chips chips";
    gap: 8px 12px;
    align-items: center;
    padding: 12px;
  }
  .glance__row:not(:last-child) { border-bottom: 1px solid var(--hk-line); }
  .glance__row:not(:last-child) > td { border-bottom: 0; }
  .glance td { display: block; padding: 0; }
  .glance td.glance__badge {
    grid-area: badge;
    width: auto;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  /* The table widths have to go, not just the ellipsis. A cell that is still 24 % wide is
     24 % of the grid area it now sits in, which is a column of one word per line inside a
     card that has the whole screen. */
  .glance td.glance__name { grid-area: name; width: auto; max-width: none; }
  .glance td.glance__meter { grid-area: meter; width: auto; min-width: 0; }
  .glance td.glance__meter .chart { height: 12px; }
  .glance td.glance__meter .spark { height: 30px; }
  .glance td.glance__pct { grid-area: pct; width: auto; text-align: right; align-self: center; }
  .glance td.glance__next { grid-area: next; }
  .glance td.glance__when { grid-area: chips; width: auto; }
  .glance td.glance__when:empty { display: none; }
}

/* Event pills */
.pill { display: inline-flex; align-items: center; gap: 6px; max-width: 100%; padding: 3px 9px; border-radius: var(--hk-radius-pill); font-size: 0.78rem; font-weight: 600; line-height: 1.35;
  background: color-mix(in srgb, var(--pill-tone, var(--hk-tone-general)) 15%, transparent); color: color-mix(in srgb, var(--pill-tone, var(--hk-tone-general)) 88%, var(--hk-text)); }
.pill .icon { width: 14px; height: 14px; }
.pill__text { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.zone { display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px; border-radius: 50%; flex: 0 0 auto;
  font-size: 0.66rem; font-weight: 700; letter-spacing: 0; color: #fff; }
.zones { display: inline-flex; gap: 3px; }
.pill .zone { width: 15px; height: 15px; font-size: 0.6rem; }
.cal__dots .zone { width: 14px; height: 14px; font-size: 0.58rem; }
.pill__time { font-weight: 500; opacity: 0.75; }
.pill__detail { font-weight: 500; opacity: 0.75; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pill[data-category="irrigation"] { --pill-tone: var(--hk-tone-irrigation); }
.pill[data-category="mowing"] { --pill-tone: var(--hk-tone-mowing); }
.pill[data-category="fertilizing"] { --pill-tone: var(--hk-tone-fertilizing); }
.pill[data-category="seeding"] { --pill-tone: var(--hk-tone-seeding); }
.pill[data-category="weeds"] { --pill-tone: var(--hk-tone-weeds); }
.pill[data-category="disease"] { --pill-tone: var(--hk-tone-disease); }
.pill[data-category="aeration"] { --pill-tone: var(--hk-tone-aeration); }
.pill--logged { opacity: 0.72; font-weight: 500; }
.pill--planned { background: transparent; border: 1px dashed color-mix(in srgb, var(--pill-tone, var(--hk-tone-general)) 55%, transparent); }

/* Month grid */
.cal__banner { display: flex; align-items: flex-start; gap: 10px; padding: 10px 12px; border-bottom: 1px solid var(--hk-line); background: color-mix(in srgb, var(--hk-text) 3%, transparent); }
.cal__banner-label { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--hk-text-dim); white-space: nowrap; padding-top: 3px; }
.cal__banner-items { display: flex; flex-wrap: wrap; gap: 6px; }
.action__repeat { font-size: 0.82rem; font-weight: 600; color: color-mix(in srgb, var(--act-tone, var(--hk-accent)) 85%, var(--hk-text)); }
.cal { background: var(--hk-surface); border: 1px solid var(--hk-line); border-radius: var(--hk-radius); overflow: hidden; }
.cal__head { display: grid; grid-template-columns: repeat(7, 1fr); border-bottom: 1px solid var(--hk-line); }
.cal__dow { padding: 8px 6px; text-align: center; font-size: 0.7rem; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; color: var(--hk-text-dim); }
.cal__grid { display: grid; grid-template-columns: repeat(7, 1fr); grid-auto-rows: 112px; }
.cal__day { display: flex; flex-direction: column; gap: 4px; align-items: stretch; overflow: hidden; padding: 6px; text-align: left; border-right: 1px solid var(--hk-line); border-bottom: 1px solid var(--hk-line); }
.cal__day:nth-child(7n) { border-right: 0; }
.cal__day:hover { background: color-mix(in srgb, var(--hk-text) 4%, transparent); }
.cal__day--outside { opacity: 0.4; }
.cal__day--today .cal__num { color: var(--hk-accent); font-weight: 700; }
.cal__day--selected { background: color-mix(in srgb, var(--hk-accent) 10%, transparent); box-shadow: inset 0 0 0 2px var(--hk-accent); }
.cal__num { display: flex; align-items: center; justify-content: space-between; font-size: 0.82rem; font-variant-numeric: tabular-nums; color: var(--hk-text-dim); }
.cal__dots { display: inline-flex; gap: 3px; }
.cal__dot { width: 6px; height: 6px; border-radius: 50%; }
.cal__events { display: flex; flex-direction: column; gap: 3px; min-width: 0; overflow: hidden; }
.cal__more { font-size: 0.72rem; color: var(--hk-text-dim); }
@media (max-width: 700px) {
  .cal__grid { grid-auto-rows: 66px; }
  .cal__day { padding: 4px; }
  .cal__events .pill__text { display: none; }
  .cal__events { flex-direction: row; flex-wrap: wrap; }
  .cal__events .pill { padding: 3px; }
}

/* Agenda */
.agenda { display: flex; flex-direction: column; background: var(--hk-surface); border: 1px solid var(--hk-line); border-radius: var(--hk-radius); overflow: hidden; }
.agenda__day { display: grid; grid-template-columns: 76px 1fr; gap: 12px; align-items: start; padding: 10px 14px; text-align: left; border-bottom: 1px solid var(--hk-line); }
.agenda__day:last-child { border-bottom: 0; }
.agenda__day:hover { background: color-mix(in srgb, var(--hk-text) 4%, transparent); }
.agenda__day--past { opacity: 0.6; }
.agenda__day--selected { background: color-mix(in srgb, var(--hk-accent) 8%, transparent); }
.agenda__day--today .agenda__num { color: var(--hk-accent); }
.agenda__date { display: flex; align-items: baseline; gap: 6px; }
.agenda__dow { font-size: 0.76rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--hk-text-dim); }
.agenda__num { font-size: 1.05rem; font-weight: 600; font-variant-numeric: tabular-nums; }
.agenda__today { font-size: 0.68rem; font-weight: 700; text-transform: uppercase; color: var(--hk-accent); }
.agenda__events { display: flex; flex-wrap: wrap; gap: 6px; min-width: 0; }
.agenda__empty { color: var(--hk-text-dim); }

/* Next actions on the overview */
.actions { display: flex; flex-direction: column; gap: 8px; }
.action { display: grid; grid-template-columns: 58px 1fr; gap: 14px; align-items: start; text-align: left; padding: 10px 14px 12px 10px; background: var(--hk-surface); border: 1px solid var(--hk-line); border-left: 4px solid var(--act-tone, var(--hk-tone-general)); border-radius: var(--hk-radius); }
.action:hover { border-color: color-mix(in srgb, var(--act-tone, var(--hk-accent)) 45%, var(--hk-line)); }
.action[data-category="irrigation"] { --act-tone: var(--hk-tone-irrigation); }
.action[data-category="mowing"] { --act-tone: var(--hk-tone-mowing); }
.action[data-category="fertilizing"] { --act-tone: var(--hk-tone-fertilizing); }
.action[data-category="seeding"] { --act-tone: var(--hk-tone-seeding); }
.action[data-category="weeds"] { --act-tone: var(--hk-tone-weeds); }
.action[data-category="disease"] { --act-tone: var(--hk-tone-disease); }
.action[data-category="aeration"] { --act-tone: var(--hk-tone-aeration); }
.action__body { display: flex; flex-direction: column; gap: 3px; padding-top: 2px; min-width: 0; }
.action__head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.action__zones { display: inline-flex; gap: 3px; }
.action__title { font-weight: 600; }
.datechip { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0; padding: 6px 4px; border-radius: var(--hk-radius-sm);
  background: var(--hk-surface-sunken); line-height: 1.05; }
.datechip__dow { font-size: 0.64rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: var(--hk-text-dim); }
.datechip__num { font-size: 1.5rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.datechip__mon { font-size: 0.66rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--hk-text-dim); }
.datechip--today { background: color-mix(in srgb, var(--hk-accent) 16%, transparent); }
.datechip--month { justify-content: center; padding: 10px 4px; }
.datechip__monthname { font-size: 0.95rem; font-weight: 700; text-transform: capitalize; }
.datechip__year { font-size: 0.66rem; font-weight: 600; color: var(--hk-text-dim); }
.datechip--today .datechip__num, .datechip--today .datechip__dow, .datechip--today .datechip__mon { color: color-mix(in srgb, var(--hk-accent) 88%, var(--hk-text)); }
.rate__options--wrap { flex-wrap: wrap; }
.track__sub { margin: 4px 0 2px; font-size: 0.76rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.04em; color: var(--hk-text-dim); }
.rate__btn--primary { border-color: transparent; background: color-mix(in srgb, var(--hk-accent) 16%, transparent); color: color-mix(in srgb, var(--hk-accent) 90%, var(--hk-text)); }
.rate__btn--primary:hover { background: color-mix(in srgb, var(--hk-accent) 26%, transparent); }

/* The dialog lives inside the page it belongs to: the panel is in a shadow root, and one
   appended to the document would lose every style it has. */
/* The layer generates no box of its own, so a dialog inside it is positioned against the
   panel and covers exactly what the panel covers, whatever Home Assistant wraps it in. */
.layer { display: contents; }
.modal { position: absolute; inset: 0; z-index: 20; display: flex; align-items: center; justify-content: center; padding: 16px; }
.modal[hidden] { display: none; }
.modal__scrim { position: absolute; inset: 0; background: rgba(0, 0, 0, 0.42); }
.modal__card { position: relative; display: flex; flex-direction: column; gap: 12px; width: min(26rem, 100%); max-height: 90vh; overflow: auto; padding: 18px; border-radius: var(--hk-radius); background: var(--hk-surface); box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3); }
.modal__title { font-size: 1.02rem; font-weight: 700; }
.modal__actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 4px; }
.record__field { display: flex; align-items: center; justify-content: space-between; gap: 12px; font-size: 0.86rem; font-weight: 600; }
.record__field[hidden] { display: none; }
.record__inline { display: inline-flex; align-items: center; gap: 6px; }
.track { display: flex; flex-direction: column; gap: 8px; }
.track__row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.track__facts { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-left: auto; }
.track__none { font-size: 0.82rem; color: var(--hk-text-dim); font-style: italic; }
.track__act { margin-top: 12px; }
.record__text { flex: 1 1 auto; min-width: 0; max-width: 13rem; padding: 5px 9px; border: 1px solid var(--hk-line); border-radius: var(--hk-radius-pill); background: var(--hk-surface); color: var(--hk-text); font: inherit; font-size: 0.86rem; }
.record__time { max-width: 8rem; text-align: center; font-variant-numeric: tabular-nums; }
.record__select { max-width: 13rem; padding: 5px 9px; border: 1px solid var(--hk-line); border-radius: var(--hk-radius-pill); background: var(--hk-surface); color: var(--hk-text); font: inherit; font-size: 0.82rem; font-weight: 600; }
.record__select:focus-visible { outline: 2px solid var(--hk-accent); outline-offset: 1px; }
.water__input { width: 5rem; padding: 5px 9px; border: 1px solid var(--hk-line); border-radius: var(--hk-radius-pill); background: var(--hk-surface); color: var(--hk-text); font: inherit; font-size: 0.86rem; font-weight: 600; text-align: right; }
.water__input:focus-visible { outline: 2px solid var(--hk-accent); outline-offset: 1px; }
.water__unit { font-size: 0.8rem; color: var(--hk-text-dim); }
/* A row with no date beside it. The grid above reserves 58px for the tear-off date, so a
   row that has none puts its whole body in that column and wraps every word onto its own
   line, which is what Tracking looked like. */
.action--static { grid-template-columns: 1fr; cursor: default; }
.rate { display: flex; flex-direction: column; gap: 8px; }
.rate__row, .issues__row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.rate__lawn { display: inline-flex; align-items: center; gap: 7px; min-width: 0; }
.rate__name { font-weight: 600; font-size: 0.9rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
/* In a summary row the chips sit at the right, after the lawn's name. In a dialog they are
   the answer to the question above them, so they start where the question starts: sharing one
   class made the short row of ratings drift right while the long row of issues filled and
   looked left. */
.rate__options { display: inline-flex; gap: 6px; margin-left: auto; flex-wrap: wrap; }
.dialog__choices { display: flex; gap: 6px; flex-wrap: wrap; }
.rate__btn { display: inline-flex; align-items: center; gap: 4px; padding: 5px 11px; border: 1px solid var(--hk-line); border-radius: var(--hk-radius-pill); background: var(--hk-surface); font-size: 0.8rem; font-weight: 600; color: var(--hk-text-dim); }
.rate__btn:hover { border-color: var(--hk-text-dim); color: var(--hk-text); }
.rate__btn[aria-pressed="true"][data-tone="reserve"] { border-color: transparent; background: color-mix(in srgb, var(--hk-reserve) 20%, transparent); color: color-mix(in srgb, var(--hk-reserve) 85%, var(--hk-text)); }
.rate__btn[aria-pressed="true"][data-tone="warn"] { border-color: transparent; background: color-mix(in srgb, var(--hk-warn) 22%, transparent); color: color-mix(in srgb, var(--hk-warn) 85%, var(--hk-text)); }
.rate__btn[aria-pressed="true"][data-tone="error"] { border-color: transparent; background: color-mix(in srgb, var(--hk-error) 20%, transparent); color: color-mix(in srgb, var(--hk-error) 85%, var(--hk-text)); }
@media (max-width: 560px) {
  .rate__options { margin-left: 0; width: 100%; }
  .rate__btn { flex: 1 1 auto; justify-content: center; }
}
.confirm { display: inline-flex; align-items: center; gap: 5px; padding: 4px 10px; border: 1px solid var(--hk-line); border-radius: 999px; background: var(--hk-surface); color: var(--hk-text-dim); font: inherit; font-size: 0.78rem; font-weight: 600; cursor: pointer; }
.confirm:hover { border-color: var(--hk-reserve); color: var(--hk-reserve); }
.confirm--compact { padding: 4px; }
.action__detail { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap; font-size: 0.82rem; color: var(--hk-text-dim); }
.action__clock { font-size: 0.95rem; font-weight: 700; color: var(--hk-text); font-variant-numeric: tabular-nums; }
.action__how { font-size: 0.9rem; line-height: 1.45; }

/* One event, in full */
.events { display: flex; flex-direction: column; gap: 10px; }
.event { display: grid; grid-template-columns: 4px 1fr; gap: 14px; background: var(--hk-surface); border: 1px solid var(--hk-line); border-radius: var(--hk-radius); overflow: hidden; }
.event__rail { background: var(--evt-tone, var(--hk-tone-general)); }
.event[data-category="irrigation"] { --evt-tone: var(--hk-tone-irrigation); }
.event[data-category="mowing"] { --evt-tone: var(--hk-tone-mowing); }
.event[data-category="fertilizing"] { --evt-tone: var(--hk-tone-fertilizing); }
.event[data-category="seeding"] { --evt-tone: var(--hk-tone-seeding); }
.event[data-category="weeds"] { --evt-tone: var(--hk-tone-weeds); }
.event[data-category="disease"] { --evt-tone: var(--hk-tone-disease); }
.event[data-category="aeration"] { --evt-tone: var(--hk-tone-aeration); }
.event__body { padding: 12px 14px 12px 0; min-width: 0; }
.event__head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.event__why { display: inline-flex; align-items: center; justify-content: center; width: 26px; height: 26px; border-radius: 50%; color: var(--hk-text-dim); }
.event__why:hover { background: color-mix(in srgb, currentColor 14%, transparent); }
.event__why .icon { transition: transform 160ms var(--hk-ease); }
.event__why[aria-expanded="true"] .icon { transform: rotate(180deg); }
.event__why-panel { margin: 10px 0 0; padding: 10px 12px; border-radius: var(--hk-radius-sm); background: color-mix(in srgb, var(--evt-tone, var(--hk-tone-general)) 7%, var(--hk-surface-sunken)); }
.event__why-panel[hidden] { display: none; }
.event__why-title { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--hk-text-dim); margin-bottom: 6px; }
.event__reasons { display: flex; flex-wrap: wrap; gap: 6px; }
.reason { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: var(--hk-radius-pill); font-size: 0.8rem; line-height: 1.35;
  background: var(--hk-surface); border: 1px solid var(--hk-line); color: var(--hk-text); }
.reason::before { content: ""; width: 5px; height: 5px; border-radius: 50%; background: var(--evt-tone, var(--hk-tone-general)); flex: 0 0 auto; }
.event__footer { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 12px; padding-top: 10px; border-top: 1px solid var(--hk-line); }
.event__footer-label { font-size: 0.7rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.07em; color: var(--hk-text-dim); }
.event__footer-zones { display: flex; gap: 6px; flex-wrap: wrap; }
.event__title { font-weight: 600; }
.event__time { font-size: 0.84rem; color: var(--hk-text-dim); }
.event__detail { font-size: 0.84rem; color: var(--hk-text-dim); margin-top: 3px; }
.event__how { margin: 8px 0 0; font-size: 0.92rem; line-height: 1.5; }
.event--logged { opacity: 0.82; }
.event--logged .event__title { font-weight: 500; }
.badge--logged { border-color: transparent; background: color-mix(in srgb, var(--hk-ok) 16%, transparent); color: color-mix(in srgb, var(--hk-ok) 80%, var(--hk-text)); }
.badge--noted { border-color: var(--hk-line); color: var(--hk-text-dim); }
.pill--noted { background: transparent; border: 1px solid var(--hk-line); color: var(--hk-text-dim); font-weight: 500; }
.event--noted { opacity: 0.9; }
.event--noted .event__title { font-weight: 500; }
.badge--projected { border-color: transparent; background: color-mix(in srgb, var(--hk-accent) 16%, transparent); color: color-mix(in srgb, var(--hk-accent) 85%, var(--hk-text)); }
.badge--alert { border-color: transparent; background: color-mix(in srgb, var(--hk-error) 16%, transparent); color: color-mix(in srgb, var(--hk-error) 85%, var(--hk-text)); }
.trend { display: flex; flex-direction: column; gap: 14px; }

/* Diary rows */
.rows { background: var(--hk-surface); border: 1px solid var(--hk-line); border-radius: var(--hk-radius); padding: 0 14px; }
.rows__row { display: flex; align-items: center; gap: 10px; padding: 9px 0; border-bottom: 1px solid var(--hk-line); font-size: 0.88rem; }
.rows__row:last-child { border-bottom: 0; }
.rows__row--dim { color: var(--hk-text-dim); }
.rows__date { min-width: 84px; }
.rows__num { min-width: 64px; font-variant-numeric: tabular-nums; }

/* Stat tiles */
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 10px; }
.stat { padding: 12px 14px; border-radius: var(--hk-radius-sm); background: var(--hk-surface); border: 1px solid var(--hk-line); }
.stat__label { font-size: 0.74rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--hk-text-dim); }
.stat__value { font-size: 1.35rem; font-weight: 600; font-variant-numeric: tabular-nums; line-height: 1.2; margin-top: 2px; }
.stat__value small { font-size: 0.8rem; font-weight: 500; color: var(--hk-text-dim); margin-left: 3px; }
.stat__note { font-size: 0.78rem; color: var(--hk-text-dim); margin-top: 2px; }

/* Charts */
.chart { width: 100%; height: auto; display: block; overflow: visible; }
.chart__label { font-size: 0.78rem; font-weight: 600; color: var(--hk-text-dim); margin-bottom: 4px; }
.chart text { font-size: 10px; fill: var(--hk-text-dim); font-family: inherit; }
.chart .grid line { stroke: var(--hk-line); stroke-dasharray: 2 3; }

.legend { display: flex; gap: 14px; flex-wrap: wrap; font-size: 0.78rem; color: var(--hk-text-dim); margin-top: 6px; }
.legend__item { display: inline-flex; align-items: center; gap: 5px; }
.legend__swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; }
`;

export const SHARED = TOKENS + BASE;
