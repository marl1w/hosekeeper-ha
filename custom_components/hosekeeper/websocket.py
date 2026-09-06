"""What the panel asks for: one snapshot per field, the list of fields, and confirmations.

Everything the panel shows comes through here in one shape, so a test can assert on it and
the preview script can fabricate it.

There is one write, and it is deliberately narrow: confirming that a job on the screen was
done. It is here rather than left to the services because the panel is where the job is
named — the button sits on the line that says the lawn wants mowing — and because a
confirmation that had to be composed as a service call is a confirmation nobody makes. The
services stay for automations, which have the reverse need.
"""

from __future__ import annotations

from dataclasses import asdict
import datetime as dt
from typing import Any

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.sun import get_astral_event_next
from homeassistant.util import dt as dt_util
import voluptuous as vol

from .const import DOMAIN, ISSUES, LAWN_STATUSES, MAINTENANCE_KINDS
from .engine.knowledge import fertilizers
from .events import PAST_DAYS, build as build_events
from .services import fertilizing_details

HISTORY_DAYS = PAST_DAYS


def sunrise_hint(hass: HomeAssistant) -> dt.time:
    """Return the next sunrise as a local time, for placing projected dawn cycles."""
    event = get_astral_event_next(hass, "sunrise")
    return dt_util.as_local(event).time().replace(second=0, microsecond=0)


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register the websocket commands once."""
    websocket_api.async_register_command(hass, ws_fields)
    websocket_api.async_register_command(hass, ws_field)
    websocket_api.async_register_command(hass, ws_log)


def _entries(hass: HomeAssistant):
    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if hasattr(entry, "runtime_data") and entry.runtime_data is not None
    ]


def field_summary(entry) -> dict[str, Any]:
    """Return what the field switcher needs."""
    runtime = entry.runtime_data
    state = runtime.coordinator.data
    return {
        "entry_id": entry.entry_id,
        "name": runtime.field.name,
        "grass_type": runtime.field.grass_type,
        "area_m2": runtime.field.area_m2,
        "next_action": state.next_action if state else None,
        "status": state.status if state else None,
    }


def field_snapshot(hass: HomeAssistant, entry) -> dict[str, Any]:
    """Return everything the panel shows for one field."""
    runtime = entry.runtime_data
    field = runtime.field
    state = runtime.coordinator.data
    today = dt_util.now().date()
    days = []
    for date, record in runtime.diary.recent(HISTORY_DAYS, until=today):
        item = {k: v for k, v in record.items() if k not in ("obs", "fc")}
        item["date"] = date.isoformat()
        if record.get("fc"):
            item["forecast"] = record["fc"]
        days.append(item)
    config = asdict(field)
    config["features"] = [asdict(f) for f in field.features]
    config["establishment_date"] = (
        field.establishment_date.isoformat() if field.establishment_date else None
    )
    config["shaded_fraction"] = field.shaded_fraction
    config["application_rate_mm_h"] = field.application_rate_mm_h
    return {
        "entry_id": entry.entry_id,
        "field": config,
        "state": asdict(state) if state else None,
        "days": days,
        "adaptation": runtime.diary.adaptation,
        "plan": runtime.diary.plan.get("operations", []),
        "events": build_events(
            field, entry.entry_id, runtime.diary, state, today, sunrise_hint(hass)
        ),
        # What a person may report. The panel offers these and nothing else, so the two
        # never drift apart.
        "issues": list(ISSUES),
        "maintenance_kinds": list(MAINTENANCE_KINDS),
        "fertilizers": {
            key: {
                "name": f.name,
                "n": f.n,
                "p": f.p,
                "k": f.k,
                "role": f.role,
                "dose_g_m2": f.default_dose_g_m2,
            }
            for key, f in fertilizers.PRESETS.items()
        },
    }


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/fields"})
@callback
def ws_fields(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """List the fields."""
    connection.send_result(msg["id"], [field_summary(entry) for entry in _entries(hass)])


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/field", vol.Required("entry_id"): str}
)
@callback
def ws_field(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict) -> None:
    """Return one field's snapshot."""
    for entry in _entries(hass):
        if entry.entry_id == msg["entry_id"]:
            connection.send_result(msg["id"], field_snapshot(hass, entry))
            return
    connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "No such field")


def _when(msg: dict[str, Any]) -> dt.datetime | None:
    """Return the moment a job happened, as the local clock has it."""
    at = msg.get("at")
    if at is None:
        return None
    return dt_util.as_local(at) if at.tzinfo else at.replace(tzinfo=dt_util.get_default_time_zone())


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/log",
        vol.Required("entry_id"): str,
        vol.Required("what"): vol.In(
            ("maintenance", "fertilizing", "irrigation", "status", "issue")
        ),
        vol.Optional("kind"): vol.In(MAINTENANCE_KINDS),
        vol.Optional("product"): cv.string,
        vol.Optional("dose_g_m2"): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=500)),
        vol.Optional("at"): cv.datetime,
        vol.Optional("minutes"): vol.All(vol.Coerce(float), vol.Range(min=0, max=1440)),
        vol.Optional("status"): vol.In(LAWN_STATUSES),
        vol.Optional("issue"): vol.In(ISSUES),
        vol.Optional("details"): dict,
    }
)
@websocket_api.async_response
async def ws_log(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict
) -> None:
    """Write one confirmation to a lawn's diary and send the fresh snapshot back.

    The snapshot goes back with the result so the panel never has to guess what the entry
    changed: it redraws from the same shape it drew from before, with the day's page as the
    coordinator now sees it.
    """
    entry = next((e for e in _entries(hass) if e.entry_id == msg["entry_id"]), None)
    if entry is None:
        connection.send_error(msg["id"], websocket_api.ERR_NOT_FOUND, "No such field")
        return
    coordinator = entry.runtime_data.coordinator
    what = msg["what"]
    try:
        if what == "maintenance":
            if "kind" not in msg:
                raise vol.Invalid("kind is required to log maintenance")
            await coordinator.async_log_maintenance(
                msg["kind"], msg.get("details") or {}, at=_when(msg)
            )
        elif what == "fertilizing":
            # Through the same builder as the service: the yearly nitrogen budget is summed
            # from the grams it works out, and a feed recorded from the panel has to count
            # exactly as much as the same feed recorded from an automation.
            await coordinator.async_log_maintenance(
                "fertilizing",
                fertilizing_details(msg.get("product"), dose_g_m2=msg.get("dose_g_m2")),
                at=_when(msg),
            )
        elif what == "irrigation":
            if "minutes" not in msg:
                raise vol.Invalid("minutes is required to log irrigation")
            await coordinator.async_log_irrigation(float(msg["minutes"]), replace_today=True)
        elif what == "status":
            if "status" not in msg:
                raise vol.Invalid("status is required")
            await coordinator.async_set_status(msg["status"])
        else:
            if "issue" not in msg:
                raise vol.Invalid("issue is required")
            await coordinator.async_log_issue(msg["issue"])
    except vol.Invalid as err:
        connection.send_error(msg["id"], websocket_api.ERR_INVALID_FORMAT, str(err))
        return
    connection.send_result(msg["id"], field_snapshot(hass, entry))
