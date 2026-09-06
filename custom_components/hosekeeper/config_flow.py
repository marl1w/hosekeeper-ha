"""Config flow: a lawn in three steps, then the zones that water it.

A lawn is one piece of turf: one soil, one seed mix, laid or sown on one day, under one sky,
fed by one system. It is asked about once. A zone is a part of that lawn with its own valve
and its own aspect, and there may be several; each is added on top and answers only what is
true of itself.

The same steps serve first setup and later reconfiguration, so a lawn that gets a new
sprinkler or a new rain gauge is edited where it was created, not in a second place.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import (
    SOURCE_RECONFIGURE,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    SubentryFlowResult,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.util import slugify
import voluptuous as vol

from .const import (
    CONF_AREA,
    CONF_DECK_MAX_MM,
    CONF_DECK_MIN_MM,
    CONF_ESTABLISHMENT_DATE,
    CONF_ESTABLISHMENT_METHOD,
    CONF_EXPOSURE,
    CONF_FEATURES,
    CONF_FLOW_L_MIN,
    CONF_GRASS_TYPE,
    CONF_HUMIDITY_SENSOR,
    CONF_IRRIGATION_TYPE,
    CONF_LOCATION,
    CONF_MOWER_ENTITY,
    CONF_PRECIPITATION_RATE,
    CONF_RAIN_SENSOR,
    CONF_ROBOT_CADENCE,
    CONF_SOIL_MOISTURE_SENSOR,
    CONF_SOIL_TYPE,
    CONF_SOLAR_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_VALVE_ENTITY,
    CONF_WEATHER_ENTITY,
    CONF_WIND_SENSOR,
    DOMAIN,
    ESTABLISHMENT_METHODS,
    EXPOSURES,
    FEATURE_SLOTS,
    FEATURE_TYPES,
    GRASS_TYPES,
    IRRIGATION_TYPES,
    ROBOT_CADENCES,
    SOIL_TYPES,
    ZONE_SUBENTRY,
)

STEP_LAWN = "lawn"
STEP_ZONE = "zone"
STEP_IRRIGATION = "irrigation"
STEP_SOURCES = "sources"
STEP_FEATURES = "features"

# Sensors that are optional in the form arrive as a missing key when left empty; the
# reconfigure form needs them listed to clear a previously chosen entity.
OPTIONAL_ENTITY_KEYS = (
    CONF_RAIN_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_HUMIDITY_SENSOR,
    CONF_WIND_SENSOR,
    CONF_SOLAR_SENSOR,
    CONF_SOIL_MOISTURE_SENSOR,
    CONF_MOWER_ENTITY,
)
# The mower's own deck is asked for on the same step, but it is a pair of numbers, not an
# entity, so it is kept out of the check that no entity feeds two things at once.
OPTIONAL_SOURCE_KEYS = (*OPTIONAL_ENTITY_KEYS, CONF_DECK_MIN_MM, CONF_DECK_MAX_MM)
OPTIONAL_IRRIGATION_KEYS = (CONF_FLOW_L_MIN, CONF_PRECIPITATION_RATE)
OPTIONAL_LAWN_KEYS = (CONF_ESTABLISHMENT_DATE,)
OPTIONAL_ZONE_KEYS = (CONF_VALVE_ENTITY,)


def _select(options: tuple[str, ...], key: str) -> selector.SelectSelector:
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=list(options),
            translation_key=key,
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


def _sensor(device_class: SensorDeviceClass) -> selector.EntitySelector:
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain="sensor", device_class=device_class)
    )


def _lawn_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Return the lawn's own schema: what every zone of it shares.

    A lawn is one piece of turf however many zones water it. It is one soil, one seed mix,
    laid or sown on one day, so those are asked here rather than repeated for every zone and
    left free to disagree with each other.
    """
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME)): selector.TextSelector(),
            vol.Required(
                CONF_LOCATION, default=defaults.get(CONF_LOCATION)
            ): selector.LocationSelector(selector.LocationSelectorConfig(radius=False)),
            vol.Required(CONF_SOIL_TYPE, default=defaults.get(CONF_SOIL_TYPE)): _select(
                SOIL_TYPES, CONF_SOIL_TYPE
            ),
            vol.Required(CONF_GRASS_TYPE, default=defaults.get(CONF_GRASS_TYPE)): _select(
                GRASS_TYPES, CONF_GRASS_TYPE
            ),
            vol.Required(
                CONF_ESTABLISHMENT_METHOD, default=defaults.get(CONF_ESTABLISHMENT_METHOD)
            ): _select(ESTABLISHMENT_METHODS, CONF_ESTABLISHMENT_METHOD),
            vol.Optional(
                CONF_ESTABLISHMENT_DATE,
                description={"suggested_value": defaults.get(CONF_ESTABLISHMENT_DATE)},
            ): selector.DateSelector(),
        }
    )


def _zone_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Return one zone's schema: what is true of it and not of its neighbours."""
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME)): selector.TextSelector(),
            vol.Required(CONF_AREA, default=defaults.get(CONF_AREA)): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=100_000,
                    step=1,
                    unit_of_measurement="m²",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(CONF_EXPOSURE, default=defaults.get(CONF_EXPOSURE)): _select(
                EXPOSURES, CONF_EXPOSURE
            ),
            vol.Optional(
                CONF_VALVE_ENTITY,
                description={"suggested_value": defaults.get(CONF_VALVE_ENTITY)},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["valve", "switch", "input_boolean"])
            ),
        }
    )


def _irrigation_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_IRRIGATION_TYPE, default=defaults.get(CONF_IRRIGATION_TYPE)): _select(
                IRRIGATION_TYPES, CONF_IRRIGATION_TYPE
            ),
            vol.Optional(
                CONF_FLOW_L_MIN,
                description={"suggested_value": defaults.get(CONF_FLOW_L_MIN)},
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1,
                    max=10_000,
                    step=0.1,
                    unit_of_measurement="L/min",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Optional(
                CONF_PRECIPITATION_RATE,
                description={"suggested_value": defaults.get(CONF_PRECIPITATION_RATE)},
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0.1,
                    max=200,
                    step=0.1,
                    unit_of_measurement="mm/h",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _sources_schema(defaults: dict[str, Any]) -> vol.Schema:
    def optional(key: str, sel: selector.Selector) -> dict[vol.Marker, selector.Selector]:
        return {vol.Optional(key, description={"suggested_value": defaults.get(key)}): sel}

    schema: dict[vol.Marker, Any] = {
        vol.Required(
            CONF_WEATHER_ENTITY, default=defaults.get(CONF_WEATHER_ENTITY)
        ): selector.EntitySelector(selector.EntitySelectorConfig(domain="weather")),
    }
    schema |= optional(CONF_RAIN_SENSOR, _sensor(SensorDeviceClass.PRECIPITATION))
    schema |= optional(CONF_TEMPERATURE_SENSOR, _sensor(SensorDeviceClass.TEMPERATURE))
    schema |= optional(CONF_HUMIDITY_SENSOR, _sensor(SensorDeviceClass.HUMIDITY))
    schema |= optional(CONF_WIND_SENSOR, _sensor(SensorDeviceClass.WIND_SPEED))
    schema |= optional(CONF_SOLAR_SENSOR, _sensor(SensorDeviceClass.IRRADIANCE))
    schema |= optional(CONF_SOIL_MOISTURE_SENSOR, _sensor(SensorDeviceClass.MOISTURE))
    schema |= optional(
        CONF_MOWER_ENTITY,
        selector.EntitySelector(selector.EntitySelectorConfig(domain="lawn_mower")),
    )
    # How often that robot is wanted out. Every pass has the lawn occupied and goes over the
    # same ground, so daily is a choice rather than the only answer.
    schema[
        vol.Optional(
            CONF_ROBOT_CADENCE, default=defaults.get(CONF_ROBOT_CADENCE, ROBOT_CADENCES[1])
        )
    ] = _select(ROBOT_CADENCES, CONF_ROBOT_CADENCE)
    # What the mower can actually be set to. Without it the advice is the species' ideal,
    # which on a robot with a low deck is a height the machine has no setting for.
    for key in (CONF_DECK_MIN_MM, CONF_DECK_MAX_MM):
        schema |= optional(
            key,
            selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=5,
                    max=150,
                    step=1,
                    unit_of_measurement="mm",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        )
    return vol.Schema(schema)


def _features_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Return up to FEATURE_SLOTS pairs of (kind, shade percent)."""
    existing = defaults.get(CONF_FEATURES) or []
    schema: dict[vol.Marker, Any] = {}
    for slot in range(FEATURE_SLOTS):
        current = existing[slot] if slot < len(existing) else {}
        schema[vol.Optional(f"feature_{slot}_kind", default=current.get("kind", "none"))] = _select(
            FEATURE_TYPES, "feature_kind"
        )
        schema[
            vol.Optional(
                f"feature_{slot}_shade",
                description={"suggested_value": current.get("shade_pct")},
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=90,
                step=5,
                unit_of_measurement="%",
                mode=selector.NumberSelectorMode.SLIDER,
            )
        )
    return vol.Schema(schema)


def _features_from_input(user_input: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for slot in range(FEATURE_SLOTS):
        kind = user_input.get(f"feature_{slot}_kind", "none")
        shade = user_input.get(f"feature_{slot}_shade")
        if kind and kind != "none" and shade:
            out.append({"kind": kind, "shade_pct": float(shade)})
    return out


def _validate_features(features: list[dict[str, Any]]) -> dict[str, str]:
    if sum(f["shade_pct"] for f in features) > 90:
        return {"base": "too_much_shade"}
    return {}


def _validate_irrigation(data: dict[str, Any]) -> dict[str, str]:
    """Return form errors for the irrigation step."""
    if data[CONF_IRRIGATION_TYPE] == "none":
        return {}
    if not data.get(CONF_FLOW_L_MIN) and not data.get(CONF_PRECIPITATION_RATE):
        return {"base": "flow_required"}
    return {}


def _validate_sources(data: dict[str, Any]) -> dict[str, str]:
    """Return form errors for the sources step: one entity may feed one thing only."""
    chosen = [data[key] for key in (CONF_WEATHER_ENTITY, *OPTIONAL_ENTITY_KEYS) if data.get(key)]
    if len(chosen) != len(set(chosen)):
        return {"base": "duplicate_source"}
    low, high = data.get(CONF_DECK_MIN_MM), data.get(CONF_DECK_MAX_MM)
    if low is not None and high is not None and float(low) > float(high):
        return {"base": "deck_reversed"}
    return {}


def _merge(target: dict[str, Any], user_input: dict[str, Any], optional: tuple[str, ...]) -> None:
    """Apply a step's answers, treating an optional key left empty as cleared."""
    for key in optional:
        target.pop(key, None)
    target.update(user_input)


class HosekeeperConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create or reconfigure a lawn, and hand its zones to the subentry flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Start with nothing collected."""
        self._data: dict[str, Any] = {}
        self._reconfiguring = False

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        """Return the kinds of thing a lawn holds: zones, added and edited one by one."""
        return {ZONE_SUBENTRY: ZoneSubentryFlow}

    # ------------------------------------------------------------------ first setup

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Begin: the lawn itself."""
        return await self.async_step_lawn(user_input)

    async def async_step_lawn(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Name the lawn, place it on the map, and say what it is made of."""
        if user_input is not None:
            if not self._reconfiguring:
                await self.async_set_unique_id(slugify(user_input[CONF_NAME]))
                self._abort_if_unique_id_configured()
            _merge(self._data, user_input, OPTIONAL_LAWN_KEYS)
            return await self.async_step_irrigation()

        defaults = dict(self._data)
        defaults.setdefault(
            CONF_LOCATION,
            {
                CONF_LATITUDE: self.hass.config.latitude,
                CONF_LONGITUDE: self.hass.config.longitude,
            },
        )
        return self.async_show_form(step_id=STEP_LAWN, data_schema=_lawn_schema(defaults))

    async def async_step_irrigation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Describe the watering system the whole lawn shares."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_irrigation(user_input)
            if not errors:
                _merge(self._data, user_input, OPTIONAL_IRRIGATION_KEYS)
                return await self.async_step_sources()

        defaults = dict(self._data)
        if user_input is not None:
            defaults.update(user_input)
        defaults.setdefault(CONF_IRRIGATION_TYPE, "pop_up_spray")
        return self.async_show_form(
            step_id=STEP_IRRIGATION, data_schema=_irrigation_schema(defaults), errors=errors
        )

    async def async_step_sources(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Choose what the weather over the lawn is read from."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_sources(user_input)
            if not errors:
                _merge(self._data, user_input, OPTIONAL_SOURCE_KEYS)
                if self._reconfiguring:
                    # Updated, not `..._reload_and_abort`: writing the entry already fires
                    # the update listener that reloads it, and asking for a reload here as
                    # well would rebuild every zone twice over.
                    self.hass.config_entries.async_update_entry(
                        self._get_reconfigure_entry(),
                        data=self._data,
                        title=self._data[CONF_NAME],
                    )
                    return self.async_abort(reason="reconfigure_successful")
                return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)

        defaults = dict(self._data)
        if user_input is not None:
            defaults.update(user_input)
        if CONF_WEATHER_ENTITY not in defaults:
            weather = self.hass.states.async_entity_ids("weather")
            if len(weather) == 1:
                defaults[CONF_WEATHER_ENTITY] = weather[0]
        return self.async_show_form(
            step_id=STEP_SOURCES, data_schema=_sources_schema(defaults), errors=errors
        )

    # ------------------------------------------------------------------ reconfigure

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit the lawn. Its zones are edited one by one, on themselves."""
        self._reconfiguring = True
        self._data = dict(self._get_reconfigure_entry().data)
        return await self.async_step_lawn()


class ZoneSubentryFlow(ConfigSubentryFlow):
    """Add or edit one zone of a lawn.

    Everything asked here is true of this zone and not of its neighbours: how big it is, how
    much sun it gets, which valve opens it and what shades it. The lawn answers the rest
    once, because a lawn is one soil and one seed mix however many valves water it.
    """

    def __init__(self) -> None:
        """Start with nothing collected."""
        self._data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Add a zone."""
        return await self.async_step_zone(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Edit a zone through the same two steps it was created with."""
        self._data = dict(self._get_reconfigure_subentry().data)
        return await self.async_step_zone()

    async def async_step_zone(self, user_input: dict[str, Any] | None = None) -> SubentryFlowResult:
        """Describe the zone."""
        if user_input is not None:
            _merge(self._data, user_input, OPTIONAL_ZONE_KEYS)
            return await self.async_step_features()

        defaults = dict(self._data)
        defaults.setdefault(CONF_EXPOSURE, "full_sun")
        return self.async_show_form(step_id=STEP_ZONE, data_schema=_zone_schema(defaults))

    async def async_step_features(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        """Note the trees and structures that shade this zone."""
        errors: dict[str, str] = {}
        if user_input is not None:
            features = _features_from_input(user_input)
            errors = _validate_features(features)
            if not errors:
                self._data[CONF_FEATURES] = features
                title = self._data[CONF_NAME]
                if self.source == SOURCE_RECONFIGURE:
                    return self.async_update_and_abort(
                        self._get_entry(),
                        self._get_reconfigure_subentry(),
                        data=self._data,
                        title=title,
                    )
                return self.async_create_entry(title=title, data=self._data)
        return self.async_show_form(
            step_id=STEP_FEATURES, data_schema=_features_schema(self._data), errors=errors
        )
