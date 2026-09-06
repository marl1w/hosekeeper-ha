"""Replay a lawn's real weather through the engine, day by day.

    make replay STATS=stats.json AGE=2026-06-06

Answers the only question that matters before this thing is let near a real lawn: what
would it have told me to do, and would the grass have survived it? It walks the days in
order, asks the rules what to do each morning, applies exactly that, and reports how close
the lawn came to drought — beside what a fixed daily schedule would have done with the same
weather.

The statistics come from Home Assistant's own recorder, so this is the user's lawn and not
an invented one:

    python scripts/pull_stats.py > stats.json
"""

from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from weather import believable_sun, believable_wind, from_open_meteo, from_statistics  # noqa: E402

from custom_components.hosekeeper.engine import (  # noqa: E402
    climate,
    et,
    phenology,
    rules,
    schedule,
    water,
)
from custom_components.hosekeeper.engine.knowledge import grass  # noqa: E402


def main() -> None:
    """Replay and report."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("stats", type=Path, nargs="?", help="statistics from pull_stats.py")
    parser.add_argument(
        "--open-meteo",
        action="store_true",
        help="use the Open-Meteo archive for the coordinates instead of a station's own record",
    )
    parser.add_argument("--days", type=int, default=45, help="how far back to go with --open-meteo")
    parser.add_argument(
        "--prefix",
        default="sensor.weather_station_",
        help="entity-id prefix of your station's sensors",
    )
    parser.add_argument("--longitude", type=float, default=9.0)
    parser.add_argument("--latitude", type=float, default=45.0)
    parser.add_argument("--elevation", type=float, default=100.0)
    parser.add_argument("--grass", default="tall_fescue")
    parser.add_argument("--soil", default="loam")
    parser.add_argument("--method", default="sod")
    parser.add_argument("--established", default=None, help="YYYY-MM-DD the lawn was laid or sown")
    parser.add_argument("--rate", type=float, default=20.0, help="mm/h the system applies")
    parser.add_argument(
        "--fixed", type=float, default=None, help="mm a day a fixed schedule applies"
    )
    args = parser.parse_args()

    if args.open_meteo:
        end = dt.date.today() - dt.timedelta(days=1)
        data = from_open_meteo(
            args.latitude, args.longitude, end - dt.timedelta(days=args.days), end
        )
    elif args.stats:
        data = from_statistics(args.stats, args.prefix)
    else:
        parser.error("give a statistics file or --open-meteo")
    days = sorted(set(data["tmax"]) & set(data["tmin"]) & set(data["rh"]) & set(data["solar"]))
    if not days:
        print("No overlapping days in the statistics.")
        return
    laid = dt.date.fromisoformat(args.established) if args.established else None
    profile = grass.profile(args.grass)

    print(f"{len(days)} days, {days[0]} to {days[-1]}\n")
    print(
        f"{'day':<11}{'ETc':>6}{'rain':>6}{'roots':>7}{'point':>7}{'deficit':>9}{'engine':>8}{'fixed':>7}"
    )

    deficit = fixed_deficit = 0.0
    engine_total = fixed_total = 0.0
    engine_stress = fixed_stress = 0
    engine_worst = fixed_worst = 0.0
    engine_runs = 0
    # Real stress, not the ordinary dip before a watering: three quarters of the reserve
    # gone is where cool-season turf starts to lose colour.
    stress_at = 0.75
    for day in days:
        doy = day.timetuple().tm_yday
        ra = et.extraterrestrial_radiation(args.latitude, doy)
        measured = data["solar"].get(day)
        estimate = et.solar_radiation_from_temperature(data["tmax"][day], data["tmin"][day], ra)
        rs = believable_sun(measured, estimate)
        u2 = believable_wind(data["wind"].get(day))
        weather = et.WeatherDay(
            data["tmax"][day], data["tmin"][day], rh_mean=data["rh"][day], wind_2m_ms=u2, rs_mj=rs
        )
        et0 = et.penman_monteith_et0(
            weather, latitude_deg=args.latitude, elevation_m=args.elevation, day_of_year=doy
        )
        etc = et0 * grass.crop_coefficient(args.grass, day.month)
        rain = data["rain"].get(day, 0.0)
        age = (day - laid).days if laid else None
        depth = grass.root_depth(args.grass, age, args.method)

        # What the engine would have said that morning.
        history = [
            phenology.DayTemps(d, data["tmax"][d], data["tmin"][d])
            for d in days
            if d <= day and d in data["tmax"] and d in data["tmin"]
        ]
        phen = phenology.assess(
            history, day, latitude=args.latitude, cool_season=profile.cool_season
        )
        # A young lawn, or one in a heat wave, is asked to give up less of its reserve.
        soil = water.soil_water(
            args.soil,
            depth,
            water.allowed_depletion(
                young=age is not None and age < water.YOUNG_LAWN_DAYS,
                heat_stress=phen.heat_stress,
            ),
        )
        ctx = rules.Context(
            today=day,
            cool_season=profile.cool_season,
            northern_hemisphere=args.latitude >= 0,
            grass_type=args.grass,
            soil_type=args.soil,
            establishment_method=args.method,
            establishment_age_days=age,
            mow_height_mm=profile.mow_height_mm,
            phenology=phen,
            deficit_mm=deficit,
            taw_mm=soil.taw_mm,
            raw_mm=soil.raw_mm,
            etc_today_mm=etc,
            rain_today_mm=rain,
            irrigation_today_mm=0.0,
            can_convert_minutes=True,
            minutes_per_mm=60.0 / args.rate,
            forecast_rain_24h_mm=0.0,
            forecast_rain_72h_mm=0.0,
            forecast_tmax_3d=data["tmax"][day],
            forecast_tmin_3d=data["tmin"][day],
            skill=climate.NEUTRAL_SKILL,
            anomalies=climate.Anomalies(None, None, None, 0, 0.0, 0),
            days_since_mowing=3,
            days_since_fertilizing=30,
            days_since_aeration=None,
            days_since_scarifying=None,
            days_since_sowing=None,
            nitrogen_60d_g_m2=2.0,
            nitrogen_year_g_m2=10.0,
            feeds_done_this_year=set(),
            statuses_14d=[],
            issues_30d=set(),
            dollar_spot_probability=None,
            brown_patch_index=None,
        )
        advice = rules.evaluate(ctx)
        irrigate = next((a for a in advice if a.code == "irrigate_now"), None)
        applied = float(irrigate.params["mm"]) if irrigate else 0.0
        if applied:
            engine_runs += 1
        engine_total += applied
        deficit = water.next_deficit(deficit, etc, rain, applied, soil)
        engine_worst = max(engine_worst, deficit / soil.taw_mm)
        if deficit > stress_at * soil.taw_mm:
            engine_stress += 1

        fixed = args.fixed if args.fixed is not None else 0.0
        fixed_total += fixed
        fixed_deficit = water.next_deficit(fixed_deficit, etc, rain, fixed, soil)
        fixed_worst = max(fixed_worst, fixed_deficit / soil.taw_mm)
        if fixed_deficit > stress_at * soil.taw_mm:
            fixed_stress += 1

        runs = schedule.split_into_cycles(applied, args.soil)
        note = f"{applied:.0f} mm" + (f" x{len(runs)}" if len(runs) > 1 else "") if applied else "-"
        print(
            f"{day!s:<11}{etc:>6.1f}{rain:>6.1f}{depth * 100:>6.0f}cm{soil.raw_mm:>7.1f}"
            f"{deficit:>9.1f}{note:>8}{fixed_deficit:>7.1f}"
        )

    weeks = len(days) / 7
    per_week = engine_total / weeks
    print(f"\nThe engine: {engine_total:.0f} mm over {engine_runs} waterings")
    print(
        f"  that is {per_week:.0f} mm a week, one every {len(days) / max(engine_runs, 1):.1f} days"
    )
    print(f"  driest the lawn ever got: {100 * engine_worst:.0f} % of its reserve used")
    print(f"  days in real stress: {engine_stress}")
    if args.fixed is not None:
        fixed_week = fixed_total / weeks
        print(f"A fixed {args.fixed} mm every day: {fixed_total:.0f} mm")
        print(f"  that is {fixed_week:.0f} mm a week")
        print(f"  driest: {100 * fixed_worst:.0f} % of the reserve used")
        print(f"  days in real stress: {fixed_stress}")


if __name__ == "__main__":
    main()
