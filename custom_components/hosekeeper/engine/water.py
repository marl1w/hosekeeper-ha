"""A soil water balance for turf: how far the root zone is from full, in millimetres.

The bookkeeping is FAO-56 chapter 8 reduced to what a lawn needs. The root zone holds a
total available water (TAW) that depends on soil texture and rooting depth; the grass can
draw a fraction of that (the readily available water, RAW) before it starts to suffer.
Every day evapotranspiration adds to the deficit and rain or irrigation take away from it,
and the deficit can neither go negative (excess drains) nor exceed TAW (the grass would be
dead by then anyway).
"""

from __future__ import annotations

from dataclasses import dataclass

# Total available water per metre of soil, FAO-56 table 19, midpoints of the ranges.
TAW_MM_PER_M: dict[str, float] = {
    "sandy": 70.0,
    "sandy_loam": 110.0,
    "loam": 150.0,
    "clay_loam": 170.0,
    "clay": 160.0,
}

# The fraction of TAW turf can use before stress shows, FAO-56 table 22 gives 0.50 for
# turf grass; cool-season turf is on the sensitive side of that.
ALLOWED_DEPLETION = 0.50

# And the fraction to use when the lawn cannot take that much.
#
# Half the profile is what a healthy, deep-rooted lawn will give up without complaint. A
# lawn in its first year has not built that reserve; a lawn in a heat wave is using water to
# cool itself and stops being able to when the soil tightens; a lawn already rated poor has
# no margin left to spend. FAO-56 lowers the depletion fraction as demand rises for exactly
# this reason (eq. 84). Each of these takes the lawn a step nearer to being watered little
# and often, which is right for a lawn that cannot yet do anything else.
CAUTIOUS_DEPLETION = 0.30
YOUNG_LAWN_DAYS = 365


def allowed_depletion(
    *, young: bool = False, heat_stress: bool = False, struggling: bool = False
) -> float:
    """Return how much of the reserve this lawn should be asked to give up."""
    if young or heat_stress or struggling:
        return CAUTIOUS_DEPLETION
    return ALLOWED_DEPLETION


# How fast water enters each soil, millimetres an hour, once it is no longer dry. A system
# that puts water down faster than this makes puddles and runoff, however long it runs.
# FAO-56 chapter 7 and USDA infiltration classes, rounded to the class midpoint.
INFILTRATION_MM_H: dict[str, float] = {
    "sandy": 30.0,
    "sandy_loam": 20.0,
    "loam": 12.0,
    "clay_loam": 8.0,
    "clay": 5.0,
}

# The most a single run should put down before the surface seals and the rest runs off.
# Roughly an hour of infiltration, which is what cycle-and-soak guidance assumes.
MAX_SINGLE_APPLICATION_MM: dict[str, float] = {
    "sandy": 20.0,
    "sandy_loam": 16.0,
    "loam": 12.0,
    "clay_loam": 9.0,
    "clay": 6.0,
}


def infiltration_rate(soil_type: str) -> float:
    """Return how fast the soil takes water, millimetres an hour."""
    return INFILTRATION_MM_H.get(soil_type, INFILTRATION_MM_H["loam"])


def max_single_application(soil_type: str) -> float:
    """Return the most one run should apply before water starts to run off."""
    return MAX_SINGLE_APPLICATION_MM.get(soil_type, MAX_SINGLE_APPLICATION_MM["loam"])


# Rain below this over a day mostly wets leaves and the top few millimetres and is gone
# by noon; it does not reach the roots.
RAIN_THRESHOLD_MM = 2.0

# Rain heavier than this in a day runs off or drains past turf roots on most soils.
RAIN_CAP_MM = 35.0


@dataclass(frozen=True, slots=True)
class SoilWater:
    """The reservoir the grass lives in."""

    taw_mm: float
    raw_mm: float

    def available_fraction(self, deficit_mm: float) -> float:
        """Return how full the root zone is, 1.0 at field capacity."""
        if self.taw_mm <= 0:
            return 0.0
        return max(0.0, min(1.0, 1.0 - deficit_mm / self.taw_mm))


def soil_water(
    soil_type: str, root_depth_m: float, allowed_depletion: float = ALLOWED_DEPLETION
) -> SoilWater:
    """Return the reservoir for a soil texture and rooting depth."""
    taw = TAW_MM_PER_M.get(soil_type, TAW_MM_PER_M["loam"]) * root_depth_m
    return SoilWater(taw_mm=taw, raw_mm=taw * allowed_depletion)


def effective_rain(rain_mm: float) -> float:
    """Return the part of a day's rain that reaches the root zone."""
    if rain_mm <= RAIN_THRESHOLD_MM:
        return 0.0
    return min(rain_mm, RAIN_CAP_MM)


def next_deficit(
    previous_mm: float, etc_mm: float, rain_mm: float, irrigation_mm: float, soil: SoilWater
) -> float:
    """Return the deficit after one day's water in and out."""
    deficit = previous_mm + etc_mm - effective_rain(rain_mm) - irrigation_mm
    return max(0.0, min(soil.taw_mm, deficit))


def irrigation_needed_mm(
    deficit_mm: float, soil: SoilWater, forecast_rain_mm: float = 0.0
) -> float:
    """Return how much to irrigate now, or 0 if the grass can wait.

    Watering starts when the readily available water is used up and refills the root
    zone completely — deep and infrequent is what grows deep roots. Rain the forecast
    promises within the next day is trusted only past the same threshold real rain has
    to pass, and is then subtracted.
    """
    if deficit_mm < soil.raw_mm:
        return 0.0
    expected = effective_rain(forecast_rain_mm)
    return max(0.0, deficit_mm - expected)
