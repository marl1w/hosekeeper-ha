"""The services write the diary with the details the buttons cannot carry."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hosekeeper.const import DOMAIN


async def _setup(hass: HomeAssistant, field_data: dict[str, Any]) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, data=field_data, unique_id="south_lawn", title="South lawn"
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_fertilizing_by_preset_counts_nitrogen(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    entry = await _setup(hass, field_data)
    await hass.services.async_call(
        DOMAIN,
        "log_fertilizing",
        {"config_entry_id": entry.entry_id, "product": "bottos_slow_green", "dose_g_m2": 30},
        blocking=True,
    )
    record = entry.runtime_data.diary.today()["maintenance"][0]
    assert record["type"] == "fertilizing"
    assert record["details"]["n"] == 22
    assert record["details"]["n_g_m2"] == pytest.approx(6.6)
    assert record["details"]["role"] == "growth"
    state = hass.states.get("sensor.south_lawn_nitrogen_applied_this_year")
    assert state is not None and float(state.state) == pytest.approx(6.6)
    assert state.attributes["days_since_fertilizing"] == 0


async def test_fertilizing_by_composition(hass: HomeAssistant, field_data: dict[str, Any]) -> None:
    entry = await _setup(hass, field_data)
    await hass.services.async_call(
        DOMAIN,
        "log_fertilizing",
        {
            "config_entry_id": entry.entry_id,
            "product": "custom",
            "n": 15,
            "p": 5,
            "k": 5,
            "dose_g_m2": 20,
        },
        blocking=True,
    )
    details = entry.runtime_data.diary.today()["maintenance"][0]["details"]
    assert details["product"] == "custom"
    assert details["n_g_m2"] == pytest.approx(3.0)


async def test_sowing_issue_and_irrigation(hass: HomeAssistant, field_data: dict[str, Any]) -> None:
    entry = await _setup(hass, field_data)
    await hass.services.async_call(
        DOMAIN,
        "log_sowing",
        {
            "config_entry_id": entry.entry_id,
            "kind": "overseed",
            "seed_mix": "Festuca 80 / Loietto 20",
            "rate_g_m2": 35,
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, "log_issue", {"config_entry_id": entry.entry_id, "issue": "weeds"}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, "log_irrigation", {"config_entry_id": entry.entry_id, "minutes": 12}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN,
        "log_maintenance",
        {"config_entry_id": entry.entry_id, "kind": "mowing", "height_mm": 55},
        blocking=True,
    )
    today = entry.runtime_data.diary.today()
    kinds = [m["type"] for m in today["maintenance"]]
    assert kinds == ["sowing", "mowing"]
    assert today["maintenance"][0]["details"]["rate_g_m2"] == 35
    assert today["maintenance"][1]["details"]["height_mm"] == 55
    assert today["issues"] == ["weeds"]
    assert today["irrigation_min"] == 12


async def test_unknown_entry_is_refused(hass: HomeAssistant, field_data: dict[str, Any]) -> None:
    await _setup(hass, field_data)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN, "log_issue", {"config_entry_id": "nope", "issue": "moss"}, blocking=True
        )
