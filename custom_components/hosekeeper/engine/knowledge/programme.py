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
import math


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


def standing_height(kept_mm: float, phase: str, days_since_mowing: int | None) -> float:
    """Return about how tall the leaf is standing now, given when it was last cut.

    Nothing measures the grass, so the only honest estimate is where it was put and what the
    season has added since. It is what the third rule has to be read against: the rule is
    about the leaf that is there today, not about the height the deck was set to a week ago.
    """
    growth = GROWTH_MM_DAY.get(phase)
    if not growth or not days_since_mowing:
        return kept_mm
    return kept_mm + growth * days_since_mowing


def third_rule_floor(standing_mm: float) -> int:
    """Return the lowest a cut can be set to without taking more than a third of the leaf."""
    return round(standing_mm * (2.0 / 3.0))


# A deck is set in notches, not in millimetres. "Cut at 79 mm" is arithmetic read out loud:
# nobody can set it, and the person reading it has to round it themselves, which is the one
# part of the advice the engine should not be handing back. Five millimetres is about the
# step a mower gives, and rounding up rather than down keeps the third rule intact -- a
# height rounded down takes more leaf than the rule allows, which is what it is there for.
MOW_HEIGHT_STEP_MM = 5


def to_deck_step(height_mm: float) -> int:
    """Return the height rounded up to a notch a mower can actually be set to."""
    step = MOW_HEIGHT_STEP_MM
    return int(-(-round(height_mm) // step) * step)


def next_cut_height(
    kept_mm: float,
    target_mm: int,
    phase: str,
    days_since_mowing: int | None,
    deck_max_mm: int | None = None,
) -> int:
    """Return the height to set for the next cut on a lawn climbing back from a low one.

    Half again the last cut is where the lawn is going; the third rule is what it is allowed
    to do today, and the two are not the same number once a recovery cut has been missed. A
    sward taken to 20 mm and left a week is standing at 60 by then, and "half again the last
    cut" still says 30 -- which is not a step back up, it is the scalp the rule exists to
    prevent, taken on grass that is also carrying new seed. So the climb sets the floor and
    the leaf standing there sets the floor under that, and the higher of the two wins.

    It may come out above the target: grass that has run away is brought down in stages, and
    a cut that cannot be made without breaking the rule is not made. What it cannot come out
    above is the deck, because a height the mower has no setting for is not advice.
    """
    climb = min(target_mm, round(kept_mm * RAISE_FACTOR))
    floor = third_rule_floor(standing_height(kept_mm, phase, days_since_mowing))
    height = max(climb, floor)
    # The target is a height the mower is known to reach, so it is left exactly as it is.
    # Every other number here is arithmetic -- two thirds of an estimated leaf, half again a
    # recorded cut -- and goes on a notch before it is read out as an instruction.
    if height != target_mm:
        height = to_deck_step(height)
    if deck_max_mm is not None:
        height = min(height, deck_max_mm)
    return int(height)


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


# How many passes a day's drying power asks for.
#
# Reference evapotranspiration is the rate the surface loses water, so it is what the number
# of passes follows: the base is the demand three passes comfortably hold, and every further
# millimetre of it buys one more, up to what a controller can be set to. Six start times per
# programme is the common limit on domestic controllers (Hunter, Rain Bird, Gardena), and it
# is also about the point past which the passes are too light to wet anything.
SEEDBED_ET0_BASE_MM = 1.5
SEEDBED_ET0_PER_PASS_MM = 1.0
SEEDBED_MAX_PASSES = 6


@dataclass(frozen=True, slots=True)
class SeedbedRegime:
    """How often a seedbed is wetted through the day, and how much goes on each time."""

    code: str
    min_passes: int
    """The fewest passes that hold a surface damp, on a day with little drying power."""
    mm: float

    def passes_for(self, et0_mm: float | None) -> int:
        """Return how many passes today asks for, given the day's drying power.

        A seedbed is not lost to the day's total evaporation; it is lost to the longest gap
        between two waterings. So the count follows the rate the surface dries at, and the
        depth of each follows from the day's total divided among them. On a cool, overcast
        day three passes hold the top centimetre; on a hot bright one the same water in three
        goes to the air between them and the surface is dry by mid-afternoon, whatever the
        daily total says.

        The curve is deliberately cautious. A pass too many costs a few minutes of water; a
        surface allowed to dry once costs the sowing, and the loss is not symmetrical.
        """
        if et0_mm is None:
            return self.min_passes
        over = max(0.0, et0_mm - SEEDBED_ET0_BASE_MM)
        return min(SEEDBED_MAX_PASSES, self.min_passes + int(over // SEEDBED_ET0_PER_PASS_MM))

    @property
    def passes(self) -> int:
        """Return the fewest passes the regime runs, for a day whose weather is not known."""
        return self.min_passes

    def daily_mm_for(self, passes: int) -> float:
        """Return the depth a day of `passes` puts on the surface between them."""
        return round(passes * self.mm, 1)

    @property
    def daily_mm(self) -> float:
        """Return the depth the fewest passes put on, for a day with no weather yet."""
        return self.daily_mm_for(self.min_passes)


# The ordinary seedbed: three passes at least, across the part of the day that dries, the
# first once the dew has gone and the last early enough that the leaf dries before dark,
# because a seedbed wet all night grows damping-off rather than grass. They are spread rather
# than bunched into the afternoon because between them they are the day's whole watering on a
# lawn that has been sown: the morning is a third of the day the surface has to survive.
STANDARD_SEEDBED = SeedbedRegime("standard", 3, 2.0)

# The chitted seedbed: five lighter passes at least, over the same span. The same water in a
# day, spread so the top centimetre never gets the two hours it needs to dry out, and the
# last pass no later -- damping-off is a worse risk on chitted seed, not a lesser one.
CHITTED_SEEDBED = SeedbedRegime("chitted", 5, 1.5)


# Where the passes sit in the day, which is a question about the sun and not about the clock.
#
# The times used to be fixed at nine, one and five. That is right for midsummer and wrong for
# the seeding months at either end of it: in late September at 45 degrees the sun is not up
# until twenty past seven, the dew is still on the leaf at nine, and a pass then waters water
# -- it adds nothing to the soil and adds an hour to the leaf wetness that drives dollar spot
# and damping-off. The window therefore hangs off sunrise and sunset, and moves through the
# season with them.
#
# The first pass waits for the dew to lift, which is roughly three hours after sunrise on a
# clear morning. The last finishes far enough before sunset that the canopy dries standing
# up: three hours, the figure extension guidance uses for evening irrigation cut-offs.
SEEDBED_AFTER_SUNRISE = dt.timedelta(hours=3)
SEEDBED_BEFORE_SUNSET = dt.timedelta(hours=3)

# Three hours is a clear morning at a middle latitude, and a lawn with a hygrometer on it
# need not be guessed at. Relative humidity is the surrogate the disease models already use
# for leaf wetness -- Smith-Kerns is built on it -- and 80 % is where the leaf is taken to
# have dried. So when the lawn's own humidity has been watched through a morning, the hour
# it crossed is the hour the dew lifted, and it replaces the rule of thumb.
#
# Within limits, because one morning is not a habit and a hygrometer in a hedge is not a
# lawn. The observed hour is never taken earlier than an hour after sunrise, which is about
# the soonest a real canopy dries, nor later than solar noon, past which the morning is gone
# and a seedbed that has waited that long has waited too long.
SEEDBED_DEW_RH_PCT = 80.0
SEEDBED_DEW_EARLIEST = dt.timedelta(hours=1)
SEEDBED_DEW_LATEST = dt.timedelta(hours=6)

# What shade does to the two margins.
#
# Dew burns off when the sun reaches the leaf, so a zone under a wall or a canopy keeps its
# for longer in the morning and stops drying earlier in the evening -- the same hours of
# daylight, fewer of them with any drying power in them. Both margins therefore widen with
# the shaded fraction, an hour and a half at full shade, which is about the difference
# turfgrass shade trials report between a north wall and open ground in autumn.
#
# It is applied to the observed hour as well as to the assumed one, because a weather
# station stands in the open by definition: what it reports is when open ground dried, and
# the shaded part of a zone is still wet when it did. A lawn whose hygrometer sits in the
# shade will be watered a little late for it, which is the safer of the two errors.
SEEDBED_SHADE_DELAY = dt.timedelta(minutes=90)


def seedbed_window(
    sunrise: dt.time,
    sunset: dt.time,
    dew_clear: dt.time | None = None,
    shaded_fraction: float = 0.0,
) -> tuple[dt.time, dt.time]:
    """Return the first and last hour a seedbed's passes may run on a day with this sun.

    `dew_clear` is the hour the lawn's own humidity says the leaf dried, averaged over the
    mornings there are records for. Given one, it stands in for the three-hour rule of thumb.
    `shaded_fraction` then pushes both margins in, because shaded turf dries later and stops
    drying sooner; the result is clamped to the span a canopy plausibly dries in.
    """
    day = dt.date(2000, 1, 1)
    up = dt.datetime.combine(day, sunrise)
    shade = SEEDBED_SHADE_DELAY * max(0.0, min(1.0, shaded_fraction))
    first = up + SEEDBED_AFTER_SUNRISE + shade
    if dew_clear is not None:
        first = dt.datetime.combine(day, dew_clear) + shade
    first = min(max(first, up + SEEDBED_DEW_EARLIEST), up + SEEDBED_DEW_LATEST)
    last = dt.datetime.combine(day, sunset) - SEEDBED_BEFORE_SUNSET - shade
    if last - first < SEEDBED_MIN_SPAN:
        # Short days, or deep shade: give up the drying margin before the dew margin, because
        # a pass onto a wet leaf is wasted outright while one a little late merely dries a
        # little slower.
        last = min(first + SEEDBED_MIN_SPAN, dt.datetime.combine(day, sunset))
    return first.time(), last.time()


# What is left when the days are too short for that to be true at both ends. Deep in the
# autumn window the useful span closes to nothing, and the seedbed still has to be wetted;
# the dew matters more than the drying then, because there is little drying left to do.
SEEDBED_MIN_SPAN = dt.timedelta(hours=2)


# The grid the passes are put on.
#
# A seedbed's window moves a minute or two a day, and a schedule that moves with it is a
# schedule nobody can keep: these times are typed into a controller by hand, and "10:18
# today, 10:20 tomorrow" is a job no one will do twice. So the passes land on the half hour,
# which is coarse enough to stay put for weeks at a time and fine enough to divide any
# window a seedbed is watered in.
#
# Both ends round inward, never outward: the first pass to the half hour at or after the dew
# has lifted, the last to the one at or before the drying margin closes. Rounding the other
# way would spend the margin that was the point of the window.
SEEDBED_SLOT_MINUTES = 30


def _slot(at: dt.time, *, up: bool) -> int:
    """Return the half-hour slot at or after `at`, or at or before it."""
    minutes = at.hour * 60 + at.minute
    if up:
        return -(-minutes // SEEDBED_SLOT_MINUTES)
    return minutes // SEEDBED_SLOT_MINUTES


def _at_slot(slot: int) -> dt.time:
    """Return the time a half-hour slot stands for."""
    minutes = min(slot * SEEDBED_SLOT_MINUTES, 24 * 60 - 1)
    return dt.time(minutes // 60, minutes % 60)


def seedbed_times(count: int, window: tuple[dt.time, dt.time]) -> tuple[dt.time, ...]:
    """Return `count` pass times spread evenly across the window, on the half hour.

    Evenly, because what the seedbed cares about is the longest gap between two waterings,
    and even spacing is what makes the longest gap as short as the count allows. On the half
    hour, because the times are kept by hand and a schedule that drifts with the sunrise is
    one nobody will keep up with.

    A window with fewer half hours in it than the day asked for passes gets the passes it has
    room for: two runs in the same slot are one run, and the water is better in fewer,
    heavier passes than in a count the clock cannot express.
    """
    if count <= 0:
        return ()
    first = _slot(window[0], up=True)
    last = _slot(window[1], up=False)
    if last < first:
        # A window too narrow to hold a whole slot -- deep in the autumn, or a lawn far
        # enough north. One pass, at the half hour the window is nearest to covering.
        return (_at_slot(first if window[0] != window[1] else last),)
    count = min(count, last - first + 1)
    if count == 1:
        return (_at_slot(last),)
    span = last - first
    return tuple(_at_slot(first + round(span * i / (count - 1))) for i in range(count))


# What rain has to come to before a seedbed's day is called off entirely.
#
# A forecast gives a day's total and says nothing about when in the day it falls. Six
# millimetres at three in the morning leaves a seedbed dry by five in the afternoon, and a
# seedbed allowed to dry once is a seedbed sown twice -- the loss is not symmetrical, so the
# caution is not either. Rain therefore comes off what the day owes, which is enough to stop
# the sprinklers running into a wet morning, but the last pass of the day is kept until the
# rain is heavy enough that the surface cannot plausibly have dried before dark.
SEEDBED_SOAKING_MM = 15.0

# The least a pass may be and still be worth running. Below about a millimetre the water
# wets the leaf, the leaf holds it, and the soil under it is no damper than it was -- the
# canopy interception alone accounts for a few tenths.
SEEDBED_MIN_PASS_MM = 0.8


def seedbed_passes(
    regime: SeedbedRegime, day_mm: float, cap_mm: float, passes: int | None = None
) -> list[float]:
    """Return the depths of the passes a day needs, to put `day_mm` on between them.

    A sown lawn is not watered to a schedule of fixed millimetres. It has two jobs at once:
    the surface has to stay damp, which is a floor under the day however little the lawn is
    using, and the root zone underneath still has to be replaced, which on a hot week is more
    than the floor comes to. The caller works out what the day owes, rain included; this
    divides it into runs, each held up to the floor and down to what sown ground can take
    without the seed moving. What will not fit is not forced into the day -- the surface would
    shed it -- and the balance carries the rest into tomorrow, which is what it is for.

    A day that owes less than one pass gets none. Watering a seedbed is not a ritual: when
    rain has done the job, half a millimetre spread over three runs wets nothing, costs the
    water anyway, and leaves a canopy damp at an hour nothing will dry it. Fewer, proper
    passes beat more, token ones -- and the ones kept are the late ones, because the surface
    is wettest in the morning, from dew and from whatever fell overnight, and driest by the
    end of the afternoon.
    """
    most = SEEDBED_MAX_PASSES if passes is None else passes
    depth = min(regime.mm, cap_mm)
    if most <= 0 or day_mm <= 0 or depth < SEEDBED_MIN_PASS_MM:
        return []
    # A pass is one size, and the day varies by how many of them it gets.
    #
    # It used to be the other way about: the day's water was divided by the count, so a pass
    # was whatever was left over after arithmetic. Two things then moved at once -- the count
    # with the drying rate, the depth inversely with the count -- and the run length came out
    # different almost every day: ten minutes, then four, then nine, on a lawn whose daily
    # total had barely shifted. On a system set by hand that is unusable, and it was never
    # meaningful: what makes a pass the right size is the soil and the seed, not the day's
    # remainder. Two millimetres wets the top centimetre and does not float seed, and that is
    # true on Tuesday as well.
    #
    # So the depth is the regime's, held down only by what sown ground can take at once, and
    # the day is simply how many of them its water comes to. The drying rate does not appear
    # here at all: it sets the floor under the day's water, which is the caller's business,
    # and a hot day therefore arrives with more millimetres and leaves with more passes. Rain
    # comes off the same total and takes whole passes off the day with it.
    #
    # The ceiling is what a controller can be set to. What the day owes beyond it is not
    # forced in -- the surface would shed it -- and the balance carries the rest into
    # tomorrow, which is what it is for.
    count = min(most, math.ceil(day_mm / depth))
    return [round(depth, 1)] * max(0, count)


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
