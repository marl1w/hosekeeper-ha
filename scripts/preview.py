"""Serve the real panel against an invented lawn, no Home Assistant needed.

    make preview                # http://127.0.0.1:8123
    make preview SEED=7 LOCALE=it # another household, in Italian

The page defines a fake `hass` — language, a few states, `callWS` answering from a snapshot
this script builds, a `callService` that only logs — and loads the panel
module exactly as Home Assistant would. The snapshot is not hand-written: the diary is
invented, but the advice, the plan and the nutrition come from the real engine, so what you
see is what those numbers would produce in Home Assistant.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import random
import sys
from types import SimpleNamespace
from typing import Any, ClassVar

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from weather import (  # noqa: E402
    believable_sun,
    believable_wind,
    from_file,
    from_open_meteo,
    from_statistics,
)

from custom_components.hosekeeper.const import ISSUES, MAINTENANCE_KINDS  # noqa: E402
from custom_components.hosekeeper.engine import (  # noqa: E402
    activity,
    agenda,
    assess,
    et,
    phenology,
    schedule,
    water,
)
from custom_components.hosekeeper.engine.knowledge import fertilizers, grass  # noqa: E402
from custom_components.hosekeeper.events import build as build_events  # noqa: E402

FRONTEND = ROOT / "custom_components" / "hosekeeper" / "frontend"


def invent(
    seed: int,
    today: dt.date,
    name: str = "South lawn",
    zone_id: str = "preview",
    zone: dict[str, Any] | None = None,
    weather: dict[str, dict[dt.date, float]] | None = None,
    lawn: dict[str, Any] | None = None,
    thirsty: bool = False,
    chain: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a snapshot in the websocket shape.

    With no `weather` the days are invented; given a real station's statistics they are that
    station's own days, so the preview shows the lawn as it actually was.
    """
    rng = random.Random(seed)

    def sky(day: dt.date) -> random.Random:
        """Return the generator for that day's weather, shared by every zone of the lawn.

        Two lawns twenty metres apart cannot be given different rain, and they were: each
        drew from its own generator, so the same afternoon was forecast wet on one and dry
        on the next.
        """
        return random.Random(int(day.strftime("%Y%m%d")))

    zone = zone or {}
    lawn = lawn or {}
    name = zone.get("name", name)
    zone_id = zone.get("zone_id", zone_id)

    def answer(key: str, default: Any = None) -> Any:
        """Read one answer the way the integration does: the zone's, else the lawn's.

        The soil, the grass and how the turf was made belong to the lawn; the area, the
        aspect and the valve to the zone. A sample that puts one of the lawn's answers on a
        zone still works, because that is exactly the override the config flow allows.
        """
        return zone.get(key, lawn.get(key, default))

    field = {
        "name": name,
        "area_m2": float(zone.get("area_m2", 120.0 if zone_id == "preview" else 80.0)),
        "latitude": float(lawn.get("latitude", 45.0)),
        "longitude": float(lawn.get("longitude", 9.0)),
        "exposure": zone.get("exposure", "full_sun"),
        "soil_type": answer("soil_type", "loam"),
        "grass_type": answer("grass_type", "tall_fescue"),
        "establishment_method": answer("establishment_method", "sod"),
        "establishment_date": answer("establishment_date", "2025-04-12"),
        "irrigation_type": answer("irrigation_type", "pop_up_spray"),
        "flow_l_min": None,
        "precipitation_rate_mm_h": float(answer("precipitation_rate_mm_h", 15.0)),
        "valve_entity": zone.get("valve_entity", "switch.lawn_valve"),
        "mower_entity": answer("mower_entity"),
        "weather_entity": "weather.forecast_home",
        "features": [] if zone else [{"kind": "deciduous_tree", "shade_pct": 20.0}],
        "shaded_fraction": 0.0 if zone else 0.2,
        "application_rate_mm_h": float(answer("precipitation_rate_mm_h", 15.0)),
    }
    days: list[dict[str, Any]] = []
    deficit = 8.0
    temps: list[phenology.DayTemps] = []
    laid = (
        dt.date.fromisoformat(field["establishment_date"]) if field["establishment_date"] else None
    )
    rate = field["application_rate_mm_h"]
    minutes_per_day = float(zone.get("minutes_per_day", 0))
    for offset in range(39, -1, -1):
        date = today - dt.timedelta(days=offset)
        doy = date.timetuple().tm_yday
        ra = et.extraterrestrial_radiation(field["latitude"], doy)
        if weather and date in weather["tmax"] and date in weather["tmin"]:
            tmax, tmin = weather["tmax"][date], weather["tmin"][date]
            rh = weather["rh"].get(date, 60.0)
            # Already in the units the equations want: weather.py normalises both sources,
            # wind to metres a second at two metres and radiation to megajoules over the day.
            # Converting again here put the wind under the anemometer-in-the-lee threshold and
            # the radiation under the trust threshold, so every measured day quietly fell back
            # to the defaults -- which is the one thing --open-meteo exists not to do.
            u2 = believable_wind(weather["wind"].get(date))
            rs = believable_sun(
                weather["solar"].get(date),
                et.solar_radiation_from_temperature(tmax, tmin, ra),
            )
            rain = weather["rain"].get(date, 0.0)
        else:
            weather_rng = sky(date)
            season = (1 - math.cos(2 * math.pi * (doy - 15) / 365)) / 2
            tmax = 6 + 24 * season + weather_rng.uniform(-3, 3)
            tmin = tmax - weather_rng.uniform(8, 13)
            rain = 0.0
            if weather_rng.random() < (0.16 if 5 <= date.month <= 8 else 0.24):
                rain = weather_rng.choice([2, 4, 8, 14, 26]) * weather_rng.uniform(0.7, 1.2)
            if thirsty and offset < 7:
                rain = 0.0
            rh = weather_rng.uniform(45, 85) if rain == 0 else weather_rng.uniform(75, 95)
            u2 = weather_rng.uniform(0.5, 2.5)
            rs = et.solar_radiation_from_temperature(tmax, tmin, ra)
            irrigation = 0.0
        weather_day = et.WeatherDay(tmax, tmin, rh_mean=rh, wind_2m_ms=u2, rs_mj=rs)
        et0, _ = et.reference_et0(
            weather_day,
            latitude_deg=field["latitude"],
            elevation_m=float(lawn.get("elevation", 280)),
            day_of_year=doy,
        )
        kc = grass.crop_coefficient(field["grass_type"], date.month) * (
            1 - 0.35 * field["shaded_fraction"]
        )
        etc = et0 * kc
        age = (date - laid).days if laid else None
        depth = grass.root_depth(field["grass_type"], age, field["establishment_method"])
        soil = water.soil_water(
            field["soil_type"],
            depth,
            water.allowed_depletion(young=age is not None and age < water.YOUNG_LAWN_DAYS),
        )
        # A timer that runs every morning has already run this morning, so the routine is
        # applied to every day the diary covers, today included.
        irrigation = 0.0
        if minutes_per_day:
            irrigation = round(minutes_per_day / 60 * rate, 1)
        elif not weather and deficit + etc > soil.raw_mm and rain < 2 and offset > 0:
            # One lawn is left dry for the last week, so a watering plan is visible at all.
            irrigation = 0.0 if (thirsty and offset < 7) else round(deficit + etc, 1)
        deficit = water.next_deficit(deficit, etc, rain, irrigation, soil)
        temps.append(phenology.DayTemps(date, tmax, tmin))
        record: dict[str, Any] = {
            "date": date.isoformat(),
            "tmax": round(tmax, 1),
            "tmin": round(tmin, 1),
            "rh_mean": round(rh, 1),
            "et0_mm": round(et0, 2),
            "etc_mm": round(etc, 2),
            "kc": round(kc, 3),
            "rain_mm": round(rain, 1),
            "rain_source": "sensor",
            "irrigation_mm": irrigation,
            "irrigation_min": round(irrigation / rate * 60) if irrigation and rate else 0,
            "deficit_mm": round(deficit, 1),
            "maintenance": [],
            "forecast": {
                "tmax": round(tmax - 2 + sky(date).uniform(-1, 1), 1),
                "tmin": round(tmin, 1),
                "rain": round(rain * sky(date).choice([0, 0.5, 1, 1.5]), 1),
            },
        }
        mown_on = set(zone.get("mown_on", []))
        if date.isoformat() in mown_on or (not mown_on and offset % 6 == 0):
            record["maintenance"].append(
                {
                    "type": "mowing",
                    "at": f"{date.isoformat()}T16:30:00+02:00",
                    "source": "mower",
                    "details": {"height_mm": zone.get("mow_height_mm")},
                }
            )
        if zone.get("sown_on") == date.isoformat():
            record["maintenance"].append(
                {
                    "type": "sowing",
                    "at": f"{date.isoformat()}T10:00:00+02:00",
                    "source": "manual",
                    "details": {"kind": "overseed"},
                }
            )
        if offset in (33, 5):
            record["status"] = rng.choice(["good", "fair", "good", "excellent"])
        if offset == 20 and not weather:
            record["issues"] = ["bare_spots"]
        days.append(record)

    last = days[-1]

    # From here on nothing is worked out here. The engine is handed the lawn and its diary
    # and gives back the same assessment the integration would publish, which is the whole
    # point of a preview: what you see is what Home Assistant would say.
    turf = assess.Lawn(
        name=name,
        latitude=field["latitude"],
        soil_type=field["soil_type"],
        grass_type=field["grass_type"],
        establishment_method=field["establishment_method"],
        establishment_date=(
            dt.date.fromisoformat(field["establishment_date"])
            if field["establishment_date"]
            else None
        ),
        application_rate_mm_h=field["application_rate_mm_h"],
        shaded_fraction=field["shaded_fraction"],
        tree_fraction=sum(f["shade_pct"] for f in field["features"] if f["kind"].endswith("_tree"))
        / 100,
        deciduous_trees=any(f["kind"] == "deciduous_tree" for f in field["features"]),
        elevation_m=float(lawn.get("elevation", 280)),
        robot_mower=bool(field.get("mower_entity")),
    )
    # The week ahead, carried forward from the days just gone: the mean of the last three,
    # held flat, and no rain. The preview used to roll dice for the forecast rain, which is
    # the one number that decides whether the lawn is watered tomorrow — a sample that
    # invents 8 mm of rain shows a lawn that needs no water, and says nothing true about the
    # lawn it claims to be showing. Persistence is the standard baseline and, unlike a die,
    # it invents nothing: a record that ends in a hot dry spell goes on being one.
    recent = days[-3:] if len(days) >= 3 else days[-1:]
    tmax_ahead = round(sum(d["tmax"] for d in recent) / len(recent), 1)
    tmin_ahead = round(sum(d["tmin"] for d in recent) / len(recent), 1)
    forecast_days = [
        {
            "datetime": f"{(today + dt.timedelta(days=i)).isoformat()}T10:00:00+00:00",
            "condition": "sunny",
            "temperature": tmax_ahead,
            "templow": tmin_ahead,
            "humidity": 50,
            "wind_speed": 8.0,
            "precipitation": 0.0,
        }
        for i in range(7)
    ]
    ahead_days = [
        agenda.DayForecast(
            dt.date.fromisoformat(f["datetime"][:10]),
            f["temperature"],
            f["templow"],
            f["precipitation"],
        )
        for f in forecast_days
    ]
    by_key = {day["date"]: day for day in days}
    today_weather = et.WeatherDay(
        last["tmax"], last["tmin"], rh_mean=last["rh_mean"], wind_2m_ms=2.0, rs_mj=None
    )
    adaptation_state = {
        "irrigation_factor": 1.0,
        "feed_factor": 1.0,
        "last_evaluated": None,
        "history": [],
    }
    plan_state: dict[str, Any] = {}
    result = assess.assess(
        turf,
        by_key,
        today=today,
        weather=et.WeatherDay(
            today_weather.tmax,
            today_weather.tmin,
            rh_mean=today_weather.rh_mean,
            wind_2m_ms=2.0,
            rs_mj=et.solar_radiation_from_temperature(
                today_weather.tmax,
                today_weather.tmin,
                et.extraterrestrial_radiation(turf.latitude, today.timetuple().tm_yday),
            ),
        ),
        forecast=ahead_days,
        adaptation_state=adaptation_state,
        plan_state=plan_state,
    )

    sunrise = dt.datetime.combine(
        today + dt.timedelta(days=1),
        dt.time(6, 55),
        tzinfo=dt.timezone(dt.timedelta(hours=lawn.get("timezone_offset_hours", 2))),
    )
    booked = (chain or {}).get("earliest_end")
    irrigation = schedule.irrigation_plan(
        date=sunrise.date(),
        sunrise=min(sunrise, booked + schedule.DAWN_BUFFER) if booked else sunrise,
        needed_mm=result.needed_mm,
        minutes_per_mm=turf.minutes_per_mm,
        heat_stress=result.phenology.heat_stress,
        forecast_tmax=ahead_days[0].tmax if ahead_days else None,
        dormant=result.phenology.phase == "dormant",
        soil_type=turf.soil_type,
        germinating=result.germinating,
        germination_offset=dt.timedelta(minutes=int((chain or {}).get("germination_minutes", 0))),
    )
    # One valve at a time, as on the box: each lawn's dawn cycle ends where the next lawn's
    # begins, and its seedbed passes start where the queue ahead of it finishes. Without this
    # the preview showed three lawns watering at the same minute for the same length, which
    # is the one thing the controller cannot do.
    if chain is not None:
        if irrigation.main_start is not None:
            chain["earliest_end"] = min(
                chain.get("earliest_end", irrigation.main_start), irrigation.main_start
            )
        if irrigation.germination:
            chain["germination_minutes"] = int(chain.get("germination_minutes", 0)) + (
                irrigation.germination[0].minutes
            )
    now = dt.datetime.now(tz=sunrise.tzinfo)
    mowing = schedule.mowing_window(
        now=now,
        due=result.mowing_due,
        rain_today_mm=last["rain_mm"],
        last_rain_at=None,
        heat_stress=result.phenology.heat_stress,
        irrigating=irrigation.active_cycle(now) is not None,
    )

    logged_today = {item.get("type") for item in last.get("maintenance", []) if item.get("type")}
    if last.get("irrigation_mm"):
        logged_today.add("irrigation")
    doing = activity.current(
        zone=name,
        zone_id=zone_id,
        now_iso=now.isoformat(),
        advice=[a.as_dict() for a in result.advice],
        irrigation_cycle=irrigation.active_cycle(now),
        irrigation_plan=irrigation.as_dict(),
        mowing_open=mowing.open,
        mowing_window=mowing.as_dict(),
        mowing_ends=dt.datetime.combine(
            today, schedule.MOW_WINDOW[1], tzinfo=now.tzinfo
        ).isoformat(),
        mow_height_mm=next(
            (
                a.params.get("height_mm")
                for a in result.advice
                if a.category == "mowing" and a.params.get("height_mm")
            ),
            None,
        ),
        logged_today=logged_today,
        has_valve=bool(field.get("valve_entity")),
        has_robot=bool(field.get("mower_entity")),
        valve_entity=field.get("valve_entity"),
        mower_entity=field.get("mower_entity"),
    )
    state = {
        "day": today.isoformat(),
        "et0_mm": round(result.et0_mm, 2),
        "etc_mm": round(result.etc_mm, 2),
        "et_method": result.et_method,
        "kc": round(result.kc, 3),
        "tmax": last["tmax"],
        "tmin": last["tmin"],
        "rh_mean": last["rh_mean"],
        "wind_ms": 2.0,
        "rs_mj": None,
        "rain_today_mm": last["rain_mm"],
        "rain_source": "sensor",
        "irrigation_today_min": last["irrigation_min"],
        "irrigation_today_mm": last["irrigation_mm"],
        "deficit_mm": round(result.deficit_mm, 1),
        "taw_mm": round(result.soil.taw_mm, 1),
        "raw_mm": round(result.soil.raw_mm, 1),
        "available_fraction": result.soil.available_fraction(result.deficit_mm),
        "root_depth_m": result.root_depth_m,
        "irrigation_needed_mm": round(result.needed_mm, 1),
        "irrigation_needed_min": (
            round(result.needed_mm * turf.minutes_per_mm) if turf.minutes_per_mm else None
        ),
        "forecast_rain_24h_mm": result.forecast_rain_24h_mm,
        "forecast_rain_3d_mm": result.forecast_rain_72h_mm,
        "rain_7d_mm": round(sum(d["rain_mm"] for d in days[-7:]), 1),
        "irrigation_7d_mm": round(sum(d["irrigation_mm"] for d in days[-7:]), 1),
        "days_since_mowing": result.context.days_since_mowing,
        "days_since_fertilizing": result.context.days_since_fertilizing,
        "soil_moisture_pct": None,
        "status": result.context.statuses_14d[-1] if result.context.statuses_14d else None,
        "forecast_days": forecast_days,
        "advice": [a.as_dict() for a in result.advice],
        "plan": assess.status_of(result.operations, by_key, today),
        "agenda": [item.as_dict() for item in result.agenda],
        "projection": [day.as_dict() for day in result.projection],
        "irrigation_plan": irrigation.as_dict(),
        "irrigation_cycle": irrigation.active_cycle(now),
        "irrigation_next_start": (irrigation.next_start(now) or sunrise).isoformat(),
        "mowing_window": mowing.as_dict(),
        "activity": doing.state,
        "activity_details": doing.details,
        "logged_today": sorted(logged_today),
        "season_phase": result.phenology.phase,
        "soil_temperature_c": result.phenology.soil_temperature_c,
        "gdd": result.phenology.gdd_base0,
        "heat_stress": result.phenology.heat_stress,
        "days_to_first_frost": result.phenology.days_to_first_frost,
        "dollar_spot_probability": result.dollar_spot,
        "brown_patch_index": result.brown_patch,
        "nitrogen_60d_g_m2": result.nitrogen_60d,
        "nitrogen_year_g_m2": result.nitrogen_year,
        "forecast_rain_reliability": result.skill.rain_hit_rate if result.skill.trusted else None,
        "forecast_tmax_bias": result.skill.tmax_bias if result.skill.trusted else None,
        "dry_spell_days": result.anomalies.dry_spell_days,
        "et_anomaly": result.anomalies.et_anomaly,
        "irrigation_factor": result.irrigation_factor,
        "feed_factor": result.feed_factor,
    }

    shim_field = SimpleNamespace(name=name)
    shim_diary = SimpleNamespace(
        recent=lambda count, until=today: [
            (dt.date.fromisoformat(d["date"]), d) for d in days[-count:]
        ]
    )
    shim_state = SimpleNamespace(
        irrigation_plan=state["irrigation_plan"],
        agenda=state["agenda"],
        plan=state["plan"],
        heat_stress=state["heat_stress"],
    )
    events = build_events(
        shim_field,
        zone_id,
        shim_diary,
        shim_state,
        today,
        dt.time(6, 55),
        dt.timezone(dt.timedelta(hours=2)),
        field["soil_type"],
    )

    return {
        "zone_id": zone_id,
        "field": field,
        "events": events,
        "state": state,
        "days": days,
        "adaptation": adaptation_state,
        "plan": state["plan"],
        "issues": list(ISSUES),
        "maintenance_kinds": list(MAINTENANCE_KINDS),
        "fertilizers": {
            k: {"name": f.name, "n": f.n, "p": f.p, "k": f.k, "role": f.role}
            for k, f in fertilizers.PRESETS.items()
        },
    }


INDEX = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Hosekeeper preview</title>
<style>
  html, body { margin: 0; height: 100%; font-family: Roboto, system-ui, sans-serif; }
  :root { --primary-color: #03a9f4; --primary-background-color: #f2f4f7; --card-background-color: #fff;
          --primary-text-color: #1c1e21; --secondary-text-color: #6b7280; --divider-color: rgba(127,127,127,.22);
          --secondary-background-color: #e9ecf1; --error-color: #db4437; --warning-color: #ffa600; --success-color: #43a047;
          --app-header-background-color: #03a9f4; --app-header-text-color: #fff; --text-primary-color: #fff; }
  @media (prefers-color-scheme: dark) {
    :root { --primary-background-color: #111318; --card-background-color: #1c1f26; --primary-text-color: #e6e8ee;
            --secondary-text-color: #9aa3b2; --secondary-background-color: #262a33; --divider-color: rgba(255,255,255,.12);
            --app-header-background-color: #1c1f26; }
  }
</style></head>
<body>
<script type="module">
  const snapshots = await (await fetch("/api/snapshot")).json();
  const lawns = Object.values(snapshots);
  const params = new URLSearchParams(location.search);
  const lang = params.get("lang") || "__LANG__";
  if (params.get("view")) localStorage.setItem("hosekeeper.view", params.get("view"));
  // One next-action sensor per zone, named as Home Assistant would name it: that is how the
  // panel notices a zone has been recomputed. Looking a zone up by a fixed key is what left
  // this page blank when the sample changed.
  const slug = (name) => name.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "");
  const states = {};
  for (const zone of lawns) {
    states[`sensor.${slug(zone.field.name)}_next_action`] = {
      state: zone.state.next_action,
      last_updated: new Date().toISOString(),
    };
    states[`sensor.${slug(zone.field.name)}_activity`] = {
      state: zone.state.activity || "idle",
      attributes: zone.state.activity_details || {},
    };
  }
  const hass = {
    language: lang,
    locale: { language: lang },
    states,
    async callWS(msg) {
      if (msg.type === "hosekeeper/fields") return Object.values(snapshots).map((s) => ({ zone_id: s.zone_id, name: s.field.name }));
      if (msg.type === "hosekeeper/field") return snapshots[msg.zone_id];
      if (msg.type === "hosekeeper/log") {
        // The preview writes to its own copy so the button can be tried: the row moves to
        // "logged today" exactly as it would on the box, and is gone on the next rebuild.
        const snapshot = snapshots[msg.zone_id];
        const today = new Date().toISOString().slice(0, 10);
        const kind = msg.what === "irrigation" ? "irrigation" : msg.kind || msg.what;
        if (msg.what === "status") {
          snapshot.state.status = msg.status;
        } else {
          snapshot.events = [
            ...snapshot.events.filter((e) => !(e.date === today && e.kind === "logged" && e.code === kind)),
            {
              uid: `${msg.zone_id}:${today}:preview:${kind}`,
              date: today,
              start: null,
              end: null,
              all_day: true,
              code: kind,
              category: snapshot.events.find((e) => e.code === kind)?.category || "general",
              kind: "logged",
              params: msg.minutes ? { minutes: msg.minutes } : {},
              zone: snapshot.field.name,
              zone_id: msg.zone_id,
            },
          ];
        }
        return snapshot;
      }
      throw new Error("unknown " + msg.type);
    },
    async callService(domain, service, data) {
      console.log("callService", domain, service, data);
    },
  };
  await import("/frontend/hosekeeper-panel.js");
  const panel = document.createElement("hosekeeper-panel");
  panel.hass = hass;
  panel.narrow = window.innerWidth < 700;
  document.body.append(panel);
</script>
</body></html>
"""


class Handler(SimpleHTTPRequestHandler):
    """Serve the index, the snapshot and the frontend directory."""

    # Rebuilt on every request rather than once at startup: a reload in the browser should
    # show the current engine's answer, not the one this process happened to compute when it
    # was launched. Only a change to the Python modules themselves still needs a restart.
    lang = "en"
    seed = 1
    today: ClassVar[dt.date] = dt.date.today()
    weather: ClassVar[dict[str, dict[dt.date, float]] | None] = None
    lawn: ClassVar[dict[str, Any] | None] = None

    def do_GET(self) -> None:
        """Serve the snapshot, a frontend module, or the index."""
        if self.path.startswith("/api/snapshot"):
            zones = self.lawn["zones"]
            # One queue for the whole property, so the lawns chain rather than collide.
            chain: dict[str, Any] = {}
            snapshots = {
                z["zone_id"]: invent(
                    self.seed + index,
                    self.today,
                    zone=z,
                    weather=self.weather,
                    lawn=self.lawn,
                    # With invented weather one lawn is kept dry, or nothing ever waters.
                    thirsty=self.weather is None and index == len(zones) - 1,
                    chain=chain,
                )
                for index, z in enumerate(zones)
            }
            body = json.dumps(snapshots).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/frontend/"):
            self.path = self.path[len("/frontend") :]
            return super().do_GET()
        body = INDEX.replace("__LANG__", self.lang).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self) -> None:
        """Disable caching: an edit must show on reload."""
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def translate_path(self, path: str) -> str:
        """Map URL paths onto the frontend directory."""
        return str(FRONTEND / path.lstrip("/"))

    def log_message(self, fmt: str, *args: Any) -> None:
        """Stay quiet; the browser's network tab says more."""
        return


HERE = Path(__file__).resolve().parent


def _sample(name: str) -> Path:
    """Return your own file if you have one, else the sample committed with the repository.

    A real lawn and a real station's weather say where somebody lives, so they are kept in
    `scripts/local/`, which git ignores. The preview picks them up without being asked, and
    falls back to a made-up lawn under a made-up summer for everybody else.
    """
    mine = HERE / "local" / f"{name}.json"
    return mine if mine.exists() else HERE / f"example-{name}.json"


def main() -> None:
    """Run the preview server."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--port", type=int, default=8123)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--lang", default="en", choices=("en", "it"))
    parser.add_argument("--date", default=None, help="YYYY-MM-DD to pretend it is")
    parser.add_argument(
        "--stats",
        type=Path,
        default=None,
        help="statistics from pull_stats.py: the preview then shows this station's own weather",
    )
    parser.add_argument(
        "--lawn",
        type=Path,
        default=None,
        help="the zones to show; defaults to scripts/local/lawn.json if present, else the sample",
    )
    parser.add_argument(
        "--prefix",
        default="sensor.weather_station_",
        help="entity-id prefix of the station in --stats",
    )
    parser.add_argument(
        "--open-meteo",
        action="store_true",
        help="fetch fresh weather for the lawn's coordinates instead of the saved sample",
    )
    parser.add_argument(
        "--weather",
        type=Path,
        default=None,
        help="the weather to replay; defaults to scripts/local/weather.json if present, else the sample",
    )
    args = parser.parse_args()
    args.lawn = args.lawn or _sample("lawn")
    args.weather = args.weather or _sample("weather")
    today = dt.date.fromisoformat(args.date) if args.date else dt.date.today()
    Handler.seed = args.seed
    Handler.today = today
    Handler.lang = args.lang
    lawn = json.loads(args.lawn.read_text())
    if args.stats:
        Handler.weather = from_statistics(args.stats, args.prefix)
    elif args.open_meteo:
        end = today - dt.timedelta(days=1)
        Handler.weather = from_open_meteo(
            lawn["latitude"], lawn["longitude"], end - dt.timedelta(days=60), end
        )
    elif args.weather.exists():
        Handler.weather = from_file(args.weather)
    # The lawn says which zones there are; the weather source is a separate choice, so the
    # preview shows the real property whether or not real weather was asked for.
    Handler.lawn = lawn
    if Handler.weather:
        measured = sorted(Handler.weather["tmax"])
        if not args.date:
            # The sample's today is the morning after its last real day, so every day the
            # diary shows is a day that actually happened.
            today = measured[-1] + dt.timedelta(days=1)
            Handler.today = today
        print(f"Real weather, {measured[0]} to {measured[-1]}; showing {today}")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(
        f"Hosekeeper preview: http://127.0.0.1:{args.port}/  (lang={args.lang}, seed={args.seed}, {today})"
    )
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()


if __name__ == "__main__":
    main()
