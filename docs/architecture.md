# Hosekeeper — architecture

Hosekeeper is a Home Assistant custom integration that keeps a lawn diary per zone, computes a
daily water balance from weather and irrigation, and turns the diary plus a turf-management
knowledge base into concrete advice. Everything the panel shows is also a sensor, so plain
automations can use it.

## Layers

```
config entry (a lawn)
  └── subentry (a zone) ─► FieldConfig ─► Coordinator ─► entities (sensor/calendar)
                                  │  ▲
                                  ▼  │
                          Diary (Store, one file per zone)
                                  │
                       engine/ (ET₀, water balance, phenology, rules, adaptation)
                                  │
                       websocket API ─► sidebar panel (frontend/, no build step)
```

### Config entries — one per lawn, one subentry per zone

A lawn is the turf as a whole; a zone is a part of it with its own valve. What the whole lawn
shares is asked once, when the integration is added:

| Step | Data |
| --- | --- |
| `lawn` | name, latitude/longitude (defaults to the home zone), soil type, grass type, how the lawn was established (sod rolls, seed, hydroseed) and when |
| `irrigation` | irrigation system type, flow rate (L/min) or precipitation rate (mm/h) |
| `sources` | weather entity (required), optional observed sensors: rain total, temperature, humidity, wind, solar radiation, soil moisture; optional robot mower entity and the cutting heights its deck can be set to |

`Add zone` on the lawn's card then asks what is particular to each part of it:

| Step | Data |
| --- | --- |
| `zone` | name, area (m²), sun exposure, optional valve or switch entity |
| `features` | up to three shading features (deciduous tree, evergreen tree, structure) with the share of the zone each shades |

A `FieldConfig` — everything the engine needs about one piece of grass — is built by laying a
zone's answers over its lawn's, so a zone can only ever add to what the lawn said. Both flows
reconfigure: re-opening the lawn re-opens its three steps, a zone its two. Changing the sources
or the irrigation setup reloads the entry; the diaries are untouched.

### Diary — `Store` per entry

`homeassistant.helpers.storage.Store`, one per zone, key `hosekeeper.<zone_id>`, version 1:

```json
{
  "days": {
    "2026-09-06": {
      "irrigation_min": 20, "irrigation_mm": 5.4, "irrigation_source": "manual|valve",
      "rain_mm": 0.0, "et0_mm": 5.1, "tmax": 33.7, "tmin": 24.8, "rs_mj": 22.4,
      "status": "good", "issues": ["weeds"],
      "maintenance": [{"type": "mowing", "at": "2026-09-06T08:10:00+02:00", "height_mm": 45}],
      "deficit_mm": 12.3
    }
  },
  "adaptation": {"irrigation_factor": 1.0, "fertilizer_interval_factor": 1.0, "history": []}
}
```

Recorder history is not relied on: it is purged after ten days by default and the analysis
needs seasons. Only today is writable from the entities and the panel.

### Coordinator

A `DataUpdateCoordinator` per zone, refreshed every hour and at every change of a linked
source entity. Each refresh:

1. Reads observed weather (sensors first, weather-entity attributes as fallback) and the daily
   and hourly forecast via `weather.get_forecasts`.
2. Computes today's ET₀: FAO-56 Penman-Monteith when solar radiation, humidity and wind are
   available, Hargreaves-Samani from temperature only otherwise. ETc = ET₀ × Kc, with Kc by
   grass type and season.
3. Accumulates rain (daily-reset `total_increasing` sensors are handled by tracking the last
   seen value and its day), valve on-time and mower sessions into the diary.
4. Rolls the soil water balance: `deficit = clamp(deficit + ETc − effective_rain − irrigation, 0, TAW)`
   where total available water TAW comes from soil type and root depth.
5. Runs the rules engine and the adaptation step, then publishes the result to the entities.

Mower sessions: a `lawn_mower` entity leaving `docked` for `mowing` and returning logs one
mowing event with the duration.

### Engine — pure Python, no Home Assistant imports

`engine/` is a plain package so it can be tested with numbers alone and reused by the panel
through the websocket API.

- `et.py` — FAO-56 and Hargreaves ET₀, extraterrestrial radiation, Kc tables.
- `water.py` — soil parameters, effective rainfall, deficit bookkeeping, irrigation
  minutes ⇄ millimetres through the zone's precipitation rate.
- `phenology.py` — climate zone from latitude and hemisphere, season phase, growing degree
  days, estimated soil temperature (a lagged air-temperature model), frost and heat stress flags.
- `knowledge/` — the turf knowledge base as data: grass profiles (Kc, mowing heights, nitrogen
  per season, optimal soil temperature for germination), the fertilizer catalog (generic types
  plus the Bottos range, with NPK and release period), the seasonal care calendar per climate
  zone, and the first-year programme for sod versus seed. Every entry cites its source in
  `docs/knowledge.md`.
- `climate.py` — the forecast-versus-actual loop. Every day the forecast that was issued for
  that day is kept next to what the sensors measured, so the engine learns the local bias of
  the forecast (rain over- or under-called, highs called too low under haze) and weights
  tomorrow's forecast accordingly. Rolling statistics of ET, rain and temperature against the
  field's own history flag anomalies — a heat wave, a dry spell, an early autumn — and advice
  is timed on them, not on the calendar alone.
- `nutrition.py` — which fertilizer, not only whether: the N-P-K class (starter 1-2-1, growth
  4-1-2, stress 2-1-3, autumn 1-0-1), the minimum slow-release share, whether to split the
  dose, the grams of nitrogen, and the closest preset with its dose. Shaped by the lawn's age
  and condition, the soil, the season phase, the disease models and the forecast highs.
The month's plan is decided once and kept in the diary, so the weather cannot reshuffle it
from one morning to the next; only the timing of its operations moves. It is built again when
the month turns, when the lawn or what has been reported about it changes, and whenever Home
Assistant loads the entry — a restart, a reload or an upgrade, which are the moments somebody
has changed something rather than the weather having moved.

- `outlook.py` — the month ahead: which programme windows (feeds, seeding, pre-emergent,
  aeration) are upcoming, open or done, so the panel's month view is a plan and not a list.
- `rules.py` — turns state into a ranked list of `Advice(code, priority, params, valid_until)`.
  Codes are stable identifiers (`irrigate_now`, `reduce_irrigation`, `mow_soon`,
  `fertilize_autumn_slow_release`, …) that the frontend and translations render.
- `adaptation.py` — the "past experience" loop. Bounded multipliers per zone move when the
  tracked status trends up or down after an advice was followed, with the reasoning kept in
  `adaptation.history` so the panel can show why.

### Entities per zone

| Platform | Entity | Purpose |
| --- | --- | --- |
| sensor | activity | what the lawn is busy with, as one enum an automation acts on, and the only entity it needs: `idle`, `irrigating_automatic`, `irrigating_manual`, `mowing_automatic`, `mowing_manual`, and one manual state per kind of work. `alerts` lists any standing warning, so what to do and what is wrong arrive together. Every state carries `zone`, `config_entry_id`, `target_entity_id` — the valve for watering, the mower for cutting, and null where no machine is involved, so one template covers every kind of work — and `target_entity_ids`, every machine the lawn has by the job it does, which answers "what has this zone got" when `target_entity_id` is null. A machine's run adds the time it ends, so a valve is held open exactly as long as this zone's cycle asks |
| sensor | lawn water use today (ET₀ and inputs as attributes), soil water deficit (available water as attributes), irrigation recommended (minutes, forecast rain and the adaptation factor as attributes), rain today (7-day, forecast and dry spell as attributes), irrigation today, days since mowing, nitrogen this year (60-day, days since fertilizing), next action (enum, full advice list as attribute), season phase (heat stress, degree days, frost), soil temperature, forecast rain reliability | the analysis, one entity per question an automation asks |
| calendar | the zone's calendar | what was logged, what the week projects and what the month plans, in Home Assistant's own calendar dashboard |

The panel's weather comes from three places and always says which: the diary for days that
have happened, `state.forecast_days` for the week the model covers, and `state.projection`
for the days past it, where the numbers are the season's rate with no rain assumed. The rain
shown for a future day is the forecast already discounted by this location's measured
forecast skill, because that is the number the watering decision was made on.

Sensors are kept to what a dashboard or an automation would read directly; every secondary
figure is an attribute of the sensor it explains, not an entity of its own.

The panel has five views: **Overview**, **Tracking**, **Day**, **Week**, **Month**. The first
four answer "what should I do"; Tracking answers the question going the other way, and is the
only place a person tells the engine something. It has three sections, in the order the work happens: the day's outstanding jobs with their
Done buttons, then how the lawn is, then work you did. Each states where every zone stands
before it offers its button, and the last two open a dialog. The recording dialog asks each
job for what it needs — a cut for its height, a feed for its product and rate, a sowing for
its mix — and a feed goes through the same builder as `hosekeeper.log_fertilizing`, because
the yearly nitrogen budget is summed from the grams that builder works out. It does not repeat what was already recorded:
the week and the month show that, with the plan around it.

**Recording what was done is not an entity.** There is no number, no select and no row of
buttons on the device page. A confirmation is only ever made about a job somebody is looking
at, so it lives in the panel, on the line that asked for the job, in the overview and the day
view, and in the Tracking tab. It writes through one websocket command, `hosekeeper/log`, which answers with the
zone's fresh snapshot so the panel redraws from truth rather than guessing what changed. The
services below stay for automations, which have the reverse need.

Services: `hosekeeper.log_irrigation`, `hosekeeper.log_maintenance` (type, fertilizer product,
amount, cut height, notes), `hosekeeper.log_issue` (issue tags). These carry the details the
buttons cannot. `hosekeeper.import_weather` enters one past day as it was measured, through
the same `engine/assess.observe()` that writes a live one, so a lawn set up in September can
be given the summer it lived through: applied oldest first the days rebuild the balance
between them, each carrying in the deficit the one before it left behind.

### Panel

`frontend/` follows reolink-stamina: ES modules, shadow DOM, HA theme variables, `ha-icon`
only, served under a content-fingerprinted static URL and registered with `panel_custom`.
`scripts/preview.py` serves the same modules against an invented lawn for local work.

The panel is a calendar for the lawn, over every zone at once. There is no zone switcher:
a filter narrows the calendar to one zone, and every event carries its zone's colour. While
that filter is on it is named beside the view tabs, with its colour and the way back to all of
them; with nothing filtered nothing is drawn, because there is nothing to undo.

- **Overview** — no dates to think about: one line per zone with the water left in the root
  zone, its next action and when it will be watered; today's alerts; the next actions in the
  order they fall due, each with what to do; and what has been logged today.
- **Day** — one day in full: every event with its time, its detail (product, dose, run time),
  what to do in a sentence, and why behind a toggle. The month's standing lines are left out
  of the day and the week: "mow every five days at 60 mm" is the reason Tuesday's cut is on
  the calendar, not a job to do on Tuesday, and anything actually due inside the week has been
  dated by the agenda already.
- **Week** — the seven days of the week as an agenda, each day's events as pills.
- **Month** — a month grid, a coloured dot per zone on each day and pills for what falls due,
  with the selected day opening in full below.

The numbers behind the calendar — rain, irrigation, water use, the deficit, nitrogen — are a
fold-out section rather than the first thing on the page. Language follows the frontend's,
Italian and English shipped.

## Repository layout

```
custom_components/hosekeeper/
  __init__.py  config_flow.py  const.py  coordinator.py  diary.py  services.py
  entity.py  events.py  field.py  sensor.py  calendar.py  websocket.py
  engine/  frontend/  strings.json  translations/{en,it}.json  services.yaml
docs/   tests/   scripts/   Makefile  pyproject.toml  hacs.json
```

## Phases

1. Skeleton, config and reconfigure flow, diary, translations. ✔
2. Coordinator, weather sources, ET₀ and water balance, sensors and inputs, valve and mower
   auto-logging. ✔
3. Knowledge base with sources, phenology, disease models, forecast-versus-actual skill,
   rules engine, adaptation, services, analysis sensors. ✔
4. Panel with day, week and month views, websocket API, `scripts/preview.py` (`make preview`). ✔
5. Diagnostics, README and docs, first beta. ← next
