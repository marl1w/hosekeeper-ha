"""When in the day: the dawn irrigation, the midday syringing, the mowing window.

The water balance says how much. This says at what hour, and holds the answer for the day.
Irrigation finishes at sunrise: the leaves dry as soon as the sun is up, which is what keeps
brown patch and dollar spot down, and the air is still and cool, which is what keeps the
water on the lawn. On days of heat stress a light midday syringing cools the canopy without
adding much water. Mowing waits for the dew to lift and for the grass to be dry.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
import datetime as dt
import math
from typing import Any

from . import water

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
# the day on top of whatever the established turf around it is given. The last one is early
# enough that the leaf dries before dark, because a seedbed wet all night grows damping-off
# rather than grass.
GERMINATION_TIMES = (dt.time(11, 0), dt.time(14, 0), dt.time(17, 0))
GERMINATION_MM = 2.0

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
) -> IrrigationPlan:
    """Return the plan for the dawn that ends at `sunrise`.

    One watering, deep enough to refill the root zone, finishing as the sun comes up. It is
    laid out backwards from there: the last cycle ends ten minutes before sunrise, and any
    earlier cycles are stacked behind it with a soak between, so the soil has time to take
    the water in. Nothing starts before one in the morning; a refill too big to fit says so
    and the rest waits for the next day.
    """
    reasons: list[str] = []
    cycles, left_over = lay_out_cycles(needed_mm, minutes_per_mm, soil_type, sunrise - DAWN_BUFFER)
    if left_over:
        reasons.append("run_capped_split_tomorrow")
    if len(cycles) > 1:
        reasons.append("cycle_and_soak")
    if cycles:
        reasons.append("finish_by_sunrise_leaves_dry")
    elif needed_mm > 0:
        reasons.append("rate_unknown_no_timing")

    syringe = not dormant and (
        heat_stress or (forecast_tmax is not None and forecast_tmax >= SYRINGE_TMAX_C)
    )
    syringe_start = syringe_end = None
    if syringe:
        syringe_start = dt.datetime.combine(date, SYRINGE_TIME, tzinfo=sunrise.tzinfo)
        minutes = round(SYRINGE_MM * minutes_per_mm) if minutes_per_mm else 3
        syringe_end = syringe_start + dt.timedelta(minutes=max(1, minutes))
        reasons.append("midday_syringing_heat")

    germination = (
        germination_cycles(date, sunrise.tzinfo, minutes_per_mm, germination_offset)
        if germinating
        else ()
    )
    if germination:
        reasons.append("keep_the_seedbed_damp")

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
) -> IrrigationPlan:
    """Return the plan with the seedbed's passes added, keeping everything else as decided.

    Seed goes down on a day whose watering was decided that morning, and the passes that keep
    a seedbed damp are not part of what was decided: they are two millimetres on the surface
    three times over, they never enter the balance, and without them the day the seed went
    down is the one day it is left to dry out. So, like a syringing, they can join a plan
    that has already been settled.
    """
    if plan.germination:
        return plan
    cycles = germination_cycles(plan.date, tzinfo, minutes_per_mm, offset)
    if not cycles:
        return plan
    return replace(plan, germination=cycles, reasons=(*plan.reasons, "keep_the_seedbed_damp"))


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
    if plan.syringe:
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


def germination_cycles(
    date: dt.date,
    tzinfo: dt.tzinfo,
    minutes_per_mm: float | None,
    offset: dt.timedelta = dt.timedelta(),
) -> tuple[Cycle, ...]:
    """Return the short waterings a sown lawn needs through the day.

    `offset` moves this lawn's passes past the lawns already booked into the same slot. A
    controller opens one valve at a time, so three lawns all starting at eleven means the
    second and third get whatever pressure is left, or nothing at all.
    """
    minutes = max(1, round(GERMINATION_MM * minutes_per_mm)) if minutes_per_mm else 3
    out = []
    for at in GERMINATION_TIMES:
        start = dt.datetime.combine(date, at, tzinfo=tzinfo) + offset
        out.append(Cycle(start, start + dt.timedelta(minutes=minutes), GERMINATION_MM))
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
