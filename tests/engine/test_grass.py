"""Crop coefficients follow the season on both sides of the equator."""

from __future__ import annotations

from custom_components.hosekeeper.engine.knowledge import grass


def test_cool_season_peaks_in_summer_and_rests_in_winter() -> None:
    assert grass.crop_coefficient("tall_fescue", 7) == 0.85
    assert grass.crop_coefficient("tall_fescue", 4) == 0.80
    assert grass.crop_coefficient("tall_fescue", 1) == 0.60


def test_warm_season_goes_dormant() -> None:
    assert grass.crop_coefficient("bermuda", 7) == 0.65
    assert grass.crop_coefficient("bermuda", 1) == 0.30


def test_southern_hemisphere_folds_the_calendar() -> None:
    assert grass.crop_coefficient("tall_fescue", 1, northern_hemisphere=False) == 0.85
    assert grass.crop_coefficient("tall_fescue", 7, northern_hemisphere=False) == 0.60


def test_unknown_grass_is_a_cool_season_mix() -> None:
    assert grass.profile("moss") == grass.profile("cool_season_mix")
