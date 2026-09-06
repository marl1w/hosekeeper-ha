"""The diary: what is written today is what is read back after a restart."""

from __future__ import annotations

import datetime as dt

from freezegun import freeze_time
from homeassistant.core import HomeAssistant

from custom_components.hosekeeper.diary import Diary


async def test_round_trip_through_storage(hass: HomeAssistant) -> None:
    with freeze_time("2026-09-06 18:00:00+02:00"):
        diary = Diary(hass, "entry1")
        await diary.async_load()
        diary.add_irrigation(20, 5.0, "manual")
        diary.add_irrigation(10, 2.5, "valve")
        diary.set_status("good")
        diary.add_issue("weeds")
        diary.add_issue("weeds")
        diary.add_maintenance("mowing", details={"height_mm": 45})
        await diary.async_save()

        again = Diary(hass, "entry1")
        await again.async_load()
        today = again.today()
        assert today["irrigation_min"] == 30
        assert today["irrigation_mm"] == 7.5
        assert today["status"] == "good"
        assert today["issues"] == ["weeds"]
        assert today["maintenance"][0]["type"] == "mowing"
        assert today["maintenance"][0]["details"] == {"height_mm": 45}


async def test_recent_fills_missing_days(hass: HomeAssistant) -> None:
    diary = Diary(hass, "entry2")
    await diary.async_load()
    diary.day("2026-09-04")["rain_mm"] = 3.0
    window = diary.recent(3, until=dt.date(2026, 9, 6))
    assert [date.isoformat() for date, _ in window] == ["2026-09-04", "2026-09-05", "2026-09-06"]
    assert window[0][1]["rain_mm"] == 3.0
    assert window[1][1] == {}


async def test_last_maintenance_picks_the_latest(hass: HomeAssistant) -> None:
    diary = Diary(hass, "entry3")
    await diary.async_load()
    early = dt.datetime(2026, 8, 30, 9, 0, tzinfo=dt.UTC)
    late = dt.datetime(2026, 9, 4, 9, 0, tzinfo=dt.UTC)
    diary.add_maintenance("mowing", at=late)
    diary.add_maintenance("mowing", at=early)
    diary.add_maintenance("fertilizing", at=early)
    assert diary.last_maintenance("mowing") == late
    assert diary.last_maintenance("fertilizing") == early
    assert diary.last_maintenance("aeration") is None


async def test_remove_deletes_the_file(hass: HomeAssistant) -> None:
    diary = Diary(hass, "entry4")
    await diary.async_load()
    diary.set_status("poor")
    await diary.async_save()
    await diary.async_remove()

    again = Diary(hass, "entry4")
    await again.async_load()
    assert again.days == {}
