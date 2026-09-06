"""Where the lawn is in its year, from temperatures alone.

Soil temperature is estimated as a running mean of the daily mean air temperature — the
five-to-seven day average that extension services use as a stand-in for a 5 cm probe.
Growing degree days count from 1 January with a 0 °C base, which is what the crabgrass
pre-emergent models use. The season phase combines both with the calendar so that a warm
March and a cold March land in different phases.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import datetime as dt

from .knowledge import programme

SOIL_LAG_DAYS = 5
HEAT_STRESS_TMAX_C = 30.0
HEAT_STRESS_DAYS = 3
FROST_TMIN_C = 0.0


@dataclass(frozen=True, slots=True)
class DayTemps:
    """The temperatures of one past day."""

    date: dt.date
    tmax: float
    tmin: float

    @property
    def tmean(self) -> float:
        """Return the midpoint mean."""
        return (self.tmax + self.tmin) / 2.0


@dataclass(frozen=True, slots=True)
class Phenology:
    """The lawn's position in the season."""

    soil_temperature_c: float | None
    gdd_base0: float
    phase: str
    heat_stress: bool
    frost_recent: bool
    days_to_first_frost: int | None
    """A rough estimate from latitude, refined when frosts are observed."""


def soil_temperature(history: Sequence[DayTemps]) -> float | None:
    """Return the estimated 5 cm soil temperature from the last few days' means."""
    recent = list(history)[-SOIL_LAG_DAYS:]
    if not recent:
        return None
    return sum(day.tmean for day in recent) / len(recent)


def growing_degree_days(history: Sequence[DayTemps], year: int, base_c: float = 0.0) -> float:
    """Return GDD accumulated since 1 January of `year`."""
    return sum(max(0.0, day.tmean - base_c) for day in history if day.date.year == year)


def heat_stress(history: Sequence[DayTemps]) -> bool:
    """Return whether the last few days were all above the stress threshold."""
    recent = list(history)[-HEAT_STRESS_DAYS:]
    return len(recent) == HEAT_STRESS_DAYS and all(d.tmax >= HEAT_STRESS_TMAX_C for d in recent)


def frost_recent(history: Sequence[DayTemps], days: int = 7) -> bool:
    """Return whether any of the last `days` nights froze."""
    return any(d.tmin <= FROST_TMIN_C for d in list(history)[-days:])


def first_frost_estimate(latitude: float, year: int) -> dt.date:
    """Return a first-autumn-frost date from latitude alone.

    Mid-latitude Europe sees its first frost around early November at 45°, a week earlier
    for every degree north and later going south. Crude, and the observed frosts in the
    diary override it once there are any.
    """
    northern = latitude >= 0
    lat = abs(latitude)
    offset_days = int((45.0 - lat) * 7)
    if northern:
        base = dt.date(year, 11, 5)
        return base + dt.timedelta(days=offset_days)
    base = dt.date(year, 5, 5)
    return base + dt.timedelta(days=offset_days)


def season_phase(
    today: dt.date,
    soil_c: float | None,
    *,
    cool_season: bool,
    northern_hemisphere: bool,
    stressed: bool,
) -> str:
    """Return the phase name (dormant, spring_greenup, ..., late_autumn)."""
    month = programme.fold_month(today.month, northern_hemisphere)
    limits = programme.thresholds_for(cool_season)
    if soil_c is None:
        # Calendar only.
        if month in (12, 1, 2):
            return "dormant"
        if month in (3, 4):
            return "spring_greenup"
        if month in (5, 6):
            return "spring_active"
        if month in (7, 8):
            return "summer_stress"
        if month in (9, 10):
            return "autumn_active"
        return "late_autumn"

    if month <= 6:
        if soil_c < limits["growth_start_c"]:
            return "dormant"
        if month <= 4 and soil_c < limits["growth_start_c"] + 4:
            return "spring_greenup"
        if cool_season and (stressed or soil_c >= limits["stress_c"]):
            return "summer_stress"
        return "spring_active"
    if month in (7, 8):
        if cool_season and (stressed or soil_c >= limits["stress_c"] - 2):
            return "summer_stress"
        return "spring_active" if not cool_season else "autumn_active"
    # September onwards.
    if soil_c < limits["growth_stop_c"]:
        return "dormant"
    if month >= 11 or soil_c < limits["growth_start_c"] + 2:
        return "late_autumn"
    if cool_season and stressed:
        return "summer_stress"
    return "autumn_active"


def assess(
    history: Sequence[DayTemps],
    today: dt.date,
    *,
    latitude: float,
    cool_season: bool,
) -> Phenology:
    """Return the phenology for today from the temperature history."""
    northern = latitude >= 0
    soil_c = soil_temperature(history)
    stressed = heat_stress(history)
    frost_date = first_frost_estimate(latitude, today.year)
    if frost_date < today:
        frost_date = first_frost_estimate(latitude, today.year + 1)
    return Phenology(
        soil_temperature_c=None if soil_c is None else round(soil_c, 1),
        gdd_base0=round(growing_degree_days(history, today.year), 1),
        phase=season_phase(
            today, soil_c, cool_season=cool_season, northern_hemisphere=northern, stressed=stressed
        ),
        heat_stress=stressed,
        frost_recent=frost_recent(history),
        days_to_first_frost=(frost_date - today).days,
    )
