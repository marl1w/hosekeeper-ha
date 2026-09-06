"""Hosekeeper — a lawn diary that knows what the grass needs.

One config entry per field. The entry's data describes the lawn and which entities feed it;
a diary in storage keeps what happened each day; the engine turns both into advice.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import logging
from pathlib import Path

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import services, websocket
from .const import (
    DOMAIN,
    PANEL_COMPONENT,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
    STATIC_URL,
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
class HosekeeperRuntime:
    """What a loaded field carries around."""

    field: FieldConfig
    diary: Diary
    coordinator: HosekeeperCoordinator


type HosekeeperConfigEntry = ConfigEntry[HosekeeperRuntime]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


_PANEL_REGISTERED = f"{DOMAIN}_panel_registered"


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
    """Serve the frontend and add the sidebar panel, once per Home Assistant run."""
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
    """Set up one field."""
    field = FieldConfig.from_data(entry.data)
    diary = Diary(hass, entry.entry_id)
    await diary.async_load()
    coordinator = HosekeeperCoordinator(hass, entry, field, diary)
    await coordinator.async_setup()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = HosekeeperRuntime(field=field, diary=diary, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_register_panel(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: HosekeeperConfigEntry) -> bool:
    """Unload one field, keeping its diary on disk."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.coordinator.async_shutdown()
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
    """Delete the diary with the field: removing the integration removes its data."""
    await Diary(hass, entry.entry_id).async_remove()
