"""FieldConfig: the entry's data as the engine sees it."""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest

from custom_components.hosekeeper.const import (
    CONF_FLOW_L_MIN,
    CONF_IRRIGATION_TYPE,
    CONF_PRECIPITATION_RATE,
)
from custom_components.hosekeeper.field import FieldConfig


def test_reads_every_field(field_data: dict[str, Any]) -> None:
    field = FieldConfig.from_data(field_data)
    assert field.name == "South lawn"
    assert field.area_m2 == 120.0
    assert (field.latitude, field.longitude) == (45.0, 9.0)
    assert field.establishment_date == dt.date(2025, 4, 12)
    assert field.rain_sensor == "sensor.weather_station_rain"
    assert field.temperature_sensor is None
    assert field.linked_entities == ("weather.forecast_home", "sensor.weather_station_rain")


def test_rate_from_flow_over_area(field_data: dict[str, Any]) -> None:
    # 30 L/min on 120 m² is 1800 L/h, and a litre on a square metre is a millimetre.
    field = FieldConfig.from_data(field_data)
    assert field.application_rate_mm_h == pytest.approx(15.0)
    assert field.minutes_to_mm(20) == pytest.approx(5.0)
    assert field.mm_to_minutes(5.0) == pytest.approx(20.0)


def test_measured_rate_wins(field_data: dict[str, Any]) -> None:
    field = FieldConfig.from_data(field_data | {CONF_PRECIPITATION_RATE: 12.0})
    assert field.application_rate_mm_h == 12.0


def test_no_irrigation_means_no_rate(field_data: dict[str, Any]) -> None:
    data = {**field_data, CONF_IRRIGATION_TYPE: "none"}
    del data[CONF_FLOW_L_MIN]
    field = FieldConfig.from_data(data)
    assert field.application_rate_mm_h is None
    assert field.minutes_to_mm(10) is None
    assert field.mm_to_minutes(10) is None


def test_shade_features_are_summed_and_capped(field_data: dict[str, Any]) -> None:
    from custom_components.hosekeeper.const import CONF_FEATURES

    field = FieldConfig.from_data(field_data)
    assert field.shaded_fraction == 0.0 and not field.has_deciduous_trees
    shaded = FieldConfig.from_data(
        field_data
        | {
            CONF_FEATURES: [
                {"kind": "deciduous_tree", "shade_pct": 30},
                {"kind": "structure", "shade_pct": 20},
                {"kind": "none", "shade_pct": 50},
            ]
        }
    )
    assert shaded.shaded_fraction == pytest.approx(0.5)
    assert shaded.tree_fraction == pytest.approx(0.3)
    assert shaded.has_deciduous_trees
