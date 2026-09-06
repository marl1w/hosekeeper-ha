"""The week ahead, day by day.

Today's advice says what to do now. The agenda projects the next seven days: the water
balance run forward on the forecast, with irrigation placed where the readily available
water would run out; the mowing day from the season's interval; the best day in the week for
each operation the month still owes, given rain, heat and the mowing day; and the alerts that
stand today. It is a plan to look at on Sunday evening, not a promise: the coordinator
recomputes it at every refresh and the days move as the forecast does.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime as dt
from typing import TYPE_CHECKING, Any

from . import et, rules, schedule, water
from .climate import expected_rain
from .knowledge import grass, programme

if TYPE_CHECKING:
    from .rules import Advice, Context

# Three horizons, because three different things are being predicted and they are not
# knowable equally far out. The weather model is worth reading for a week. The water balance
# can be run on past it for another week, drying at the season's rate with no rain assumed,
# which is a projection rather than a promise but is better than a blank fortnight. Work on
# a cadence — the cut, the seedbed — needs no forecast at all and is laid out for a month, so
# the calendar is not empty from the middle of one month to the first of the next.
DAYS = 7
BALANCE_DAYS = 14
HORIZON_DAYS = 28


@dataclass(frozen=True, slots=True)
class AgendaItem:
    """One thing on one day."""

    date: str
    code: str
    category: str
    params: dict[str, Any] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly shape."""
        return {
            "date": self.date,
            "code": self.code,
            "category": self.category,
            "params": self.params,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class DayProjection:
    """One coming day as the balance expects it to go."""

    date: dt.date
    rain_mm: float
    etc_mm: float
    irrigation_mm: float
    deficit_mm: float
    seedbed_mm: float = 0.0
    """Light waterings over a seedbed. Water applied, but not water the roots get.

    Their whole purpose is to keep the top centimetre damp, and most of two millimetres on a
    warm afternoon goes back to the air. Counting them in the balance would tell the engine
    the root zone is full and stop the dawn cycle the established turf around the seed still
    needs. So they are drawn, because the lawn is being watered and the picture must say so,
    and they are not credited to the deficit.
    """
    forecast: bool = True
    """Whether a weather forecast covered this day, or the season's own rate stood in."""

    def as_dict(self) -> dict[str, Any]:
        """Return the shape the panel's charts read, matching a diary day."""
        return {
            "date": self.date.isoformat(),
            "rain_mm": round(self.rain_mm, 1),
            "etc_mm": round(self.etc_mm, 2),
            "irrigation_mm": round(self.irrigation_mm, 1),
            "seedbed_mm": round(self.seedbed_mm, 1),
            "deficit_mm": round(self.deficit_mm, 1),
            "projected": True,
            "forecast": self.forecast,
        }


@dataclass(frozen=True, slots=True)
class DayForecast:
    """What the forecast says about one coming day."""

    date: dt.date
    tmax: float | None
    tmin: float | None
    rain_mm: float | None


def _et_for(day: DayForecast, latitude: float, kc: float) -> float:
    if day.tmax is None or day.tmin is None:
        return 0.0
    ra = et.extraterrestrial_radiation(latitude, day.date.timetuple().tm_yday)
    return et.hargreaves_et0(day.tmax, day.tmin, ra) * kc


def project(
    ctx: Context, forecast: list[DayForecast], advice: list[Advice], *, latitude: float
) -> list[DayProjection]:
    """Return the balance run forward over the coming days.

    The same numbers place the irrigation days in the agenda and draw the future half of the
    charts, so the picture and the plan can never disagree.
    """
    soil = water.SoilWater(ctx.taw_mm, ctx.raw_mm)
    by_date = {f.date: f for f in forecast}
    threshold = ctx.raw_mm / ctx.irrigation_factor
    dormant = ctx.phase == "dormant"
    advised_now = next((a for a in advice if a.code == "irrigate_now"), None)
    deficit = ctx.deficit_mm
    # The seedbed's own regime, so the picture agrees with the agenda about what is being
    # put on the lawn. It is drawn, not credited: see DayProjection.seedbed_mm.
    seedbed_left = (
        programme.SEED_GERMINATION_DAYS - (ctx.days_since_sowing or 0)
        if ctx.germinating and not ctx.new_lawn
        else 0
    )
    seedbed_daily = len(schedule.GERMINATION_TIMES) * schedule.GERMINATION_MM
    out: list[DayProjection] = []

    for offset in range(BALANCE_DAYS):
        date = ctx.today + dt.timedelta(days=offset)
        fc = by_date.get(date)
        kc = grass.crop_coefficient(ctx.grass_type, date.month, ctx.northern_hemisphere)
        etc = _et_for(fc, latitude, kc) if fc else ctx.etc_today_mm
        rain = expected_rain(fc.rain_mm if fc else None, ctx.skill)
        seedbed = seedbed_daily if offset < seedbed_left else 0.0
        if offset == 0:
            # Today's rain and water use are already in the deficit the coordinator handed
            # over; only tonight's cycle is still to come.
            irrigation = float(advised_now.params.get("mm", 0.0)) if advised_now else 0.0
            deficit = water.next_deficit(deficit, 0.0, 0.0, irrigation, soil)
            out.append(
                DayProjection(
                    date,
                    ctx.rain_today_mm,
                    ctx.etc_today_mm,
                    irrigation,
                    deficit,
                    seedbed,
                    fc is not None,
                )
            )
            continue
        irrigation = 0.0
        if not dormant and deficit + etc - water.effective_rain(rain) >= threshold:
            candidate = round(max(0.0, deficit * ctx.irrigation_factor - rain))
            if candidate >= 3:
                irrigation = float(candidate)
        deficit = water.next_deficit(deficit, etc, rain, irrigation, soil)
        out.append(DayProjection(date, rain, etc, irrigation, deficit, seedbed, fc is not None))
    return out


def build(
    ctx: Context,
    forecast: list[DayForecast],
    advice: list[Advice],
    *,
    latitude: float,
    minutes_per_mm: float | None,
) -> list[AgendaItem]:
    """Return the agenda for the next seven days, today included."""
    by_date = {f.date: f for f in forecast}
    items: list[AgendaItem] = []
    days = [ctx.today + dt.timedelta(days=i) for i in range(DAYS)]
    horizon = ctx.today + dt.timedelta(days=HORIZON_DAYS - 1)

    # What the rules already say to do today is not a projection: it is today's answer, and
    # the week must agree with it. Anything else would put "overseed now" at a glance and the
    # same job three days out in the list beside it.
    now_codes = {a.code for a in advice if a.priority <= 2}
    # The rules are the authority on what is suppressed. The week used to re-derive it and
    # ended up proposing a second sowing, and a mow over the seedlings, days after a sowing
    # the rules had already taken account of.
    held_back = set()
    if rules.recently_sown(ctx):
        held_back.add("seeding")
    do_today = {
        "fertilizing": {"feed_now"},
        "seeding": {"overseed_now", "prepare_overseeding"},
        "weeds": {
            "weed_control_broadleaf_now",
            "weed_control_grassy_now",
            "moss_control_now",
            "pre_emergent_window",
        },
        "aeration": {"aerate_now", "scarify_now", "top_dress_now"},
        "disease": {"disease_preventive_now"},
    }

    # --- irrigation: from the projection, so the chart and the plan agree ---------------
    for day in project(ctx, forecast, advice, latitude=latitude):
        if day.irrigation_mm <= 0:
            continue
        params: dict[str, Any] = {"mm": round(day.irrigation_mm)}
        if minutes_per_mm:
            # The same split the planner uses, so the agenda cannot promise one long run
            # that the morning will actually be given as two or three.
            runs = schedule.split_into_cycles(day.irrigation_mm, ctx.soil_type)
            params["minutes"] = round(sum(max(1, round(mm * minutes_per_mm)) for mm in runs))
            if len(runs) > 1:
                params["cycles"] = len(runs)
        reason = "advised_today" if day.date == ctx.today else "dawn_cycle"
        items.append(AgendaItem(day.date.isoformat(), "irrigate", "irrigation", params, (reason,)))

    # --- the seedbed, every day until the seed is up -------------------------------------
    if ctx.germinating and not ctx.new_lawn:
        left = programme.SEED_GERMINATION_DAYS - (ctx.days_since_sowing or 0)
        for offset in range(HORIZON_DAYS):
            if offset >= left:
                break
            date = ctx.today + dt.timedelta(days=offset)
            items.append(
                AgendaItem(
                    date.isoformat(),
                    "germination_watering",
                    "irrigation",
                    {"times": len(schedule.GERMINATION_TIMES), "mm": schedule.GERMINATION_MM},
                    ("keep_the_seedbed_damp",),
                )
            )

    # --- mowing: from the last cut and the season's interval -------------------------------
    interval = programme.MOW_INTERVAL_DAYS.get(ctx.phase)
    mow_days: list[dt.date] = []
    if interval is not None and not ctx.phenology.heat_stress and not rules.mower_held(ctx):
        since = ctx.days_since_mowing if ctx.days_since_mowing is not None else interval
        next_mow = ctx.today + dt.timedelta(days=max(0, interval - since))
        low, high = ctx.mow_height_mm
        height = high if ctx.phase == "summer_stress" else round((low + high) / 2)
        while next_mow <= horizon:
            fc = by_date.get(next_mow)
            # Shift off a wet day.
            if fc and fc.rain_mm and fc.rain_mm >= 5:
                next_mow += dt.timedelta(days=1)
                continue
            mow_days.append(next_mow)
            items.append(
                AgendaItem(
                    next_mow.isoformat(),
                    "mow",
                    "mowing",
                    {"height_mm": height},
                    ("interval_reached", "afternoon_grass_dry"),
                )
            )
            next_mow += dt.timedelta(days=interval)

    # --- the month's operations: the best day this week ------------------------------------
    def dry_mild(date: dt.date, *, max_tmax: float, max_rain: float) -> bool:
        fc = by_date.get(date)
        if fc is None:
            return False
        return (fc.rain_mm or 0.0) <= max_rain and (fc.tmax is None or fc.tmax <= max_tmax)

    for op in ctx.planned():
        if op.category in held_back:
            continue
        if op.category in ("general", "irrigation") or op.code in (
            "first_mow",
            "raise_mowing_height",
            "last_mow_lower",
            "summer_watch",
            "summer_rest",
            "winter_rest",
        ):
            continue
        if now_codes & do_today.get(op.category, set()):
            items.append(
                AgendaItem(
                    ctx.today.isoformat(),
                    "operation",
                    op.category,
                    {"operation": op.code, "optional": op.optional, **op.params},
                    ("advised_today", *op.basis[:1]),
                )
            )
            continue
        candidates: list[dt.date] = []
        for date in days:
            if op.category == "weeds":
                # Herbicides: dry leaves, two days clear of a mow, mild.
                near_mow = any(abs((date - m).days) < 2 for m in mow_days)
                if near_mow or not dry_mild(date, max_tmax=27.0, max_rain=1.0):
                    continue
                nxt = by_date.get(date + dt.timedelta(days=1))
                if nxt and (nxt.rain_mm or 0.0) > 3:
                    continue
            elif op.category == "fertilizing":
                if not dry_mild(date, max_tmax=29.0, max_rain=15.0):
                    continue
                if date in mow_days:
                    continue
            elif op.category == "seeding":
                if not dry_mild(date, max_tmax=28.0, max_rain=10.0):
                    continue
            elif op.category == "disease":
                if not dry_mild(date, max_tmax=35.0, max_rain=2.0):
                    continue
            elif op.category == "aeration" and not dry_mild(date, max_tmax=30.0, max_rain=20.0):
                continue
            candidates.append(date)
        if not candidates:
            items.append(
                AgendaItem(
                    days[-1].isoformat(),
                    "no_good_day",
                    op.category,
                    {"operation": op.code, "optional": op.optional},
                    ("week_unsuitable",),
                )
            )
            continue
        # Feeds prefer the day after a mow; everything else the first suitable day.
        best = candidates[0]
        if op.category == "fertilizing":
            after_mow = [d for d in candidates if (d - dt.timedelta(days=1)) in mow_days]
            if after_mow:
                best = after_mow[0]
        items.append(
            AgendaItem(
                best.isoformat(),
                "operation",
                op.category,
                {"operation": op.code, "optional": op.optional, **op.params},
                ("planned_this_month", *op.basis[:1]),
            )
        )

    # --- alerts that stand today ---------------------------------------------------------
    for a in advice:
        if a.category == "disease" and a.priority <= 2:
            items.append(AgendaItem(ctx.today.isoformat(), a.code, "disease", a.params, a.reasons))

    return sorted(items, key=lambda i: (i.date, _order(i.category)))


def _order(category: str) -> int:
    return (
        [
            "irrigation",
            "mowing",
            "fertilizing",
            "seeding",
            "weeds",
            "aeration",
            "disease",
            "general",
        ].index(category)
        if category
        in (
            "irrigation",
            "mowing",
            "fertilizing",
            "seeding",
            "weeds",
            "aeration",
            "disease",
            "general",
        )
        else 9
    )
