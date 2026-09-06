"""Shared fixtures."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntryState, ConfigSubentryData
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.util import slugify
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hosekeeper.const import (
    CONF_AREA,
    CONF_ESTABLISHMENT_DATE,
    CONF_ESTABLISHMENT_METHOD,
    CONF_EXPOSURE,
    CONF_FLOW_L_MIN,
    CONF_GRASS_TYPE,
    CONF_HUMIDITY_SENSOR,
    CONF_IRRIGATION_TYPE,
    CONF_LOCATION,
    CONF_MOWER_ENTITY,
    CONF_PRECIPITATION_RATE,
    CONF_RAIN_SENSOR,
    CONF_SOIL_MOISTURE_SENSOR,
    CONF_SOIL_TYPE,
    CONF_SOLAR_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_WEATHER_ENTITY,
    CONF_WIND_SENSOR,
    DOMAIN,
    ZONE_SUBENTRY,
)

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Make the custom integration loadable in every test."""
    return enable_custom_integrations


@pytest.fixture
def lawn_data() -> dict[str, Any]:
    """Return a lawn: where it is, what it is made of, and what waters it."""
    return {
        CONF_NAME: "The lawn",
        CONF_LOCATION: {CONF_LATITUDE: 45.0, CONF_LONGITUDE: 9.0},
        CONF_SOIL_TYPE: "loam",
        CONF_GRASS_TYPE: "tall_fescue",
        CONF_ESTABLISHMENT_METHOD: "sod",
        CONF_ESTABLISHMENT_DATE: "2025-04-12",
        CONF_IRRIGATION_TYPE: "pop_up_spray",
        CONF_FLOW_L_MIN: 30.0,
        CONF_WEATHER_ENTITY: "weather.forecast_home",
        CONF_RAIN_SENSOR: "sensor.weather_station_rain",
    }


@pytest.fixture
def zone_data() -> dict[str, Any]:
    """Return one zone of that lawn."""
    return {
        CONF_NAME: "South lawn",
        CONF_AREA: 120.0,
        CONF_EXPOSURE: "full_sun",
    }


@pytest.fixture
def field_data(lawn_data: dict[str, Any], zone_data: dict[str, Any]) -> dict[str, Any]:
    """Return the two as one mapping, for the engine, which wants a zone flat."""
    return {**lawn_data, **zone_data}


# What the lawn answers once. Everything else belongs to the zone.
LAWN_KEYS = (
    CONF_LOCATION,
    CONF_SOIL_TYPE,
    CONF_GRASS_TYPE,
    CONF_ESTABLISHMENT_METHOD,
    CONF_ESTABLISHMENT_DATE,
    CONF_IRRIGATION_TYPE,
    CONF_FLOW_L_MIN,
    CONF_PRECIPITATION_RATE,
    CONF_WEATHER_ENTITY,
    CONF_RAIN_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_HUMIDITY_SENSOR,
    CONF_WIND_SENSOR,
    CONF_SOLAR_SENSOR,
    CONF_SOIL_MOISTURE_SENSOR,
    CONF_MOWER_ENTITY,
)


def split(flat: dict[str, Any], lawn_name: str = "The lawn") -> tuple[dict, dict]:
    """Split one flat mapping into the lawn's answers and the zone's own."""
    lawn = {k: v for k, v in flat.items() if k in LAWN_KEYS} | {CONF_NAME: lawn_name}
    zone = {k: v for k, v in flat.items() if k not in LAWN_KEYS}
    return lawn, zone


@pytest.fixture(autouse=True)
async def _unload_everything(hass):
    """Unload every lawn when a test ends.

    A loaded coordinator holds clock listeners: one for midnight, one for each edge of the
    mowing window. A test that leaves an entry loaded leaves those behind, and Home
    Assistant's own check then fails whichever test happens to run last.
    """
    yield
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()


def only_zone(entry):
    """Return the single zone of a lawn, for the many tests that set up exactly one."""
    return next(iter(entry.runtime_data.zones.values()))


def make_entry(
    hass, lawn: dict[str, Any], zones: list[dict[str, Any]], *, title: str | None = None
) -> MockConfigEntry:
    """Return a lawn entry with a subentry per zone, added to Home Assistant.

    The shape the integration actually runs on: one entry for the lawn, one subentry for each
    zone of it, so a test exercises the same wiring a real setup does.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=lawn,
        unique_id=slugify(title or lawn[CONF_NAME]),
        title=title or lawn[CONF_NAME],
        subentries_data=[
            ConfigSubentryData(
                data=zone,
                subentry_type=ZONE_SUBENTRY,
                title=zone[CONF_NAME],
                unique_id=None,
            )
            for zone in zones
        ],
    )
    entry.add_to_hass(hass)
    return entry
