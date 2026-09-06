"""Constants shared across the integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "hosekeeper"

# --- config entry data -------------------------------------------------------------------

CONF_AREA: Final = "area"
CONF_LOCATION: Final = "location"
CONF_EXPOSURE: Final = "exposure"
CONF_SOIL_TYPE: Final = "soil_type"
CONF_GRASS_TYPE: Final = "grass_type"
CONF_ESTABLISHMENT_METHOD: Final = "establishment_method"
CONF_ESTABLISHMENT_DATE: Final = "establishment_date"

CONF_IRRIGATION_TYPE: Final = "irrigation_type"
CONF_FLOW_L_MIN: Final = "flow_l_min"
CONF_PRECIPITATION_RATE: Final = "precipitation_rate_mm_h"
CONF_VALVE_ENTITY: Final = "valve_entity"

CONF_FEATURES: Final = "features"
FEATURE_SLOTS: Final = 3
FEATURE_TYPES: Final = ("none", "deciduous_tree", "evergreen_tree", "structure")

CONF_WEATHER_ENTITY: Final = "weather_entity"
CONF_RAIN_SENSOR: Final = "rain_sensor"
CONF_TEMPERATURE_SENSOR: Final = "temperature_sensor"
CONF_HUMIDITY_SENSOR: Final = "humidity_sensor"
CONF_WIND_SENSOR: Final = "wind_sensor"
CONF_SOLAR_SENSOR: Final = "solar_sensor"
CONF_SOIL_MOISTURE_SENSOR: Final = "soil_moisture_sensor"
CONF_MOWER_ENTITY: Final = "mower_entity"

# --- select options ----------------------------------------------------------------------
# These are stable identifiers: they appear in stored entries and in the translation files,
# so renaming one is a migration, not an edit.

EXPOSURES: Final = ("full_sun", "partial_shade", "shade")

SOIL_TYPES: Final = ("sandy", "sandy_loam", "loam", "clay_loam", "clay")

GRASS_TYPES: Final = (
    # Cool season — what grows in Northern Italy and most of temperate Europe.
    "cool_season_mix",
    "tall_fescue",
    "perennial_ryegrass",
    "kentucky_bluegrass",
    "fine_fescue",
    "microclover_mix",
    # Warm season.
    "bermuda",
    "zoysia",
    "st_augustine",
    "dichondra",
)

ESTABLISHMENT_METHODS: Final = ("sod", "seed", "hydroseed", "unknown")

IRRIGATION_TYPES: Final = ("pop_up_spray", "rotor", "drip", "hose_manual", "none")

# --- panel -------------------------------------------------------------------------------

PANEL_URL_PATH: Final = "hosekeeper"
PANEL_COMPONENT: Final = "hosekeeper-panel"
PANEL_TITLE: Final = "Hosekeeper"
PANEL_ICON: Final = "mdi:grass"
STATIC_URL: Final = "/hosekeeper_static"

# --- storage -----------------------------------------------------------------------------

DIARY_STORAGE_VERSION: Final = 1
DIARY_STORAGE_KEY: Final = f"{DOMAIN}.diary"

# --- tracking ----------------------------------------------------------------------------

LAWN_STATUSES: Final = ("excellent", "good", "fair", "poor")

# What a person can see that no instrument reports. Each one changes a decision: weeds and
# moss make their treatment pass compulsory instead of optional, bare or thin turf makes the
# overseeding compulsory and brings the seed forward, thatch and moss make the autumn soil
# work compulsory, and fungus or brown patches hold back nitrogen and make the preventive
# treatment compulsory. "thin" was read by the plan in three places and was not on this list,
# so those three branches could never fire.
ISSUES: Final = (
    "brown_patches",
    "thin",
    "bare_spots",
    "weeds",
    "moss",
    "fungus",
    "pests",
    "thatch",
)

MAINTENANCE_KINDS: Final = (
    "mowing",
    "fertilizing",
    "sowing",
    "weeding",
    "aeration",
    "scarifying",
    "top_dressing",
    "treatment",
    "leaf_clearing",
    # Water that wets the surface and not the root zone. Recorded as work done, never as
    # irrigation, so the balance is not told the roots were filled when they were not.
    "seedbed_watering",
    "syringing",
)

# The kinds a person can confirm with one tap in the panel, needing nothing but a timestamp.
# The rest go through a service that can carry the product, the rate or the seed mix.
SIMPLE_MAINTENANCE: Final = ("mowing", "weeding", "aeration", "scarifying", "top_dressing")
