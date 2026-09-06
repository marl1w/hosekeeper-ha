/**
 * Hosekeeper — a calendar for the lawn.
 *
 * Registered by the integration via panel_custom, so this runs inside the Home Assistant
 * frontend with the real `hass` object. Every lawn is on one calendar: what was done, what
 * this week projects, what the month plans. The panel reads; rating and logging go through
 * the entities and services, so automations and the panel use the same one way.
 */

import { adoptStyles, clear, el, frameDebounce, icon } from "./dom.js";
import { SHARED } from "./theme.js";
import { HosekeeperApi } from "./api.js";
import { fill, fmtDate, fmtMonth, pickLocale } from "./format.js";
import { pickLanguage, strings } from "./i18n.js";
import { renderNow } from "./views/now.js";
import { isoDay, parseDay, renderAgenda, renderMonthGrid, weekLabel } from "./views/calendar.js";
import { renderOverview } from "./views/overview.js";
import { renderTracking } from "./views/tracking.js";
import { zoneBadge } from "./views/events.js";
import { CATEGORY_ORDER, mergeEvents } from "./merge.js";
import { renderDayDetail } from "./views/day-detail.js";
import { renderTrend } from "./views/trend.js";

// Lawn colours, kept clear of the job colours in theme.js so a lawn is never read as a job.
const ZONE_COLOURS = ["#6c5ce7", "#00a3a3", "#d6336c", "#8b5e00", "#5f3dc4", "#0b7285"];
const CATEGORIES = CATEGORY_ORDER;

const STYLES = /* css */ `
:host { position: relative; display: flex; flex-direction: column; height: 100vh; height: 100dvh; background: var(--hk-bg); overflow: hidden; }
.app-header {
  display: flex; align-items: center; gap: 8px; padding: 0 8px 0 16px; height: var(--header-height, 56px); flex: 0 0 auto;
  background: var(--app-header-background-color, var(--hk-accent)); color: var(--app-header-text-color, #fff); box-shadow: var(--hk-shadow); z-index: 4;
}
.app-header__title { font-size: 1.15rem; font-weight: 500; margin-left: 8px; }
.menu-btn[hidden] { display: none; }
.app-header .icon-btn { color: inherit; }

.toolbar { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 10px 20px; background: var(--hk-surface); border-bottom: 1px solid var(--hk-line); flex: 0 0 auto; }
.nav { display: flex; align-items: center; gap: 2px; }
.nav .icon-btn { width: 34px; height: 34px; }

/*
 * The date control: arrows, the date, and Today, read as one thing.
 *
 * Its width is fixed. The label is a date in words, so it is "Fri 4 Sep" one day and
 * "Wednesday 16 September" the next, and a control sized by its contents moves its own
 * arrows out from under the finger that is pressing them. The label is given room for the
 * longest of them and centred in it; anything longer is cut rather than allowed to push.
 */
.datenav { display: inline-flex; align-items: center; gap: 2px; margin-left: auto; padding: 2px; border: 1px solid var(--hk-line); border-radius: var(--hk-radius-pill); background: var(--hk-surface); }
.datenav__arrow { display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 30px; flex: 0 0 auto; border-radius: 50%; color: var(--hk-text-dim); }
.datenav__arrow:hover { background: var(--hk-surface-sunken); color: var(--hk-text); }
.datenav__label { width: 14rem; flex: 0 0 auto; text-align: center; font-size: 0.92rem; font-weight: 600; text-transform: capitalize; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.datenav__divider { width: 1px; height: 18px; flex: 0 0 auto; margin: 0 4px; background: var(--hk-line); }
.datenav__today { flex: 0 0 auto; padding: 5px 12px; border-radius: var(--hk-radius-pill); font-size: 0.82rem; font-weight: 600; color: var(--hk-accent); }
.datenav__today:hover { background: color-mix(in srgb, var(--hk-accent) 12%, transparent); }
.segmented { display: inline-flex; background: var(--hk-surface-sunken); border-radius: var(--hk-radius-pill); padding: 2px; }
.segmented button { padding: 6px 14px; border-radius: var(--hk-radius-pill); font-size: 0.86rem; font-weight: 500; color: var(--hk-text-dim); }
.segmented button[aria-pressed="true"] { background: var(--hk-surface); color: var(--hk-text); box-shadow: var(--hk-shadow); }
.filters { display: flex; gap: 6px; flex-wrap: wrap; margin-left: auto; }
.filter { display: inline-flex; align-items: center; gap: 6px; padding: 5px 11px; border-radius: var(--hk-radius-pill); font-size: 0.8rem; font-weight: 600; border: 1px solid var(--hk-line); color: var(--hk-text-dim); }
.filter[aria-pressed="true"] { border-color: transparent; background: color-mix(in srgb, var(--hk-accent) 18%, transparent); color: color-mix(in srgb, var(--hk-accent) 88%, var(--hk-text)); }
.filter .icon { --mdc-icon-size: 15px; width: 15px; height: 15px; }

.content { flex: 1 1 auto; min-height: 0; overflow: auto; padding: 18px 20px; padding-bottom: calc(28px + var(--hk-safe-bottom)); }
.content > .page { max-width: 1040px; }
@media (max-width: 700px) {
  .app-header { height: 44px; padding-right: 4px; }
  .toolbar { padding: 8px 12px; gap: 8px; }
  .segmented { width: 100%; justify-content: space-between; }
  .segmented button { flex: 1 1 auto; padding: 6px 8px; text-align: center; }
  /* On a phone it takes the whole width instead, and the label takes what is left. */
  .datenav { margin-left: 0; width: 100%; }
  .datenav__label { width: auto; min-width: 0; flex: 1 1 auto; font-size: 0.88rem; }
  .content { padding: 12px; }
}
`;

class HosekeeperPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    adoptStyles(this.shadowRoot, SHARED + STYLES);
    this._hass = null;
    this._api = null;
    this._fields = [];
    this._snapshots = new Map();
    this._stamps = new Map();
    this._built = false;
    this._render = frameDebounce(() => this._doRender());
    const today = isoDay(new Date());
    this._selected = today;
    this._anchor = today;
    this._mode = this._restore("mode", "overview");
    this._zone = this._restore("zone", null);
  }

  _restore(key, fallback) {
    try {
      const value = localStorage.getItem(`hosekeeper.${key}`);
      return value === null ? fallback : value;
    } catch {
      return fallback;
    }
  }

  _remember(key, value) {
    try {
      if (value === null) localStorage.removeItem(`hosekeeper.${key}`);
      else localStorage.setItem(`hosekeeper.${key}`, value);
    } catch {
      /* private windows have no storage; the panel works without it */
    }
  }

  set hass(hass) {
    const first = this._hass === null;
    this._hass = hass;
    this._api = new HosekeeperApi(hass);
    if (first) this._loadAll();
    else this._maybeRefresh();
    this._render();
  }

  get hass() {
    return this._hass;
  }

  set narrow(value) {
    this._narrow = value;
    this._render();
  }

  set panel(_value) {
    /* unused */
  }

  connectedCallback() {
    this._build();
    this._render();
  }

  _build() {
    if (this._built) return;
    this._built = true;
    this._menuBtn = el("button", { class: "icon-btn menu-btn", onClick: () => this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true })) }, icon("mdi:menu"));
    this._header = el(
      "header",
      { class: "app-header" },
      this._menuBtn,
      el("div", { class: "app-header__title" }, "Hosekeeper"),
      el("div", { class: "spacer" }),
      el("button", { class: "icon-btn", onClick: () => this._loadAll() }, icon("mdi:refresh"))
    );
    this._toolbar = el("div", { class: "toolbar" });
    this._content = el("main", { class: "content" });
    // Dialogs live here, outside the scrolling column. Inside it they were positioned
    // against the whole scroll height, so they opened halfway down the page and ran off the
    // bottom of the window.
    this._layer = el("div", { class: "layer" });
    this.shadowRoot.append(this._header, this._toolbar, this._content, this._layer);
  }

  // ------------------------------------------------------------------ data

  async _loadAll() {
    try {
      this._fields = await this._api.fields();
    } catch (err) {
      console.error("hosekeeper: fields", err);
      this._fields = [];
    }
    await Promise.all(this._fields.map((f) => this._loadField(f.entry_id)));
    this._render();
  }

  async _loadField(entryId) {
    try {
      const snapshot = await this._api.field(entryId);
      this._snapshots.set(entryId, snapshot);
      this._stamps.set(entryId, this._stamp(snapshot));
    } catch (err) {
      console.error("hosekeeper: field", entryId, err);
    }
  }

  /** The next-action sensor's last_updated is the cheapest tell that a field was recomputed. */
  _stamp(snapshot) {
    if (!this._hass || !snapshot) return null;
    const slug = (snapshot.field?.name || "").toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
    const id = Object.keys(this._hass.states).find((k) => k.startsWith("sensor.") && k.includes(slug) && /next_action|prossimo_intervento/.test(k));
    return id ? this._hass.states[id].last_updated : null;
  }

  _maybeRefresh() {
    for (const [entryId, snapshot] of this._snapshots) {
      const stamp = this._stamp(snapshot);
      if (stamp && stamp !== this._stamps.get(entryId)) {
        this._stamps.set(entryId, stamp);
        this._loadField(entryId).then(() => this._render());
      }
    }
  }

  // ------------------------------------------------------------------ derived

  _visibleSnapshots() {
    const all = this._fields.map((f) => this._snapshots.get(f.entry_id)).filter(Boolean);
    return this._zone ? all.filter((s) => s.entry_id === this._zone) : all;
  }

  _eventsByDay() {
    return mergeEvents(this._visibleSnapshots());
  }

  _zoneColour = (entryId) => {
    const index = this._fields.findIndex((f) => f.entry_id === entryId);
    return ZONE_COLOURS[(index < 0 ? 0 : index) % ZONE_COLOURS.length];
  };

  _snapshotFor = (event) => this._snapshots.get(event.entry_id);

  _zoneName = (entryId) => this._fields.find((f) => f.entry_id === entryId)?.name || "";

  // ------------------------------------------------------------------ actions

  _shift(step) {
    const anchor = parseDay(this._anchor);
    if (this._mode === "month") anchor.setMonth(anchor.getMonth() + step);
    else if (this._mode === "week") anchor.setDate(anchor.getDate() + step * 7);
    else anchor.setDate(anchor.getDate() + step);
    this._anchor = isoDay(anchor);
    if (this._mode === "day") this._selected = this._anchor;
    this._render();
  }

  _goToday() {
    this._anchor = isoDay(new Date());
    this._selected = this._anchor;
    this._render();
  }

  _setMode(mode) {
    this._mode = mode;
    this._remember("mode", mode);
    if (mode === "day") this._anchor = this._selected;
    this._render();
  }

  /**
   * Record that a job was done, on the lawns it applies to.
   *
   * A job shown once for three lawns is confirmed once for three lawns: the row already
   * says which, so asking again would be asking the reader to repeat what they can see.
   */
  _confirm = async (event, payload) => {
    const zones = event.zones || [event.entry_id];
    for (const entryId of zones) {
      try {
        const snapshot = await this._api.log(entryId, payload);
        this._snapshots.set(entryId, snapshot);
        this._stamps.set(entryId, this._stamp(snapshot));
      } catch (err) {
        console.error("hosekeeper: log", entryId, err);
      }
    }
    this._render();
  };

  /** Record how a lawn looks today. */
  _rate = (entryId, status) => this._confirm({ entry_id: entryId }, { what: "status", status });

  /** Report something seen on a lawn. */
  _issue = (entryId, issue) => this._confirm({ entry_id: entryId }, { what: "issue", issue });

  /** Set how many minutes a lawn was watered for today. */
  _water = (entryId, minutes, at) =>
    this._confirm({ entry_id: entryId }, { what: "irrigation", minutes, at });

  /** Record a job nothing asked for. */
  _record = (entryId, kind, details, at) =>
    this._confirm({ entry_id: entryId }, { what: "maintenance", kind, details, at });

  /** Record a feed. The integration works the nitrogen out from the product and the rate. */
  _feed = (entryId, product, dose, at) =>
    this._confirm({ entry_id: entryId }, { what: "fertilizing", product, dose_g_m2: dose, at });

  _selectZone(entryId) {
    this._zone = entryId;
    this._remember("zone", entryId);
    this._render();
  }

  // ------------------------------------------------------------------ render

  _label(locale) {
    if (this._mode === "month") return fmtMonth(this._anchor.slice(0, 7), locale);
    if (this._mode === "week") return weekLabel(this._anchor, locale);
    return new Intl.DateTimeFormat(locale, { weekday: "long", day: "numeric", month: "long" }).format(parseDay(this._anchor));
  }

  _renderToolbar(lang, locale) {
    const s = strings(lang);
    clear(this._toolbar);
    const dated = this._mode !== "overview" && this._mode !== "tracking";
    const zone = this._zone ? this._fields.find((f) => f.entry_id === this._zone) : null;
    const parts = [
      el(
        "div",
        { class: "segmented" },
        ...[
          ["overview", s.ui.overview],
          ["tracking", s.ui.tracking],
          ["day", s.ui.day],
          ["week", s.ui.week],
          ["month", s.ui.monthGrid],
        ].map(([mode, label]) =>
          el("button", { "aria-pressed": this._mode === mode ? "true" : "false", onClick: () => this._setMode(mode) }, label)
        )
      ),
    ];
    if (dated) {
      // The arrows, the date and Today read as one control rather than three loose ones.
      parts.push(
        el(
          "div",
          { class: "datenav" },
          el("button", { class: "datenav__arrow", "aria-label": s.ui.previous, onClick: () => this._shift(-1) }, icon("mdi:chevron-left", "icon--sm")),
          el("span", { class: "datenav__label" }, this._label(locale)),
          el("button", { class: "datenav__arrow", "aria-label": s.ui.next, onClick: () => this._shift(1) }, icon("mdi:chevron-right", "icon--sm")),
          el("span", { class: "datenav__divider" }),
          el("button", { class: "datenav__today", onClick: () => this._goToday() }, s.ui.today)
        )
      );
    }
    this._toolbar.append(...parts);
  }

  _doRender() {
    if (!this._built || !this._hass) return;
    const lang = pickLanguage(this._hass);
    const locale = pickLocale(this._hass, lang);
    const s = strings(lang);
    this._menuBtn.hidden = !this._narrow;
    this._renderToolbar(lang, locale);

    clear(this._content);
    clear(this._layer);
    if (!this._fields.length) {
      this._content.append(el("div", { class: "empty" }, icon("mdi:grass"), el("div", { class: "empty__title" }, s.ui.noFields), el("div", { class: "empty__body" }, s.ui.noFieldsBody)));
      return;
    }
    const snapshots = this._visibleSnapshots();
    if (!snapshots.length) {
      this._content.append(el("div", { class: "empty" }, el("div", { class: "empty__body" }, s.ui.loading)));
      return;
    }
    const byDay = this._eventsByDay();
    const today = isoDay(new Date());
    const multiZone = this._fields.length > 1 && this._zone === null;
    const shared = {
      lang,
      locale,
      zoneColour: this._zoneColour,
      zoneName: this._zoneName,
      snapshotFor: this._snapshotFor,
      multiZone,
      todayIso: today,
      // Any one lawn, read only for the weather: the property shares a sky.
      snapshot: snapshots[0],
      snapshots,
      onConfirm: this._confirm,
      onSelectDay: (iso) => {
        this._selected = iso;
        if (this._mode === "agenda") this._anchor = iso;
        this._render();
      },
    };

    // The glance follows the day on screen. A dry spell reported as it stands today, above
    // a calendar showing next week, describes a different day from everything under it.
    const shownDay = this._mode === "day" ? this._anchor : this._selected;
    const glance = el(
      "section",
      { class: "section enter" },
      el(
        "div",
        { class: "section__label" },
        icon("mdi:eye-outline"),
        s.ui.atAGlance,
        shownDay === today
          ? null
          : el(
              "span",
              { class: "section__label-note" },
              fill(s.ui.atThisDay, { date: fmtDate(shownDay, locale, { day: "numeric", month: "short" }) }, locale)
            )
      ),
      renderNow(this._fields.map((f) => this._snapshots.get(f.entry_id)).filter(Boolean), {
        lang,
        locale,
        zoneColour: this._zoneColour,
        zoneName: this._zoneName,
        selectedZone: this._zone,
        onSelectZone: (id) => this._selectZone(id),
        dateIso: shownDay,
        todayIso: today,
        eventsByDay: byDay,
      })
    );

    const trendSection = el(
      "section",
      { class: "section" },
      el("div", { class: "section__label" }, icon("mdi:chart-timeline-variant"), s.ui.trend),
      el("div", { class: "section__hint" }, s.ui.soilWaterHint),
      renderTrend(snapshots, {
        lang,
        locale,
        zoneColour: this._zoneColour,
        zoneName: this._zoneName,
        pastDays: { day: 7, week: 14, month: 31 }[this._mode] ?? 21,
      })
    );

    if (this._mode === "overview") {
      this._content.append(
        renderOverview(this._fields.map((f) => this._snapshots.get(f.entry_id)).filter(Boolean), snapshots, byDay, {
          ...shared,
          todayIso: today,
          selectedZone: this._zone,
          onSelectZone: (id) => this._selectZone(id),
          onOpenDay: (iso) => {
            this._selected = iso;
            this._anchor = iso;
            this._setMode("day");
          },
        })
      );
      return;
    }

    if (this._mode === "tracking") {
      const tracking = renderTracking(snapshots, {
        ...shared,
        todayIso: today,
        byDay,
        issues: snapshots[0]?.issues || [],
        kinds: snapshots[0]?.maintenance_kinds || [],
        onRate: this._rate,
        onIssue: this._issue,
        onWater: this._water,
        onRecord: this._record,
        onFeed: this._feed,
      });
      this._content.append(tracking);
      this._layer.append(...(tracking.dialogs || []));
      return;
    }

    const calendar =
      this._mode === "month"
        ? renderMonthGrid(byDay, this._anchor, this._selected, today, shared)
        : this._mode === "week"
          ? renderAgenda(byDay, this._anchor, this._selected, today, shared)
          : null;

    this._content.append(
      el(
        "div",
        { class: "page" },
        // The glance is about one day, so it belongs on the day. Above a week or a month it
        // was answering a question the view was not asking.
        this._mode === "day" ? glance : null,
        calendar ? el("section", { class: "section enter" }, calendar) : null,
        renderDayDetail(this._mode === "day" ? this._anchor : this._selected, byDay.get(this._mode === "day" ? this._anchor : this._selected) || [], shared),
        trendSection
      )
    );
  }
}

if (!customElements.get("hosekeeper-panel")) customElements.define("hosekeeper-panel", HosekeeperPanel);
