"""Hosekeeper — a lawn diary that knows what the grass needs.

One config entry per field. The entry's data describes the lawn and which entities feed it;
a diary in storage keeps what happened each day; the engine turns both into advice.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import hashlib
import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry
from homeassistant.helpers.typing import ConfigType

from . import services, websocket
from .const import (
    DOMAIN,
    PANEL_COMPONENT,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
    STATIC_URL,
    ZONE_SUBENTRY,
)
from .coordinator import HosekeeperCoordinator
from .diary import Diary
from .field import FieldConfig

_LOGGER = logging.getLogger(__name__)

# What a lawn is, as entities: what it needs, and what is due.
#
# There is no row of booleans. Seven of them once answered seven questions an automation does
# not ask; the one it does ask — what should be happening on this lawn at this moment, and is
# a machine doing it or am I — is `sensor.<lawn>_activity`, with the timing, the entity to act
# on and any standing alert in its attributes. Recording what was done is not an entity
# either: it happens in the panel, where the job is on the screen beside the button, and
# through the services, for automations.
PLATFORMS: list[Platform] = [
    Platform.CALENDAR,
    Platform.SENSOR,
]


@dataclass(slots=True)
class HosekeeperZone:
    """What one loaded zone carries around."""

    zone_id: str
    field: FieldConfig
    diary: Diary
    coordinator: HosekeeperCoordinator


@dataclass(slots=True)
class HosekeeperRuntime:
    """A loaded lawn: every zone of it, by subentry id."""

    zones: dict[str, HosekeeperZone]


type HosekeeperConfigEntry = ConfigEntry[HosekeeperRuntime]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


_PANEL_REGISTERED = f"{DOMAIN}_panel_registered"
_PANEL_LOCK = f"{DOMAIN}_panel_lock"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the services and the websocket API; they outlive any one field."""
    await services.async_register(hass)
    websocket.async_register(hass)
    return True


def _frontend_fingerprint(path: Path) -> str:
    """Return a short digest of the frontend directory's contents.

    Used as the static path segment, so that changing any module changes every module's
    URL and the browser cannot keep serving yesterday's panel from its cache.
    """
    digest = hashlib.sha256()
    for file in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(str(file.relative_to(path)).encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()[:12]


async def _async_register_panel(hass: HomeAssistant) -> None:
    """Serve the frontend and add the sidebar panel, once per Home Assistant run.

    Every lawn is its own config entry, and Home Assistant sets them up at the same time. The
    check and the registration are separated by an await, so on a property with three lawns
    all three got past the check before any of them had registered, and the second and third
    died on "Overwriting panel hosekeeper owned by custom" — taking their whole entry down
    with them. One lock around the whole thing, so the first arrival registers and the others
    find the work done.
    """
    lock = hass.data.setdefault(_PANEL_LOCK, asyncio.Lock())
    async with lock:
        frontend_path = Path(__file__).parent / "frontend"
        fingerprint = await hass.async_add_executor_job(_frontend_fingerprint, frontend_path)
        static_url = f"{STATIC_URL}/{fingerprint}"
        if hass.data.get(_PANEL_REGISTERED) == static_url:
            return
        if _PANEL_REGISTERED in hass.data:
            frontend.async_remove_panel(hass, PANEL_URL_PATH)
        await hass.http.async_register_static_paths(
            [StaticPathConfig(static_url, str(frontend_path), True)]
        )
        await panel_custom.async_register_panel(
            hass,
            frontend_url_path=PANEL_URL_PATH,
            webcomponent_name=PANEL_COMPONENT,
            module_url=f"{static_url}/hosekeeper-panel.js",
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            require_admin=False,
            embed_iframe=False,
        )
        hass.data[_PANEL_REGISTERED] = static_url


async def async_setup_entry(hass: HomeAssistant, entry: HosekeeperConfigEntry) -> bool:
    """Set up a lawn and every zone of it.

    The entry is the lawn; each zone is a subentry of it, with its own diary, its own
    coordinator and its own device. What the lawn answers once — where it is, what it is made
    of, what waters it, what the weather is read from — is merged into each zone's answers.
    """
    zones: dict[str, HosekeeperZone] = {}
    for zone_id, subentry in entry.subentries.items():
        if subentry.subentry_type != ZONE_SUBENTRY:
            continue
        field = FieldConfig.from_entry(entry.data, subentry.data)
        diary = Diary(hass, zone_id)
        await diary.async_load()
        coordinator = HosekeeperCoordinator(hass, entry, zone_id, field, diary)
        await coordinator.async_setup()
        await coordinator.async_config_entry_first_refresh()
        zones[zone_id] = HosekeeperZone(
            zone_id=zone_id, field=field, diary=diary, coordinator=coordinator
        )
    entry.runtime_data = HosekeeperRuntime(zones=zones)
    _async_register_lawn_device(hass, entry)
    # Adding a zone does not reload the lawn it belongs to. Home Assistant writes the
    # subentry, fires the entry's update listeners and stops there, so without this a zone
    # added from the lawn's card has no diary, no coordinator and no entities until Home
    # Assistant is restarted — and the panel, seeing no zones, says there is no lawn at all.
    entry.async_on_unload(entry.add_update_listener(_async_entry_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    # A lawn works without its sidebar entry. Losing the whole field because the panel could
    # not be put up is the wrong trade, so this is reported and not raised.
    try:
        await _async_register_panel(hass)
    except Exception:  # whatever the frontend raises, the field still stands
        _LOGGER.exception("Could not register the Hosekeeper panel; the lawn is set up anyway")
    return True


async def _async_entry_updated(hass: HomeAssistant, entry: HosekeeperConfigEntry) -> None:
    """Rebuild the lawn when its own answers change, or when a zone is added or edited."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HosekeeperConfigEntry) -> bool:
    """Unload a lawn, keeping every zone's diary on disk."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        for zone in entry.runtime_data.zones.values():
            await zone.coordinator.async_shutdown()
    others_loaded = any(
        e.entry_id != entry.entry_id and e.state is ConfigEntryState.LOADED
        for e in hass.config_entries.async_entries(DOMAIN)
    )
    if unloaded and not others_loaded and _PANEL_REGISTERED in hass.data:
        # The last field is gone: the sidebar entry goes with it.
        frontend.async_remove_panel(hass, PANEL_URL_PATH)
        hass.data.pop(_PANEL_REGISTERED, None)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Delete every zone's diary with the lawn: removing it removes its data."""
    for zone_id in entry.subentries:
        await Diary(hass, zone_id).async_remove()


async def async_remove_config_entry_subentry(
    hass: HomeAssistant, entry: ConfigEntry, subentry_id: str
) -> None:
    """Delete one zone's diary when the zone itself is removed."""
    await Diary(hass, subentry_id).async_remove()


def _async_register_lawn_device(hass: HomeAssistant, entry: HosekeeperConfigEntry) -> None:
    """Give the lawn a device of its own, so its zones hang beneath it."""
    device_registry.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer="Hosekeeper",
        model="Lawn",
    )
