"""Water on the leaf: dew laid down by the night and taken off by the morning."""

from __future__ import annotations

import pytest

from custom_components.hosekeeper.engine import dew

# The reporting lawn on 24 September 2026, as its station read it on the hour: temperature,
# humidity, incoming sunshine W/m² and wind m/s. Sunrise was at 07:19. The air crossed 80 %
# at 08:34 and the grass was still plainly wet at half past nine.
MORNING = [
    (0, 16.2, 78, 0, 0.0),
    (1, 15.9, 79, 0, 0.0),
    (2, 15.8, 79, 0, 0.0),
    (3, 16.0, 77, 0, 0.0),
    (4, 15.8, 77, 0, 0.0),
    (5, 14.1, 84, 0, 0.0),
    (6, 13.3, 86, 0, 0.0),
    (7, 12.5, 87, 0, 0.0),
    (8, 12.5, 87, 24, 0.0),
    (9, 17.0, 79, 102, 0.0),
    (10, 18.7, 70, 184, 0.0),
    (11, 20.0, 66, 268, 0.0),
    (12, 22.3, 60, 297, 0.0),
    (13, 23.0, 57, 320, 0.0),
]


def _replay(cloud_fraction: float | None = None) -> list[tuple[int, float]]:
    water = 0.0
    trace = []
    for hour, temperature, humidity, solar, wind in MORNING:
        rate = dew.wet_leaf_rate(
            temperature, humidity, solar, wind_ms=wind, cloud_fraction=cloud_fraction
        )
        water = dew.step(water, rate, 1.0)
        trace.append((hour, water))
    return trace


def test_a_clear_still_night_lays_dew_down() -> None:
    assert dew.wet_leaf_rate(13.0, 87, 0, wind_ms=0.0) < 0


def test_cloud_keeps_the_night_warm_and_the_leaf_drier() -> None:
    """Cloud sends back the longwave a clear sky lets go.

    That loss is what cools a leaf below the dew point in the first place.
    """
    clear = dew.wet_leaf_rate(13.0, 87, 0, wind_ms=0.5, cloud_fraction=0.0)
    overcast = dew.wet_leaf_rate(13.0, 87, 0, wind_ms=0.5, cloud_fraction=1.0)
    assert clear < overcast


def test_wind_mixes_drier_air_down_and_lays_less_dew() -> None:
    still = dew.wet_leaf_rate(13.0, 87, 0, wind_ms=0.5)
    breezy = dew.wet_leaf_rate(13.0, 87, 0, wind_ms=3.0)
    assert still < breezy


def test_the_sun_dries_the_leaf_and_more_sun_dries_it_faster() -> None:
    weak = dew.wet_leaf_rate(18.0, 70, 150, wind_ms=0.5)
    strong = dew.wet_leaf_rate(18.0, 70, 500, wind_ms=0.5)
    assert 0 < weak < strong


def test_a_stalled_anemometer_is_not_taken_as_a_vacuum() -> None:
    assert dew.wet_leaf_rate(13.0, 87, 0, wind_ms=0.0) == dew.wet_leaf_rate(
        13.0, 87, 0, wind_ms=dew.LEAF_MIN_WIND_MS
    )


def test_the_leaf_holds_only_so_much_and_never_less_than_nothing() -> None:
    assert dew.step(0.0, 0.0, 0.0, added_mm=12.0) == dew.LEAF_CAPACITY_MM
    assert dew.step(0.1, 0.5, 1.0) == 0.0
    assert dew.step(0.1, -0.05, 2.0) == pytest.approx(0.2)


def test_the_morning_that_started_this_dries_well_after_the_air_does() -> None:
    """The air crossed 80 % at 08:34; the leaf was wet an hour later, and the store says so.

    It was dry by early afternoon: a model that never lets the leaf dry would be as wrong as
    the threshold it replaces, only in the direction nobody complains about.
    """
    trace = dict(_replay())
    assert trace[7] > 0.1, "a clear, still night leaves a real film of dew by sunrise"
    assert trace[9] > dew.LEAF_DRY_MM, "still wet at nine, as it was"
    assert trace[10] > dew.LEAF_DRY_MM, "and at ten"
    dried = min(hour for hour, water in trace.items() if water <= dew.LEAF_DRY_MM and hour > 7)
    assert 10 < dried <= 13


def test_a_cloudy_night_leaves_less_to_dry() -> None:
    clear = dict(_replay(0.0))
    cloudy = dict(_replay(1.0))
    assert cloudy[7] < clear[7]
