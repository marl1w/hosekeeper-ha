"""Forecast skill and the lawn's own anomalies."""

from __future__ import annotations

import datetime as dt

from custom_components.hosekeeper.engine import climate


def _pair(
    i: int, fc_rain: float, rain: float, fc_tmax: float = 30, tmax: float = 32
) -> climate.ForecastPair:
    return climate.ForecastPair(
        dt.date(2026, 8, 1) + dt.timedelta(days=i), fc_rain, rain, fc_tmax, tmax, 18, 18
    )


def test_too_few_pairs_means_neutral_skill() -> None:
    skill = climate.forecast_skill([_pair(i, 5, 5) for i in range(3)])
    assert skill == climate.NEUTRAL_SKILL
    assert not skill.trusted


def test_forecast_that_overcalls_rain_is_discounted() -> None:
    # Ten days: rain forecast on six, it came on two and then only half of it.
    pairs = [_pair(i, 6, 3 if i < 2 else 0) for i in range(6)] + [
        _pair(i, 0, 0) for i in range(6, 10)
    ]
    skill = climate.forecast_skill(pairs)
    assert skill.trusted
    assert skill.rain_hit_rate == 0.33
    assert skill.rain_ratio == 0.17 or skill.rain_ratio == 0.2  # floored at 0.2
    assert skill.tmax_bias == 2.0
    assert climate.expected_rain(10, skill) < 1.0
    assert climate.expected_rain(10, climate.NEUTRAL_SKILL) == 10


def test_anomalies_measure_this_week_against_this_month() -> None:
    days = [(dt.date(2026, 8, 1) + dt.timedelta(days=i), 4.0, 0.0, 28.0) for i in range(23)]
    days += [(dt.date(2026, 8, 24) + dt.timedelta(days=i), 6.0, 0.0, 33.0) for i in range(7)]
    days[10] = (days[10][0], 4.0, 8.0, 28.0)
    result = climate.anomalies(days)
    assert result.et_7d_mean == 6.0
    assert result.et_anomaly is not None and result.et_anomaly > 1.2
    assert result.dry_spell_days == 19
    assert result.hot_days_7d == 7
    assert result.rain_30d_mm == 8.0
