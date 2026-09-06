"""The config flow: three steps in, one field out, and the same steps to edit it."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hosekeeper.const import (
    CONF_AREA,
    CONF_ESTABLISHMENT_DATE,
    CONF_ESTABLISHMENT_METHOD,
    CONF_EXPOSURE,
    CONF_FEATURES,
    CONF_FLOW_L_MIN,
    CONF_GRASS_TYPE,
    CONF_IRRIGATION_TYPE,
    CONF_LOCATION,
    CONF_MOWER_ENTITY,
    CONF_PRECIPITATION_RATE,
    CONF_RAIN_SENSOR,
    CONF_SOIL_MOISTURE_SENSOR,
    CONF_SOIL_TYPE,
    CONF_WEATHER_ENTITY,
    DOMAIN,
)

FIELD_KEYS = (
    CONF_NAME,
    CONF_AREA,
    CONF_LOCATION,
    CONF_EXPOSURE,
    CONF_SOIL_TYPE,
    CONF_GRASS_TYPE,
    CONF_ESTABLISHMENT_METHOD,
    CONF_ESTABLISHMENT_DATE,
)
IRRIGATION_KEYS = (CONF_IRRIGATION_TYPE, CONF_FLOW_L_MIN)
SOURCE_KEYS = (CONF_WEATHER_ENTITY, CONF_RAIN_SENSOR)


def _pick(data: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: data[key] for key in keys if key in data}


async def test_full_flow_creates_a_field(hass: HomeAssistant, field_data: dict[str, Any]) -> None:
    hass.states.async_set("weather.forecast_home", "sunny")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "field"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _pick(field_data, FIELD_KEYS)
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "irrigation"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _pick(field_data, IRRIGATION_KEYS)
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sources"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _pick(field_data, SOURCE_KEYS)
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "features"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"feature_0_kind": "deciduous_tree", "feature_0_shade": 30, "feature_1_kind": "none"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "South lawn"
    assert result["data"] == field_data | {
        CONF_FEATURES: [{"kind": "deciduous_tree", "shade_pct": 30.0}]
    }
    assert result["result"].unique_id == "south_lawn"


async def test_irrigation_needs_a_rate(hass: HomeAssistant, field_data: dict[str, Any]) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _pick(field_data, FIELD_KEYS)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IRRIGATION_TYPE: "rotor"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "irrigation"
    assert result["errors"] == {"base": "flow_required"}

    # No system at all is a valid answer that needs no rate.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IRRIGATION_TYPE: "none"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sources"


async def test_shade_cannot_exceed_the_lawn(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _pick(field_data, FIELD_KEYS)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _pick(field_data, IRRIGATION_KEYS)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _pick(field_data, SOURCE_KEYS)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "feature_0_kind": "structure",
            "feature_0_shade": 60,
            "feature_1_kind": "evergreen_tree",
            "feature_1_shade": 50,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "too_much_shade"}


async def test_same_name_twice_is_refused(hass: HomeAssistant, field_data: dict[str, Any]) -> None:
    MockConfigEntry(domain=DOMAIN, data=field_data, unique_id="south_lawn").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _pick(field_data, FIELD_KEYS)
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_edits_in_place(hass: HomeAssistant, field_data: dict[str, Any]) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, data=field_data, unique_id="south_lawn", title="South lawn"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "field"

    # The area grew, the lawn is no longer dated, a measured rate replaces the flow, the
    # rain gauge is gone and a mower arrived.
    field = _pick(field_data, FIELD_KEYS) | {CONF_AREA: 150.0}
    del field[CONF_ESTABLISHMENT_DATE]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], field)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IRRIGATION_TYPE: "rotor", CONF_PRECIPITATION_RATE: 12.0}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_WEATHER_ENTITY: "weather.forecast_home", CONF_MOWER_ENTITY: "lawn_mower.robot"},
    )
    assert result["step_id"] == "features"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    # The abort schedules a reload; let it finish, or the new coordinator's listeners
    # outlive the test.
    await hass.async_block_till_done()

    data = entry.data
    assert data[CONF_AREA] == 150.0
    assert CONF_ESTABLISHMENT_DATE not in data
    assert data[CONF_IRRIGATION_TYPE] == "rotor"
    assert data[CONF_PRECIPITATION_RATE] == 12.0
    assert CONF_FLOW_L_MIN not in data
    assert CONF_RAIN_SENSOR not in data
    assert data[CONF_MOWER_ENTITY] == "lawn_mower.robot"
    assert data[CONF_FEATURES] == []


async def test_one_entity_cannot_feed_two_sources(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _pick(field_data, FIELD_KEYS)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _pick(field_data, IRRIGATION_KEYS)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_WEATHER_ENTITY: "weather.forecast_home",
            CONF_RAIN_SENSOR: "sensor.station_rain",
            CONF_SOIL_MOISTURE_SENSOR: "sensor.station_rain",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sources"
    assert result["errors"] == {"base": "duplicate_source"}
