"""Setting a lawn up, and keeping it in step with its zones."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import pytest

from custom_components.hosekeeper.const import ZONE_SUBENTRY
from tests.conftest import make_entry, split


@pytest.fixture(autouse=True)
def _mid_afternoon(freezer) -> None:
    """Run in the same afternoon the other suites do, so the plan is the same one."""
    freezer.move_to("2026-09-06T22:00:00+00:00")


async def test_a_zone_added_later_is_set_up_without_a_restart(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    """A zone added to a lawn that is already running gets its own coordinator.

    Home Assistant writes the subentry and fires the entry's update listeners; it does not
    reload the entry. Without a listener of our own the new zone had no diary, no coordinator
    and no entities until Home Assistant was restarted — and the panel, which is fed from the
    loaded zones, said there was no lawn at all.
    """
    lawn, zone = split(field_data)
    entry = make_entry(hass, lawn, [zone])
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(entry.runtime_data.zones) == 1

    hass.config_entries.async_add_subentry(
        entry,
        ConfigSubentry(
            data=zone | {CONF_NAME: "North lawn"},
            subentry_type=ZONE_SUBENTRY,
            title="North lawn",
            unique_id=None,
        ),
    )
    await hass.async_block_till_done()

    zones = entry.runtime_data.zones
    assert len(zones) == 2
    assert sorted(z.field.name for z in zones.values()) == ["North lawn", "South lawn"]
    assert hass.states.get("sensor.north_lawn_next_action") is not None


async def test_removing_a_zone_leaves_the_lawn_running(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    """Taking one zone away rebuilds the lawn around the zones that are left."""
    lawn, zone = split(field_data)
    entry = make_entry(hass, lawn, [zone, zone | {CONF_NAME: "North lawn"}])
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(entry.runtime_data.zones) == 2

    gone = next(
        subentry_id
        for subentry_id, subentry in entry.subentries.items()
        if subentry.title == "North lawn"
    )
    hass.config_entries.async_remove_subentry(entry, gone)
    await hass.async_block_till_done()

    assert [z.field.name for z in entry.runtime_data.zones.values()] == ["South lawn"]
