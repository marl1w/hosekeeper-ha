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
    entry = MockConfigEntry(domain=DOMAIN, data=data, unique_id="south_lawn", title="South lawn")
    entry.add_to_hass(hass)
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
    today = entry.runtime_data.diary.today()
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

    mows = [m for m in entry.runtime_data.diary.today()["maintenance"] if m["type"] == "mowing"]
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
            DOMAIN, service, {"config_entry_id": entry.entry_id, **data}, blocking=True
        )

    await call("log_irrigation", minutes=40, replace_today=True)
    await call("set_status", status="fair")
    await call("log_maintenance", kind="aeration")
    await hass.async_block_till_done()

    today = entry.runtime_data.diary.today()
    assert today["irrigation_min"] == 40
    assert today["irrigation_mm"] == pytest.approx(10.0)
    assert today["status"] == "fair"
    assert today["maintenance"][0]["type"] == "aeration"
    assert _state(hass, "sensor.south_lawn_irrigation_applied_today") == "10.0"

    # Replacing the total rather than adding to it, so a figure can be corrected.
    await call("log_irrigation", minutes=10, replace_today=True)
    await hass.async_block_till_done()
    assert entry.runtime_data.diary.today()["irrigation_min"] == 10


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
    diary = entry.runtime_data.diary
    yesterday = (dt_util.now().date() - dt.timedelta(days=1)).isoformat()
    # Loam under tall fescue: TAW 45 mm, RAW 22.5 mm. Yesterday ended 20 mm down.
    diary.day(yesterday)["deficit_mm"] = 20.0
    await entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    deficit = float(_state(hass, "sensor.south_lawn_soil_water_deficit"))
    assert deficit > 22.5
    assert float(_state(hass, "sensor.south_lawn_irrigation_recommended")) > 0
    recommended = float(_state(hass, "sensor.south_lawn_irrigation_recommended"))
    # Tomorrow's 6 mm of forecast rain is trusted and taken off the refill.
    assert recommended == pytest.approx(deficit - 6.0, abs=0.6)  # advice is in whole millimetres
    attrs = hass.states.get("sensor.south_lawn_irrigation_recommended").attributes
    assert attrs["minutes"] == pytest.approx(recommended / 15.0 * 60.0, abs=0.5)


@pytest.mark.usefixtures("weather_service", "station")
async def test_analysis_sensors_and_advice(hass: HomeAssistant, field_data: dict[str, Any]) -> None:
    entry = await _setup(hass, field_data)
    diary = entry.runtime_data.diary
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
    await entry.runtime_data.coordinator.async_refresh()
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
    assert "delay_mowing_stress" in codes
    assert "dollar_spot_risk" in codes
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
    diary = entry.runtime_data.diary
    today = dt_util.now().date()
    for i in range(1, 10):
        day = diary.day((today - dt.timedelta(days=i)).isoformat())
        day.update(status="poor", deficit_mm=30.0, rain_mm=0.0)
    diary.adaptation["last_evaluated"] = (today - dt.timedelta(days=8)).isoformat()
    await entry.runtime_data.coordinator.async_refresh()
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
async def test_two_fields_chain_their_dawn_cycles(
    hass: HomeAssistant, field_data: dict[str, Any]
) -> None:
    first = await _setup(hass, field_data)
    second_data = field_data | {CONF_NAME: "Giardino nord"}
    second = MockConfigEntry(
        domain=DOMAIN, data=second_data, unique_id="giardino_nord", title="Giardino nord"
    )
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()

    today = dt_util.now().date()
    for entry in (first, second):
        diary = entry.runtime_data.diary
        diary.day((today - dt.timedelta(days=1)).isoformat())["deficit_mm"] = 24.0
        diary.today().pop("irrigation_plan", None)
    hass.data[DOMAIN]["dawn_chain"] = {}
    await first.runtime_data.coordinator.async_refresh()
    await second.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    a = first.runtime_data.diary.today()["irrigation_plan"]
    b = second.runtime_data.diary.today()["irrigation_plan"]
    assert a["main_minutes"] and b["main_minutes"]
    # One valve at a time: the second field's cycle ends where the first one starts.
    assert b["main_end"] <= a["main_start"]
    assert a["main_end"] > b["main_end"]
    agenda_items = first.runtime_data.coordinator.data.agenda
    assert isinstance(agenda_items, list)


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
    await entry.runtime_data.coordinator.async_refresh()
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
        {"config_entry_id": entry.entry_id, "kind": "overseed"},
        blocking=True,
    )
    # The plan for the coming dawn was decided before the sowing was recorded, and is kept
    # for the day on purpose. Drop it so the coordinator decides again with the seed in it.
    entry.runtime_data.diary.today().pop("irrigation_plan", None)
    await entry.runtime_data.coordinator.async_refresh()
    await _settle(hass, freezer)

    plan = entry.runtime_data.coordinator.data.irrigation_plan
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

    page = entry.runtime_data.diary.day(run_start.date().isoformat())
    assert page.get("seedbed_min", 0) > 0, "the pass was not recorded at all"
    assert not page.get("irrigation_mm"), "a seedbed pass was credited to the root zone"


@pytest.mark.usefixtures("weather_service", "station")
async def test_two_lawns_never_open_their_valves_at_the_same_minute(
    hass: HomeAssistant, field_data: dict[str, Any], freezer: FrozenDateTimeFactory
) -> None:
    """A controller runs one zone at a time, so the lawns queue rather than collide.

    Both halves have to queue: the deep dawn cycles, which stack backwards from sunrise, and
    the seedbed's passes, which stack forwards from their hour. The second was missed, so
    three lawns sown together would all have opened at eleven.
    """
    first = await _setup(hass, field_data)
    second = MockConfigEntry(
        domain=DOMAIN,
        data=field_data | {CONF_NAME: "North lawn", CONF_VALVE_ENTITY: VALVE},
        unique_id="north_lawn",
        title="North lawn",
    )
    second.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()

    for entry in (first, second):
        await hass.services.async_call(
            DOMAIN,
            "log_sowing",
            {"config_entry_id": entry.entry_id, "kind": "overseed"},
            blocking=True,
        )
        entry.runtime_data.diary.today().pop("irrigation_plan", None)
        await entry.runtime_data.coordinator.async_refresh()
    await _settle(hass, freezer)

    plans = [entry.runtime_data.coordinator.data.irrigation_plan for entry in (first, second)]
    runs = []
    for plan in plans:
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
