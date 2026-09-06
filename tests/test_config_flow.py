"""The config flow: a lawn in three steps, then a zone at a time on top of it.

The split is the point of the shape. Where the lawn is, what soil it sits on, what grows on
it and what waters it are asked once; how big a zone is, how much sun it gets and which valve
opens it are asked of each zone. A test that could not tell the two apart would let them
drift back together.
"""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

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
    CONF_VALVE_ENTITY,
    CONF_WEATHER_ENTITY,
    DOMAIN,
    ZONE_SUBENTRY,
)
from tests.conftest import make_entry

LAWN_STEP = (
    CONF_NAME,
    CONF_LOCATION,
    CONF_SOIL_TYPE,
    CONF_GRASS_TYPE,
    CONF_ESTABLISHMENT_METHOD,
    CONF_ESTABLISHMENT_DATE,
)
IRRIGATION_STEP = (CONF_IRRIGATION_TYPE, CONF_FLOW_L_MIN)
SOURCES_STEP = (CONF_WEATHER_ENTITY, CONF_RAIN_SENSOR)
ZONE_STEP = (CONF_NAME, CONF_AREA, CONF_EXPOSURE)


def _pick(data: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: data[key] for key in keys if key in data}


async def _garden(hass: HomeAssistant, lawn_data: dict[str, Any]) -> dict[str, Any]:
    """Walk the three steps that describe a property, and return the result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _pick(lawn_data, LAWN_STEP)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _pick(lawn_data, IRRIGATION_STEP)
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], _pick(lawn_data, SOURCES_STEP)
    )


async def test_the_lawn_is_created_from_three_steps(
    hass: HomeAssistant, lawn_data: dict[str, Any]
) -> None:
    """Where it is, what it is made of, what waters it. Nothing about any one zone."""
    result = await _garden(hass, lawn_data)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == lawn_data[CONF_NAME]

    data = result["data"]
    assert data[CONF_LOCATION] == lawn_data[CONF_LOCATION]
    assert data[CONF_WEATHER_ENTITY] == lawn_data[CONF_WEATHER_ENTITY]
    assert data[CONF_FLOW_L_MIN] == lawn_data[CONF_FLOW_L_MIN]
    assert data[CONF_GRASS_TYPE] == lawn_data[CONF_GRASS_TYPE]
    assert data[CONF_SOIL_TYPE] == lawn_data[CONF_SOIL_TYPE]
    # And nothing about any one zone: those answers live on the subentries.
    for key in (CONF_AREA, CONF_EXPOSURE, CONF_VALVE_ENTITY):
        assert key not in data


async def test_a_zone_is_added_to_the_lawn_as_a_subentry(
    hass: HomeAssistant, lawn_data: dict[str, Any], zone_data: dict[str, Any]
) -> None:
    """And it carries only its own answers: its size, its aspect, its valve."""
    entry = make_entry(hass, lawn_data, [])
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, ZONE_SUBENTRY), context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _pick(zone_data, ZONE_STEP) | {CONF_VALVE_ENTITY: "switch.south"}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"feature_0_kind": "none"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == zone_data[CONF_NAME]

    data = result["data"]
    assert data[CONF_AREA] == zone_data[CONF_AREA]
    assert data[CONF_EXPOSURE] == zone_data[CONF_EXPOSURE]
    assert data[CONF_VALVE_ENTITY] == "switch.south"
    assert data[CONF_FEATURES] == []
    # And nothing the lawn already answered: one soil, one seed mix, laid once.
    for key in (
        CONF_LOCATION,
        CONF_WEATHER_ENTITY,
        CONF_FLOW_L_MIN,
        CONF_SOIL_TYPE,
        CONF_GRASS_TYPE,
        CONF_ESTABLISHMENT_METHOD,
    ):
        assert key not in data


async def test_the_irrigation_step_needs_a_rate(
    hass: HomeAssistant, lawn_data: dict[str, Any]
) -> None:
    """A system that waters must say how fast, or nothing can be turned into minutes."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _pick(lawn_data, LAWN_STEP)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IRRIGATION_TYPE: "pop_up_spray"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "flow_required"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IRRIGATION_TYPE: "pop_up_spray", CONF_PRECIPITATION_RATE: 12.0}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "sources"


async def test_shade_cannot_exceed_the_lawn(
    hass: HomeAssistant, lawn_data: dict[str, Any], zone_data: dict[str, Any]
) -> None:
    """Three features adding to more than nine tenths of a lawn is not a lawn."""
    entry = make_entry(hass, lawn_data, [])
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, ZONE_SUBENTRY), context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _pick(zone_data, ZONE_STEP)
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "feature_0_kind": "deciduous_tree",
            "feature_0_shade": 60,
            "feature_1_kind": "structure",
            "feature_1_shade": 60,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "too_much_shade"}


async def test_the_same_lawn_twice_is_refused(
    hass: HomeAssistant, lawn_data: dict[str, Any]
) -> None:
    """The name is the lawn's identity, and a lawn is set up once."""
    make_entry(hass, lawn_data, [])
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _pick(lawn_data, LAWN_STEP)
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_one_entity_cannot_feed_two_sources(
    hass: HomeAssistant, lawn_data: dict[str, Any]
) -> None:
    """One sensor answering two questions is a mistake, not a shortcut."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _pick(lawn_data, LAWN_STEP)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _pick(lawn_data, IRRIGATION_STEP)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_WEATHER_ENTITY: "weather.forecast_home",
            CONF_RAIN_SENSOR: "sensor.one",
            CONF_SOIL_MOISTURE_SENSOR: "sensor.one",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "duplicate_source"}


async def test_the_lawn_is_reconfigured_in_place(
    hass: HomeAssistant, lawn_data: dict[str, Any], zone_data: dict[str, Any]
) -> None:
    """Editing the lawn leaves its zones alone."""
    entry = make_entry(hass, lawn_data, [zone_data])
    result = await entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], _pick(lawn_data, LAWN_STEP) | {CONF_NAME: "The other lawn"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_IRRIGATION_TYPE: "rotor", CONF_PRECIPITATION_RATE: 9.0}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_WEATHER_ENTITY: "weather.forecast_home", CONF_MOWER_ENTITY: "lawn_mower.robot"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    assert entry.data[CONF_NAME] == "The other lawn"
    assert entry.data[CONF_IRRIGATION_TYPE] == "rotor"
    assert entry.data[CONF_PRECIPITATION_RATE] == 9.0
    assert entry.data[CONF_MOWER_ENTITY] == "lawn_mower.robot"
    # The rain sensor was left empty this time, so it is cleared rather than remembered.
    assert CONF_RAIN_SENSOR not in entry.data
    # And the zone of it is untouched.
    assert [s.title for s in entry.subentries.values()] == [zone_data[CONF_NAME]]


async def test_a_zone_is_reconfigured_on_itself(
    hass: HomeAssistant, lawn_data: dict[str, Any], zone_data: dict[str, Any]
) -> None:
    """A zone's own answers are edited where the zone is, not on the lawn."""
    entry = make_entry(hass, lawn_data, [zone_data])
    subentry_id = next(iter(entry.subentries))
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, ZONE_SUBENTRY),
        context={"source": config_entries.SOURCE_RECONFIGURE, "subentry_id": subentry_id},
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], _pick(zone_data, ZONE_STEP) | {CONF_AREA: 75.0}
    )
    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"], {"feature_0_kind": "none"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert entry.subentries[subentry_id].data[CONF_AREA] == 75.0


async def test_a_lawn_can_hold_several_zones(
    hass: HomeAssistant, lawn_data: dict[str, Any], zone_data: dict[str, Any]
) -> None:
    """Which is the whole reason for the shape."""
    entry = make_entry(
        hass,
        lawn_data,
        [zone_data, zone_data | {CONF_NAME: "North lawn", CONF_AREA: 30.0}],
    )
    assert len(entry.subentries) == 2
    assert {s.data[CONF_NAME] for s in entry.subentries.values()} == {"South lawn", "North lawn"}
    assert all(s.subentry_type == ZONE_SUBENTRY for s in entry.subentries.values())


async def test_a_subentry_that_is_not_a_lawn_is_ignored(
    hass: HomeAssistant, lawn_data: dict[str, Any]
) -> None:
    """Setup walks the subentries, so anything else must not be mistaken for a zone."""
    entry = make_entry(hass, lawn_data, [])
    entry.runtime_data = None
    hass.config_entries.async_add_subentry(
        entry,
        config_entries.ConfigSubentry(
            data=ConfigSubentryData(data={}, subentry_type="other", title="x", unique_id=None)[
                "data"
            ],
            subentry_type="other",
            title="x",
            unique_id=None,
        ),
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.zones == {}
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
