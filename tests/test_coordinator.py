"""The coordinator against a make-believe weather station, mower and valve."""

from __future__ import annotations

import datetime as dt
from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.hosekeeper.const import (
    CONF_HUMIDITY_SENSOR,
    CONF_MOWER_ENTITY,
    CONF_SOLAR_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_VALVE_ENTITY,
    CONF_WIND_SENSOR,
    DOMAIN,
)
from custom_components.hosekeeper.engine import schedule
from tests.conftest import make_entry, only_zone, split

RAIN = "sensor.weather_station_rain"
TEMP = "sensor.weather_station_temperature"
RH = "sensor.weather_station_humidity"
WIND = "sensor.weather_station_wind_speed"
SOLAR = "sensor.weather_station_solar_radiation"
VALVE = "switch.lawn_valve"
MOWER = "lawn_mower.robot"


def _forecast(day: dt.date, **overrides: Any) -> dict[str, Any]:
    base = {
        "datetime": dt.datetime.combine(day, dt.time(10), tzinfo=dt.UTC).isoformat(),
        "condition": "sunny",
        "temperature": 33.0,
        "templow": 22.0,
        "humidity": 40,
        "wind_speed": 7.2,
        "precipitation": 0.0,
    }
    return base | overrides


@pytest.fixture(autouse=True)
def _mid_afternoon(freezer: FrozenDateTimeFactory) -> None:
    """Run every test in the same afternoon.

    The coordinator reads the day differently as it goes on: before evening the forecast
    still speaks for the hours that have not happened, and after it the station's own record
    is the day. Left to the wall clock the suite passed at midnight and failed at breakfast,
    which is measuring the clock rather than the code.
    """
    freezer.move_to("2026-09-06T22:00:00+00:00")


@pytest.fixture
def forecast_days() -> list[dict[str, Any]]:
    today = dt_util.now().date()
    return [
        _forecast(today),
        _forecast(today + dt.timedelta(days=1), precipitation=6.0),
        _forecast(today + dt.timedelta(days=2), precipitation=1.0),
        _forecast(today + dt.timedelta(days=3), precipitation=20.0),
    ]


@pytest.fixture
def weather_service(hass: HomeAssistant, forecast_days: list[dict[str, Any]]) -> None:
    async def handle(call: ServiceCall) -> dict[str, Any]:
        return {"weather.forecast_home": {"forecast": forecast_days}}

    hass.services.async_register(
        "weather", "get_forecasts", handle, supports_response=SupportsResponse.ONLY
    )
    hass.states.async_set(
        "weather.forecast_home", "sunny", {"wind_speed_unit": "km/h", "temperature": 33.0}
    )


@pytest.fixture
def station(hass: HomeAssistant) -> None:
    hass.states.async_set(RAIN, "0.0", {"unit_of_measurement": "mm"})
    hass.states.async_set(TEMP, "30.0", {"unit_of_measurement": "°C"})
    hass.states.async_set(RH, "40", {"unit_of_measurement": "%"})
    hass.states.async_set(WIND, "3.6", {"unit_of_measurement": "km/h"})
    hass.states.async_set(SOLAR, "500", {"unit_of_measurement": "W/m²"})
    hass.states.async_set(VALVE, "off")
    hass.states.async_set(MOWER, "docked")


async def _setup(hass: HomeAssistant, field_data: dict[str, Any]) -> MockConfigEntry:
    data = field_data | {
        CONF_TEMPERATURE_SENSOR: TEMP,
        CONF_HUMIDITY_SENSOR: RH,
        CONF_WIND_SENSOR: WIND,
        CONF_SOLAR_SENSOR: SOLAR,
        CONF_VALVE_ENTITY: VALVE,
        CONF_MOWER_ENTITY: MOWER,
    }
    lawn, zone = split(data)
    entry = make_entry(hass, lawn, [zone])
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _settle(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the coordinator's request debouncer fire: rapid changes are coalesced for 10 s."""
    await hass.async_block_till_done()
    freezer.tick(dt.timedelta(seconds=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _state(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    assert state is not None, entity_id
    return state.state


@pytest.mark.usefixtures("weather_service", "station")
async def test_first_refresh_computes_the_balance(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    await _setup(hass, field_data)

    # Tmax comes from the forecast's 33 °C (the sensor has only seen 30 °C so far), the
    # radiation is the temperature-based estimate before sunset, so Penman-Monteith runs on
    # estimated radiation and gives a hot dry day's 6-ish millimetres.
    use = hass.states.get("sensor.south_lawn_lawn_water_use_today")
    assert use is not None
    et0 = use.attributes["reference_et0_mm"]
    assert 3.0 < et0 < 8.5
    assert use.attributes["method"] == "penman_monteith_estimated_radiation"
    assert use.attributes["tmax"] == 33.0
    assert use.attributes["tmin"] == 22.0

    etc = float(use.state)
    # September is a shoulder month for tall fescue: Kc 0.80.
    assert etc == pytest.approx(et0 * 0.80, abs=0.06)

    # Starting from a full profile, the deficit is today's crop ET and nothing more.
    deficit = float(_state(hass, "sensor.south_lawn_soil_water_deficit"))
    assert deficit == pytest.approx(etc, abs=0.06)
    assert float(_state(hass, "sensor.south_lawn_irrigation_recommended")) == 0.0
    rain = hass.states.get("sensor.south_lawn_rain_today")
    assert rain is not None and rain.state == "0.0"
    assert rain.attributes["forecast_next_3_days_mm"] == 7.0
    assert _state(hass, "sensor.south_lawn_days_since_mowing") == "unknown"
    assert _state(hass, "sensor.south_lawn_activity") is not None


@pytest.mark.usefixtures("weather_service", "station")
async def test_rain_gauge_deltas_and_resets(
    hass: HomeAssistant, field_data: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    await _setup(hass, field_data)
    hass.states.async_set(RAIN, "2.5", {"unit_of_measurement": "mm"})
    await _settle(hass, freezer)
    hass.states.async_set(RAIN, "4.0", {"unit_of_measurement": "mm"})
    await _settle(hass, freezer)
    assert _state(hass, "sensor.south_lawn_rain_today") == "4.0"

    # The gauge resets (midnight, or a battery change): the new value is new rain.
    hass.states.async_set(RAIN, "1.0", {"unit_of_measurement": "mm"})
    await _settle(hass, freezer)
    rain = hass.states.get("sensor.south_lawn_rain_today")
    assert rain is not None
    assert rain.state == "5.0"
    assert rain.attributes["source"] == "sensor"


@pytest.mark.usefixtures("weather_service", "station")
async def test_valve_run_is_logged_as_irrigation(
    hass: HomeAssistant, field_data: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    entry = await _setup(hass, field_data)
    hass.states.async_set(VALVE, "on")
    await _settle(hass, freezer)
    freezer.tick(dt.timedelta(minutes=20))
    hass.states.async_set(VALVE, "off")
    await _settle(hass, freezer)

    # 20 minutes (plus the seconds the debouncer waited) at 30 L/min over 120 m² is 5 mm.
    today = only_zone(entry).diary.today()
    assert today["irrigation_min"] == pytest.approx(20.0, abs=0.3)
    assert float(_state(hass, "sensor.south_lawn_irrigation_applied_today")) == pytest.approx(
        5.0, abs=0.1
    )
    assert today["irrigation_source"] == "valve"


@pytest.mark.usefixtures("weather_service", "station")
async def test_mower_session_is_logged_as_a_mow(
    hass: HomeAssistant, field_data: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    entry = await _setup(hass, field_data)
    hass.states.async_set(MOWER, "mowing")
    await hass.async_block_till_done()
    freezer.tick(dt.timedelta(minutes=30))
    hass.states.async_set(MOWER, "paused")
    await hass.async_block_till_done()
    hass.states.async_set(MOWER, "mowing")
    await hass.async_block_till_done()
    freezer.tick(dt.timedelta(minutes=45))
    hass.states.async_set(MOWER, "returning")
    await _settle(hass, freezer)
    hass.states.async_set(MOWER, "docked")
    await _settle(hass, freezer)

    mows = [m for m in only_zone(entry).diary.today()["maintenance"] if m["type"] == "mowing"]
    assert len(mows) == 1
    assert mows[0]["source"] == "mower"
    assert mows[0]["details"]["duration_min"] == 75.0
    assert _state(hass, "sensor.south_lawn_days_since_mowing") == "0"


@pytest.mark.usefixtures("weather_service", "station")
async def test_inputs_write_the_diary(hass: HomeAssistant, field_data: dict[str, Any]) -> None:
    """Confirmations come through the services now; the panel uses its own command.

    There is no number, no select and no row of buttons on the device page: a confirmation
    is made about a job somebody is looking at, and that is the panel's business.
    """
    entry = await _setup(hass, field_data)

    async def call(service: str, **data: Any) -> None:
        await hass.services.async_call(
            DOMAIN, service, {"zone_id": only_zone(entry).zone_id, **data}, blocking=True
        )

    await call("log_irrigation", minutes=40, replace_today=True)
    await call("set_status", status="fair")
    await call("log_maintenance", kind="aeration")
    await hass.async_block_till_done()

    today = only_zone(entry).diary.today()
    assert today["irrigation_min"] == 40
    assert today["irrigation_mm"] == pytest.approx(10.0)
    assert today["status"] == "fair"
    assert today["maintenance"][0]["type"] == "aeration"
    assert _state(hass, "sensor.south_lawn_irrigation_applied_today") == "10.0"

    # Replacing the total rather than adding to it, so a figure can be corrected.
    await call("log_irrigation", minutes=10, replace_today=True)
    await hass.async_block_till_done()
    assert only_zone(entry).diary.today()["irrigation_min"] == 10


@pytest.mark.usefixtures("station")
async def test_without_a_forecast_service_the_sensors_still_work(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    await _setup(hass, field_data)
    use = hass.states.get("sensor.south_lawn_lawn_water_use_today")
    assert use is not None
    # Only the sensors: 30 °C seen once is both the high and the low, so the temperature range
    # is nil and radiation cannot be estimated from it, but the measured integral is not yet
    # there either — a zero ET is the honest answer until the day has some spread in it.
    assert use.attributes["method"] == "penman_monteith_estimated_radiation"
    rain = hass.states.get("sensor.south_lawn_rain_today")
    assert rain is not None and rain.state == "0.0"
    assert rain.attributes["forecast_next_3_days_mm"] is None


@pytest.mark.usefixtures("weather_service", "station")
async def test_deficit_carries_over_and_triggers_irrigation(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    entry = await _setup(hass, field_data)
    diary = only_zone(entry).diary
    yesterday = (dt_util.now().date() - dt.timedelta(days=1)).isoformat()
    # Loam under tall fescue: TAW 45 mm, RAW 22.5 mm. Yesterday ended 20 mm down.
    diary.day(yesterday)["deficit_mm"] = 20.0
    await only_zone(entry).coordinator.async_refresh()
    await hass.async_block_till_done()

    deficit = float(_state(hass, "sensor.south_lawn_soil_water_deficit"))
    assert deficit > 22.5
    assert float(_state(hass, "sensor.south_lawn_irrigation_recommended")) > 0
    recommended = float(_state(hass, "sensor.south_lawn_irrigation_recommended"))
    # Tomorrow's 6 mm of forecast rain is trusted and taken off the refill.
    assert recommended == pytest.approx(deficit - 6.0, abs=0.6)  # advice is in whole millimetres
    attrs = hass.states.get("sensor.south_lawn_irrigation_recommended").attributes
    assert attrs["minutes"] == pytest.approx(recommended / 15.0 * 60.0, abs=0.5)


def _heights(state) -> list[int]:
    """Every cutting height the day names, wherever it names it."""
    return [
        item["params"]["height_mm"]
        for item in [*state.advice, *state.plan, *state.agenda]
        if isinstance(item, dict) and item.get("params", {}).get("height_mm")
    ]


@pytest.mark.usefixtures("weather_service", "station")
async def test_loading_the_lawn_builds_its_plan_again(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    """An upgrade has to reach the plan, or the fix ships and the screen does not change.

    The plan is kept through the month so the weather cannot reshuffle it from one morning to
    the next. A restart, a reload and an upgrade are none of them weather: they are the
    moments somebody has changed something, and building a plan costs a few milliseconds.
    """
    entry = await _setup(hass, field_data)
    month = dt_util.now().strftime("%Y-%m")
    # A plan as the code before this one left it: correctly stamped, so nothing about the
    # lawn or the month asks for it to be built again.
    only_zone(entry).diary.plan["operations"].append(
        {
            "month": month,
            "code": "invented_by_an_older_version",
            "category": "mowing",
            "optional": False,
            "params": {},
            "basis": [],
            "tailoring": [],
        }
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    codes = [op["code"] for op in only_zone(entry).coordinator.data.plan]
    assert "invented_by_an_older_version" not in codes
    assert codes, "the plan was thrown away and not rebuilt"


@pytest.mark.usefixtures("weather_service", "station")
async def test_reporting_bare_patches_puts_the_overseeding_in_the_month(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    """A first-year lawn is left to thicken on its own -- until somebody says it is not.

    The month's operations are decided once and kept so the weather cannot reshuffle them,
    but what the person reports is not weather. Bare turf is exactly what makes the autumn
    overseeding required rather than optional, and a report that changed nothing until the
    month turned is a report nobody would make twice.
    """
    from custom_components.hosekeeper.const import CONF_ESTABLISHMENT_DATE

    # Sod laid this June: young, so the yearly overseeding is not in its first autumn.
    entry = await _setup(hass, field_data | {CONF_ESTABLISHMENT_DATE: "2026-06-21"})
    zone = only_zone(entry)
    seeding = [op for op in zone.coordinator.data.plan if op["category"] == "seeding"]
    assert not [op for op in seeding if op["month"] == "2026-09"]

    await hass.services.async_call(
        DOMAIN,
        "log_issue",
        {"zone_id": zone.zone_id, "issue": "bare_spots"},
        blocking=True,
    )
    await hass.async_block_till_done()

    september = [
        op
        for op in only_zone(entry).coordinator.data.plan
        if op["category"] == "seeding" and op["month"] == "2026-09"
    ]
    assert september, "bare patches were reported and the month still plans no seeding"
    assert "bare_or_thin_areas_seen" in september[0]["tailoring"]
    assert september[0]["optional"] is False


@pytest.mark.usefixtures("weather_service", "station")
async def test_no_cut_is_advised_above_what_the_mower_can_be_set_to(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    """Tall fescue wants 60-90 mm; a robot deck that stops at 60 gets 60.

    Advising a height the machine has no setting for is advice nobody can follow, and the
    lawn ends up cut at whatever the deck was left on.
    """
    from custom_components.hosekeeper.const import CONF_DECK_MAX_MM, CONF_DECK_MIN_MM

    entry = await _setup(hass, field_data | {CONF_DECK_MIN_MM: 20, CONF_DECK_MAX_MM: 60})
    heights = _heights(only_zone(entry).coordinator.data)
    assert heights, "nothing said what to cut to"
    assert max(heights) <= 60, heights


@pytest.mark.usefixtures("weather_service", "station")
async def test_the_month_plan_follows_the_mower_it_was_given(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    """A plan built for the old setup is not left arguing with today's advice.

    The month's operations are decided once and kept, so the weather cannot reshuffle them.
    Changing the lawn is not weather: a deck that cannot reach 90 mm makes every mowing line
    of the stored plan unfollowable, and waiting for the month to turn means a month of a
    plan that says 90 beside advice that says 60.
    """
    from custom_components.hosekeeper.const import CONF_DECK_MAX_MM, CONF_DECK_MIN_MM

    entry = await _setup(hass, field_data)
    zone = only_zone(entry)
    assert max(_heights(zone.coordinator.data)) > 60  # what the species asks for

    hass.config_entries.async_update_entry(
        entry, data=entry.data | {CONF_DECK_MIN_MM: 20, CONF_DECK_MAX_MM: 60}
    )
    await hass.async_block_till_done()
    assert max(_heights(only_zone(entry).coordinator.data)) <= 60


@pytest.mark.usefixtures("weather_service", "station")
async def test_analysis_sensors_and_advice(hass: HomeAssistant, field_data: dict[str, Any]) -> None:
    entry = await _setup(hass, field_data)
    diary = only_zone(entry).diary
    today = dt_util.now().date()
    # A fortnight of hot, humid, rainless late summer with a dishonest forecast behind it.
    for i in range(1, 15):
        day = diary.day((today - dt.timedelta(days=i)).isoformat())
        day.update(tmax=32.0, tmin=21.0, rh_mean=85.0, et0_mm=5.5, rain_mm=0.0, deficit_mm=15.0)
        day["fc"] = {"tmax": 29.0, "tmin": 20.0, "rain": 6.0}
        day["status"] = "fair"
    yesterday = diary.day((today - dt.timedelta(days=1)).isoformat())
    yesterday["deficit_mm"] = 24.0
    yesterday["disease_flags"] = ["dollar_spot", "brown_patch"]
    await only_zone(entry).coordinator.async_refresh()
    await hass.async_block_till_done()

    assert _state(hass, "sensor.south_lawn_season_phase") == "summer_stress"
    phase = hass.states.get("sensor.south_lawn_season_phase")
    assert phase is not None and phase.attributes["heat_stress"] is True
    assert float(_state(hass, "sensor.south_lawn_soil_temperature_estimated")) == pytest.approx(
        26.5, abs=0.6
    )
    rain = hass.states.get("sensor.south_lawn_rain_today")
    assert rain is not None and rain.attributes["dry_spell_days"] == 15  # fourteen days and today

    # Rain was forecast every day and never came: the forecast is not trusted.
    assert _state(hass, "sensor.south_lawn_forecast_rain_reliability") == "0"
    reliability = hass.states.get("sensor.south_lawn_forecast_rain_reliability")
    assert reliability is not None and reliability.attributes["tmax_bias_c"] == 3.0

    # Warm humid nights: both disease models are up. There is no boolean for it — the one
    # sensor an automation reads carries the standing alerts, and the models' own numbers sit
    # with the rest of the season's analysis.
    activity = hass.states.get("sensor.south_lawn_activity")
    assert activity is not None
    assert "dollar_spot_risk" in activity.attributes["alerts"]
    season = hass.states.get("sensor.south_lawn_season_phase")
    assert season is not None and season.attributes["dollar_spot_probability_pct"] > 20

    next_action = hass.states.get("sensor.south_lawn_next_action")
    assert next_action is not None
    codes = [a["code"] for a in next_action.attributes["advice"]]
    assert next_action.state == "irrigate_now"
    assert "dollar_spot_risk" in codes
    # A fortnight of 33 °C does not mean the grass stops growing. Nothing has been cut here,
    # so the cut is still asked for -- at the top of the range, with the heat named as what
    # it is a compromise with. Waiting out the heat is what leaves a lawn to be scalped.
    assert "mow_soon" in codes
    mow = next(a for a in next_action.attributes["advice"] if a["code"] == "mow_soon")
    assert "heat_stress" in mow["reasons"]
    assert mow["params"]["height_mm"] == 90
    irrigate = next(a for a in next_action.attributes["advice"] if a["code"] == "irrigate_now")
    assert "heat_stress" in irrigate["reasons"]
    assert "minutes" in irrigate["params"]
    assert float(_state(hass, "sensor.south_lawn_irrigation_recommended")) > 0
    assert (
        float(_state(hass, "sensor.south_lawn_irrigation_recommended")) == irrigate["params"]["mm"]
    )


@pytest.mark.usefixtures("weather_service", "station")
async def test_adaptation_runs_weekly_and_is_recorded(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    entry = await _setup(hass, field_data)
    diary = only_zone(entry).diary
    today = dt_util.now().date()
    for i in range(1, 10):
        day = diary.day((today - dt.timedelta(days=i)).isoformat())
        day.update(status="poor", deficit_mm=30.0, rain_mm=0.0)
    diary.adaptation["last_evaluated"] = (today - dt.timedelta(days=8)).isoformat()
    await only_zone(entry).coordinator.async_refresh()
    await hass.async_block_till_done()

    assert diary.adaptation["irrigation_factor"] == 1.1
    assert diary.adaptation["history"][-1]["reason"] == "dry_and_declining"
    attrs = hass.states.get("sensor.south_lawn_irrigation_recommended").attributes
    assert attrs["irrigation_factor"] == 1.1


@pytest.mark.usefixtures("weather_service", "station")
async def test_shade_lowers_the_crop_coefficient(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    from custom_components.hosekeeper.const import CONF_FEATURES

    await _setup(hass, field_data | {CONF_FEATURES: [{"kind": "structure", "shade_pct": 40}]})
    use = hass.states.get("sensor.south_lawn_lawn_water_use_today")
    assert use is not None
    # Tall fescue in September is 0.80 in the open; a structure over 40 % of the lawn takes
    # 0.35 * 0.4 off it and, being no tree, gives nothing back.
    assert use.attributes["crop_coefficient"] == pytest.approx(0.80 * (1 - 0.35 * 0.4), abs=0.001)


@pytest.mark.usefixtures("weather_service", "station")
async def test_two_zones_on_one_lawn_chain_their_dawn_cycles(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    """A controller opens one zone at a time, so the zones queue backwards from sunrise."""
    lawn, zone = split(field_data | {CONF_VALVE_ENTITY: VALVE})
    entry = make_entry(
        hass,
        lawn,
        [zone, zone | {CONF_NAME: "North lawn", CONF_VALVE_ENTITY: "switch.north_valve"}],
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    lawns = list(entry.runtime_data.zones.values())
    assert len(lawns) == 2
    today = dt_util.now().date()
    for lawn in lawns:
        lawn.diary.day((today - dt.timedelta(days=1)).isoformat())["deficit_mm"] = 24.0
        lawn.diary.today().pop("irrigation_plan", None)
    hass.data[DOMAIN]["dawn_chain"] = {}
    for lawn in lawns:
        await lawn.coordinator.async_refresh()
    await hass.async_block_till_done()

    runs = []
    for lawn in lawns:
        plan = lawn.diary.today()["irrigation_plan"]
        runs.append(
            [
                (dt_util.parse_datetime(c["start"]), dt_util.parse_datetime(c["end"]))
                for c in plan["cycles"]
            ]
        )
    assert runs[0] and runs[1], "neither lawn was given a cycle"
    for a_start, a_end in runs[0]:
        for b_start, b_end in runs[1]:
            assert a_end <= b_start or b_end <= a_start, "two lawns share the valve"


@pytest.mark.usefixtures("weather_service", "station")
async def test_seed_sown_today_is_watered_today(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    """The day's watering is decided in the morning; the seed goes down in the afternoon.

    The plan is settled once so its depth cannot wobble, and that left the day the seed went
    down as the one day the seedbed was never watered -- and, since the plan is what the
    calendar draws from, every day after it reading as though there were no seedbed at all.
    Surface water is not part of the bargain the settling protects.
    """
    entry = await _setup(hass, field_data)
    zone = only_zone(entry)
    assert not (zone.diary.today().get("irrigation_plan") or {}).get("germination")

    zone.diary.add_maintenance("sowing", at=dt_util.now())
    await zone.coordinator.async_refresh()
    await hass.async_block_till_done()

    passes = zone.coordinator.data.irrigation_plan.get("germination") or []
    assert len(passes) == len(schedule.GERMINATION_TIMES)
    assert passes[0]["mm"] == pytest.approx(schedule.GERMINATION_MM)


@pytest.mark.usefixtures("weather_service", "station")
async def test_rain_after_the_plan_was_made_takes_the_watering_back(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    """A settled plan is not a promise to water a lawn the sky has already watered."""
    entry = await _setup(hass, field_data)
    zone = only_zone(entry)
    today = dt_util.now().date()
    zone.diary.day((today - dt.timedelta(days=1)).isoformat())["deficit_mm"] = 24.0
    zone.diary.today().pop("irrigation_plan", None)
    await zone.coordinator.async_refresh()
    await hass.async_block_till_done()
    planned = zone.coordinator.data.irrigation_plan
    assert planned["cycles"], "no watering was planned to take back"

    # An afternoon of rain nobody forecast, read from the station on the lawn, and the plan
    # is decided again before a drop of it has run.
    hass.states.async_set(RAIN, "30.0", {"unit_of_measurement": "mm"})
    await zone.coordinator.async_refresh()
    await hass.async_block_till_done()

    revised = zone.coordinator.data.irrigation_plan
    assert not revised["cycles"]
    assert "revised_rain_since" in revised["reasons"]


@pytest.mark.usefixtures("weather_service", "station")
async def test_a_lawn_watered_by_hand_is_given_no_queue(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    """The queue is a fact about a controller, not about grass.

    A lawn with no valve is watered by somebody with a hose, who does one zone and then the
    next. Staggering the hours they are given by seven minutes and then fourteen is a
    precision nobody asked for and nothing enforces, and it reads as though the zones needed
    watering at different times of day.
    """
    lawn, zone = split(field_data)
    entry = make_entry(hass, lawn, [zone, zone | {CONF_NAME: "North lawn"}])
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    zones = list(entry.runtime_data.zones.values())
    sown = dt_util.now() - dt.timedelta(days=3)
    for each in zones:
        each.diary.add_maintenance("sowing", at=sown)
        each.diary.today().pop("irrigation_plan", None)
    hass.data[DOMAIN]["dawn_chain"] = {}
    for each in zones:
        await each.coordinator.async_refresh()
    await hass.async_block_till_done()

    hours = [
        [c["start"][11:16] for c in each.coordinator.data.irrigation_plan["germination"]]
        for each in zones
    ]
    assert hours[0] == hours[1] == ["11:00", "14:00", "17:00"]
    assert all(each.coordinator.data.seedbed_queue_min == 0 for each in zones)


@pytest.mark.usefixtures("weather_service", "station")
async def test_two_zones_do_not_water_their_seedbeds_at_the_same_minute(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    """A seedbed is watered three times a day, and one valve cannot serve two zones at once.

    Three zones all told to water at eleven is two zones getting whatever pressure is left,
    or nothing at all, and on the calendar it reads as one job the reader cannot carry out.
    """
    lawn, zone = split(field_data | {CONF_VALVE_ENTITY: VALVE})
    entry = make_entry(
        hass,
        lawn,
        [zone, zone | {CONF_NAME: "North lawn", CONF_VALVE_ENTITY: "switch.north_valve"}],
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    zones = list(entry.runtime_data.zones.values())
    today = dt_util.now().date()
    sown = dt_util.now() - dt.timedelta(days=3)
    for each in zones:
        each.diary.add_maintenance("sowing", at=sown)
        each.diary.today().pop("irrigation_plan", None)
    hass.data[DOMAIN]["dawn_chain"] = {}
    for each in zones:
        await each.coordinator.async_refresh()
    await hass.async_block_till_done()

    passes = []
    for each in zones:
        plan = each.diary.day(today.isoformat())["irrigation_plan"]
        assert plan.get("germination"), f"{each.field.name} was not given a seedbed regime"
        passes.append(
            [
                (dt_util.parse_datetime(c["start"]), dt_util.parse_datetime(c["end"]))
                for c in plan["germination"]
            ]
        )
    for a_start, a_end in passes[0]:
        for b_start, b_end in passes[1]:
            assert a_end <= b_start or b_end <= a_start, "two zones water the seedbed at once"
    assert passes[0][0][0] != passes[1][0][0], "both zones start their first pass at the same time"
    # And not merely back to back: a valve takes a moment, and two runs written to the minute
    # against each other read as one long run.
    gap = min(abs(b[0] - a[1]) for a in passes[0] for b in passes[1] if b[0] >= a[1])
    assert gap >= schedule.VALVE_GAP


@pytest.mark.usefixtures("weather_service", "station")
async def test_the_station_outranks_the_forecast_once_the_day_is_over(
    hass: HomeAssistant, field_data: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    # The forecast calls 33 °C; the station on the lawn recorded 36. During the day the
    # forecast may still anticipate a higher peak, but by evening the measurement is the day.
    entry = await _setup(hass, field_data | {CONF_TEMPERATURE_SENSOR: TEMP})
    hass.states.async_set(TEMP, "36.0", {"unit_of_measurement": "°C"})
    await _settle(hass, freezer)

    use = hass.states.get("sensor.south_lawn_lawn_water_use_today")
    assert use is not None
    assert use.attributes["tmax"] == 36.0, "the station's own reading, not the forecast's 33"

    # And a forecast that overshoots does not raise the day's water use after sunset.
    freezer.move_to(dt_util.now().replace(hour=21, minute=0))
    await only_zone(entry).coordinator.async_refresh()
    await hass.async_block_till_done()
    evening = hass.states.get("sensor.south_lawn_lawn_water_use_today")
    assert evening is not None
    assert evening.attributes["tmax"] == 36.0


@pytest.mark.usefixtures("weather_service", "station")
async def test_a_seedbed_pass_through_the_valve_is_not_credited_to_the_balance(
    hass: HomeAssistant, field_data: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    """The valve serves both regimes, and only one of them fills the root zone.

    Three light passes over a seedbed wet the top centimetre and mostly go back to the air.
    Counting them as irrigation would tell the balance the roots were filled and cancel the
    dawn cycle the turf around the seed still needs, which is the failure that nearly killed
    a real lawn during development.
    """
    entry = await _setup(hass, field_data)
    await hass.services.async_call(
        DOMAIN,
        "log_sowing",
        {"zone_id": only_zone(entry).zone_id, "kind": "overseed"},
        blocking=True,
    )
    # The plan for the coming dawn was decided before the sowing was recorded, and is kept
    # for the day on purpose. Drop it so the coordinator decides again with the seed in it.
    only_zone(entry).diary.today().pop("irrigation_plan", None)
    await only_zone(entry).coordinator.async_refresh()
    await _settle(hass, freezer)

    plan = only_zone(entry).coordinator.data.irrigation_plan
    runs = plan.get("germination") or []
    assert runs, "a lawn sown today should be given its seedbed passes"

    # Open the valve inside one of those passes, the way the controller would.
    run_start = dt_util.parse_datetime(runs[0]["start"])
    assert run_start is not None
    freezer.move_to(run_start)
    hass.states.async_set(VALVE, "on")
    await _settle(hass, freezer)
    freezer.tick(dt.timedelta(minutes=6))
    hass.states.async_set(VALVE, "off")
    await _settle(hass, freezer)

    page = only_zone(entry).diary.day(run_start.date().isoformat())
    assert page.get("seedbed_min", 0) > 0, "the pass was not recorded at all"
    assert not page.get("irrigation_mm"), "a seedbed pass was credited to the root zone"


@pytest.mark.usefixtures("weather_service", "station")
async def test_two_lawns_never_open_their_valves_at_the_same_minute(
    hass: HomeAssistant, field_data: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    """Both halves have to queue: the deep dawn cycles, and the seedbed's own passes.

    The second was missed, so lawns sown together would all have opened at eleven.
    """
    lawn, zone = split(field_data | {CONF_VALVE_ENTITY: VALVE})
    entry = make_entry(hass, lawn, [zone, zone | {CONF_NAME: "North lawn"}])
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    lawns = list(entry.runtime_data.zones.values())
    for lawn in lawns:
        await hass.services.async_call(
            DOMAIN,
            "log_sowing",
            {"zone_id": lawn.zone_id, "kind": "overseed"},
            blocking=True,
        )
        lawn.diary.today().pop("irrigation_plan", None)
        await lawn.coordinator.async_refresh()
    await _settle(hass, freezer)

    runs = []
    for lawn in lawns:
        plan = lawn.coordinator.data.irrigation_plan
        runs.append(
            [
                (dt_util.parse_datetime(c["start"]), dt_util.parse_datetime(c["end"]))
                for c in [*(plan.get("cycles") or []), *(plan.get("germination") or [])]
            ]
        )
    assert runs[0] and runs[1], "neither lawn was given anything to run"
    for a_start, a_end in runs[0]:
        for b_start, b_end in runs[1]:
            assert a_end <= b_start or b_end <= a_start, (
                f"two lawns share the valve from {max(a_start, b_start)} to {min(a_end, b_end)}"
            )


@pytest.mark.usefixtures("weather_service", "station")
async def test_a_hot_day_ahead_is_planned_for_on_the_very_first_refresh(
    hass: HomeAssistant, field_data: dict[str, Any], forecast_days: list[dict[str, Any]]
) -> None:
    """The plan reads the forecast fetched this cycle, not the one on the last state.

    It used to read the previous refresh's, which on the first run after setup does not
    exist. The plan was made blind, and being made once and kept for the day, it stayed
    blind: a lawn set up the evening before a 33 °C day was given no midday syringing.
    """
    tomorrow = dt_util.now().date() + dt.timedelta(days=1)
    for day in forecast_days:
        if day["datetime"].startswith(tomorrow.isoformat()):
            day["temperature"] = 33.4

    entry = await _setup(hass, field_data)
    plan = only_zone(entry).coordinator.data.irrigation_plan
    assert plan["date"] == tomorrow.isoformat()
    assert plan["syringe"] is True, "a 33 °C day ahead was planned for without a syringing"
    assert plan["syringe_start"] is not None
    assert "midday_syringing_heat" in plan["reasons"]


@pytest.mark.usefixtures("weather_service", "station")
async def test_heat_reaches_a_plan_that_was_already_decided(
    hass: HomeAssistant, field_data: dict[str, Any], forecast_days: list[dict[str, Any]]
) -> None:
    """A watering is decided once and kept; a syringing may still be added afterwards.

    The depth must not wobble with every refresh, which is why the plan is settled and
    stored. But heat does not always announce itself before that happens, and a syringing is
    a millimetre and a half that never enters the balance. Without this a plan made on a mild
    forecast stayed mild all day, however hot the forecast turned.
    """
    # A mild forecast when the plan is made, so there is nothing to add yet.
    tomorrow = dt_util.now().date() + dt.timedelta(days=1)
    for day in forecast_days:
        if day["datetime"].startswith(tomorrow.isoformat()):
            day["temperature"] = 24.0
    entry = await _setup(hass, field_data)
    stored = only_zone(entry).diary.today()["irrigation_plan"]
    assert stored["syringe"] is False, "the day was already hot, so nothing is being tested"

    # And then the forecast turns.
    for day in forecast_days:
        if day["datetime"].startswith(tomorrow.isoformat()):
            day["temperature"] = 34.0
    await only_zone(entry).coordinator.async_refresh()
    await hass.async_block_till_done()

    plan = only_zone(entry).coordinator.data.irrigation_plan
    assert plan["date"] == tomorrow.isoformat()
    assert plan["syringe"] is True
    assert plan["syringe_start"].endswith("13:00:00") or "T13:" in plan["syringe_start"]
    assert "midday_syringing_heat" in plan["reasons"]
