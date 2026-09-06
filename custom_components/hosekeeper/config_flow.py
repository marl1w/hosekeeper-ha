"""Config flow: one field per entry, described in three short steps.

The same three steps serve first setup and later reconfiguration, so a lawn that gets a
new sprinkler or a new rain gauge is edited where it was created, not in a second place.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.helpers import selector
from homeassistant.util import slugify
import voluptuous as vol

from .const import (
    CONF_AREA,
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
    SOIL_TYPES,
)

STEP_FIELD = "field"
STEP_IRRIGATION = "irrigation"
STEP_SOURCES = "sources"
STEP_FEATURES = "features"

# Sensors that are optional in the form arrive as a missing key when left empty; the
# reconfigure form needs them listed to clear a previously chosen entity.
OPTIONAL_SOURCE_KEYS = (
    CONF_RAIN_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_HUMIDITY_SENSOR,
    CONF_WIND_SENSOR,
    CONF_SOLAR_SENSOR,
    CONF_SOIL_MOISTURE_SENSOR,
    CONF_MOWER_ENTITY,
)
OPTIONAL_IRRIGATION_KEYS = (CONF_FLOW_L_MIN, CONF_PRECIPITATION_RATE, CONF_VALVE_ENTITY)
OPTIONAL_FIELD_KEYS = (CONF_ESTABLISHMENT_DATE,)


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


def _field_schema(defaults: dict[str, Any]) -> vol.Schema:
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
            vol.Required(
                CONF_LOCATION, default=defaults.get(CONF_LOCATION)
            ): selector.LocationSelector(selector.LocationSelectorConfig(radius=False)),
            vol.Required(CONF_EXPOSURE, default=defaults.get(CONF_EXPOSURE)): _select(
                EXPOSURES, CONF_EXPOSURE
            ),
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
            vol.Optional(
                CONF_VALVE_ENTITY,
                description={"suggested_value": defaults.get(CONF_VALVE_ENTITY)},
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["valve", "switch", "input_boolean"])
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
    chosen = [data[key] for key in (CONF_WEATHER_ENTITY, *OPTIONAL_SOURCE_KEYS) if data.get(key)]
    if len(chosen) != len(set(chosen)):
        return {"base": "duplicate_source"}
    return {}


def _merge(target: dict[str, Any], user_input: dict[str, Any], optional: tuple[str, ...]) -> None:
    """Apply a step's answers, treating an optional key left empty as cleared."""
    for key in optional:
        target.pop(key, None)
    target.update(user_input)


class HosekeeperConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create or reconfigure a field."""

    VERSION = 1

    def __init__(self) -> None:
        """Start with nothing collected."""
        self._data: dict[str, Any] = {}
        self._reconfiguring = False

    # ------------------------------------------------------------------ first setup

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Begin: the lawn itself."""
        return await self.async_step_field(user_input)

    async def async_step_field(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Describe the lawn."""
        if user_input is not None:
            if not self._reconfiguring:
                await self.async_set_unique_id(slugify(user_input[CONF_NAME]))
                self._abort_if_unique_id_configured()
            _merge(self._data, user_input, OPTIONAL_FIELD_KEYS)
            return await self.async_step_irrigation()

        defaults = dict(self._data)
        defaults.setdefault(
            CONF_LOCATION,
            {
                CONF_LATITUDE: self.hass.config.latitude,
                CONF_LONGITUDE: self.hass.config.longitude,
            },
        )
        defaults.setdefault(CONF_EXPOSURE, "full_sun")
        defaults.setdefault(CONF_SOIL_TYPE, "loam")
        defaults.setdefault(CONF_GRASS_TYPE, "cool_season_mix")
        defaults.setdefault(CONF_ESTABLISHMENT_METHOD, "unknown")
        return self.async_show_form(step_id=STEP_FIELD, data_schema=_field_schema(defaults))

    async def async_step_irrigation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Describe how the lawn is watered."""
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
        """Choose what feeds the field."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate_sources(user_input)
            if not errors:
                _merge(self._data, user_input, OPTIONAL_SOURCE_KEYS)
                return await self.async_step_features()

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

    async def async_step_features(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Note the trees and structures that shade the lawn."""
        errors: dict[str, str] = {}
        if user_input is not None:
            features = _features_from_input(user_input)
            errors = _validate_features(features)
            if not errors:
                self._data[CONF_FEATURES] = features
                if self._reconfiguring:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        data=self._data,
                        title=self._data[CONF_NAME],
                    )
                return self.async_create_entry(title=self._data[CONF_NAME], data=self._data)
        return self.async_show_form(
            step_id=STEP_FEATURES, data_schema=_features_schema(self._data), errors=errors
        )

    # ------------------------------------------------------------------ reconfigure

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit an existing field through the same three steps."""
        self._reconfiguring = True
        self._data = dict(self._get_reconfigure_entry().data)
        return await self.async_step_field()
