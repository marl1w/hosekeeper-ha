"""When in the day: the dawn irrigation, the midday syringing, the mowing window.

The water balance says how much. This says at what hour, and holds the answer for the day.
Irrigation finishes at sunrise: the leaves dry as soon as the sun is up, which is what keeps
brown patch and dollar spot down, and the air is still and cool, which is what keeps the
water on the lawn. On days of heat stress a light midday syringing cools the canopy without
adding much water. Mowing waits for the dew to lift and for the grass to be dry.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
import datetime as dt
import math
from typing import Any

from . import water
from .knowledge import programme

DAWN_BUFFER = dt.timedelta(minutes=10)
SYRINGE_TIME = dt.time(13, 0)
SYRINGE_MM = 1.5
SYRINGE_TMAX_C = 32.0

# Cycle and soak.
#
# One long run is what grows deep roots, and it is what Hosekeeper aims for: the whole
# refill in a single dawn cycle, so the soil dries down to the readily available limit
# before the next one. But a lawn can only take water as fast as the soil lets it in. When
# the refill is deeper than that, the run is split into cycles with a soak between them —
# the same water, the same morning, still one deep watering, minus the puddles and the
# runoff. Extension guidance calls this cycle and soak; the alternative, watering a little
# every day, keeps the roots at the surface and is what the engine is built to avoid.
SOAK = dt.timedelta(minutes=45)
EARLIEST_START = dt.time(1, 0)
MAX_CYCLES = 4

# Germination.
#
# Seed needs the top centimetre damp for a fortnight, which no deep cycle can do: it wets
# the root zone and the surface is dry by noon. So a sown lawn gets short waterings through
# the day on top of whatever the established turf around it is given. How many and how deep
# is the seedbed's business and lives in the knowledge layer, because the rules quote the
# same figures back to the user; what is settled here is where they land in the day. The
# last one is early enough that the leaf dries before dark, whichever regime is running,
# because a seedbed wet all night grows damping-off rather than grass.
STANDARD_SEEDBED = programme.STANDARD_SEEDBED
GERMINATION_MM = STANDARD_SEEDBED.mm

# The window a seedbed's passes are spread across, for a caller that has no sun to hand.
# Real days come with their own, worked out from the lawn's latitude and the date; this is
# the midsummer shape of it, kept so a bare call still lands somewhere sensible.
GERMINATION_WINDOW = (dt.time(9, 0), dt.time(17, 0))

# The same window at the ordinary count, for a caller that needs hours and has neither a
# decided plan nor a day to work them out from.
GERMINATION_TIMES = programme.seedbed_times(STANDARD_SEEDBED.min_passes, GERMINATION_WINDOW)

# When a watering already decided is worth deciding again.
#
# The plan is settled once so its depth cannot wobble with every refresh -- a figure that
# moves each hour is a figure nobody can act on. But the day it was decided for can turn: an
# afternoon of rain nobody forecast, or a forecast that fills up after the plan was made,
# leaves the lawn being given water it no longer needs, and the reverse leaves it short.
#
# So the same test the month's plan gets: a material change re-decides, drift does not. A
# third of the planned depth, and never less than three millimetres, which is about what a
# summer shower puts down and less than any watering worth running.
RETHINK_MM = 3.0
RETHINK_FRACTION = 0.3


def worth_rethinking(planned_mm: float, needed_mm: float) -> bool:
    """Return whether the day has moved enough to decide the watering again."""
    return abs(needed_mm - planned_mm) >= max(RETHINK_MM, RETHINK_FRACTION * planned_mm)


def revised(plan: IrrigationPlan, *, wetter: bool) -> IrrigationPlan:
    """Return the plan with a note of why it is not the one made this morning."""
    reasons = (*plan.reasons, "revised_rain_since" if wetter else "revised_drier_since")
    return replace(plan, reasons=reasons)


def rescheduled(plan: IrrigationPlan) -> IrrigationPlan:
    """Return the plan with a note that it was re-laid because its hours had moved."""
    return replace(plan, reasons=(*plan.reasons, "revised_hours_moved"))


def hours_moved(plan: IrrigationPlan, window: tuple[dt.time, dt.time]) -> bool:
    """Return whether a settled seedbed's passes no longer sit where today's rules put them.

    The depth test cannot see this. A plan holding the same millimetres at the wrong hours is
    materially wrong and reads as right: the passes drifted by four hours when the window
    stopped being a constant and started following the sun, and nothing in the millimetres
    moved at all. The same is true of a lawn that has just learned when its dew lifts, or one
    whose window has crossed a half hour as the season turned.

    Cheap to ask and almost always false, because the hours are on a half-hour grid precisely
    so they stay put for weeks at a time.
    """
    if not plan.germination:
        return False
    planned = tuple(cycle.start.time() for cycle in plan.germination)
    return planned != programme.seedbed_times(len(planned), window)


# What one zone leaves between its run and the next zone's.
#
# A controller opens one valve at a time and takes a moment over it, and two runs written
# back to back read as one long run to anybody looking at the calendar. A minute is enough to
# be a boundary and too little to matter to the grass.
VALVE_GAP = dt.timedelta(minutes=1)

# When the robot may be out at all, and the slot the calendar proposes inside it.
#
# Not the morning: dew sits on the grass until mid-morning and later in autumn, and a wet
# cut tears rather than slices, smears clippings and spreads disease. Mid to late afternoon
# is dry and past the heat of the day; on a day of heat stress it moves to the evening.
MOW_WINDOW = (dt.time(10, 30), dt.time(20, 0))
MOW_HEAT_PAUSE = (dt.time(12, 0), dt.time(17, 0))
MOW_PREFERRED = (dt.time(16, 0), dt.time(18, 0))
MOW_PREFERRED_HOT = (dt.time(18, 0), dt.time(20, 0))
WET_RAIN_MM = 2.0
WET_HOURS_AFTER_RAIN = 6


@dataclass(frozen=True, slots=True)
class Cycle:
    """One run of the system."""

    start: dt.datetime
    end: dt.datetime
    mm: float

    @property
    def minutes(self) -> int:
        """Return how long it runs."""
        return round((self.end - self.start).total_seconds() / 60)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly shape."""
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "mm": round(self.mm, 1),
            "minutes": self.minutes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Cycle:
        """Rebuild from the diary."""
        return cls(
            dt.datetime.fromisoformat(data["start"]),
            dt.datetime.fromisoformat(data["end"]),
            float(data["mm"]),
        )


def split_into_cycles(needed_mm: float, soil_type: str) -> list[float]:
    """Return the depths of the runs one watering should be split into.

    A single run wherever the soil can take it; otherwise as few runs as will go in without
    running off, never more than four, because past that the morning is gone.
    """
    if needed_mm <= 0:
        return []
    cap = water.max_single_application(soil_type)
    count = min(MAX_CYCLES, max(1, math.ceil(needed_mm / cap)))
    share = needed_mm / count
    return [share] * count


@dataclass(frozen=True, slots=True)
class IrrigationPlan:
    """The day's watering, decided once."""

    date: dt.date
    cycles: tuple[Cycle, ...] = ()
    germination: tuple[Cycle, ...] = ()
    syringe: bool = False
    syringe_start: dt.datetime | None = None
    syringe_end: dt.datetime | None = None
    reasons: tuple[str, ...] = ()

    @property
    def seedbed_day(self) -> bool:
        """Return whether the seedbed's passes are the whole of this day's watering.

        A lawn sown all over has no dawn cycle for the fortnight, and its passes are real
        water on a real root zone rather than damp kept on a surface. Everything downstream
        -- what the balance is credited with, what the chart hatches -- turns on this, so it
        is read back off the plan rather than worked out again from the lawn.
        """
        return "seedbed_day_replaces_dawn_cycle" in self.reasons

    @property
    def seedbed_mm(self) -> float:
        """Return the depth the day's seedbed passes put on the lawn between them."""
        return round(sum(cycle.mm for cycle in self.germination), 1)

    @property
    def planned_mm(self) -> float:
        """Return what this plan puts on the lawn, whichever regime the day is on."""
        return self.seedbed_mm if self.seedbed_day else self.main_mm

    # The whole watering, as one span: what a sensor, a calendar entry and a row all want.
    @property
    def main_mm(self) -> float:
        """Return the depth the whole watering applies."""
        return round(sum(cycle.mm for cycle in self.cycles), 1)

    @property
    def main_minutes(self) -> int | None:
        """Return the minutes the system actually runs, soak time excluded."""
        return sum(cycle.minutes for cycle in self.cycles) if self.cycles else None

    @property
    def main_start(self) -> dt.datetime | None:
        """Return when the first cycle starts."""
        return self.cycles[0].start if self.cycles else None

    @property
    def main_end(self) -> dt.datetime | None:
        """Return when the last cycle ends."""
        return self.cycles[-1].end if self.cycles else None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly shape for the diary and the sensors."""
        return {
            "date": self.date.isoformat(),
            "cycles": [cycle.as_dict() for cycle in self.cycles],
            "germination": [cycle.as_dict() for cycle in self.germination],
            "main_mm": self.main_mm,
            "main_minutes": self.main_minutes,
            "main_start": _iso(self.main_start),
            "main_end": _iso(self.main_end),
            "syringe": self.syringe,
            "syringe_start": _iso(self.syringe_start),
            "syringe_end": _iso(self.syringe_end),
            "reasons": list(self.reasons),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IrrigationPlan:
        """Rebuild from the diary."""
        return cls(
            date=dt.date.fromisoformat(data["date"]),
            cycles=tuple(Cycle.from_dict(c) for c in data.get("cycles", [])),
            germination=tuple(Cycle.from_dict(c) for c in data.get("germination", [])),
            syringe=bool(data.get("syringe")),
            syringe_start=_parse(data.get("syringe_start")),
            syringe_end=_parse(data.get("syringe_end")),
            reasons=tuple(data.get("reasons", [])),
        )

    def active_cycle(self, now: dt.datetime) -> str | None:
        """Return main, syringe or None for the cycle that should be running now."""
        if any(cycle.start <= now < cycle.end for cycle in self.cycles):
            return "main"
        if any(cycle.start <= now < cycle.end for cycle in self.germination):
            return "germination"
        if (
            self.syringe
            and self.syringe_start
            and self.syringe_end
            and self.syringe_start <= now < self.syringe_end
        ):
            return "syringe"
        return None

    def next_start(self, now: dt.datetime) -> dt.datetime | None:
        """Return the next cycle start after now, if any."""
        starts = [cycle.start for cycle in (*self.cycles, *self.germination)]
        if self.syringe and self.syringe_start:
            starts.append(self.syringe_start)
        future = [start for start in starts if start > now]
        return min(future) if future else None


def irrigation_plan(
    *,
    date: dt.date,
    sunrise: dt.datetime,
    needed_mm: float,
    minutes_per_mm: float | None,
    heat_stress: bool,
    forecast_tmax: float | None,
    dormant: bool,
    soil_type: str = "loam",
    germinating: bool = False,
    germination_offset: dt.timedelta = dt.timedelta(),
    seedbed: programme.SeedbedRegime = STANDARD_SEEDBED,
    seedbed_whole_zone: bool = False,
    seedbed_depths: Sequence[float] = (),
    seedbed_window: tuple[dt.time, dt.time] = GERMINATION_WINDOW,
) -> IrrigationPlan:
    """Return the plan for the dawn that ends at `sunrise`, or the day a seedbed asks for.

    Ordinarily: one watering, deep enough to refill the root zone, finishing as the sun comes
    up. It is laid out backwards from there -- the last cycle ends ten minutes before
    sunrise, and any earlier cycles are stacked behind it with a soak between, so the soil
    has time to take the water in. Nothing starts before one in the morning; a refill too big
    to fit says so and the rest waits for the next day.

    A lawn sown all over is the exception, and it is not the ordinary day with extra
    waterings bolted onto it. Water put down at dawn is in the root zone by breakfast and the
    top centimetre is dry by eleven, which is the one centimetre the seed is living in; and
    seed sitting on the surface is what a deep run moves. So for the fortnight the seed is
    coming up the dawn cycle gives way: the day's whole watering is the seedbed's passes,
    spread from morning to late afternoon, each one deep enough to count and light enough to
    leave the seed where it was sown. The deep cycle comes back when the seed is up, and with
    it the deep roots it is there to grow.
    """
    reasons: list[str] = []
    seedbed_day = germinating and seedbed_whole_zone
    if seedbed_day:
        cycles: tuple[Cycle, ...] = ()
        left_over = False
        reasons.append("seedbed_day_replaces_dawn_cycle")
        if not minutes_per_mm:
            reasons.append("rate_unknown_no_timing")
    else:
        cycles, left_over = lay_out_cycles(
            needed_mm, minutes_per_mm, soil_type, sunrise - DAWN_BUFFER
        )
    if left_over:
        reasons.append("run_capped_split_tomorrow")
    if len(cycles) > 1:
        reasons.append("cycle_and_soak")
    if cycles:
        reasons.append("finish_by_sunrise_leaves_dry")
    elif needed_mm > 0 and not seedbed_day:
        reasons.append("rate_unknown_no_timing")

    # No syringing on a seedbed day: the passes already cross the hottest part of it, and a
    # second regime on the same valve would only be the same water twice.
    syringe = (
        not dormant
        and not seedbed_day
        and (heat_stress or (forecast_tmax is not None and forecast_tmax >= SYRINGE_TMAX_C))
    )
    syringe_start = syringe_end = None
    if syringe:
        syringe_start = dt.datetime.combine(date, SYRINGE_TIME, tzinfo=sunrise.tzinfo)
        minutes = round(SYRINGE_MM * minutes_per_mm) if minutes_per_mm else 3
        syringe_end = syringe_start + dt.timedelta(minutes=max(1, minutes))
        reasons.append("midday_syringing_heat")

    germination = (
        germination_cycles(
            date,
            sunrise.tzinfo,
            minutes_per_mm,
            germination_offset,
            seedbed,
            seedbed_depths,
            seedbed_window,
        )
        if germinating
        else ()
    )
    if germination:
        reasons.extend(seedbed_reasons(seedbed))

    return IrrigationPlan(
        date=date,
        cycles=cycles,
        germination=germination,
        syringe=syringe,
        syringe_start=syringe_start,
        syringe_end=syringe_end,
        reasons=tuple(reasons),
    )


def lay_out_cycles(
    needed_mm: float,
    minutes_per_mm: float | None,
    soil_type: str,
    end: dt.datetime,
) -> tuple[tuple[Cycle, ...], bool]:
    """Return the runs that end at `end`, and whether some of the water had to be left over.

    Laid out backwards from the finish: the last run ends there, earlier ones are stacked
    behind it with a soak between, and nothing starts before one in the morning.
    """
    if needed_mm <= 0 or not minutes_per_mm:
        return (), False
    cycles: list[Cycle] = []
    floor = dt.datetime.combine(end.date(), EARLIEST_START, tzinfo=end.tzinfo)
    if end.time() < EARLIEST_START:
        floor -= dt.timedelta(days=1)
    left_over = False
    for depth in reversed(split_into_cycles(needed_mm, soil_type)):
        minutes = max(1, round(depth * minutes_per_mm))
        start = end - dt.timedelta(minutes=minutes)
        if start < floor:
            left_over = True
            break
        cycles.insert(0, Cycle(start, end, depth))
        end = start - SOAK
    return tuple(cycles), left_over


def with_germination(
    plan: IrrigationPlan,
    tzinfo: dt.tzinfo,
    minutes_per_mm: float | None,
    offset: dt.timedelta = dt.timedelta(),
    regime: programme.SeedbedRegime = STANDARD_SEEDBED,
    depths: Sequence[float] = (),
    window: tuple[dt.time, dt.time] = GERMINATION_WINDOW,
    *,
    whole_zone: bool = False,
) -> IrrigationPlan:
    """Return the plan the lawn needs now that seed has gone down on it.

    Seed goes down on a day whose watering was decided that morning, and the seedbed's passes
    are not part of what was decided; without them the day the seed went down is the one day
    it is left to dry out. So, like a syringing, they can join a plan already settled.

    A sowing over the whole zone does more than add to the plan, though. The lawn the plan
    was made for was turf; it is now a seedbed, and the deep cycle that was right at eight
    this morning would wash the seed about at four tomorrow. Settling the plan protects it
    from the weather changing its mind, not from the lawn itself changing -- so a whole-zone
    sowing takes the dawn cycle back out and the day becomes the seedbed's.
    """
    if plan.germination:
        return plan
    cycles = germination_cycles(plan.date, tzinfo, minutes_per_mm, offset, regime, depths, window)
    if not cycles:
        return plan
    reasons = (*plan.reasons, *seedbed_reasons(regime))
    if not whole_zone:
        return replace(plan, germination=cycles, reasons=reasons)
    return replace(
        plan,
        cycles=(),
        germination=cycles,
        syringe=False,
        syringe_start=None,
        syringe_end=None,
        reasons=(
            *(r for r in reasons if r not in DAWN_ONLY_REASONS),
            "seedbed_day_replaces_dawn_cycle",
        ),
    )


# Reasons that belong to a dawn cycle and mean nothing once there is not one.
DAWN_ONLY_REASONS = frozenset(
    {
        "cycle_and_soak",
        "finish_by_sunrise_leaves_dry",
        "run_capped_split_tomorrow",
        "midday_syringing_heat",
    }
)


def with_syringe(
    plan: IrrigationPlan, tzinfo: dt.tzinfo, minutes_per_mm: float | None
) -> IrrigationPlan:
    """Return the plan with a midday syringing added, keeping everything else as decided.

    The day's watering is decided once and kept, so the depth cannot wobble with every
    refresh. A syringing is not part of that bargain: it is a response to heat that may not
    have been forecast when the plan was made, it is a millimetre and a half rather than a
    watering, and it is not counted in the balance. So it can be added to a plan that has
    already been settled, as long as its hour has not gone by.
    """
    if plan.syringe or plan.seedbed_day:
        return plan
    start = dt.datetime.combine(plan.date, SYRINGE_TIME, tzinfo=tzinfo)
    minutes = round(SYRINGE_MM * minutes_per_mm) if minutes_per_mm else 3
    return replace(
        plan,
        syringe=True,
        syringe_start=start,
        syringe_end=start + dt.timedelta(minutes=max(1, minutes)),
        reasons=(*plan.reasons, "midday_syringing_heat"),
    )


def without_syringe(plan: IrrigationPlan) -> IrrigationPlan:
    """Return the plan with its midday syringing taken back out.

    For a plan that should never have had one: a day whose passes are its whole watering
    already crosses the afternoon, and a syringing on the same valve is the same water twice.
    Only the hour that is still ahead can be taken back; one already run is a fact.
    """
    if not plan.syringe:
        return plan
    return replace(
        plan,
        syringe=False,
        syringe_start=None,
        syringe_end=None,
        reasons=tuple(r for r in plan.reasons if r != "midday_syringing_heat"),
    )


def seedbed_reasons(regime: programme.SeedbedRegime) -> tuple[str, ...]:
    """Return why the day carries seedbed passes, and why this many of them."""
    if regime is programme.CHITTED_SEEDBED:
        return ("keep_the_seedbed_damp", "chitted_seed_cannot_dry")
    return ("keep_the_seedbed_damp",)


def germination_cycles(
    date: dt.date,
    tzinfo: dt.tzinfo,
    minutes_per_mm: float | None,
    offset: dt.timedelta = dt.timedelta(),
    regime: programme.SeedbedRegime = STANDARD_SEEDBED,
    depths: Sequence[float] = (),
    window: tuple[dt.time, dt.time] = GERMINATION_WINDOW,
) -> tuple[Cycle, ...]:
    """Return the day's waterings over a sown lawn, and how deep each one goes.

    `offset` moves this lawn's passes past the lawns already booked into the same slot. A
    controller opens one valve at a time, so three lawns all starting at nine means the
    second and third get whatever pressure is left, or nothing at all.

    `regime` is how often the seedbed is wetted: the ordinary three passes, or the five
    lighter ones chitted seed needs while its radicle has no root to fall back on -- and more
    of either on a day with the drying power to ask for them. `depths` is what the day
    actually owes, worked out where the rain and the balance are known.

    `window` is the part of the day the passes may run in, which hangs off sunrise and sunset
    rather than the clock: a pass before the dew has lifted waters water, and one late enough
    to leave the leaf wet after dark grows damping-off. The passes are spread evenly across
    it, because what a seedbed suffers from is the longest gap between two of them.

    Fewer depths than the window was divided for means rain has taken passes off the day. The
    ones that stay are the later hours, because the surface is wettest in the morning, from
    dew and from whatever fell overnight, and driest by the end of the afternoon.
    """
    if not depths:
        return ()
    hours = programme.seedbed_times(len(depths), window)
    out = []
    for at, mm in zip(hours, depths, strict=True):
        start = dt.datetime.combine(date, at, tzinfo=tzinfo) + offset
        minutes = max(1, round(mm * minutes_per_mm)) if minutes_per_mm else 3
        out.append(Cycle(start, start + dt.timedelta(minutes=minutes), mm))
    return tuple(out)


def preferred_mow_slot(*, heat_stress: bool) -> tuple[dt.time, dt.time]:
    """Return the slot to propose for a cut: afternoon, or evening when the day is hot."""
    return MOW_PREFERRED_HOT if heat_stress else MOW_PREFERRED


@dataclass(frozen=True, slots=True)
class MowingWindow:
    """Whether the robot should be out now."""

    open: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly shape."""
        return {"open": self.open, "reasons": list(self.reasons)}


def mowing_window(
    *,
    now: dt.datetime,
    due: bool,
    rain_today_mm: float,
    last_rain_at: dt.datetime | None,
    heat_stress: bool,
    irrigating: bool,
) -> MowingWindow:
    """Return whether to mow now, and why not if not."""
    if not due:
        return MowingWindow(False, ("not_due",))
    reasons: list[str] = []
    local = now.time()
    if not (MOW_WINDOW[0] <= local < MOW_WINDOW[1]):
        reasons.append("outside_daytime_window")
    if irrigating:
        reasons.append("irrigation_running")
    recently_rained = last_rain_at is not None and (now - last_rain_at) < dt.timedelta(
        hours=WET_HOURS_AFTER_RAIN
    )
    wet_morning = rain_today_mm >= WET_RAIN_MM and local < dt.time(15, 0)
    if recently_rained or wet_morning:
        reasons.append("grass_wet_after_rain")
    if heat_stress and MOW_HEAT_PAUSE[0] <= local < MOW_HEAT_PAUSE[1]:
        reasons.append("heat_of_the_day")
    if reasons:
        return MowingWindow(False, tuple(reasons))
    return MowingWindow(True, ("due_and_dry",))


def _iso(value: dt.datetime | None) -> str | None:
    return None if value is None else value.isoformat()


def _parse(value: str | None) -> dt.datetime | None:
    return None if not value else dt.datetime.fromisoformat(value)
