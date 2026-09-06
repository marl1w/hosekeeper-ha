"""The year's plan, one month at a time: what to do, and why, decided once a month.

Advice that changes every day is advice nobody follows. The operations — a feed, an
overseeding, a preventive treatment, an aeration — are therefore planned by month for the
twelve months ahead, from the programme the research supports, and then tailored with what
the diary knows about this lawn: its age, its soil, the problems seen, how the forecast has
behaved, what has already been done. The daily rules only decide *when inside the month* an
operation should happen and what is blocking it; they do not reshuffle the plan.

Each operation carries two kinds of reasons: `basis`, the research it rests on, and
`tailoring`, the data about this lawn that shaped it. Both are shown, so the plan reads as
"the programme says X; your lawn says Y".
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
from typing import TYPE_CHECKING, Any

from . import nutrition
from .knowledge import programme

if TYPE_CHECKING:
    from .rules import Context

PLAN_MONTHS = 12


@dataclass(frozen=True, slots=True)
class Operation:
    """One planned thing for one month."""

    month: str
    """YYYY-MM."""
    code: str
    category: str
    optional: bool = False
    """True when the operation is only needed if the lawn asks for it."""
    params: dict[str, Any] = field(default_factory=dict)
    basis: tuple[str, ...] = ()
    tailoring: tuple[str, ...] = ()

    def as_dict(self, status: str) -> dict[str, Any]:
        """Return a JSON-friendly shape with the status derived from the diary."""
        return {
            "month": self.month,
            "code": self.code,
            "category": self.category,
            "optional": self.optional,
            "status": status,
            "params": self.params,
            "basis": list(self.basis),
            "tailoring": list(self.tailoring),
        }


def _days_left_in(today: dt.date, year: int, month: int) -> int:
    """Return how many days of that month are still to come, today included."""
    first = dt.date(year, month, 1)
    next_month = dt.date(year + (month == 12), month % 12 + 1, 1)
    return (next_month - max(today, first)).days


def _month_key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def months_ahead(today: dt.date, count: int = PLAN_MONTHS) -> list[tuple[int, int]]:
    """Return (year, month) pairs from this month on."""
    out: list[tuple[int, int]] = []
    year, month = today.year, today.month
    for _ in range(count):
        out.append((year, month))
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return out


def _cool_season_year(
    ctx: Context,
) -> dict[int, list[tuple[str, str, bool, dict[str, Any], tuple[str, ...]]]]:
    """Return the cool-season programme by northern month.

    Tuples are (code, category, optional, params, basis). Tailoring is applied afterwards.
    The skeleton is the Italian professional calendar (see docs/knowledge.md); the research
    codes say why each month holds what it holds.
    """
    pre = {"gdd_window": list(programme.PRE_EMERGENT_GDD)}
    return {
        1: [("winter_rest", "general", False, {}, ("research_dormant_below_6c",))],
        2: [("moss_control", "weeds", True, {}, ("research_iron_moss_late_winter",))],
        3: [
            (
                "feed_march_starter",
                "fertilizing",
                False,
                {},
                ("pro_programme_march_starter", "research_spring_phosphorus_roots"),
            ),
            ("pre_emergent", "weeds", True, pre, ("research_crabgrass_gdd_140_280",)),
            ("first_mow", "mowing", False, {"soil_min_c": 8}, ("research_greenup_soil_8c",)),
        ],
        4: [
            ("mow_routine", "mowing", False, {}, ("research_third_rule",)),
            (
                "feed_april_greening",
                "fertilizing",
                False,
                {},
                ("pro_programme_spring_greening", "research_two_growth_peaks"),
            ),
            ("aeration_spring", "aeration", True, {}, ("research_aerate_when_growing",)),
        ],
        5: [
            (
                "weed_control_broadleaf",
                "weeds",
                False,
                {},
                ("pro_programme_broadleaf_may", "research_post_emergent_active_growth"),
            ),
            (
                "feed_may_greening",
                "fertilizing",
                False,
                {},
                ("pro_programme_spring_greening", "research_two_growth_peaks"),
            ),
            ("raise_mowing_height", "mowing", False, {}, ("research_summer_height_shades_soil",)),
        ],
        6: [
            ("mow_routine", "mowing", False, {}, ("research_summer_height_shades_soil",)),
            (
                "feed_june_summer",
                "fertilizing",
                False,
                {},
                (
                    "pro_programme_summer_potassium",
                    "research_potassium_before_summer",
                    "research_coated_nitrogen_no_disease_flush",
                ),
            ),
            (
                "disease_preventive",
                "disease",
                True,
                {},
                ("research_brown_patch_warm_nights", "research_smith_kerns_20pct"),
            ),
            (
                "irrigation_deep_infrequent",
                "irrigation",
                False,
                {},
                ("research_deep_infrequent_roots",),
            ),
        ],
        7: [
            ("mow_routine", "mowing", False, {}, ("research_summer_height_shades_soil",)),
            (
                "feed_july_summer",
                "fertilizing",
                False,
                {},
                ("pro_programme_summer_potassium", "research_coated_nitrogen_no_disease_flush"),
            ),
            (
                "weed_control_grassy",
                "weeds",
                False,
                {},
                ("pro_programme_grassy_weeds_july", "research_crabgrass_post_emergent_young"),
            ),
            ("summer_watch", "general", False, {}, ("research_cool_season_heat_stress_30c",)),
        ],
        8: [
            ("mow_routine", "mowing", False, {}, ("research_summer_height_shades_soil",)),
            (
                "summer_rest",
                "general",
                False,
                {},
                ("pro_programme_nothing_in_august", "research_cool_season_heat_stress_30c"),
            ),
            ("prepare_overseeding", "seeding", True, {}, ("research_autumn_seeding_window",)),
        ],
        9: [
            ("mow_routine", "mowing", False, {}, ("research_third_rule",)),
            (
                "overseed",
                "seeding",
                False,
                {"soil_min_c": 12, "soil_max_c": 22},
                (
                    "pro_programme_september_overseed",
                    "research_autumn_seeding_window",
                    "research_45_days_before_frost",
                ),
            ),
            ("aeration_autumn", "aeration", True, {}, ("research_aerate_when_growing",)),
        ],
        10: [
            ("mow_routine", "mowing", False, {}, ("research_third_rule",)),
            ("clear_leaves", "general", True, {}, ("research_leaf_cover_smothers_turf",)),
            (
                "weed_control_broadleaf",
                "weeds",
                False,
                {},
                ("pro_programme_broadleaf_october", "research_autumn_broadleaf_translocation"),
            ),
            (
                "feed_october_autumn",
                "fertilizing",
                False,
                {},
                ("pro_programme_autumn_potassium", "research_late_autumn_potassium_hardiness"),
            ),
            ("top_dressing", "aeration", True, {}, ("research_topdress_after_aeration",)),
        ],
        11: [
            ("clear_leaves", "general", True, {}, ("research_leaf_cover_smothers_turf",)),
            (
                "feed_november_autumn",
                "fertilizing",
                False,
                {},
                ("pro_programme_autumn_potassium", "research_late_autumn_potassium_hardiness"),
            ),
            ("last_mow_lower", "mowing", False, {}, ("research_last_cut_lower_snow_mould",)),
        ],
        12: [("winter_rest", "general", False, {}, ("research_dormant_below_6c",))],
    }


def _warm_season_year(
    ctx: Context,
) -> dict[int, list[tuple[str, str, bool, dict[str, Any], tuple[str, ...]]]]:
    return {
        1: [("winter_rest", "general", False, {}, ("research_warm_season_dormant_15c",))],
        2: [("winter_rest", "general", False, {}, ("research_warm_season_dormant_15c",))],
        3: [
            (
                "pre_emergent",
                "weeds",
                True,
                {"gdd_window": list(programme.PRE_EMERGENT_GDD)},
                ("research_crabgrass_gdd_140_280",),
            )
        ],
        4: [
            ("mow_routine", "mowing", False, {}, ("research_third_rule",)),
            ("scarify_dethatch", "aeration", True, {}, ("research_warm_season_dethatch_greenup",)),
            ("feed_spring_start", "fertilizing", False, {}, ("research_warm_season_feed_in_heat",)),
        ],
        5: [
            ("mow_routine", "mowing", False, {}, ("research_third_rule",)),
            ("overseed", "seeding", True, {"soil_min_c": 18}, ("research_warm_season_seed_18c",)),
        ],
        6: [
            ("mow_routine", "mowing", False, {}, ("research_third_rule",)),
            ("feed_late_spring", "fertilizing", False, {}, ("research_warm_season_feed_in_heat",)),
        ],
        7: [
            ("mow_routine", "mowing", False, {}, ("research_third_rule",)),
            (
                "feed_summer_stress",
                "fertilizing",
                False,
                {},
                ("research_warm_season_feed_in_heat",),
            ),
        ],
        8: [
            ("mow_routine", "mowing", False, {}, ("research_third_rule",)),
            ("aeration_autumn", "aeration", True, {}, ("research_aerate_when_growing",)),
        ],
        9: [
            ("mow_routine", "mowing", False, {}, ("research_third_rule",)),
            (
                "feed_early_autumn",
                "fertilizing",
                False,
                {},
                ("research_potassium_before_dormancy",),
            ),
        ],
        10: [
            ("last_mow_lower", "mowing", False, {}, ("research_last_cut_lower_snow_mould",)),
            ("feed_late_autumn", "fertilizing", False, {}, ("research_potassium_before_dormancy",)),
        ],
        11: [("winter_rest", "general", False, {}, ("research_warm_season_dormant_15c",))],
        12: [("winter_rest", "general", False, {}, ("research_warm_season_dormant_15c",))],
    }


def build(ctx: Context) -> list[Operation]:
    """Return the plan for the twelve months from this one, tailored to the lawn."""
    programme_year = _cool_season_year(ctx) if ctx.cool_season else _warm_season_year(ctx)
    needs_seed = bool({"bare_spots", "thin"} & ctx.issues_30d) or (
        ctx.status_score is not None and ctx.status_score < 2.0
    )
    out: list[Operation] = []

    for year, month in months_ahead(ctx.today):
        folded = programme.fold_month(month, ctx.northern_hemisphere)
        key = _month_key(year, month)
        # The lawn is a month older every time round: a herbicide withheld from this
        # autumn's seedlings is not withheld from the same lawn next autumn.
        then = _at_month(ctx, year, month)
        young = (
            then.establishment_age_days is not None
            and then.establishment_age_days < programme.FIRST_YEAR_DAYS
        )
        for code, category, optional, params, basis in programme_year.get(folded, []):
            tailoring: list[str] = []
            params = dict(params)

            if category == "fertilizing":
                window = next(
                    (w for w in programme.feeds_for(ctx.cool_season) if w.code == code), None
                )
                if window is not None:
                    feed = nutrition.plan(then, window)
                    params.update(feed.as_params())
                    tailoring.extend(r for r in feed.reasons if not r.startswith("window_"))

            if code in ("overseed", "prepare_overseeding"):
                if needs_seed:
                    tailoring.append(
                        "bare_or_thin_areas_seen"
                        if {"bare_spots", "thin"} & ctx.issues_30d
                        else "condition_poor"
                    )
                    optional = False
                elif young:
                    continue  # a lawn in its first year is not overseeded
                elif (
                    code == "overseed" and ctx.status_score is not None and ctx.status_score >= 3.5
                ):
                    # Rated excellent all fortnight: the yearly overseed is optional.
                    optional = True
                    tailoring.append("lawn_dense_overseed_optional")
                if code == "overseed":
                    params["starter_feed"] = nutrition.plan(
                        then,
                        programme.FeedWindow("feed_with_overseed", (month,), 4.0, "starter"),
                    ).as_params()
                    if ctx.phenology.days_to_first_frost is not None:
                        params["days_to_first_frost"] = ctx.phenology.days_to_first_frost

            if code == "pre_emergent":
                if "weeds" in ctx.issues_30d:
                    tailoring.append("weeds_seen")
                    optional = False
                elif young:
                    continue  # pre-emergents stop grass seed too

            if code == "moss_control":
                if "moss" in ctx.issues_30d:
                    tailoring.append("moss_seen")
                    optional = False
                elif ctx.shaded_fraction >= 0.3:
                    tailoring.append("shade_favours_moss")
                else:
                    continue

            if code == "clear_leaves":
                if not ctx.deciduous_trees:
                    continue
                tailoring.append("deciduous_trees_on_the_lawn")
                optional = False

            if code == "overseed" and ctx.shaded_fraction >= 0.3:
                tailoring.append("shade_tolerant_mix")

            if code in ("weed_control_broadleaf", "weed_control_grassy"):
                if "weeds" in ctx.issues_30d:
                    tailoring.append("weeds_seen")
                elif ctx.status_score is not None and ctx.status_score >= 3.5:
                    # No weeds reported and a dense lawn: the herbicide pass is optional.
                    optional = True
                    tailoring.append("no_weeds_reported_optional")
                # Seedlings do not tolerate a selective herbicide, and the wait is counted
                # from the sowing, not from the lawn's birthday: a lawn overseeded in
                # September is sprayable by the middle of October, which is what the
                # professional calendar does. Sod is mature grass and waits only to root.
                since_seed = then.days_since_sowing
                since_laid = then.establishment_age_days
                laid_wait = (
                    programme.SOD_ROOTING_DAYS
                    if ctx.establishment_method == "sod"
                    else programme.HERBICIDE_AFTER_SOWING_DAYS
                )
                if since_seed is not None and since_seed < programme.HERBICIDE_AFTER_SOWING_DAYS:
                    continue
                if since_laid is not None and since_laid < laid_wait:
                    continue
                if (
                    since_seed is not None
                    and since_seed < 2 * programme.HERBICIDE_AFTER_SOWING_DAYS
                ):
                    tailoring.append("young_grass_spot_treat")

            if code == "disease_preventive":
                pressure = (ctx.dollar_spot_probability or 0) >= 0.2 or (
                    ctx.brown_patch_index is not None and ctx.brown_patch_index >= 6
                )
                if "fungus" in ctx.issues_30d:
                    tailoring.append("fungus_history")
                    optional = False
                elif pressure:
                    tailoring.append("disease_pressure_measured")
                    optional = False
                else:
                    continue

            if code in ("aeration_spring", "aeration_autumn", "top_dressing", "scarify_dethatch"):
                compaction = {"moss", "thatch"} & ctx.issues_30d
                if compaction:
                    tailoring.append("compaction_signs")
                    optional = False
                elif young:
                    continue
                if code == "aeration_spring" and not compaction:
                    continue  # once a year is enough for a home lawn: autumn

            if category == "mowing":
                # What the month asks for between the milestones: a height and how often.
                # Without it the plan reads as though the grass stops growing in April.
                # A lawn sown from bare soil is not cut at all for three weeks, so a month
                # spent waiting for it carries no mowing line. A lawn that was overseeded
                # keeps every one of them: the turf around the seed goes on growing, and
                # left uncut it shades the seedlings out.
                held = then.days_since_sowing
                if (
                    code == "mow_routine"
                    and held is not None
                    and held < programme.MOWING_HELD_AFTER_SOWING_DAYS
                    and not then.overseeded
                ):
                    continue
                phase = programme.NOMINAL_PHASE[folded]
                # While the new seed roots the cut is made by hand, and the month says so.
                #
                # But a fortnight of it does not make a month of it. A line describes how the
                # month is cut, and calling the whole of September a hand-mown month because
                # its first week is leaves the plan disagreeing with itself: one lawn read as
                # hand-mown and the one beside it as the robot's, on the same interval at the
                # same height, for a difference that is over by the middle of the month. The
                # month keeps the machine that cuts most of it; the days the robot is held
                # off are the day's own advice, which counts them down.
                left = (
                    None
                    if not ctx.robot_mower or then.days_since_sowing is None
                    else programme.SEED_GERMINATION_DAYS - then.days_since_sowing
                )
                robot_waiting = left is not None and left * 2 >= _days_left_in(
                    ctx.today, year, month
                )
                if left is not None and left > 0 and code == "mow_routine":
                    tailoring.append("robot_wheels_tear_seedlings")
                robot = ctx.robot_mower and code == "mow_routine" and not robot_waiting
                shaded = ctx.shaded_fraction >= 0.3
                taller = phase == "summer_stress" or code == "raise_mowing_height"
                if shaded and not taller and code != "last_mow_lower":
                    tailoring.append("shade_needs_leaf")
                height = programme.cutting_height(
                    ctx.mow_height_mm,
                    taller=taller or shaded,
                    lower=code == "last_mow_lower",
                )
                # A robot keeps up with growth rather than keeping the third rule, so its
                # cadence is the season's alone; a hand mower's follows the height it cuts to.
                interval = (
                    programme.robot_pass_days(phase, height, ctx.robot_cadence)
                    if robot
                    else programme.mow_interval_days(phase, height)
                )
                if interval is None:
                    continue
                if robot:
                    # "Every 1 days" is not a sentence anybody says.
                    code = "mow_routine_robot_daily" if interval == 1 else "mow_routine_robot"
                params.setdefault("height_mm", height)
                params.setdefault("interval_days", interval)

            if code == "irrigation_deep_infrequent":
                if ctx.soil_type in ("sandy", "sandy_loam"):
                    tailoring.append("sandy_soil_shorter_cycles")
                if ctx.skill.trusted and ctx.skill.rain_hit_rate < 0.6:
                    tailoring.append("forecast_rain_unreliable_here")

            if code == "summer_watch" and ctx.anomalies.hot_days_7d >= 3:
                tailoring.append("heat_already_here")

            out.append(
                Operation(
                    key, code, category, optional, params, basis, tuple(dict.fromkeys(tailoring))
                )
            )

    # Seed that went down this month wants feeding, and the programme has no line for it.
    #
    # A starter went out with the overseeding as one of its parameters, which was fine while
    # the overseeding was still to do and vanished with it the moment it was ticked off. The
    # next feed in the programme is October's, potassium to harden the turf for winter, which
    # is the wrong thing for a seedling trying to put a root down. So a sowing asks for its
    # own feed, in its own month, until the ordinary programme has one of its own.
    sown = ctx.days_since_sowing
    current = _month_key(ctx.today.year, ctx.today.month)
    fed_since_sowing = ctx.days_since_fertilizing is not None and (
        sown is not None and ctx.days_since_fertilizing <= sown
    )
    if (
        sown is not None
        and sown <= programme.STARTER_AFTER_SOWING_DAYS
        and not fed_since_sowing
        and not any(op.month == current and op.category == "fertilizing" for op in out)
    ):
        starter = nutrition.plan(
            ctx, programme.FeedWindow("feed_after_seeding", (), 4.0, "starter")
        )
        out.append(
            Operation(
                current,
                "feed_after_seeding",
                "fertilizing",
                False,
                starter.as_params(),
                ("research_starter_feed_roots_seedlings",),
                ("seedlings_rooting",),
            )
        )
    return out


def _at_month(ctx: Context, year: int, month: int) -> Context:
    """Return the context as the nutrition module should see it in a future month.

    The lawn ages with the calendar. Judging next April on the lawn's age today is how a
    plan ends up prescribing a starter fertilizer for every feed of the coming year, because
    the turf happened to be three months old when the plan was drawn.
    """
    from dataclasses import replace

    if (year, month) == (ctx.today.year, ctx.today.month):
        return ctx
    ahead = (dt.date(year, month, 15) - ctx.today).days
    return replace(
        ctx,
        today=dt.date(year, month, 15),
        forecast_tmax_3d=None,
        establishment_age_days=(
            None if ctx.establishment_age_days is None else ctx.establishment_age_days + ahead
        ),
        days_since_sowing=(
            None if ctx.days_since_sowing is None else ctx.days_since_sowing + ahead
        ),
    )


# ------------------------------------------------------------------- status from the diary

DONE_BY: dict[str, tuple[str, ...]] = {
    "fertilizing": ("fertilizing",),
    "seeding": ("sowing",),
    "aeration": ("aeration", "scarifying", "top_dressing"),
    "weeds": ("weeding",),
    "general": ("leaf_clearing",),
    "disease": ("treatment",),
    "mowing": ("mowing",),
}


# Operations that last the month rather than happening once in it. Mowing again next week
# does not undo the fact that a routine is a routine: one cut is not a month of cutting, and
# a plan that ticks it off leaves the month looking as though the grass had stopped growing.
ONGOING_CODES = frozenset({"mow_routine", "mow_routine_robot", "mow_routine_robot_daily"})


# A job done in the run-up to the month it was planned for is that job, done early. The
# plan's windows are month-sized and the month boundary is arbitrary to a lawn: overseeding
# on 30 August is the September overseeding, and the first of the month does not undo it.
# Asking again a week later is the plan arguing with a diary that already says it was done.
EARLY_DAYS = 14


def month_events(days: dict[str, Any]) -> dict[str, set[str]]:
    """Return the maintenance kinds each month carries, the run-up to it included."""
    events: dict[str, set[str]] = {}
    for day_key, record in days.items():
        kinds = {item.get("type") for item in record.get("maintenance", []) if item.get("type")}
        if not kinds:
            continue
        events.setdefault(day_key[:7], set()).update(kinds)
        early = dt.date.fromisoformat(day_key) + dt.timedelta(days=EARLY_DAYS)
        if early.strftime("%Y-%m") != day_key[:7]:
            events.setdefault(early.strftime("%Y-%m"), set()).update(kinds)
    return events


def status_of(op: Operation, today: dt.date, events: dict[str, set[str]]) -> str:
    """Return done, open, upcoming or missed from what the diary records for the month.

    `events` maps YYYY-MM to the maintenance kinds logged in that month.
    """
    if op.code in ONGOING_CODES:
        current = _month_key(today.year, today.month)
        return "open" if op.month <= current else "upcoming"
    kinds = DONE_BY.get(op.category, ())
    if kinds and events.get(op.month, set()) & set(kinds):
        return "done"
    current = _month_key(today.year, today.month)
    if op.month == current:
        return "open"
    if op.month < current:
        return "skipped" if op.optional else "missed"
    return "upcoming"


def carry_over(
    plan: list[Operation], today: dt.date, events: dict[str, set[str]]
) -> Operation | None:
    """Return last month's missed feed, if this month has none planned and it can still go on."""
    current = _month_key(today.year, today.month)
    if any(op.month == current and op.category == "fertilizing" for op in plan):
        return None
    previous_month = today.month - 1 or 12
    previous_year = today.year if today.month > 1 else today.year - 1
    previous = _month_key(previous_year, previous_month)
    for op in plan:
        if (
            op.month == previous
            and op.category == "fertilizing"
            and status_of(op, today, events) == "missed"
        ):
            return Operation(
                current,
                op.code,
                op.category,
                op.optional,
                op.params,
                op.basis,
                (*op.tailoring, "carried_over_from_last_month"),
            )
    return None
