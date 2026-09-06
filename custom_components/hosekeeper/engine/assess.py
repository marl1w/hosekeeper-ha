"""One lawn, one day, assessed.

This is the whole judgement in one place: from a lawn's description, its diary and a day's
weather, the water balance, the season, the disease models, the month's plan, the week's
agenda and today's advice. Home Assistant is not imported here and nothing is read from it.

It exists because the same assembly was written twice — once in the coordinator and once in
the preview — and the two drifted. Every difference between them showed up as a wrong
answer in the preview: a lawn aged from a hard-coded date, a grass type that was not the
lawn's, aeration proposed on three-month-old turf. There is one assembly now, and the
preview and the integration both call it, so what the preview shows is what the integration
would say.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
import datetime as dt
from typing import Any

from . import adaptation, agenda, climate, disease, et, phenology, plan, rules, water
from .knowledge import grass, programme


@dataclass(frozen=True, slots=True)
class Lawn:
    """What the engine needs to know about a lawn. No Home Assistant in it."""

    name: str
    latitude: float
    soil_type: str
    grass_type: str
    establishment_method: str
    establishment_date: dt.date | None
    application_rate_mm_h: float | None
    shaded_fraction: float = 0.0
    tree_fraction: float = 0.0
    deciduous_trees: bool = False
    elevation_m: float = 0.0
    robot_mower: bool = False
    """Whether the lawn is cut by a robot, which mows little and often."""
    robot_cadence: str = programme.DEFAULT_ROBOT_CADENCE
    """How often that robot is wanted out."""
    deck_mm: tuple[int, int] | None = None
    """Lowest and highest the mower can be set to, when that is known."""

    @property
    def northern_hemisphere(self) -> bool:
        """Return which half of the world the lawn is in."""
        return self.latitude >= 0

    @property
    def minutes_per_mm(self) -> float | None:
        """Return how long the system runs to put down a millimetre."""
        rate = self.application_rate_mm_h
        return 60.0 / rate if rate else None

    def age_days(self, today: dt.date) -> int | None:
        """Return how old the lawn is, or None when it was never recorded."""
        return (today - self.establishment_date).days if self.establishment_date else None


@dataclass(slots=True)
class Assessment:
    """Everything the day amounts to."""

    day: dict[str, Any]
    context: rules.Context
    advice: list[rules.Advice]
    operations: list[plan.Operation]
    agenda: list[agenda.AgendaItem]
    projection: list[agenda.DayProjection]
    phenology: phenology.Phenology
    soil: water.SoilWater
    skill: climate.ForecastSkill
    anomalies: climate.Anomalies
    root_depth_m: float
    et0_mm: float
    etc_mm: float
    et_method: str
    kc: float
    deficit_mm: float
    needed_mm: float
    dollar_spot: float | None
    brown_patch: float | None
    nitrogen_60d: float
    nitrogen_year: float
    irrigation_factor: float
    feed_factor: float
    forecast_rain_24h_mm: float | None
    forecast_rain_72h_mm: float | None
    disease_flags: set[str] = dc_field(default_factory=set)

    @property
    def mowing_due(self) -> bool:
        """Return whether a cut is owed."""
        return any(a.code in ("mow_soon", "mow_now_third_rule") for a in self.advice)

    @property
    def germinating(self) -> bool:
        """Return whether seed sown here is still coming up."""
        return self.context.germinating


def recent(
    days: dict[str, Any], count: int, until: dt.date
) -> list[tuple[dt.date, dict[str, Any]]]:
    """Return the last `count` days ending on `until`, gaps included as empty records."""
    return [
        (
            until - dt.timedelta(days=offset),
            days.get((until - dt.timedelta(days=offset)).isoformat(), {}),
        )
        for offset in range(count - 1, -1, -1)
    ]


def last_deficit(days: dict[str, Any], before: str, within_days: int = 7) -> float | None:
    """Return the deficit carried in from the most recent day before `before`."""
    limit = (dt.date.fromisoformat(before) - dt.timedelta(days=within_days)).isoformat()
    for key in sorted(days, reverse=True):
        if key >= before:
            continue
        if key < limit:
            return None
        value = days[key].get("deficit_mm")
        if value is not None:
            return float(value)
    return None


def days_since(days: dict[str, Any], kind: str, today: dt.date) -> int | None:
    """Return how many days since a maintenance kind was last recorded."""
    best: dt.date | None = None
    for key, record in days.items():
        for item in record.get("maintenance", []):
            if item.get("type") != kind:
                continue
            date = dt.date.fromisoformat(key)
            if best is None or date > best:
                best = date
    return None if best is None else max(0, (today - best).days)


def nitrogen(
    days: dict[str, Any], today: dt.date, *, cool_season: bool, northern: bool
) -> tuple[float, float, set[str]]:
    """Return nitrogen over 60 days, over the year, and the programme windows already fed."""
    n60 = nyear = 0.0
    fed: set[str] = set()
    for key, record in days.items():
        date = dt.date.fromisoformat(key)
        for item in record.get("maintenance", []):
            if item.get("type") != "fertilizing":
                continue
            grams = float((item.get("details") or {}).get("n_g_m2") or 0.0)
            if (today - date).days < 60:
                n60 += grams
            if date.year == today.year:
                nyear += grams
                month = programme.fold_month(date.month, northern)
                for window in programme.feeds_for(cool_season):
                    if month in window.months:
                        fed.add(window.code)
    return n60, nyear, fed


def soil_for(lawn: Lawn, days: dict[str, Any], today: dt.date) -> tuple[water.SoilWater, float]:
    """Return the reservoir this lawn actually has today, and its rooting depth."""
    age = lawn.age_days(today)
    depth = grass.root_depth(lawn.grass_type, age, lawn.establishment_method)
    window = recent(days, 14, today)
    statuses = [record["status"] for _, record in window if record.get("status")]
    temps = [
        phenology.DayTemps(date, record["tmax"], record["tmin"])
        for date, record in window
        if record.get("tmax") is not None and record.get("tmin") is not None
    ]
    soil = water.soil_water(
        lawn.soil_type,
        depth,
        water.allowed_depletion(
            young=age is not None and age < water.YOUNG_LAWN_DAYS,
            heat_stress=phenology.heat_stress(temps),
            struggling=bool(statuses) and statuses[-1] in ("poor", "fair"),
        ),
    )
    return soil, depth


def observe(
    lawn: Lawn,
    days: dict[str, Any],
    day: dt.date,
    *,
    weather: et.WeatherDay | None,
    radiation_estimated: bool = False,
) -> dict[str, Any]:
    """Write one day's weather into the diary and carry the balance through it.

    The day the coordinator is running is one of these; so is a day months back, entered
    after the fact from an archive. Both go through here, so a season imported into a new
    install is the season the engine would have recorded had it been there — and applying
    the days in order rebuilds the balance, because each one carries in the deficit the day
    before it left behind.
    """
    key = day.isoformat()
    record = days.setdefault(key, {})
    soil, _ = soil_for(lawn, days, day)
    kc = grass.crop_coefficient(lawn.grass_type, day.month, lawn.northern_hemisphere)
    # Shade cuts turf water use to roughly 60 to 70 % of the open-lawn figure; tree roots in
    # the same soil take some of that saving back. Both scale with the shaded share.
    kc_effective = kc * (1 - 0.35 * lawn.shaded_fraction) + 0.15 * lawn.tree_fraction
    if weather is None:
        et0, method = 0.0, "none"
    else:
        et0, method = et.reference_et0(
            weather,
            latitude_deg=lawn.latitude,
            elevation_m=lawn.elevation_m,
            day_of_year=day.timetuple().tm_yday,
        )
        if method == "penman_monteith" and radiation_estimated:
            method = "penman_monteith_estimated_radiation"
    etc = et0 * kc_effective

    carried = last_deficit(days, key)
    deficit = water.next_deficit(
        0.0 if carried is None else carried,
        etc,
        record.get("rain_mm", 0.0),
        record.get("irrigation_mm", 0.0),
        soil,
    )
    record.update(
        et0_mm=round(et0, 2),
        etc_mm=round(etc, 2),
        et_method=method,
        kc=round(kc_effective, 3),
        deficit_mm=round(deficit, 2),
    )
    if weather is not None:
        record["tmax"] = round(weather.tmax, 1)
        record["tmin"] = round(weather.tmin, 1)
        if weather.rh_mean is not None:
            record["rh_mean"] = round(weather.rh_mean, 1)
    return record


def assess(
    lawn: Lawn,
    days: dict[str, Any],
    *,
    today: dt.date,
    weather: et.WeatherDay | None,
    forecast: list[agenda.DayForecast],
    adaptation_state: dict[str, Any],
    plan_state: dict[str, Any],
    radiation_estimated: bool = False,
    soil_moisture_pct: float | None = None,
) -> Assessment:
    """Return the day's assessment, updating the diary's record for today as it goes."""
    key = today.isoformat()
    profile = grass.profile(lawn.grass_type)
    soil, depth = soil_for(lawn, days, today)

    # --- what the lawn used today ---------------------------------------------------------
    record = observe(lawn, days, today, weather=weather, radiation_estimated=radiation_estimated)
    etc = record["etc_mm"]
    deficit = record["deficit_mm"]

    # --- the season, the forecast's honesty, and this lawn's own normal --------------------
    since = dt.date(today.year, 1, 1) - dt.timedelta(days=30)
    temps: list[phenology.DayTemps] = []
    rh_means: list[float] = []
    tmeans: list[float] = []
    pairs: list[climate.ForecastPair] = []
    rows: list[tuple[dt.date, float | None, float | None, float | None]] = []
    for day_key in sorted(days):
        date = dt.date.fromisoformat(day_key)
        if date < since or date > today:
            continue
        row = days[day_key]
        tmax, tmin = row.get("tmax"), row.get("tmin")
        if tmax is not None and tmin is not None:
            temps.append(phenology.DayTemps(date, float(tmax), float(tmin)))
        if (today - date).days < 5:
            if row.get("rh_mean") is not None:
                rh_means.append(row["rh_mean"])
            if tmax is not None and tmin is not None:
                tmeans.append((tmax + tmin) / 2)
        if (today - date).days < climate.FORECAST_WINDOW_DAYS:
            promised = row.get("fc") or {}
            if promised and date < today:
                pairs.append(
                    climate.ForecastPair(
                        date,
                        promised.get("rain"),
                        row.get("rain_mm"),
                        promised.get("tmax"),
                        tmax,
                        promised.get("tmin"),
                        tmin,
                    )
                )
            rows.append((date, row.get("et0_mm"), row.get("rain_mm"), tmax))

    phen = phenology.assess(temps, today, latitude=lawn.latitude, cool_season=profile.cool_season)
    skill = climate.forecast_skill(pairs)
    anomalies = climate.anomalies(rows)
    dollar_spot = disease.dollar_spot_probability(rh_means, tmeans)
    brown_patch = disease.brown_patch_index(record.get("rh_mean"), record.get("tmin"))

    # --- what the lawn has taught us ------------------------------------------------------
    if not adaptation_state:
        adaptation_state.update(adaptation.default_state())
    if adaptation.due(adaptation_state, today):
        adaptation_state.update(
            adaptation.evaluate(
                adaptation_state,
                [
                    adaptation.Observation(
                        date,
                        row.get("status"),
                        row.get("deficit_mm"),
                        soil.raw_mm,
                        row.get("rain_mm", 0.0),
                        frozenset(row.get("issues", [])),
                    )
                    for date, row in recent(days, 28, today)
                ],
                today,
            )
        )

    statuses = [row["status"] for _, row in recent(days, 14, today) if row.get("status")]
    issues: set[str] = set()
    for _, row in recent(days, 30, today):
        issues.update(row.get("issues", []))
    events = plan.month_events(days)

    n60, nyear, fed = nitrogen(
        days, today, cool_season=profile.cool_season, northern=lawn.northern_hemisphere
    )
    ahead = {f.date: f for f in forecast}
    next_three = [ahead.get(today + dt.timedelta(days=i)) for i in range(3)]
    rain_24h = _sum(f.rain_mm for f in next_three[:2] if f)
    rain_72h = _sum(f.rain_mm for f in next_three if f)

    context = rules.Context(
        today=today,
        cool_season=profile.cool_season,
        northern_hemisphere=lawn.northern_hemisphere,
        grass_type=lawn.grass_type,
        soil_type=lawn.soil_type,
        establishment_method=lawn.establishment_method,
        establishment_age_days=lawn.age_days(today),
        mow_height_mm=grass.mowing_range(lawn.grass_type, lawn.deck_mm),
        phenology=phen,
        deficit_mm=deficit,
        taw_mm=soil.taw_mm,
        raw_mm=soil.raw_mm,
        etc_today_mm=etc,
        rain_today_mm=record.get("rain_mm", 0.0),
        irrigation_today_mm=record.get("irrigation_mm", 0.0),
        can_convert_minutes=bool(lawn.application_rate_mm_h),
        minutes_per_mm=lawn.minutes_per_mm,
        forecast_rain_24h_mm=rain_24h,
        forecast_rain_72h_mm=rain_72h,
        forecast_tmax_3d=_best(max, (f.tmax for f in next_three if f)),
        forecast_tmin_3d=_best(min, (f.tmin for f in next_three if f)),
        skill=skill,
        anomalies=anomalies,
        days_since_mowing=days_since(days, "mowing", today),
        days_since_fertilizing=days_since(days, "fertilizing", today),
        days_since_aeration=days_since(days, "aeration", today),
        days_since_scarifying=days_since(days, "scarifying", today),
        days_since_sowing=days_since(days, "sowing", today),
        nitrogen_60d_g_m2=n60,
        nitrogen_year_g_m2=nyear,
        feeds_done_this_year=fed,
        statuses_14d=statuses,
        issues_30d=issues,
        dollar_spot_probability=dollar_spot,
        brown_patch_index=brown_patch,
        irrigation_factor=float(adaptation_state.get("irrigation_factor", 1.0)),
        feed_factor=float(adaptation_state.get("feed_factor", 1.0)),
        soil_moisture_pct=soil_moisture_pct,
        shaded_fraction=lawn.shaded_fraction,
        tree_fraction=lawn.tree_fraction,
        deciduous_trees=lawn.deciduous_trees,
        robot_mower=lawn.robot_mower,
        robot_cadence=lawn.robot_cadence,
        month_events=events.get(key[:7], set()),
        done_today={item.get("type") for item in record.get("maintenance", []) if item.get("type")},
        disease_risk_yesterday=set(
            days.get((today - dt.timedelta(days=1)).isoformat(), {}).get("disease_flags", [])
        ),
    )

    # The month's operations are decided once a month and kept, so the weather cannot
    # reshuffle them; only their timing moves. Changing the lawn itself is not weather: a
    # different species, a mower that cannot reach the height the old plan named, another
    # tree taken down — the plan was built for a lawn that no longer exists, and waiting for
    # the month to turn leaves the plan arguing with the day's own advice. So the setup it
    # was built for is stamped on it, and the plan is rebuilt when either one moves.
    month_key = key[:7]
    setup = _plan_setup(context)
    if plan_state.get("generated") != month_key or plan_state.get("setup") != setup:
        plan_state["generated"] = month_key
        plan_state["setup"] = setup
        plan_state["operations"] = [_to_dict(op) for op in plan.build(context)]
    stored = [_from_dict(op) for op in plan_state.get("operations", [])]
    context.month_plan = [op for op in stored if op.month == month_key]
    carried_feed = plan.carry_over(stored, today, events)
    if carried_feed is not None and not any(
        op.category == "fertilizing" for op in context.month_plan
    ):
        context.month_plan.append(carried_feed)

    record["disease_flags"] = sorted(rules.disease_flags_today(context))
    advice = rules.evaluate(context)
    week = agenda.build(
        context, forecast, advice, latitude=lawn.latitude, minutes_per_mm=lawn.minutes_per_mm
    )
    projection = agenda.project(context, forecast, advice, latitude=lawn.latitude)

    # The plain balance is the fallback; the rules refine it with the forecast's record, the
    # adaptation factor and the season, so their figure is the one published.
    needed = water.irrigation_needed_mm(deficit, soil, rain_24h or 0.0)
    irrigate = next((a for a in advice if a.code == "irrigate_now"), None)
    if irrigate is not None:
        needed = float(irrigate.params["mm"])
    elif any(a.category == "irrigation" for a in advice):
        needed = 0.0

    return Assessment(
        day=record,
        context=context,
        advice=advice,
        operations=stored,
        agenda=week,
        projection=projection,
        phenology=phen,
        soil=soil,
        skill=skill,
        anomalies=anomalies,
        root_depth_m=depth,
        et0_mm=record["et0_mm"],
        etc_mm=etc,
        et_method=record["et_method"],
        kc=record["kc"],
        deficit_mm=deficit,
        needed_mm=needed,
        dollar_spot=None if dollar_spot is None else round(dollar_spot, 3),
        brown_patch=None if brown_patch is None else round(brown_patch, 1),
        nitrogen_60d=round(n60, 2),
        nitrogen_year=round(nyear, 2),
        irrigation_factor=context.irrigation_factor,
        feed_factor=context.feed_factor,
        forecast_rain_24h_mm=rain_24h,
        forecast_rain_72h_mm=rain_72h,
        disease_flags=set(record["disease_flags"]),
    )


def status_of(
    operations: list[plan.Operation], days: dict[str, Any], today: dt.date
) -> list[dict[str, Any]]:
    """Return the plan with each operation's status read from what the diary records."""
    events = plan.month_events(days)
    return [op.as_dict(plan.status_of(op, today, events)) for op in operations]


def _sum(values) -> float | None:
    present = [v for v in values if v is not None]
    return round(sum(present), 1) if present else None


def _best(pick, values):
    present = [v for v in values if v is not None]
    return pick(present) if present else None


def _plan_setup(context: rules.Context) -> str:
    """Return what the month's plan was built for, as one comparable string.

    What the plan is built from and cannot re-read for itself: how the lawn is set up, and
    what the person has told it about the state of the grass. Not the season -- the lawn's
    age moves every day and the disease indices move with the weather, and a plan rebuilt
    every morning is the reshuffling the month's freeze exists to prevent.

    Reporting bare patches has to reach it, though. Bare or thin turf is what turns the
    autumn overseeding from an optional line into a required one, or puts it in the plan of a
    first-year lawn that would otherwise be left to thicken on its own, and a report that
    changed nothing until the month turned would be a report nobody would make twice.
    """
    score = context.status_score
    return "|".join(
        str(part)
        for part in (
            context.grass_type,
            context.soil_type,
            context.establishment_method,
            context.mow_height_mm,
            context.robot_mower,
            context.robot_cadence,
            round(context.shaded_fraction, 2),
            context.northern_hemisphere,
            sorted(context.issues_30d),
            None if score is None else round(score * 2) / 2,
        )
    )


def _to_dict(op: plan.Operation) -> dict[str, Any]:
    return {
        "month": op.month,
        "code": op.code,
        "category": op.category,
        "optional": op.optional,
        "params": op.params,
        "basis": list(op.basis),
        "tailoring": list(op.tailoring),
    }


def _from_dict(data: dict[str, Any]) -> plan.Operation:
    return plan.Operation(
        data["month"],
        data["code"],
        data["category"],
        bool(data.get("optional")),
        dict(data.get("params", {})),
        tuple(data.get("basis", [])),
        tuple(data.get("tailoring", [])),
    )
