"""The websocket API and the sidebar panel."""

from __future__ import annotations

import datetime as dt
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.hosekeeper.const import DOMAIN, PANEL_URL_PATH


async def _setup(
    hass: HomeAssistant, field_data: dict[str, Any], name: str = "South lawn"
) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=field_data | {"name": name},
        unique_id=name.lower().replace(" ", "_"),
        title=name,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_fields_and_snapshot(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, field_data: dict[str, Any]
) -> None:
    entry = await _setup(hass, field_data)
    await _setup(hass, field_data, "Giardino nord")
    client = await hass_ws_client(hass)

    await client.send_json_auto_id({"type": "hosekeeper/fields"})
    result = await client.receive_json()
    assert result["success"]
    assert [f["name"] for f in result["result"]] == ["South lawn", "Giardino nord"]
    assert result["result"][0]["entry_id"] == entry.entry_id

    await client.send_json_auto_id({"type": "hosekeeper/field", "entry_id": entry.entry_id})
    result = await client.receive_json()
    assert result["success"]
    snapshot = result["result"]
    assert snapshot["field"]["name"] == "South lawn"
    assert snapshot["field"]["application_rate_mm_h"] == 15.0
    assert snapshot["state"]["advice"]
    assert "plan" in snapshot["state"]
    assert len(snapshot["days"]) == 62
    assert snapshot["days"][-1]["date"] == snapshot["state"]["day"]
    assert "bottos_slow_k" in snapshot["fertilizers"]

    await client.send_json_auto_id({"type": "hosekeeper/field", "entry_id": "nope"})
    result = await client.receive_json()
    assert not result["success"]
    assert result["error"]["code"] == "not_found"


async def test_panel_is_registered_once_and_removed_with_the_last_field(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    first = await _setup(hass, field_data)
    second = await _setup(hass, field_data, "Giardino nord")
    panels = hass.data["frontend_panels"]
    assert PANEL_URL_PATH in panels
    assert panels[PANEL_URL_PATH].config["_panel_custom"]["name"] == "hosekeeper-panel"

    assert await hass.config_entries.async_unload(first.entry_id)
    await hass.async_block_till_done()
    assert PANEL_URL_PATH in panels  # the other field still uses it

    assert await hass.config_entries.async_unload(second.entry_id)
    await hass.async_block_till_done()
    assert PANEL_URL_PATH not in panels


async def test_calendar_entity_lists_the_plan_and_the_log(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    from homeassistant.util import dt as dt_util

    entry = await _setup(hass, field_data)
    await hass.services.async_call(
        DOMAIN,
        "log_maintenance",
        {"config_entry_id": entry.entry_id, "kind": "mowing", "height_mm": 60},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("calendar.south_lawn_calendar")
    assert state is not None

    from homeassistant.components.calendar import CalendarEntity

    platform = hass.data["entity_components"]["calendar"]
    entity: CalendarEntity = platform.get_entity("calendar.south_lawn_calendar")
    now = dt_util.now()
    events = await entity.async_get_events(
        hass, now - dt.timedelta(days=1), now + dt.timedelta(days=120)
    )
    summaries = [e.summary for e in events]
    assert "Mowing" in summaries
    assert any(
        "potassium feed" in s or "Overseeding" in s or "Starter feed" in s for s in summaries
    )
    assert entity.event is not None


async def test_snapshot_carries_events_with_zones(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, field_data: dict[str, Any]
) -> None:
    entry = await _setup(hass, field_data)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id({"type": "hosekeeper/field", "entry_id": entry.entry_id})
    result = await client.receive_json()
    events = result["result"]["events"]
    assert events
    assert all(e["zone"] == "South lawn" for e in events)
    kinds = {e["kind"] for e in events}
    assert "planned" in kinds
    planned = [e for e in events if e["kind"] == "planned"]
    # Filed on the first of its month, except the month already under way, which is filed
    # today so that a routine running all month is still among what is coming.
    from homeassistant.util import dt as dt_util

    today = dt_util.now().date().isoformat()
    assert all(e["date"].endswith("-01") or e["date"] == today for e in planned)


async def test_the_panel_can_confirm_a_job_and_gets_the_fresh_snapshot_back(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, field_data: dict[str, Any]
) -> None:
    """Confirming is the panel's one write, and it answers with the day as it now stands.

    The panel redraws from the reply rather than guessing what changed, which is why the
    command returns a snapshot instead of an acknowledgement.
    """
    entry = await _setup(hass, field_data)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "hosekeeper/log",
            "entry_id": entry.entry_id,
            "what": "maintenance",
            "kind": "mowing",
        }
    )
    result = await client.receive_json()
    assert result["success"], result
    today = dt_util.now().date().isoformat()
    logged = [
        e
        for e in result["result"]["events"]
        if e["date"] == today and e["kind"] == "logged" and e["code"] == "mowing"
    ]
    assert logged, "the cut is not in the day it was confirmed on"
    assert entry.runtime_data.diary.today()["maintenance"][0]["type"] == "mowing"

    # Watering carries its minutes, and replaces the day's total so a figure can be fixed.
    await client.send_json_auto_id(
        {"type": "hosekeeper/log", "entry_id": entry.entry_id, "what": "irrigation", "minutes": 25}
    )
    result = await client.receive_json()
    assert result["success"], result
    assert entry.runtime_data.diary.today()["irrigation_min"] == 25

    # A condition is an observation, not a job, and it goes in the same way.
    await client.send_json_auto_id(
        {"type": "hosekeeper/log", "entry_id": entry.entry_id, "what": "status", "status": "good"}
    )
    result = await client.receive_json()
    assert result["success"], result
    assert entry.runtime_data.diary.today()["status"] == "good"


async def test_confirming_is_refused_for_a_lawn_that_is_not_there(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, field_data: dict[str, Any]
) -> None:
    await _setup(hass, field_data)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "hosekeeper/log", "entry_id": "nope", "what": "maintenance", "kind": "mowing"}
    )
    result = await client.receive_json()
    assert not result["success"]
    assert result["error"]["code"] == "not_found"


async def test_a_feed_recorded_from_the_panel_counts_toward_the_nitrogen_budget(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, field_data: dict[str, Any]
) -> None:
    """The yearly budget is summed from the grams on each feed and from nothing else.

    So the panel sends a product and a rate, and the integration turns them into grams
    through the same builder the service uses. A feed recorded one way has to count exactly
    as much as the same feed recorded the other.
    """
    entry = await _setup(hass, field_data)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "hosekeeper/log",
            "entry_id": entry.entry_id,
            "what": "fertilizing",
            "product": "bottos_autumn_k",
            "dose_g_m2": 25,
        }
    )
    result = await client.receive_json()
    assert result["success"], result

    logged = entry.runtime_data.diary.today()["maintenance"][0]
    assert logged["type"] == "fertilizing"
    assert logged["details"]["product"] == "bottos_autumn_k"
    assert logged["details"]["dose_g_m2"] == 25
    # 21 % of 25 g/m² is 5.25 g of nitrogen, and that is the number the budget adds up.
    assert logged["details"]["n_g_m2"] == pytest.approx(5.25, abs=0.01)
    assert result["result"]["state"]["nitrogen_year_g_m2"] > 0


async def test_a_job_is_recorded_at_the_hour_it_happened(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, field_data: dict[str, Any]
) -> None:
    """Somebody opens the panel in the evening to record the cut they made at five."""
    entry = await _setup(hass, field_data)
    client = await hass_ws_client(hass)
    earlier = dt_util.now().replace(hour=17, minute=20, second=0, microsecond=0)
    await client.send_json_auto_id(
        {
            "type": "hosekeeper/log",
            "entry_id": entry.entry_id,
            "what": "maintenance",
            "kind": "mowing",
            "details": {"height_mm": 55},
            "at": earlier.isoformat(),
        }
    )
    result = await client.receive_json()
    assert result["success"], result

    logged = entry.runtime_data.diary.today()["maintenance"][0]
    assert logged["type"] == "mowing"
    assert logged["details"]["height_mm"] == 55
    assert dt_util.parse_datetime(logged["at"]).hour == 17
