# Hosekeeper

*A lawn diary that knows what your grass needs.*

Hosekeeper is a Home Assistant custom integration for looking after a lawn, zone by zone. Each
zone keeps its own diary of irrigation, rain, mowing, fertilizing and how the grass looked;
Hosekeeper turns that, the weather and turf-management research into a daily water balance,
a seasonal plan and concrete advice — irrigate 25 minutes tonight, mow this week, autumn
slow-release feed due — all exposed as sensors so automations can act on them.

A **Hosekeeper** sidebar panel shows each zone by day (what to do now, the water balance,
the dawn irrigation plan, quick logging), by week (the last seven days against the forecast)
and by month (the plan, what was done, and what the lawn has taught the engine). Advice is
anchored to a monthly programme built from turf research and the calendar an Italian
professional gardener runs, then tailored with your lawn's own data. Sources are listed in
[docs/knowledge.md](docs/knowledge.md); the design in [docs/architecture.md](docs/architecture.md).

Work in progress, not yet released.

## Requirements

- Home Assistant 2026.6 or newer
- A `weather` entity with daily forecasts (Met.no, the default, is enough)
- Optional: a weather station with rain, temperature, humidity, wind and solar radiation
  sensors (Weathercloud is the tested one), an irrigation valve or switch, a robot mower

## Install

1. HACS → **⋮** → **Custom repositories** → add this repository, category **Integration**.
2. Install **Hosekeeper**, then restart Home Assistant.
3. **Settings → Devices & services → Add integration → Hosekeeper**: the lawn once, then
   **Add zone** for each part of it that waters or grows differently.

## Contributing

```bash
make          # what there is to run
make setup    # once
make check    # lint, format, translations, tests, frontend
make preview  # the panel in a browser, no Home Assistant needed
```

## Licence

[MIT](LICENSE)
