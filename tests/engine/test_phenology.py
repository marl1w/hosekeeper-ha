"""Soil temperature, degree days and the season phase."""

from __future__ import annotations

import datetime as dt

from custom_components.hosekeeper.engine import phenology


def _days(start: dt.date, temps: list[tuple[float, float]]) -> list[phenology.DayTemps]:
    return [
        phenology.DayTemps(start + dt.timedelta(days=i), tmax, tmin)
        for i, (tmax, tmin) in enumerate(temps)
    ]


def test_soil_temperature_is_a_five_day_mean() -> None:
    days = _days(dt.date(2026, 4, 1), [(20, 10)] * 3 + [(30, 20)] * 5)
    assert phenology.soil_temperature(days) == 25.0
    assert phenology.soil_temperature([]) is None


def test_gdd_counts_only_this_year_above_base() -> None:
    days = _days(dt.date(2025, 12, 30), [(10, 0)] * 4)  # two days in 2025, two in 2026
    assert phenology.growing_degree_days(days, 2026) == 10.0


def test_heat_stress_needs_three_hot_days() -> None:
    assert phenology.heat_stress(_days(dt.date(2026, 7, 1), [(31, 20)] * 3))
    assert not phenology.heat_stress(_days(dt.date(2026, 7, 1), [(31, 20), (28, 19), (31, 20)]))


def test_phase_follows_soil_not_only_calendar() -> None:
    kwargs = {"cool_season": True, "northern_hemisphere": True, "stressed": False}
    assert phenology.season_phase(dt.date(2026, 3, 20), 5.0, **kwargs) == "dormant"
    assert phenology.season_phase(dt.date(2026, 3, 20), 9.0, **kwargs) == "spring_greenup"
    assert phenology.season_phase(dt.date(2026, 5, 20), 16.0, **kwargs) == "spring_active"
    assert phenology.season_phase(dt.date(2026, 7, 20), 23.0, **kwargs) == "summer_stress"
    assert phenology.season_phase(dt.date(2026, 9, 20), 18.0, **kwargs) == "autumn_active"
    assert phenology.season_phase(dt.date(2026, 11, 20), 7.0, **kwargs) == "late_autumn"
    assert phenology.season_phase(dt.date(2026, 12, 20), 4.0, **kwargs) == "dormant"


def test_warm_season_grows_through_july() -> None:
    assert (
        phenology.season_phase(
            dt.date(2026, 7, 20), 26.0, cool_season=False, northern_hemisphere=True, stressed=True
        )
        == "spring_active"
    )


def test_first_frost_moves_with_latitude() -> None:
    assert phenology.first_frost_estimate(45.0, 2026) == dt.date(2026, 11, 5)
    assert phenology.first_frost_estimate(50.0, 2026) < dt.date(2026, 11, 5)
    # South of the equator the frost comes in the southern autumn, later nearer the tropics.
    assert phenology.first_frost_estimate(-35.0, 2026) > dt.date(2026, 5, 5)


def test_assess_bundles_it_up() -> None:
    days = _days(dt.date(2026, 9, 1), [(30, 18)] * 5)
    result = phenology.assess(days, dt.date(2026, 9, 6), latitude=45.0, cool_season=True)
    assert result.soil_temperature_c == 24.0
    assert result.phase == "summer_stress"
    assert result.heat_stress
    assert result.days_to_first_frost == 60
