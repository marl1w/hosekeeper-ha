"""The reservoir and its bookkeeping."""

from __future__ import annotations

import pytest

from custom_components.hosekeeper.engine import water
from custom_components.hosekeeper.engine.knowledge import grass


def test_loam_under_tall_fescue_holds_45_mm() -> None:
    soil = water.soil_water("loam", grass.profile("tall_fescue").root_depth_m)
    assert soil.taw_mm == pytest.approx(45.0)
    assert soil.raw_mm == pytest.approx(22.5)
    assert soil.available_fraction(0.0) == 1.0
    assert soil.available_fraction(22.5) == 0.5
    assert soil.available_fraction(99.0) == 0.0


def test_unknown_soil_is_treated_as_loam() -> None:
    assert water.soil_water("peat", 0.2).taw_mm == water.soil_water("loam", 0.2).taw_mm


def test_effective_rain_discards_drizzle_and_caps_downpours() -> None:
    assert water.effective_rain(0.0) == 0.0
    assert water.effective_rain(1.5) == 0.0
    assert water.effective_rain(8.0) == 8.0
    assert water.effective_rain(60.0) == water.RAIN_CAP_MM


def test_deficit_is_bounded() -> None:
    soil = water.soil_water("sandy", 0.2)  # 14 mm
    assert water.next_deficit(10.0, 5.0, 0.0, 0.0, soil) == soil.taw_mm
    assert water.next_deficit(3.0, 2.0, 20.0, 0.0, soil) == 0.0
    assert water.next_deficit(5.0, 4.0, 0.0, 3.0, soil) == pytest.approx(6.0)


def test_irrigation_waits_for_the_allowed_depletion() -> None:
    soil = water.soil_water("loam", 0.2)  # TAW 30, RAW 15
    assert water.irrigation_needed_mm(10.0, soil) == 0.0
    assert water.irrigation_needed_mm(18.0, soil) == pytest.approx(18.0)


def test_forecast_rain_is_subtracted_only_when_it_counts() -> None:
    soil = water.soil_water("loam", 0.2)
    assert water.irrigation_needed_mm(18.0, soil, forecast_rain_mm=1.0) == pytest.approx(18.0)
    assert water.irrigation_needed_mm(18.0, soil, forecast_rain_mm=10.0) == pytest.approx(8.0)
    assert water.irrigation_needed_mm(18.0, soil, forecast_rain_mm=40.0) == 0.0


def test_roots_grow_with_the_lawn() -> None:
    # Sod laid in June is not a mature lawn in September: it holds a fraction of the water,
    # so it must be watered more often, not more deeply.
    mature = grass.profile("tall_fescue").root_depth_m
    assert grass.root_depth("tall_fescue", None, "sod") == mature
    laid_today = grass.root_depth("tall_fescue", 0, "sod")
    three_months = grass.root_depth("tall_fescue", 90, "sod")
    a_year = grass.root_depth("tall_fescue", 365, "sod")
    assert laid_today == grass.SOD_START_DEPTH_M
    assert laid_today < three_months < a_year == mature
    assert grass.root_depth("tall_fescue", 90, "seed") < three_months

    # And what that means for the watering interval.
    young = water.soil_water("loam", three_months)
    old = water.soil_water("loam", mature)
    assert young.raw_mm < old.raw_mm / 2


def test_a_lawn_that_cannot_take_it_is_asked_for_less() -> None:
    # Half the reserve is what a healthy deep-rooted lawn gives up. A young one, a lawn in a
    # heat wave, or one already rated poorly, is watered sooner and more often instead.
    assert water.allowed_depletion() == water.ALLOWED_DEPLETION
    for reason in ({"young": True}, {"heat_stress": True}, {"struggling": True}):
        assert water.allowed_depletion(**reason) == water.CAUTIOUS_DEPLETION

    depth = grass.root_depth("tall_fescue", 92, "sod")
    healthy = water.soil_water("loam", depth)
    careful = water.soil_water("loam", depth, water.allowed_depletion(young=True))
    assert careful.raw_mm < healthy.raw_mm
    # Which is the difference between watering a three-month-old lawn every three days and
    # every two, at three millimetres a day of use.
    assert round(healthy.raw_mm / 3.1) == 3
    assert round(careful.raw_mm / 3.1) == 2
