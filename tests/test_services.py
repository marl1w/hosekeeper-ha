"""The services write the diary with the details the buttons cannot carry."""

from __future__ import annotations

import datetime as dt
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hosekeeper.const import DOMAIN
from tests.conftest import make_entry, only_zone, split


async def _setup(hass: HomeAssistant, field_data: dict[str, Any]) -> MockConfigEntry:
    lawn, zone = split(field_data)
    entry = make_entry(hass, lawn, [zone])
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
        {"zone_id": only_zone(entry).zone_id, "product": "bottos_slow_green", "dose_g_m2": 30},
        blocking=True,
    )
    record = only_zone(entry).diary.today()["maintenance"][0]
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
            "zone_id": only_zone(entry).zone_id,
            "product": "custom",
            "n": 15,
            "p": 5,
            "k": 5,
            "dose_g_m2": 20,
        },
        blocking=True,
    )
    details = only_zone(entry).diary.today()["maintenance"][0]["details"]
    assert details["product"] == "custom"
    assert details["n_g_m2"] == pytest.approx(3.0)


async def test_sowing_issue_and_irrigation(hass: HomeAssistant, field_data: dict[str, Any]) -> None:
    entry = await _setup(hass, field_data)
    await hass.services.async_call(
        DOMAIN,
        "log_sowing",
        {
            "zone_id": only_zone(entry).zone_id,
            "kind": "overseed",
            "seed_mix": "Festuca 80 / Loietto 20",
            "rate_g_m2": 35,
        },
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, "log_issue", {"zone_id": only_zone(entry).zone_id, "issue": "weeds"}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN,
        "log_irrigation",
        {"zone_id": only_zone(entry).zone_id, "minutes": 12},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "log_maintenance",
        {"zone_id": only_zone(entry).zone_id, "kind": "mowing", "height_mm": 55},
        blocking=True,
    )
    today = only_zone(entry).diary.today()
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
            DOMAIN, "log_issue", {"zone_id": "nope", "issue": "moss"}, blocking=True
        )


async def test_a_past_day_can_be_entered_from_an_archive(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    """A lawn set up today can be given the season it lived through.

    Applied oldest first, the days rebuild the balance between them: each carries in the
    deficit the one before it left behind, which is what makes an imported summer worth
    having rather than a row of disconnected numbers.
    """
    lawn, zone = split(field_data)
    entry = make_entry(hass, lawn, [zone])
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    diary = only_zone(entry).diary
    zone_id = only_zone(entry).zone_id

    hot = [dt.date(2026, 7, 1) + dt.timedelta(days=i) for i in range(5)]
    for day in hot:
        await hass.services.async_call(
            DOMAIN,
            "import_weather",
            {
                "zone_id": zone_id,
                "date": day.isoformat(),
                "tmax": 34.0,
                "tmin": 21.0,
                "rain_mm": 0.0,
                "humidity_pct": 45.0,
                "wind_ms": 2.0,
                "solar_mj": 27.0,
            },
            blocking=True,
        )

    written = [diary.day(day.isoformat()) for day in hot]
    assert all(page["tmax"] == 34.0 for page in written)
    assert all(page["et_method"] == "penman_monteith" for page in written)
    assert all(page["etc_mm"] > 3 for page in written), "a hot dry July day uses water"
    # Five rainless days in a row: the deficit grows through them rather than starting over.
    deficits = [page["deficit_mm"] for page in written]
    assert deficits == sorted(deficits) and deficits[-1] > deficits[0]


async def test_an_imported_day_keeps_the_watering_already_recorded_on_it(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    """The two halves of a past day are entered separately and must not overwrite each other."""
    lawn, zone = split(field_data)
    entry = make_entry(hass, lawn, [zone])
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    zone_id = only_zone(entry).zone_id
    day = dt.date(2026, 7, 1)

    await hass.services.async_call(
        DOMAIN,
        "log_irrigation",
        {"zone_id": zone_id, "minutes": 25, "at": f"{day.isoformat()}T05:30:00"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN,
        "import_weather",
        {"zone_id": zone_id, "date": day.isoformat(), "tmax": 34.0, "tmin": 21.0},
        blocking=True,
    )

    page = only_zone(entry).diary.day(day.isoformat())
    assert page["irrigation_min"] == 25
    assert page["irrigation_mm"] > 0
    assert page["deficit_mm"] < page["etc_mm"], "the water put on that day counted against it"
