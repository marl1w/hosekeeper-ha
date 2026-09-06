"""Sensors: the analysis, one number at a time, for automations and history."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HosekeeperConfigEntry
from .coordinator import FieldState
from .engine import activity
from .engine.rules import ADVICE_CODES
from .entity import HosekeeperEntity

SEASON_PHASES = (
    "dormant",
    "spring_greenup",
    "spring_active",
    "summer_stress",
    "autumn_active",
    "late_autumn",
)


@dataclass(frozen=True, kw_only=True)
class HosekeeperSensorDescription(SensorEntityDescription):
    """A sensor and how to read it from the field state."""

    value: Callable[[FieldState], float | int | str | None]
    attributes: Callable[[FieldState], dict[str, Any]] | None = None


SENSORS: tuple[HosekeeperSensorDescription, ...] = (
    HosekeeperSensorDescription(
        key="water_use_today",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:grass",
        value=lambda s: s.etc_mm,
        attributes=lambda s: {
            "reference_et0_mm": s.et0_mm,
            "crop_coefficient": s.kc,
            "method": s.et_method,
            "tmax": s.tmax,
            "tmin": s.tmin,
            "humidity": None if s.rh_mean is None else round(s.rh_mean, 1),
            "wind_ms": None if s.wind_ms is None else round(s.wind_ms, 2),
            "solar_mj": None if s.rs_mj is None else round(s.rs_mj, 2),
        },
    ),
    HosekeeperSensorDescription(
        key="water_deficit",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:water-minus",
        value=lambda s: s.deficit_mm,
        attributes=lambda s: {
            "total_available_mm": s.taw_mm,
            "readily_available_mm": s.raw_mm,
            "soil_water_available_pct": round(s.available_fraction * 100),
            "soil_moisture_sensor_pct": s.soil_moisture_pct,
        },
    ),
    HosekeeperSensorDescription(
        key="irrigation_recommended",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:sprinkler-variant",
        value=lambda s: s.irrigation_needed_mm,
        attributes=lambda s: {
            "minutes": s.irrigation_needed_min,
            "forecast_rain_24h_mm": s.forecast_rain_24h_mm,
            "irrigation_factor": s.irrigation_factor,
            # The whole plan: every run with its clock, so an automation that wants more
            # than "a cycle is running now" has it here rather than on a second entity.
            "cycle": s.irrigation_cycle,
            "next_start": s.irrigation_next_start,
            **s.irrigation_plan,
        },
    ),
    HosekeeperSensorDescription(
        key="rain_today",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        device_class=SensorDeviceClass.PRECIPITATION,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value=lambda s: s.rain_today_mm,
        attributes=lambda s: {
            "source": s.rain_source,
            "last_7_days_mm": s.rain_7d_mm,
            "forecast_next_3_days_mm": s.forecast_rain_3d_mm,
            "dry_spell_days": s.dry_spell_days,
        },
    ),
    HosekeeperSensorDescription(
        key="irrigation_today",
        native_unit_of_measurement=UnitOfLength.MILLIMETERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        icon="mdi:sprinkler",
        value=lambda s: s.irrigation_today_mm,
        attributes=lambda s: {
            "minutes": s.irrigation_today_min,
            "last_7_days_mm": s.irrigation_7d_mm,
        },
    ),
    HosekeeperSensorDescription(
        key="days_since_mowing",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:mower",
        value=lambda s: s.days_since_mowing,
    ),
    HosekeeperSensorDescription(
        key="nitrogen_this_year",
        native_unit_of_measurement="g/m²",
        state_class=SensorStateClass.TOTAL,
        suggested_display_precision=1,
        icon="mdi:leaf",
        value=lambda s: s.nitrogen_year_g_m2,
        attributes=lambda s: {
            "last_60_days_g_m2": s.nitrogen_60d_g_m2,
            "days_since_fertilizing": s.days_since_fertilizing,
            "feed_factor": s.feed_factor,
        },
    ),
    HosekeeperSensorDescription(
        # The one an automation acts on: what the lawn is busy with, and whether a machine
        # or a person is doing it. Everything else about the job is in the attributes.
        key="activity",
        device_class=SensorDeviceClass.ENUM,
        options=list(activity.STATES),
        icon="mdi:progress-wrench",
        value=lambda s: s.activity,
        attributes=lambda s: s.activity_details,
    ),
    HosekeeperSensorDescription(
        key="next_action",
        device_class=SensorDeviceClass.ENUM,
        options=list(ADVICE_CODES),
        icon="mdi:clipboard-text-clock",
        value=lambda s: s.next_action,
        attributes=lambda s: {"advice": s.advice, "plan": s.plan},
    ),
    HosekeeperSensorDescription(
        key="season_phase",
        device_class=SensorDeviceClass.ENUM,
        options=list(SEASON_PHASES),
        icon="mdi:calendar-range",
        value=lambda s: s.season_phase,
        attributes=lambda s: {
            "heat_stress": s.heat_stress,
            "days_to_first_frost": s.days_to_first_frost,
            "growing_degree_days": s.gdd,
            "dollar_spot_probability_pct": (
                None
                if s.dollar_spot_probability is None
                else round(s.dollar_spot_probability * 100)
            ),
            "brown_patch_index": s.brown_patch_index,
        },
    ),
    HosekeeperSensorDescription(
        key="soil_temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value=lambda s: s.soil_temperature_c,
    ),
    HosekeeperSensorDescription(
        key="forecast_rain_reliability",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        icon="mdi:weather-cloudy-clock",
        value=lambda s: (
            None
            if s.forecast_rain_reliability is None
            else round(s.forecast_rain_reliability * 100)
        ),
        attributes=lambda s: {"tmax_bias_c": s.forecast_tmax_bias, "et_anomaly": s.et_anomaly},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HosekeeperConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the sensors for one field."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(HosekeeperSensor(coordinator, description) for description in SENSORS)


class HosekeeperSensor(HosekeeperEntity, SensorEntity):
    """One number from the field state."""

    entity_description: HosekeeperSensorDescription

    def __init__(self, coordinator, description: HosekeeperSensorDescription) -> None:
        """Bind to a description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | int | str | None:
        """Return the described value."""
        return self.entity_description.value(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the described attributes, if any."""
        if self.entity_description.attributes is None:
            return None
        return self.entity_description.attributes(self.coordinator.data)
