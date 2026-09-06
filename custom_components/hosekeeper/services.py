"""Services for the diary entries a button cannot carry: what product, how much, which seed."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
import voluptuous as vol

from .const import DOMAIN, ISSUES, LAWN_STATUSES, MAINTENANCE_KINDS
from .engine import et
from .engine.knowledge import fertilizers

ATTR_ZONE = "zone_id"

SERVICE_LOG_FERTILIZING = "log_fertilizing"
SERVICE_LOG_SOWING = "log_sowing"
SERVICE_LOG_MAINTENANCE = "log_maintenance"
SERVICE_LOG_ISSUE = "log_issue"
SERVICE_LOG_IRRIGATION = "log_irrigation"
SERVICE_SET_STATUS = "set_status"
SERVICE_IMPORT_WEATHER = "import_weather"

FERTILIZER_CHOICES = (*fertilizers.PRESETS.keys(), "custom")

_ENTRY = {vol.Required(ATTR_ZONE): cv.string}

FERTILIZING_SCHEMA = vol.Schema(
    {
        **_ENTRY,
        vol.Optional("product", default="slow_release"): vol.In(FERTILIZER_CHOICES),
        vol.Optional("n"): vol.Coerce(float),
        vol.Optional("p"): vol.Coerce(float),
        vol.Optional("k"): vol.Coerce(float),
        vol.Optional("dose_g_m2"): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=500)),
        vol.Optional("notes"): cv.string,
    }
)
SOWING_SCHEMA = vol.Schema(
    {
        **_ENTRY,
        vol.Optional("kind", default="overseed"): vol.In(("overseed", "new_lawn", "repair")),
        vol.Optional("seed_mix"): cv.string,
        vol.Optional("rate_g_m2"): vol.All(vol.Coerce(float), vol.Range(min=1, max=200)),
        vol.Optional("notes"): cv.string,
    }
)
MAINTENANCE_SCHEMA = vol.Schema(
    {
        **_ENTRY,
        vol.Required("kind"): vol.In(MAINTENANCE_KINDS),
        vol.Optional("at"): cv.datetime,
        vol.Optional("height_mm"): vol.All(vol.Coerce(int), vol.Range(min=5, max=150)),
        vol.Optional("product"): cv.string,
        vol.Optional("notes"): cv.string,
    }
)
ISSUE_SCHEMA = vol.Schema(
    {**_ENTRY, vol.Required("issue"): vol.In(ISSUES), vol.Optional("notes"): cv.string}
)
IRRIGATION_SCHEMA = vol.Schema(
    {
        **_ENTRY,
        vol.Required("minutes"): vol.All(vol.Coerce(float), vol.Range(min=0, max=1440)),
        vol.Optional("replace_today", default=False): cv.boolean,
        vol.Optional("at"): cv.datetime,
    }
)
STATUS_SCHEMA = vol.Schema({**_ENTRY, vol.Required("status"): vol.In(LAWN_STATUSES)})
# A day that has already happened, as it was measured. Everything but the two temperatures is
# optional: with humidity, wind and radiation the day is worked out by Penman-Monteith, and
# without them by Hargreaves, exactly as a live day is.
WEATHER_SCHEMA = vol.Schema(
    {
        **_ENTRY,
        vol.Required("date"): cv.date,
        vol.Required("tmax"): vol.All(vol.Coerce(float), vol.Range(min=-50, max=60)),
        vol.Required("tmin"): vol.All(vol.Coerce(float), vol.Range(min=-50, max=60)),
        vol.Optional("rain_mm"): vol.All(vol.Coerce(float), vol.Range(min=0, max=500)),
        vol.Optional("humidity_pct"): vol.All(vol.Coerce(float), vol.Range(min=0, max=100)),
        vol.Optional("wind_ms"): vol.All(vol.Coerce(float), vol.Range(min=0, max=60)),
        vol.Optional("solar_mj"): vol.All(vol.Coerce(float), vol.Range(min=0, max=50)),
    }
)


def _coordinator(hass: HomeAssistant, call: ServiceCall):
    """Return the coordinator for the lawn a call names.

    A zone is named by its own id, which the activity sensor publishes as `zone_id`. Naming
    the lawn instead is allowed when it has exactly one zone, because there the distinction
    is pedantry.
    """
    from .websocket import find_zone  # imported here: websocket imports this module

    wanted = call.data[ATTR_ZONE]
    found = find_zone(hass, wanted)
    if found is None:
        entry = hass.config_entries.async_get_entry(wanted)
        loaded = getattr(entry, "runtime_data", None) if entry else None
        if loaded and len(loaded.zones) == 1:
            found = (entry, next(iter(loaded.zones.values())))
    if found is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unknown_field",
            translation_placeholders={"entry": str(wanted)},
        )
    return found[1].coordinator


def _details(call: ServiceCall, *keys: str) -> dict[str, Any]:
    return {key: call.data[key] for key in keys if key in call.data}


def fertilizing_details(
    product: str | None,
    *,
    n: float | None = None,
    p: float | None = None,
    k: float | None = None,
    dose_g_m2: float | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Return what the diary keeps about one feed.

    The yearly nitrogen budget is summed from `n_g_m2` and from nothing else, so it is worked
    out here, once, from the composition and the rate. The panel and the service both come
    through this: a feed recorded one way must count exactly as much as the same feed
    recorded the other.
    """
    composition = fertilizers.resolve(None if product == "custom" else product, n, p, k)
    dose = float(dose_g_m2 or composition.default_dose_g_m2)
    details: dict[str, Any] = {
        "product": composition.id,
        "name": composition.name,
        "n": composition.n,
        "p": composition.p,
        "k": composition.k,
        "slow_fraction": composition.slow_fraction,
        "role": composition.role,
        "dose_g_m2": dose,
        "n_g_m2": round(composition.nitrogen_g_m2(dose), 2),
    }
    if notes:
        details["notes"] = notes
    return details


async def async_register(hass: HomeAssistant) -> None:
    """Register the services once for the whole integration."""
    if hass.services.has_service(DOMAIN, SERVICE_LOG_FERTILIZING):
        return

    async def log_fertilizing(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        await coordinator.async_log_maintenance(
            "fertilizing",
            fertilizing_details(
                call.data.get("product"),
                n=call.data.get("n"),
                p=call.data.get("p"),
                k=call.data.get("k"),
                dose_g_m2=call.data.get("dose_g_m2"),
                notes=call.data.get("notes"),
            ),
        )

    async def log_sowing(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        await coordinator.async_log_maintenance(
            "sowing", _details(call, "kind", "seed_mix", "rate_g_m2", "notes")
        )

    async def log_maintenance(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        await coordinator.async_log_maintenance(
            call.data["kind"],
            _details(call, "height_mm", "product", "notes"),
            at=call.data.get("at"),
        )

    async def log_issue(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        await coordinator.async_log_issue(call.data["issue"])

    async def log_irrigation(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        await coordinator.async_log_irrigation(
            float(call.data["minutes"]),
            replace_today=bool(call.data.get("replace_today")),
            at=call.data.get("at"),
        )

    async def set_status(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        await coordinator.async_set_status(call.data["status"])

    async def import_weather(call: ServiceCall) -> None:
        coordinator = _coordinator(hass, call)
        await coordinator.async_import_weather(
            call.data["date"],
            et.WeatherDay(
                tmax=float(call.data["tmax"]),
                tmin=float(call.data["tmin"]),
                rh_mean=call.data.get("humidity_pct"),
                wind_2m_ms=call.data.get("wind_ms"),
                rs_mj=call.data.get("solar_mj"),
            ),
            rain_mm=call.data.get("rain_mm"),
        )

    hass.services.async_register(
        DOMAIN, SERVICE_LOG_FERTILIZING, log_fertilizing, FERTILIZING_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_LOG_SOWING, log_sowing, SOWING_SCHEMA)
    hass.services.async_register(
        DOMAIN, SERVICE_LOG_MAINTENANCE, log_maintenance, MAINTENANCE_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_LOG_ISSUE, log_issue, ISSUE_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_LOG_IRRIGATION, log_irrigation, IRRIGATION_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_SET_STATUS, set_status, STATUS_SCHEMA)
    hass.services.async_register(DOMAIN, SERVICE_IMPORT_WEATHER, import_weather, WEATHER_SCHEMA)
