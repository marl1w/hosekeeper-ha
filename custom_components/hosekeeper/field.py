"""The configured description of one lawn, read from a config entry."""

from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
from typing import Any

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

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
)


@dataclass(frozen=True, slots=True)
class Feature:
    """Something that casts shade on the lawn: a tree or a structure."""

    kind: str
    """deciduous_tree | evergreen_tree | structure"""
    shade_pct: float
    """Share of the lawn it shades for a good part of the day, percent."""

    @property
    def is_tree(self) -> bool:
        """Return whether roots compete with the grass for water."""
        return self.kind.endswith("_tree")


@dataclass(frozen=True, slots=True)
class FieldConfig:
    """Everything the engine needs to know about a lawn, and nothing about Home Assistant."""

    name: str
    area_m2: float
    latitude: float
    longitude: float
    exposure: str
    soil_type: str
    grass_type: str
    establishment_method: str
    establishment_date: dt.date | None

    irrigation_type: str
    flow_l_min: float | None
    precipitation_rate_mm_h: float | None
    valve_entity: str | None

    weather_entity: str
    rain_sensor: str | None
    temperature_sensor: str | None
    humidity_sensor: str | None
    wind_sensor: str | None
    solar_sensor: str | None
    soil_moisture_sensor: str | None
    mower_entity: str | None
    robot_cadence: str = "balanced"
    deck_min_mm: int | None = None
    deck_max_mm: int | None = None
    features: tuple[Feature, ...] = ()

    @classmethod
    def from_entry(cls, lawn: dict[str, Any], zone: dict[str, Any]) -> FieldConfig:
        """Build one zone from the lawn it is part of and its own answers.

        The engine wants a zone as one flat thing, and that is what this returns. The split
        between the two dictionaries is only where the answers were given: the lawn holds
        what is true of the whole turf, the zone what is true of that part of it. A zone may
        override anything, which is what lets one corner be clay while the rest is loam.
        """
        return cls.from_data({**lawn, **zone})

    @classmethod
    def from_data(cls, data: dict[str, Any]) -> FieldConfig:
        """Build from one flat mapping of answers."""
        location = data.get(CONF_LOCATION) or {}
        raw_date = data.get(CONF_ESTABLISHMENT_DATE)
        return cls(
            name=data[CONF_NAME],
            area_m2=float(data[CONF_AREA]),
            latitude=float(location[CONF_LATITUDE]),
            longitude=float(location[CONF_LONGITUDE]),
            exposure=data[CONF_EXPOSURE],
            soil_type=data[CONF_SOIL_TYPE],
            grass_type=data[CONF_GRASS_TYPE],
            establishment_method=data[CONF_ESTABLISHMENT_METHOD],
            establishment_date=dt.date.fromisoformat(raw_date) if raw_date else None,
            irrigation_type=data[CONF_IRRIGATION_TYPE],
            flow_l_min=_optional_float(data.get(CONF_FLOW_L_MIN)),
            precipitation_rate_mm_h=_optional_float(data.get(CONF_PRECIPITATION_RATE)),
            valve_entity=data.get(CONF_VALVE_ENTITY) or None,
            weather_entity=data[CONF_WEATHER_ENTITY],
            rain_sensor=data.get(CONF_RAIN_SENSOR) or None,
            temperature_sensor=data.get(CONF_TEMPERATURE_SENSOR) or None,
            humidity_sensor=data.get(CONF_HUMIDITY_SENSOR) or None,
            wind_sensor=data.get(CONF_WIND_SENSOR) or None,
            solar_sensor=data.get(CONF_SOLAR_SENSOR) or None,
            soil_moisture_sensor=data.get(CONF_SOIL_MOISTURE_SENSOR) or None,
            mower_entity=data.get(CONF_MOWER_ENTITY) or None,
            robot_cadence=data.get(CONF_ROBOT_CADENCE) or "balanced",
            deck_min_mm=_optional_int(data.get(CONF_DECK_MIN_MM)),
            deck_max_mm=_optional_int(data.get(CONF_DECK_MAX_MM)),
            features=tuple(
                Feature(item["kind"], float(item.get("shade_pct", 0)))
                for item in data.get(CONF_FEATURES, [])
                if item.get("kind") and item["kind"] != "none"
            ),
        )

    @property
    def deck_mm(self) -> tuple[int, int] | None:
        """Return the heights the mower can be set to, when both ends were given.

        One end alone says nothing usable: a mower that cuts no lower than 20 mm can still
        cut as high as anyone likes, and a species range clamped against half a range is a
        guess dressed as a measurement.
        """
        if self.deck_min_mm is None or self.deck_max_mm is None:
            return None
        return self.deck_min_mm, self.deck_max_mm

    @property
    def shaded_fraction(self) -> float:
        """Return the share of the lawn in shade, 0 to 0.9."""
        return min(0.9, sum(f.shade_pct for f in self.features) / 100.0)

    @property
    def tree_fraction(self) -> float:
        """Return the share of the lawn under tree canopy, where roots compete."""
        return min(0.9, sum(f.shade_pct for f in self.features if f.is_tree) / 100.0)

    @property
    def has_deciduous_trees(self) -> bool:
        """Return whether leaves will fall on the lawn in autumn."""
        return any(f.kind == "deciduous_tree" for f in self.features)

    @property
    def application_rate_mm_h(self) -> float | None:
        """How many millimetres an hour of irrigation puts on the lawn.

        A measured precipitation rate wins; otherwise it follows from the flow spread over
        the area (1 L over 1 m² is 1 mm). None when the field is not irrigated at all.
        """
        if self.precipitation_rate_mm_h:
            return self.precipitation_rate_mm_h
        if self.flow_l_min and self.area_m2:
            return self.flow_l_min * 60.0 / self.area_m2
        return None

    def minutes_to_mm(self, minutes: float) -> float | None:
        """Convert irrigation run time to depth, or None when the rate is unknown."""
        rate = self.application_rate_mm_h
        return None if rate is None else minutes / 60.0 * rate

    def mm_to_minutes(self, mm: float) -> float | None:
        """Convert a depth to run time, or None when the rate is unknown."""
        rate = self.application_rate_mm_h
        return None if not rate else mm / rate * 60.0

    @property
    def linked_entities(self) -> tuple[str, ...]:
        """Every entity whose state changes should refresh the field."""
        candidates = (
            self.weather_entity,
            self.rain_sensor,
            self.temperature_sensor,
            self.humidity_sensor,
            self.wind_sensor,
            self.solar_sensor,
            self.soil_moisture_sensor,
            self.valve_entity,
            self.mower_entity,
        )
        return tuple(entity for entity in candidates if entity)


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return round(float(value))
