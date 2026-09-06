"""The forecast against what actually happened, and what the lawn's own history says.

Every day the forecast that was issued for it is kept beside what the station measured. Over
a month that gives the forecast's local habits — rain that is called and does not come, highs
the models put too low under summer haze — and tomorrow's forecast is weighted by them
before the engine trusts it. The same history gives the field's own normal, so a dry spell or
a heat wave is measured against this lawn's recent weeks rather than a textbook.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import datetime as dt
import statistics

FORECAST_WINDOW_DAYS = 30
MIN_PAIRS = 5
RAIN_EVENT_MM = 2.0


@dataclass(frozen=True, slots=True)
class ForecastPair:
    """What was predicted for a day and what was measured."""

    date: dt.date
    forecast_rain: float | None
    actual_rain: float | None
    forecast_tmax: float | None
    actual_tmax: float | None
    forecast_tmin: float | None
    actual_tmin: float | None


@dataclass(frozen=True, slots=True)
class ForecastSkill:
    """The forecast's local bias, learnt from pairs."""

    pairs: int
    rain_ratio: float
    """Measured rain over forecast rain, on days rain was forecast. 1.0 is honest."""
    rain_hit_rate: float
    """Share of forecast rain events (≥ 2 mm) that actually delivered ≥ 2 mm."""
    tmax_bias: float
    """Mean of measured minus forecast highs. Positive: the forecast runs cool."""
    tmin_bias: float

    @property
    def trusted(self) -> bool:
        """Return whether enough days were compared to weigh the forecast at all."""
        return self.pairs >= MIN_PAIRS


NEUTRAL_SKILL = ForecastSkill(0, 1.0, 1.0, 0.0, 0.0)


def forecast_skill(pairs: Sequence[ForecastPair]) -> ForecastSkill:
    """Return the forecast's bias over the pairs given."""
    complete = [p for p in pairs if p.forecast_rain is not None and p.actual_rain is not None]
    if len(complete) < MIN_PAIRS:
        return NEUTRAL_SKILL
    rainy_forecasts = [p for p in complete if p.forecast_rain >= RAIN_EVENT_MM]
    if rainy_forecasts:
        forecast_total = sum(p.forecast_rain for p in rainy_forecasts)
        actual_total = sum(p.actual_rain for p in rainy_forecasts)
        ratio = actual_total / forecast_total if forecast_total > 0 else 1.0
        hits = sum(1 for p in rainy_forecasts if p.actual_rain >= RAIN_EVENT_MM)
        hit_rate = hits / len(rainy_forecasts)
    else:
        ratio, hit_rate = 1.0, 1.0
    tmax_pairs = [
        p.actual_tmax - p.forecast_tmax
        for p in pairs
        if p.actual_tmax is not None and p.forecast_tmax is not None
    ]
    tmin_pairs = [
        p.actual_tmin - p.forecast_tmin
        for p in pairs
        if p.actual_tmin is not None and p.forecast_tmin is not None
    ]
    return ForecastSkill(
        pairs=len(complete),
        rain_ratio=round(max(0.2, min(2.0, ratio)), 2),
        rain_hit_rate=round(hit_rate, 2),
        tmax_bias=round(statistics.fmean(tmax_pairs), 1) if tmax_pairs else 0.0,
        tmin_bias=round(statistics.fmean(tmin_pairs), 1) if tmin_pairs else 0.0,
    )


def expected_rain(forecast_mm: float | None, skill: ForecastSkill) -> float:
    """Return the rain to plan on, given what the forecast said and how it has behaved.

    The ratio corrects the amount; the hit rate discounts it for the chance that nothing
    falls at all. An unproven forecast is taken at face value.
    """
    if not forecast_mm:
        return 0.0
    if not skill.trusted:
        return forecast_mm
    return round(forecast_mm * skill.rain_ratio * skill.rain_hit_rate, 1)


@dataclass(frozen=True, slots=True)
class Anomalies:
    """This week against this lawn's recent weeks."""

    et_7d_mean: float | None
    et_30d_mean: float | None
    et_anomaly: float | None
    """7-day mean over 30-day mean, 1.0 is normal; 1.3 is a demanding week."""
    dry_spell_days: int
    """Days since the last rain event of 2 mm or more."""
    rain_30d_mm: float
    hot_days_7d: int
    """Days in the last week with a high of 30 °C or more."""


def anomalies(
    days: Sequence[tuple[dt.date, float | None, float | None, float | None]],
) -> Anomalies:
    """Return the anomalies from (date, et0, rain, tmax) tuples, oldest first."""
    ordered = sorted(days, key=lambda d: d[0])
    last7 = ordered[-7:]
    last30 = ordered[-30:]
    et7 = [d[1] for d in last7 if d[1] is not None]
    et30 = [d[1] for d in last30 if d[1] is not None]
    mean7 = statistics.fmean(et7) if et7 else None
    mean30 = statistics.fmean(et30) if et30 else None
    anomaly = None
    if mean7 is not None and mean30:
        anomaly = round(mean7 / mean30, 2)
    dry = 0
    for _, _, rain, _ in reversed(ordered):
        if rain is not None and rain >= RAIN_EVENT_MM:
            break
        dry += 1
    return Anomalies(
        et_7d_mean=None if mean7 is None else round(mean7, 2),
        et_30d_mean=None if mean30 is None else round(mean30, 2),
        et_anomaly=anomaly,
        dry_spell_days=dry,
        rain_30d_mm=round(sum(d[2] or 0.0 for d in last30), 1),
        hot_days_7d=sum(1 for d in last7 if d[3] is not None and d[3] >= 30.0),
    )
