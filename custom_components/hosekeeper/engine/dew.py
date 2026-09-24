"""Water on the leaf: how much dew a night lays down, and when the morning has taken it off.

A seedbed's first pass waits for the leaf to dry, and the air is a poor witness to that. Its
humidity falls as soon as the sun warms it, while the dew on the grass below is still
evaporating: on the reporting lawn the station crossed 80 % at 08:34 and the grass was
plainly wet at half past nine. What decides when a leaf dries is how much water is on it and
how fast the day can take it off, which is an energy balance rather than a threshold.

So the leaf is kept as a store. Through the night a surface colder than the dew point
condenses water onto itself; after sunrise the sun and the air evaporate it again; rain and
irrigation top it up. The rate either way is the Penman equation for a wet surface -- the
FAO-56 hourly reference equation with the surface resistance set to zero, since a film of
water offers none -- which is the core of the surface-wetness energy balance models (Pedro
and Gillespie 1982, Magarey and others 2005). Its combination form needs no leaf temperature:
the cooling of the grass below the screen is carried by the net radiation term.
"""

from __future__ import annotations

import math

from . import et

# How much water a short grass canopy holds before it drips. Interception storage for turf
# is given as a few tenths of a millimetre to about a millimetre; half is taken. It caps
# the store, so a night of rain dries off like a heavy dew rather than like a puddle.
LEAF_CAPACITY_MM = 0.5

# Below this the leaf is dry: the last hundredths are films the eye would not call wet.
LEAF_DRY_MM = 0.02

# The least wind the aerodynamic term is given. A still morning is not a vacuum -- there is
# always convection over a warming lawn -- and a cup anemometer stalls well above zero.
LEAF_MIN_WIND_MS = 0.5

# The wind assumed with no anemometer. FAO-56's 2 m/s is a daily mean, and the hours the
# dew forms and lifts in are the calmest of the day; at 2 m/s a humid night lays down almost
# nothing, which would send the first pass out onto a wet leaf. Half of it errs the other way.
LEAF_DEFAULT_WIND_MS = 1.0

# The longest gap between samples that is integrated across. Past it the station was not
# being heard, and what the leaf did meanwhile is unknown rather than zero.
LEAF_MAX_STEP_H = 3.0

# How long the store must have been running by sunrise before its morning is believed. Dew
# is laid down mostly in the second half of the night, and a store started at two has seen
# most of it; one started at six has seen none and reads dry because it was not watching.
LEAF_NIGHT_H = 4.0

STEFAN_BOLTZMANN_W = 5.67e-8  # W m⁻² K⁻⁴


def cloudiness_factor(cloud_fraction: float | None) -> float:
    """Return the FAO-56 cloudiness term of net longwave, 1.35 Rs/Rso - 0.35.

    From cloud cover rather than measured sunshine, so it holds through the night, when
    the dew is being made and there is no sunshine to measure. Cloud cover stands in for
    the sunshine fraction n/N in the Angström relation (eq. 35, a = 0.25, b = 0.50). No
    cloud cover is taken as a clear sky: the most dew, and the later first pass.
    """
    cover = 0.0 if cloud_fraction is None else max(0.0, min(1.0, cloud_fraction))
    relative_shortwave = (0.25 + 0.50 * (1.0 - cover)) / 0.75
    return 1.35 * relative_shortwave - 0.35


def wet_leaf_rate(
    temperature: float,
    humidity: float,
    solar_w: float,
    *,
    wind_ms: float | None = None,
    cloud_fraction: float | None = None,
    elevation_m: float = 0.0,
) -> float:
    """Return how fast a wet leaf is losing water, mm per hour; negative while dew forms.

    `temperature` and `humidity` are the screen's, `solar_w` the incoming shortwave in
    W m⁻². Soil heat flux is taken as a tenth of net radiation by day and half of it by
    night, as FAO-56 does for hourly steps over grass (eqs. 45 and 46).
    """
    humidity = max(0.0, min(100.0, humidity))
    es = et.saturation_vapour_pressure(temperature)
    ea = es * humidity / 100.0
    delta = et.slope_vapour_pressure_curve(temperature)
    gamma = et.psychrometric_constant(elevation_m)
    wind = LEAF_DEFAULT_WIND_MS if wind_ms is None else max(LEAF_MIN_WIND_MS, wind_ms)

    kelvin = temperature + 273.16
    net_longwave = (
        STEFAN_BOLTZMANN_W
        * kelvin**4
        * (0.34 - 0.14 * math.sqrt(ea))
        * cloudiness_factor(cloud_fraction)
    )
    net = (1 - et.ALBEDO_GRASS) * max(0.0, solar_w) - net_longwave
    ground = (0.1 if solar_w > 0 else 0.5) * net
    available = (net - ground) * 0.0036  # W m⁻² to MJ m⁻² h⁻¹

    numerator = 0.408 * delta * available + gamma * 37 / (temperature + 273) * wind * (es - ea)
    return numerator / (delta + gamma)


def step(water_mm: float, rate_mm_h: float, hours: float, *, added_mm: float = 0.0) -> float:
    """Return the water on the leaf after `hours` at `rate_mm_h`, with `added_mm` landed on it."""
    water = water_mm + max(0.0, added_mm) - rate_mm_h * max(0.0, hours)
    return max(0.0, min(LEAF_CAPACITY_MM, water))
