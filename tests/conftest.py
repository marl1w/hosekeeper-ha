"""Shared fixtures."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
import pytest

from custom_components.hosekeeper.const import (
    CONF_AREA,
    CONF_ESTABLISHMENT_DATE,
    CONF_ESTABLISHMENT_METHOD,
    CONF_EXPOSURE,
    CONF_FLOW_L_MIN,
    CONF_GRASS_TYPE,
    CONF_IRRIGATION_TYPE,
    CONF_LOCATION,
    CONF_RAIN_SENSOR,
    CONF_SOIL_TYPE,
    CONF_WEATHER_ENTITY,
)

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make the custom integration loadable in every test."""
    return enable_custom_integrations


@pytest.fixture
def field_data() -> dict[str, Any]:
    """Return a complete, valid config entry for a lawn in the test site."""
    return {
        CONF_NAME: "South lawn",
        CONF_AREA: 120.0,
        CONF_LOCATION: {CONF_LATITUDE: 45.0, CONF_LONGITUDE: 9.0},
        CONF_EXPOSURE: "full_sun",
        CONF_SOIL_TYPE: "loam",
        CONF_GRASS_TYPE: "tall_fescue",
        CONF_ESTABLISHMENT_METHOD: "sod",
        CONF_ESTABLISHMENT_DATE: "2025-04-12",
        CONF_IRRIGATION_TYPE: "pop_up_spray",
        CONF_FLOW_L_MIN: 30.0,
        CONF_WEATHER_ENTITY: "weather.forecast_home",
        CONF_RAIN_SENSOR: "sensor.weather_station_rain",
    }
