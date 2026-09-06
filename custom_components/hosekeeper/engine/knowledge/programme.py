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

# Mowing: never remove more than a third of the leaf; intervals follow growth.
MOW_INTERVAL_DAYS = {
    "dormant": None,
    "spring_greenup": 10,
    "spring_active": 6,
    "summer_stress": 9,
    "autumn_active": 6,
    "late_autumn": 12,
}

# A robot does not cut like a mower. It takes a few millimetres off the same lawn again and
# again, so it is not held to the third rule but to keeping up with growth: through the two
# flushes it wants to be out most days, and less often when the grass slows in the heat, the
# late autumn and the winter. Robot mower manufacturers' scheduling guidance and
# extension notes on mulching mowers.
ROBOT_PASS_DAYS = {
    "dormant": None,
    "spring_greenup": 3,
    "spring_active": 1,
    "summer_stress": 2,
    "autumn_active": 1,
    "late_autumn": 4,
}

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
