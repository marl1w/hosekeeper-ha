"""From everything known about the lawn today to a short, ranked list of things to do.

Each rule is a function that looks at the context and returns zero or more pieces of
advice. Advice carries a stable code — the frontend and the translations render it — the
parameters the sentence needs, and the reasons it was given, also as codes, so the panel
can say not only "irrigate 18 mm tonight" but "because the root zone is 60 % down, the
forecast's 4 mm has only come true one time in three lately, and three days above 30 °C
are on the way".

Priorities: 1 do it today, 2 this week, 3 this month or season, 4 for information.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
import datetime as dt
from typing import Any

from . import disease, nutrition
from .climate import Anomalies, ForecastSkill
from .knowledge import programme
from .phenology import Phenology
from .plan import Operation

STATUS_SCORE = {"excellent": 4, "good": 3, "fair": 2, "poor": 1}


@dataclass(frozen=True, slots=True)
class Advice:
    """One thing to do, or to know."""

    code: str
    category: str
    priority: int
    params: dict[str, Any] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()

    @property
    def horizon(self) -> str:
        """Return today, week, month or info: which view the advice belongs to."""
        return HORIZONS[self.priority]

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly shape for attributes and the websocket."""
        return {
            "code": self.code,
            "category": self.category,
            "priority": self.priority,
            "horizon": self.horizon,
            "params": self.params,
            "reasons": list(self.reasons),
        }


HORIZONS = {1: "today", 2: "week", 3: "month", 4: "info"}


@dataclass(slots=True)
class Context:
    """Everything the rules may look at. Built by the coordinator, or by a test."""

    today: dt.date
    cool_season: bool
    northern_hemisphere: bool
    grass_type: str
    soil_type: str
    establishment_method: str
    establishment_age_days: int | None
    mow_height_mm: tuple[int, int]

    phenology: Phenology

    deficit_mm: float
    taw_mm: float
    raw_mm: float
    etc_today_mm: float
    rain_today_mm: float
    irrigation_today_mm: float
    can_convert_minutes: bool
    minutes_per_mm: float | None

    forecast_rain_24h_mm: float | None
    forecast_rain_72h_mm: float | None
    forecast_tmax_3d: float | None
    forecast_tmin_3d: float | None
    skill: ForecastSkill
    anomalies: Anomalies

    days_since_mowing: int | None
    days_since_fertilizing: int | None
    days_since_aeration: int | None
    days_since_scarifying: int | None
    days_since_sowing: int | None
    nitrogen_60d_g_m2: float
    nitrogen_year_g_m2: float
    feeds_done_this_year: set[str]
    statuses_14d: Sequence[str]
    issues_30d: set[str]

    dollar_spot_probability: float | None
    brown_patch_index: float | None

    irrigation_factor: float = 1.0
    feed_factor: float = 1.0
    soil_moisture_pct: float | None = None

    shaded_fraction: float = 0.0
    """Share of the lawn under trees or structures for a good part of the day."""
    tree_fraction: float = 0.0
    """Share under tree canopy, where roots compete for water."""
    deciduous_trees: bool = False

    robot_mower: bool = False
    robot_cadence: str = programme.DEFAULT_ROBOT_CADENCE
    """How often the robot is wanted out: frequent, balanced or gentle."""
    """A robot cuts a little every day rather than a third of the leaf every week."""

    month_plan: list[Operation] | None = None
    """This month's planned operations; built from the plan module when None."""
    month_events: set[str] = field(default_factory=set)
    """Maintenance kinds already logged this month."""
    done_today: set[str] = field(default_factory=set)
    """Maintenance kinds already logged today, so a job asked for can be seen to be done."""
    disease_risk_yesterday: set[str] = field(default_factory=set)
    """Which disease models were over threshold yesterday, for the two-day hysteresis."""

    # ------------------------------------------------------------ derived helpers

    @property
    def overseeded(self) -> bool:
        """Return whether the seed went down on a lawn that already had turf on it.

        It is the difference between two jobs that share a word. A lawn sown from bare soil
        has nothing to cut and must not be walked on. A lawn overseeded still has its own
        grass growing over the seed, and that grass has to be cut on time or it shades the
        seedlings out before they ever reach the light.
        """
        if self.days_since_sowing is None or self.establishment_age_days is None:
            return False
        age_at_sowing = self.establishment_age_days - self.days_since_sowing
        return age_at_sowing >= programme.SEED_ESTABLISHED_DAYS

    def planned(self, category: str | None = None) -> list[Operation]:
        """Return this month's operations, optionally of one category, not yet done."""
        from . import plan as plan_module

        if self.month_plan is None:
            key = f"{self.today.year:04d}-{self.today.month:02d}"
            ops = [op for op in plan_module.build(self) if op.month == key]
            self.month_plan = ops
        done_kinds = self.month_events
        out = []
        for op in self.month_plan:
            if category is not None and op.category != category:
                continue
            kinds = plan_module.DONE_BY.get(op.category, ())
            if kinds and done_kinds & set(kinds):
                continue
            out.append(op)
        return out

    @property
    def month(self) -> int:
        """Return the month folded onto the northern calendar."""
        return programme.fold_month(self.today.month, self.northern_hemisphere)

    @property
    def phase(self) -> str:
        """Return the season phase."""
        return self.phenology.phase

    @property
    def germinating(self) -> bool:
        """Return whether seed sown here is still coming up."""
        if self.days_since_sowing is not None:
            return self.days_since_sowing <= programme.SEED_GERMINATION_DAYS
        return (
            self.establishment_method in ("seed", "hydroseed")
            and self.establishment_age_days is not None
            and self.establishment_age_days <= programme.SEED_GERMINATION_DAYS
        )

    @property
    def new_lawn(self) -> bool:
        """Return whether the whole lawn is young, as opposed to seed sown into an old one."""
        return (
            self.establishment_age_days is not None
            and self.establishment_age_days <= programme.SEED_ESTABLISHED_DAYS
        )

    @property
    def growing(self) -> bool:
        """Return whether the grass is actively growing."""
        return self.phase in ("spring_greenup", "spring_active", "autumn_active")

    @property
    def status_score(self) -> float | None:
        """Return the mean status score of the last two weeks."""
        scores = [STATUS_SCORE[s] for s in self.statuses_14d if s in STATUS_SCORE]
        return sum(scores) / len(scores) if scores else None

    @property
    def expected_rain_24h(self) -> float:
        """Return forecast rain for the next day, weighted by the forecast's record."""
        from .climate import expected_rain

        return expected_rain(self.forecast_rain_24h_mm, self.skill)

    @property
    def expected_rain_72h(self) -> float:
        """Return forecast rain for the next three days, weighted."""
        from .climate import expected_rain

        return expected_rain(self.forecast_rain_72h_mm, self.skill)

    def minutes_for(self, mm: float) -> float | None:
        """Return run time for a depth, if the field's rate is known."""
        if not self.can_convert_minutes or self.minutes_per_mm is None:
            return None
        return round(mm * self.minutes_per_mm)


Rule = Callable[[Context], list[Advice]]


# ------------------------------------------------------------------- establishment


def rule_establishment(ctx: Context) -> list[Advice]:
    """Run the programme a new lawn has for its first weeks."""
    age = ctx.establishment_age_days
    if age is None or age > programme.SEED_ESTABLISHED_DAYS:
        return []
    out: list[Advice] = []
    if ctx.establishment_method == "sod" and age <= programme.SOD_ROOTING_DAYS:
        out.append(
            Advice(
                "establish_sod_water_daily",
                "irrigation",
                1,
                {"days_left": programme.SOD_ROOTING_DAYS - age, "mm": 4},
                ("sod_not_rooted",),
            )
        )
        out.append(Advice("establish_no_mowing", "mowing", 3, {}, ("sod_not_rooted",)))
    elif ctx.establishment_method in ("seed", "hydroseed"):
        if age <= programme.SEED_GERMINATION_DAYS:
            out.append(
                Advice(
                    "establish_seed_keep_moist",
                    "irrigation",
                    1,
                    {"days_left": programme.SEED_GERMINATION_DAYS - age},
                    ("seed_germinating",),
                )
            )
            out.append(Advice("establish_no_mowing", "mowing", 3, {}, ("seed_germinating",)))
        else:
            out.append(
                Advice(
                    "establish_first_mow_high",
                    "mowing",
                    3,
                    {"height_mm": ctx.mow_height_mm[1]},
                    ("seedlings_rooting",),
                )
            )
    if ctx.days_since_fertilizing is None or ctx.days_since_fertilizing > age:
        starter = programme.FeedWindow("feed_starter", (), 4.0, "starter")
        feed = nutrition.plan(ctx, starter)
        out.append(
            Advice(
                "establish_starter_feed",
                "fertilizing",
                2,
                feed.as_params(),
                ("no_starter_feed", *feed.reasons),
            )
        )
    return out


# ---------------------------------------------------------------------- irrigation


def rule_irrigation(ctx: Context) -> list[Advice]:
    """Deep and infrequent, adjusted to the lawn's record and the forecast's honesty.

    Seed sown into an established lawn does not change this: the turf around the seed still
    has roots at depth and still wants its dawn cycle. Only a lawn that is entirely young
    hands its watering over to the establishment rule.
    """
    if ctx.new_lawn and (
        ctx.establishment_age_days <= programme.SOD_ROOTING_DAYS
        if ctx.establishment_method == "sod"
        else ctx.establishment_age_days <= programme.SEED_GERMINATION_DAYS
    ):
        return []  # establishment rule owns watering for now
    if ctx.phase == "dormant" and not ctx.phenology.heat_stress:
        if ctx.deficit_mm > ctx.taw_mm * 0.8 and ctx.anomalies.dry_spell_days > 21:
            return [
                Advice(
                    "irrigate_dormant_drought",
                    "irrigation",
                    3,
                    {"mm": round(ctx.raw_mm)},
                    ("long_dry_spell", "dormant"),
                )
            ]
        return [Advice("no_irrigation_dormant", "irrigation", 4, {}, ("dormant",))]

    threshold = ctx.raw_mm / ctx.irrigation_factor
    reasons: list[str] = []
    if ctx.deficit_mm < threshold:
        soon = ctx.deficit_mm + ctx.etc_today_mm * 2 >= threshold
        if soon and ctx.expected_rain_72h < 3:
            return [
                Advice(
                    "irrigation_due_soon",
                    "irrigation",
                    3,
                    {"days": 2, "deficit_mm": round(ctx.deficit_mm)},
                    ("deficit_approaching_raw", "no_rain_expected"),
                )
            ]
        return [
            Advice("no_irrigation_needed", "irrigation", 4, {"deficit_mm": round(ctx.deficit_mm)})
        ]

    reasons.append("deficit_past_raw")
    expected = ctx.expected_rain_24h
    if ctx.forecast_rain_24h_mm and expected < ctx.forecast_rain_24h_mm * 0.7:
        reasons.append("forecast_rain_unreliable")
    target = max(0.0, ctx.deficit_mm * ctx.irrigation_factor - expected)
    if target < 3:
        return [
            Advice(
                "hold_irrigation_rain_coming",
                "irrigation",
                3,
                {"expected_mm": round(expected)},
                ("rain_expected_reliable",),
            )
        ]
    if ctx.phenology.heat_stress or ctx.anomalies.hot_days_7d >= 3:
        reasons.append("heat_stress")
    if ctx.anomalies.et_anomaly and ctx.anomalies.et_anomaly >= 1.25:
        reasons.append("high_et_week")
    if ctx.irrigation_factor > 1.05:
        reasons.append("adapted_more_water")
    elif ctx.irrigation_factor < 0.95:
        reasons.append("adapted_less_water")
    params: dict[str, Any] = {"mm": round(target), "deficit_mm": round(ctx.deficit_mm)}
    minutes = ctx.minutes_for(target)
    if minutes is not None:
        params["minutes"] = minutes
    priority = 1 if ctx.deficit_mm >= ctx.raw_mm * 1.3 or ctx.phenology.heat_stress else 2
    return [Advice("irrigate_now", "irrigation", priority, params, tuple(reasons))]


# -------------------------------------------------------------------------- mowing


MOWING_HELD_AFTER_SOWING_DAYS = programme.MOWING_HELD_AFTER_SOWING_DAYS

# And a lawn sown this recently is not sown again, whatever the month plan still says.
RESOWN_WITHIN_DAYS = 30


def recently_sown(ctx: Context) -> bool:
    """Return whether seed went down recently enough that more would be wasted."""
    return ctx.days_since_sowing is not None and ctx.days_since_sowing < RESOWN_WITHIN_DAYS


def mower_held(ctx: Context) -> bool:
    """Return whether the seedlings are still too young for the lawn to be cut at all."""
    if ctx.overseeded:
        return False  # the turf around the seed still grows, and still has to be cut
    return (
        ctx.days_since_sowing is not None and ctx.days_since_sowing < MOWING_HELD_AFTER_SOWING_DAYS
    )


def robot_held(ctx: Context) -> bool:
    """Return whether a robot should stay in its dock while the new seed roots.

    A blade set above the seedlings never touches them: what pulls them out is the wheels,
    going over the same lines again and again. So the lawn is still cut in this fortnight,
    by hand, and the robot waits for the seed to be rooted.
    """
    return (
        ctx.robot_mower
        and ctx.days_since_sowing is not None
        and ctx.days_since_sowing < programme.SEED_GERMINATION_DAYS
    )


def mowing_height(ctx: Context) -> int:
    """Return the height this lawn is to be cut to today.

    One place, because three parts of the engine say it: the day's advice, the week's
    calendar and the month's line. Read from the range the species wants and the mower can
    reach, lifted in heat and shade, dropped for the last cut of the year.
    """
    planned = {op.code for op in ctx.planned("mowing")}
    return programme.cutting_height(
        ctx.mow_height_mm,
        # In shade the leaf needs all the light it can get, and in heat it shades its soil.
        taller=(
            ctx.phase == "summer_stress"
            or "raise_mowing_height" in planned
            or ctx.shaded_fraction >= 0.3
        ),
        lower=ctx.phase == "late_autumn" or "last_mow_lower" in planned,
    )


def rule_mowing(ctx: Context) -> list[Advice]:
    """Follow growth, keep the third rule, go higher in summer and lower for the last cut."""
    if mower_held(ctx):
        return [
            Advice(
                "hold_mowing_after_sowing",
                "mowing",
                1,
                {
                    "days_left": MOWING_HELD_AFTER_SOWING_DAYS - ctx.days_since_sowing,
                    "height_mm": ctx.mow_height_mm[1],
                },
                ("seedlings_too_young_to_cut",),
            )
        ]
    if (
        ctx.establishment_age_days is not None
        and ctx.establishment_age_days <= programme.SOD_ROOTING_DAYS
    ):
        return []
    # The height first, because the interval follows from it: the third rule lets the grass
    # reach half again the height it is kept at, so a lawn cut low comes round sooner.
    height = mowing_height(ctx)
    interval = programme.mow_interval_days(ctx.phase, height)
    if interval is None:
        return [Advice("no_mowing_dormant", "mowing", 4, {}, ("dormant",))]
    since = ctx.days_since_mowing
    stressed = ctx.phenology.heat_stress or ctx.deficit_mm > ctx.raw_mm * 1.2
    stress = "heat_stress" if ctx.phenology.heat_stress else "drought_stress"
    # Stress puts a cut off; it does not cancel one. Heat is already in the interval, since
    # the summer phase grows slowly and the third rule stretches with it, and a lawn that has
    # nevertheless reached half again its height has to be cut whatever the weather: waiting
    # out a fortnight of 30 °C means taking two thirds of the leaf off at the end of it,
    # which is the scalping the rule exists to prevent. So the delay holds only while the
    # grass is still inside its allowance; past that the cut is asked for, high and late in
    # the day, and the advice says what it is a compromise with.
    if stressed and since is not None and since < interval:
        return [
            Advice(
                "delay_mowing_stress",
                "mowing",
                3,
                {"height_mm": ctx.mow_height_mm[1], "next_in_days": interval - since},
                (stress,),
            )
        ]
    if robot_held(ctx):
        # The lawn is still cut, and cut on time, but by hand: it is the wheels that pull
        # seedlings out, not the blade, which passes well above them.
        return [
            Advice(
                "mow_by_hand_while_seed_roots",
                "mowing",
                2,
                {
                    "days_left": programme.SEED_GERMINATION_DAYS - ctx.days_since_sowing,
                    "height_mm": height,
                },
                ("robot_wheels_tear_seedlings", "old_grass_shades_the_seed"),
            )
        ]
    # Under stress the cut is made at the top of what the mower can reach: the longer leaf
    # shades its own soil, which is the whole reason the height goes up in the heat.
    if stressed:
        height = ctx.mow_height_mm[1]
    if since is None:
        return [
            Advice(
                "mow_soon",
                "mowing",
                3,
                {"height_mm": height},
                ("no_mowing_recorded", *((stress,) if stressed else ())),
            )
        ]
    if since >= interval * 1.5:
        return [
            Advice(
                "mow_now_third_rule",
                "mowing",
                2,
                {"days": since, "height_mm": height},
                ("mowing_overdue", *((stress,) if stressed else ())),
            )
        ]
    if since >= interval:
        return [
            Advice(
                "mow_soon",
                "mowing",
                3,
                {"days": since, "height_mm": height},
                ("interval_reached", *((stress,) if stressed else ())),
            )
        ]
    return [
        Advice(
            "mowing_height", "mowing", 4, {"height_mm": height, "next_in_days": interval - since}
        )
    ]


# --------------------------------------------------------------------- fertilizing


def rule_fertilizing(ctx: Context) -> list[Advice]:
    """Feed what the month plans, when the weather allows. The class is fixed for the month."""
    if (
        ctx.establishment_age_days is not None
        and ctx.establishment_age_days <= programme.SEED_ESTABLISHED_DAYS
    ):
        return []
    planned = ctx.planned("fertilizing")
    if not planned:
        if ctx.days_since_fertilizing is not None and ctx.days_since_fertilizing < 28:
            return [
                Advice(
                    "feed_recently_done",
                    "fertilizing",
                    4,
                    {"days": ctx.days_since_fertilizing, "n_60d": round(ctx.nitrogen_60d_g_m2, 1)},
                )
            ]
        return []
    op = planned[0]
    soil = ctx.phenology.soil_temperature_c
    window = next((w for w in programme.feeds_for(ctx.cool_season) if w.code == op.code), None)
    blockers: list[str] = []
    if ctx.phenology.heat_stress or (
        ctx.forecast_tmax_3d is not None and ctx.forecast_tmax_3d >= 30
    ):
        blockers.append("heat_stress")
    if ctx.deficit_mm > ctx.raw_mm:
        blockers.append("drought_stress")
    if ctx.expected_rain_72h >= 20:
        blockers.append("heavy_rain_forecast")
    if window is not None and soil is not None:
        if window.soil_min_c is not None and soil < window.soil_min_c:
            blockers.append("soil_too_cold")
        if window.soil_max_c is not None and soil > window.soil_max_c:
            blockers.append("soil_too_warm")
    if "fungus" in ctx.issues_30d and op.params.get("role") in ("growth", "greening"):
        blockers.append("disease_present")
    if ctx.days_since_fertilizing is not None and ctx.days_since_fertilizing < 21:
        blockers.append("fed_less_than_three_weeks_ago")
    params = {"window": op.code, **op.params}
    if blockers:
        return [Advice("feed_wait", "fertilizing", 3, params, tuple(blockers))]
    reasons = ["planned_this_month", *op.basis, *op.tailoring]
    if 3 <= ctx.expected_rain_72h < 15:
        reasons.append("rain_will_water_in")
    if "carried_over_from_last_month" in op.tailoring:
        reasons.append("carried_over_from_last_month")
    return [Advice("feed_now", "fertilizing", 2, params, tuple(dict.fromkeys(reasons)))]


# ------------------------------------------------------------------------- seeding


def rule_seeding(ctx: Context) -> list[Advice]:
    """Overseed in the planned month, when the soil is in range and there is time before frost."""
    if (
        ctx.establishment_age_days is not None
        and ctx.establishment_age_days <= programme.SEED_ESTABLISHED_DAYS
    ):
        return []
    planned = ctx.planned("seeding")
    if not planned:
        return []
    op = planned[0]
    if op.code == "prepare_overseeding":
        return [
            Advice(
                "prepare_overseeding",
                "seeding",
                3,
                {"height_mm": ctx.mow_height_mm[0]},
                ("planned_this_month", *op.basis, *op.tailoring),
            )
        ]
    if recently_sown(ctx):
        return []
    limits = programme.thresholds_for(ctx.cool_season)
    soil = ctx.phenology.soil_temperature_c
    params: dict[str, Any] = {
        "soil_c": soil,
        "days_to_frost": ctx.phenology.days_to_first_frost,
        "starter_feed": op.params.get("starter_feed"),
        "optional": op.optional,
        "seed_mix": "shade_tolerant_fine_fescue" if ctx.shaded_fraction >= 0.3 else "sun_mix",
    }
    blockers: list[str] = []
    if soil is not None and soil > limits["seed_max_c"]:
        blockers.append("soil_too_warm")
    if soil is not None and soil < limits["seed_min_c"]:
        blockers.append("soil_too_cold")
    if ctx.phenology.heat_stress:
        blockers.append("heat_stress")
    if (
        ctx.phenology.days_to_first_frost is not None
        and ctx.phenology.days_to_first_frost < limits["seed_days_before_frost"]
    ):
        blockers.append("too_close_to_frost")
    if ctx.expected_rain_72h >= 25:
        blockers.append("heavy_rain_forecast")
    if blockers:
        return [Advice("overseed_wait", "seeding", 3, params, tuple(blockers))]
    reasons = ["planned_this_month", "soil_temperature_in_range", *op.basis, *op.tailoring]
    return [
        Advice(
            "overseed_now",
            "seeding",
            2 if not op.optional else 3,
            params,
            tuple(dict.fromkeys(reasons)),
        )
    ]


# -------------------------------------------------------------------------- weeds


WEED_ADVICE = {
    "weed_control_broadleaf": "weed_control_broadleaf_now",
    "weed_control_grassy": "weed_control_grassy_now",
    "moss_control": "moss_control_now",
}


def rule_weeds(ctx: Context) -> list[Advice]:
    """Herbicides in their planned month, on growing grass, dry leaves and mild days."""
    out: list[Advice] = []
    for op in ctx.planned("weeds"):
        if op.code == "pre_emergent":
            low, high = programme.PRE_EMERGENT_GDD
            gdd = ctx.phenology.gdd_base0
            if gdd < low:
                out.append(
                    Advice(
                        "pre_emergent_wait",
                        "weeds",
                        4,
                        {"gdd": round(gdd), "gdd_window": [low, high]},
                        ("gdd_below_window",),
                    )
                )
            elif gdd <= high:
                out.append(
                    Advice(
                        "pre_emergent_window",
                        "weeds",
                        2 if not op.optional else 3,
                        {"gdd": round(gdd), "soil_c": ctx.phenology.soil_temperature_c},
                        ("gdd_window", *op.basis, *op.tailoring),
                    )
                )
            continue
        code = WEED_ADVICE.get(op.code)
        if code is None:
            continue
        blockers: list[str] = []
        if ctx.days_since_mowing is not None and ctx.days_since_mowing < 2:
            blockers.append("just_mowed")
        if ctx.phase == "dormant" and op.code != "moss_control":
            blockers.append("grass_not_growing")
        if ctx.phenology.heat_stress or (
            ctx.forecast_tmax_3d is not None
            and ctx.forecast_tmax_3d >= 28
            and op.code != "moss_control"
        ):
            blockers.append("heat_stress")
        if ctx.expected_rain_24h >= 3:
            blockers.append("rain_within_24h")
        if ctx.deficit_mm > ctx.raw_mm:
            blockers.append("drought_stress")
        params = {"operation": op.code, "optional": op.optional}
        if blockers:
            out.append(Advice("weed_control_wait", "weeds", 3, params, tuple(blockers)))
        else:
            out.append(
                Advice(
                    code,
                    "weeds",
                    3 if op.optional else 2,
                    params,
                    ("planned_this_month", *op.basis, *op.tailoring),
                )
            )
    return out


# ------------------------------------------------------------------------ disease


def rule_disease(ctx: Context) -> list[Advice]:
    """Two validated models with two-day hysteresis, and the planned preventive treatment."""
    out: list[Advice] = []
    p = ctx.dollar_spot_probability
    dollar_today = p is not None and p >= disease.DOLLAR_SPOT_ACTION_PROBABILITY
    if dollar_today and "dollar_spot" in ctx.disease_risk_yesterday:
        reasons = ["smith_kerns_threshold_two_days"]
        if ctx.nitrogen_60d_g_m2 < 1.5:
            reasons.append("low_nitrogen_favours_dollar_spot")
        out.append(
            Advice(
                "dollar_spot_risk", "disease", 2, {"probability": round(p * 100)}, tuple(reasons)
            )
        )
    e = ctx.brown_patch_index
    brown_today = e is not None and e >= disease.BROWN_PATCH_WARNING_INDEX
    if brown_today and "brown_patch" in ctx.disease_risk_yesterday:
        reasons = ["fidanza_threshold_two_days"]
        if ctx.nitrogen_60d_g_m2 > 4:
            reasons.append("high_nitrogen_favours_brown_patch")
        if ctx.forecast_tmin_3d is not None and ctx.forecast_tmin_3d >= 20:
            reasons.append("warm_nights_ahead")
        out.append(Advice("brown_patch_risk", "disease", 2, {"index": round(e, 1)}, tuple(reasons)))
    if "fungus" in ctx.issues_30d:
        out.append(Advice("fungus_seen_measures", "disease", 2, {}, ("fungus_reported",)))
    shade_pressure = ctx.shaded_fraction >= 0.3 and (
        ctx.dollar_spot_probability is not None and ctx.dollar_spot_probability >= 0.12
    )
    for op in ctx.planned("disease"):
        # Brown patches are how a person describes what the models predict, and extension
        # guidance is to confirm a model warning by walking the lawn. Seeing them counts.
        seen = bool({"fungus", "brown_patches"} & ctx.issues_30d)
        pressure = dollar_today or brown_today or shade_pressure or seen
        if pressure or (ctx.forecast_tmin_3d is not None and ctx.forecast_tmin_3d >= 18):
            out.append(
                Advice(
                    "disease_preventive_now",
                    "disease",
                    2,
                    {"optional": op.optional},
                    ("planned_this_month", *op.basis, *op.tailoring),
                )
            )
    return out


def disease_flags_today(ctx: Context) -> set[str]:
    """Return which models are over threshold today, for tomorrow's hysteresis."""
    flags: set[str] = set()
    if (
        ctx.dollar_spot_probability is not None
        and ctx.dollar_spot_probability >= disease.DOLLAR_SPOT_ACTION_PROBABILITY
    ):
        flags.add("dollar_spot")
    if (
        ctx.brown_patch_index is not None
        and ctx.brown_patch_index >= disease.BROWN_PATCH_WARNING_INDEX
    ):
        flags.add("brown_patch")
    return flags


# ------------------------------------------------------------------- aeration etc.


SOIL_WORK_ADVICE = {
    "aeration_spring": "aerate_now",
    "aeration_autumn": "aerate_now",
    "scarify_dethatch": "scarify_now",
    "top_dressing": "top_dress_now",
}


def rule_soil_work(ctx: Context) -> list[Advice]:
    """Aerate, scarify and top dress in their planned month, when the grass can recover."""
    out: list[Advice] = []
    for op in ctx.planned("aeration"):
        code = SOIL_WORK_ADVICE.get(op.code)
        if code is None:
            continue
        blockers: list[str] = []
        if not ctx.growing:
            blockers.append("grass_not_growing")
        if ctx.phenology.heat_stress:
            blockers.append("heat_stress")
        if ctx.deficit_mm > ctx.raw_mm * 0.6:
            blockers.append("soil_too_dry")
        if (
            ctx.anomalies.rain_30d_mm > 0
            and ctx.deficit_mm < 1
            and ctx.forecast_rain_24h_mm
            and ctx.forecast_rain_24h_mm > 10
        ):
            blockers.append("soil_saturated")
        params = {"operation": op.code, "optional": op.optional}
        if blockers:
            out.append(
                Advice(
                    "soil_work_wait", "aeration", 4 if op.optional else 3, params, tuple(blockers)
                )
            )
        else:
            out.append(
                Advice(
                    code, "aeration", 3, params, ("planned_this_month", *op.basis, *op.tailoring)
                )
            )
    return out


# --------------------------------------------------------------------- germination


def rule_germination(ctx: Context) -> list[Advice]:
    """Seed sown here needs the surface damp, whatever the deep cycle is doing."""
    if not ctx.germinating or ctx.new_lawn:
        return []  # a whole young lawn is the establishment rule's business
    if "seedbed_watering" in ctx.done_today:
        # Pressing Done wrote it in the diary and the line went on asking for it, which is a
        # button that does nothing as far as anybody can see. The day's passes are one job.
        return []
    left = programme.SEED_GERMINATION_DAYS - (ctx.days_since_sowing or 0)
    return [
        Advice(
            "germination_watering",
            "irrigation",
            1,
            {"times": 3, "mm": 2, "days_left": max(1, left)},
            ("seed_germinating", "keep_the_seedbed_damp"),
        )
    ]


# ------------------------------------------------------------------------- leaves


def rule_leaves(ctx: Context) -> list[Advice]:
    """Leaves left on the grass smother it and breed disease; clear them weekly in the fall."""
    out: list[Advice] = []
    for op in ctx.planned("general"):
        if op.code == "clear_leaves":
            out.append(
                Advice(
                    "clear_leaves",
                    "general",
                    3,
                    {},
                    ("planned_this_month", *op.basis, *op.tailoring),
                )
            )
    return out


# ------------------------------------------------------------------ status feedback


def rule_status(ctx: Context) -> list[Advice]:
    """Read what the tracked condition, on its own, says."""
    score = ctx.status_score
    if score is None:
        return [Advice("record_status_reminder", "general", 4, {})]
    if score < 2.0:
        reasons: list[str] = []
        if ctx.deficit_mm > ctx.raw_mm:
            reasons.append("under_watered")
        elif ctx.anomalies.rain_30d_mm > 120:
            reasons.append("waterlogged_month")
        if ctx.nitrogen_60d_g_m2 < 1.0 and ctx.growing:
            reasons.append("under_fed")
        if ctx.phenology.heat_stress:
            reasons.append("heat_stress")
        if ctx.shaded_fraction >= 0.3 and {"moss", "thin", "bare_spots"} & ctx.issues_30d:
            reasons.append("shade_thins_turf")
        if "brown_patches" in ctx.issues_30d:
            reasons.append("brown_patches_seen")
        return [
            Advice("lawn_poor_diagnosis", "general", 2, {"score": round(score, 1)}, tuple(reasons))
        ]
    return []


ADVICE_CODES: tuple[str, ...] = (
    "establish_sod_water_daily",
    "establish_no_mowing",
    "establish_seed_keep_moist",
    "establish_first_mow_high",
    "establish_starter_feed",
    "irrigate_dormant_drought",
    "no_irrigation_dormant",
    "irrigation_due_soon",
    "no_irrigation_needed",
    "hold_irrigation_rain_coming",
    "irrigate_now",
    "no_mowing_dormant",
    "delay_mowing_stress",
    "mow_soon",
    "mow_now_third_rule",
    "mowing_height",
    "hold_mowing_after_sowing",
    "mow_by_hand_while_seed_roots",
    "feed_recently_done",
    "feed_wait",
    "feed_now",
    "prepare_overseeding",
    "overseed_wait",
    "overseed_now",
    "pre_emergent_wait",
    "pre_emergent_window",
    "weed_control_wait",
    "weed_control_broadleaf_now",
    "weed_control_grassy_now",
    "moss_control_now",
    "dollar_spot_risk",
    "brown_patch_risk",
    "fungus_seen_measures",
    "disease_preventive_now",
    "soil_work_wait",
    "aerate_now",
    "scarify_now",
    "top_dress_now",
    "germination_watering",
    "clear_leaves",
    "record_status_reminder",
    "lawn_poor_diagnosis",
)

RULES: tuple[Rule, ...] = (
    rule_establishment,
    rule_irrigation,
    rule_mowing,
    rule_fertilizing,
    rule_seeding,
    rule_weeds,
    rule_disease,
    rule_soil_work,
    rule_germination,
    rule_leaves,
    rule_status,
)


def evaluate(ctx: Context) -> list[Advice]:
    """Return every rule's advice, highest priority first, stable within a priority."""
    out: list[Advice] = []
    for rule in RULES:
        out.extend(rule(ctx))
    return sorted(out, key=lambda a: a.priority)
