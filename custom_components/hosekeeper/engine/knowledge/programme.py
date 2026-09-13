"""The seasonal programme: what a lawn asks for in each phase of its year.

Cool-season (microterme) turf in a temperate climate has two growth peaks, spring and
early autumn, and a summer it mostly survives. Warm-season (macroterme) turf does the
opposite: it grows through the heat and sleeps through the cold. The programme is written
as phases keyed on soil temperature and the calendar, with the nitrogen budget the Italian
and US extension programmes converge on: 15 to 25 g N/m² a year for a cool-season home
lawn over 4 or 5 applications, weighted to autumn; 20 to 30 g for warm-season, all in the
warm months. See docs/knowledge.md for sources.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt


@dataclass(frozen=True, slots=True)
class FeedWindow:
    """One fertilization the programme expects."""

    code: str
    months: tuple[int, ...]
    """Northern-hemisphere months the application belongs to."""
    n_g_m2: float
    """Nitrogen to apply."""
    role: str
    """Fertilizer role that fits: starter | growth | stress | autumn."""
    soil_min_c: float | None = None
    """Do not apply below this soil temperature (grass is not taking it up)."""
    soil_max_c: float | None = None
    """Do not apply above this (heat stress, disease)."""


# The cool-season calendar is the one Italian professionals run on a home lawn in the Po
# valley — a phosphorus starter as the soil wakes, two greening feeds through spring, two
# fully coated potassium feeds ahead of and through the heat, nothing in August, overseeding
# in September, and two potassium-led feeds for autumn hardiness. Nitrogen per pass follows
# the label dose of the product class; the year lands near 30 g N/m², the upper end of what
# extension programmes give a well-kept, irrigated lawn.
COOL_SEASON_FEEDS: tuple[FeedWindow, ...] = (
    FeedWindow("feed_march_starter", (3,), 4.0, "starter", soil_min_c=6.0),
    FeedWindow("feed_april_greening", (4,), 3.3, "greening", soil_min_c=8.0),
    FeedWindow("feed_may_greening", (5,), 3.3, "greening", soil_max_c=22.0),
    FeedWindow("feed_june_summer", (6,), 3.5, "stress"),
    FeedWindow("feed_july_summer", (7,), 3.5, "stress"),
    FeedWindow("feed_october_autumn", (10,), 5.5, "autumn"),
    FeedWindow("feed_november_autumn", (11,), 5.5, "autumn", soil_min_c=4.0),
)

WARM_SEASON_FEEDS: tuple[FeedWindow, ...] = (
    FeedWindow("feed_spring_start", (4, 5), 5.0, "growth", soil_min_c=15.0),
    FeedWindow("feed_late_spring", (6,), 5.0, "growth"),
    FeedWindow("feed_summer_stress", (7, 8), 5.0, "growth"),
    FeedWindow("feed_early_autumn", (9,), 4.0, "stress"),
    FeedWindow("feed_late_autumn", (10,), 3.0, "autumn", soil_min_c=15.0),
)

# Soil temperature (5 cm, daily mean) that opens and closes each behaviour.
COOL_SEASON = {
    "growth_start_c": 8.0,  # green-up, roots wake, first feed
    "growth_stop_c": 6.0,  # last feed and last mow
    "stress_c": 24.0,  # cool-season roots stop growing; summer regime
    "seed_min_c": 12.0,  # germination starts in earnest
    "seed_max_c": 22.0,
    "seed_days_before_frost": 45,
}
WARM_SEASON = {
    "growth_start_c": 15.0,
    "growth_stop_c": 15.0,
    "stress_c": 99.0,
    "seed_min_c": 18.0,
    "seed_max_c": 32.0,
    "seed_days_before_frost": 90,
}

# Weed pre-emergent timing, for annual grasses like crabgrass (Digitaria): the herbicide
# must be down before the soil sits at 10 to 13 °C, which the extension GDD model puts at
# 140 to 280 growing degree days (base 0 °C) counted from 1 January.
PRE_EMERGENT_GDD = (140.0, 280.0)
PRE_EMERGENT_SOIL_C = (10.0, 13.0)

# Mowing: never remove more than a third of the leaf.
#
# The rule is about height, not about the calendar. Cutting back to H having let the grass
# reach h removes h - H, and that may not exceed a third of h, so the grass may reach 1.5 H
# before it is cut: the growth a lawn is allowed between two cuts is half the height it is
# kept at. A lawn kept at 60 mm therefore needs cutting a fifth more often than the same
# lawn at 75, and the interval cannot be a table of days on its own.
#
# What is a table is how fast the leaf grows, which is what the season decides. These rates
# are the ones behind the intervals a home lawn is usually given -- 10 days in the spring
# green-up, 6 in each flush, 9 through the summer, 12 in the late autumn -- read back out of
# them at 75 mm, the middle of the range for a cool-season lawn.
GROWTH_MM_DAY = {
    "dormant": None,
    "spring_greenup": 3.8,
    "spring_active": 6.2,
    "summer_stress": 4.2,
    "autumn_active": 6.2,
    "late_autumn": 3.1,
}
# The third rule alone would send a very low cut to every second day, which no home lawn is
# given and no hand mower is taken out for; and a very high one past the point where the
# lawn stops looking cut at all.
MOW_INTERVAL_BOUNDS = (3, 21)


def mow_interval_days(phase: str, height_mm: float) -> int | None:
    """Return how many days a lawn kept at this height goes between cuts, or None if dormant.

    Half the cutting height is the growth the third rule allows; the season's growth rate
    turns that into days.
    """
    return days_to_grow(phase, height_mm, 1.5 * height_mm)


def days_to_grow(phase: str, from_mm: float, to_mm: float) -> int | None:
    """Return how many days this season takes to grow a leaf from one height to another.

    The interval between two cuts is this with the third rule as its target, and it is the
    general form because a lawn is not always cut at the height it is standing at. One taken
    down to 20 mm to open the sward before seed and wanted back at 60 is not on any interval:
    it is waiting to grow, and the wait is the distance divided by the season's growth.
    """
    growth = GROWTH_MM_DAY.get(phase)
    if not growth:
        return None
    low, high = MOW_INTERVAL_BOUNDS
    return int(min(max(round(max(0.0, to_mm - from_mm) / growth), low), high))


# Climbing back from a low cut.
#
# Taking a lawn down to the soil before seed is deliberate and right: it opens the sward,
# gets the seed to the ground and stops the standing grass shading what comes up. What must
# not happen is the lawn being left there. Going back up is not a cut at all -- the deck
# rises and the grass grows into it -- but it is not done in one step either, because a leaf
# grown long and thin at 20 mm and then kept at 60 is a leaf that has to build the tissue to
# stand up on its own. Half again each time is the same allowance the third rule gives in
# the other direction, and it lands a scalped lawn back in its range in two or three cuts.
RAISE_FACTOR = 1.5


def recovery_height(kept_mm: float, target_mm: int) -> int:
    """Return the height the next cut is set to, climbing back towards the target."""
    return min(target_mm, round(kept_mm * RAISE_FACTOR))


def cutting_height(range_mm: tuple[int, int], *, taller: bool = False, lower: bool = False) -> int:
    """Return the height to cut to, within what the species and the mower allow.

    The middle of the range is the working height. Heat and shade ask for all the leaf there
    is, because a longer leaf shades its own soil and catches more of what light reaches it;
    the last cut of the year goes the other way, low enough that the turf does not mat under
    the wet.
    """
    low, high = range_mm
    if lower:
        return low + (high - low) // 4
    if taller:
        return high
    return round((low + high) / 2)


# A robot does not cut like a mower. It takes a few millimetres off the same lawn again and
# again, so what it is held to is keeping up with growth rather than the third rule: through
# the two flushes the manufacturers schedule it most days, and less often when the grass
# slows in the heat, the late autumn and the winter. Robot mower manufacturers' scheduling
# guidance and extension notes on mulching mowers.
ROBOT_PASS_DAYS = {
    "dormant": None,
    "spring_greenup": 3,
    "spring_active": 1,
    "summer_stress": 2,
    "autumn_active": 1,
    "late_autumn": 4,
}

# Daily is what the machine can do, not what the lawn needs, and it is not free: a slow robot
# has the lawn occupied for hours at a time, and going over the same ground every day is the
# part of robot mowing that costs the invertebrates living in it. Cutting less often lets the
# sward flower between passes and leaves the lawn alone most days. Against that, a longer
# gap means a longer leaf to take off in one pass, and the third rule is the limit that
# cannot be crossed whatever the machine.
#
# So the cadence is a choice between the manufacturer's schedule and the agronomic maximum:
#
#   frequent  what the machine's own scheduler would do, the table above
#   balanced  half the growth the third rule allows: clippings still short enough to fall
#             into the sward and vanish, but the lawn is left alone between passes
#   gentle    the whole of it, which is what a hand mower gets, and the least disturbance
#             the grass can be kept in condition with
#
# Reducing robot mowing frequency and keeping it out of the lawn at night are the two things
# the wildlife guidance asks for; the night is the owner's to set, this is the frequency.
ROBOT_CADENCES = ("frequent", "balanced", "gentle")
DEFAULT_ROBOT_CADENCE = "balanced"


def robot_pass_days(
    phase: str, height_mm: float, cadence: str = DEFAULT_ROBOT_CADENCE
) -> int | None:
    """Return how many days a robot leaves between passes, or None if the grass is dormant."""
    manufacturer = ROBOT_PASS_DAYS.get(phase)
    if manufacturer is None:
        return None
    if cadence == "frequent":
        return manufacturer
    third_rule = mow_interval_days(phase, height_mm)
    if third_rule is None:
        return None
    if cadence == "gentle":
        return max(manufacturer, third_rule)
    return max(manufacturer, round(third_rule / 2))


# The season a month usually belongs to, for a plan drawn months ahead. The daily rules read
# the real phase from the weather; a plan for next July can only go by the calendar.
NOMINAL_PHASE = {
    1: "dormant",
    2: "dormant",
    3: "spring_greenup",
    4: "spring_active",
    5: "spring_active",
    6: "summer_stress",
    7: "summer_stress",
    8: "summer_stress",
    9: "autumn_active",
    10: "autumn_active",
    11: "late_autumn",
    12: "dormant",
}

# A selective herbicide is not put on a lawn full of seedlings: the labels ask for the new
# grass to have been cut three times, which in the autumn flush is about six weeks from
# sowing. Extension guidance on weed control in newly seeded turf (Penn State, Purdue) and
# the "mowed at least three times" instruction common to 2,4-D and mecoprop products.
HERBICIDE_AFTER_SOWING_DAYS = 42

# Establishment. Sod roots in two to three weeks; seed needs a fortnight moist to germinate
# and a couple of months before it is a lawn.
SOD_ROOTING_DAYS = 21

# Seedlings are cut for the first time when they are half again as tall as the height they
# will be kept at, which is about three weeks from sowing. Until then a mower, and a robot
# most of all because it goes over the same ground again and again, tears them out.
MOWING_HELD_AFTER_SOWING_DAYS = 21
SEED_GERMINATION_DAYS = 14
SEED_ESTABLISHED_DAYS = 60

# Pre-germinated seed, and what it costs to use it.
#
# Seed can be chitted before it goes down -- soaked and held warm and damp until the radicle
# has just broken the coat. It comes up in three to five days instead of seven to fourteen,
# which is why it is used late in the autumn window when there is no longer time for the
# ordinary fortnight. What it buys in speed it gives up in tolerance: dry seed is dormant
# and simply waits, but a radicle already out of the coat has no reserve and no root, and
# one afternoon of a dry surface kills it outright rather than delaying it. So the seedbed
# regime for chitted seed is not the ordinary one with the days renumbered -- it is lighter
# and more frequent, because the surface may not be allowed to dry between passes at all.
#
# After emergence the seedling has a root of its own and the ordinary regime is enough; the
# fortnight stands, because what the second week is for is a seedling too shallow to reach
# the water the deep cycle puts down, and that is true however the seed was started.
PRE_GERMINATED_CRITICAL_DAYS = 5


@dataclass(frozen=True, slots=True)
class SeedbedRegime:
    """How often a seedbed is wetted through the day, and how much goes on each time."""

    code: str
    times: tuple[dt.time, ...]
    mm: float

    @property
    def passes(self) -> int:
        """Return how many times a day the seedbed is wetted."""
        return len(self.times)

    @property
    def daily_mm(self) -> float:
        """Return the depth the day's passes put on the surface between them."""
        return round(self.passes * self.mm, 1)


# The ordinary seedbed: three passes across the working day, the first once the dew has gone
# and the last early enough that the leaf dries before dark, because a seedbed wet all night
# grows damping-off rather than grass. They are spread rather than bunched into the afternoon
# because between them they are the day's whole watering on a lawn that has been sown: the
# morning is a third of the day the surface has to survive.
STANDARD_SEEDBED = SeedbedRegime("standard", (dt.time(9, 0), dt.time(13, 0), dt.time(17, 0)), 2.0)

# The chitted seedbed: five lighter passes over the same span, starting in the morning. The
# same water in a day, spread so the top centimetre never gets the two hours it needs to dry
# out, and the last pass no later -- damping-off is a worse risk on chitted seed, not a
# lesser one.
CHITTED_SEEDBED = SeedbedRegime(
    "chitted",
    (dt.time(9, 0), dt.time(11, 0), dt.time(13, 0), dt.time(15, 0), dt.time(17, 0)),
    1.5,
)


def seedbed_depths(regime: SeedbedRegime, target_mm: float, cap_mm: float) -> list[float]:
    """Return how deep each of the day's passes goes, to cover `target_mm` between them.

    A sown lawn is not watered to a schedule of fixed millimetres. It has two jobs at once:
    the surface has to stay damp, which is a floor under every pass however little the lawn
    is using, and the root zone underneath still has to be replaced, which on a hot week is
    more than the floor comes to. So the day's need is divided over the passes, held up to
    the floor and down to what sown ground can take without the seed moving. What will not
    fit is not forced into the day -- the surface would shed it -- and the balance carries
    the rest into tomorrow, which is what it is for.
    """
    if not regime.passes:
        return []
    floor = min(regime.mm, cap_mm)
    share = max(floor, min(cap_mm, target_mm / regime.passes))
    return [round(share, 1)] * regime.passes


def seedbed_regime(*, pre_germinated: bool, days_since_sowing: int | None) -> SeedbedRegime:
    """Return the regime a seedbed is on today.

    Chitted seed gets the intensive regime until it is up, and the ordinary one after that:
    keeping five passes a day on a lawn of rooted seedlings is water spent on the air.
    """
    if not pre_germinated:
        return STANDARD_SEEDBED
    if days_since_sowing is not None and days_since_sowing > PRE_GERMINATED_CRITICAL_DAYS:
        return STANDARD_SEEDBED
    return CHITTED_SEEDBED


# How long after sowing a feed is still the seed's starter feed.
#
# Seedlings root on phosphorus and they root in the first month; after that the calendar
# knows better than the sowing date and the ordinary programme takes over. Extension
# overseeding guides put the starter down at sowing or with the first mowing of the new
# grass, which is two to three weeks in.
STARTER_AFTER_SOWING_DAYS = 28
FIRST_YEAR_DAYS = 365


def feeds_for(cool_season: bool) -> tuple[FeedWindow, ...]:
    """Return the fertilization programme for a grass class."""
    return COOL_SEASON_FEEDS if cool_season else WARM_SEASON_FEEDS


def thresholds_for(cool_season: bool) -> dict[str, float]:
    """Return the soil-temperature thresholds for a grass class."""
    return COOL_SEASON if cool_season else WARM_SEASON


def fold_month(month: int, northern_hemisphere: bool) -> int:
    """Return the month as the northern calendar knows it."""
    return month if northern_hemisphere else (month + 5) % 12 + 1
