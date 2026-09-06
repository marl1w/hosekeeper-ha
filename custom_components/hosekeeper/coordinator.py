"""One coordinator per field: gathers weather, keeps the diary, runs the engine.

Refreshes happen every hour and whenever a linked entity changes. Between refreshes the
coordinator also does the bookkeeping only it can do — integrating solar radiation,
summing rain deltas, timing the valve, watching the mower — because those need the
moment of each change, not the state at the next hour.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
import datetime as dt
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfLength,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import CALLBACK_TYPE, Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import (
    async_track_point_in_time,
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.sun import get_astral_event_next
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import (
    DistanceConverter,
    SpeedConverter,
    TemperatureConverter,
)

from .const import DOMAIN
from .diary import DayRecord, Diary
from .engine import activity as activity_engine, agenda, assess, et, schedule
from .field import FieldConfig

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = dt.timedelta(hours=1)

# A rain sensor seen for the first time: a value this small is today's total so far from a
# daily-reset gauge and is taken as such; anything bigger is a lifetime total and only its
# future increments count.
FIRST_RAIN_AS_TODAY_MAX_MM = 200.0

# After this hour the day's solar integral is treated as complete. Before it, the
# temperature-based estimate is a floor, so a lawn is not under-watered at noon because
# only half the sun has been counted.
SOLAR_DAY_COMPLETE_HOUR = 20

# A day's measured sunshine below this share of what the temperature range implies is taken
# as a sensor problem rather than as weather.
SOLAR_PLAUSIBLE = 0.7

# And the same for an anemometer in the lee of a house. A daily mean below this is not a
# calm day, it is a sheltered instrument: real open-air daily means rarely sit under half a
# metre a second even in an anticyclone. FAO-56 says to use 2 m/s where wind data are
# missing or of doubtful quality, and that is what is used here. It is not a detail: on this
# station under test, believing 0.4 m/s understated the lawn's water use by a fifth.
WIND_PLAUSIBLE_MS = 0.5
FAO_DEFAULT_WIND_MS = 2.0

# The hours at which the mowing window can open or close on its own.
_MOWING_EDGES = (
    schedule.MOW_WINDOW[0],
    schedule.MOW_WINDOW[1],
    schedule.MOW_HEAT_PAUSE[0],
    schedule.MOW_HEAT_PAUSE[1],
    dt.time(15, 0),
)

MOWER_ACTIVE = "mowing"
MOWER_INTERRUPTED = {"paused", "error"}
VALVE_OPEN = {STATE_ON, "open", "opening"}
VALVE_CLOSED = {STATE_OFF, "closed", "closing"}


@dataclass(slots=True)
class FieldState:
    """What the engine concluded at the last refresh; every sensor reads from here."""

    day: str
    et0_mm: float
    etc_mm: float
    et_method: str
    kc: float
    tmax: float | None
    tmin: float | None
    rh_mean: float | None
    wind_ms: float | None
    rs_mj: float | None
    rain_today_mm: float
    rain_source: str
    irrigation_today_min: float
    irrigation_today_mm: float
    deficit_mm: float
    taw_mm: float
    raw_mm: float
    available_fraction: float
    root_depth_m: float
    irrigation_needed_mm: float
    irrigation_needed_min: float | None
    forecast_rain_24h_mm: float | None
    forecast_rain_3d_mm: float | None
    rain_7d_mm: float
    irrigation_7d_mm: float
    days_since_mowing: int | None
    days_since_fertilizing: int | None
    soil_moisture_pct: float | None
    status: str | None
    forecast_days: list[dict[str, Any]] = dc_field(default_factory=list)
    advice: list[dict[str, Any]] = dc_field(default_factory=list)
    plan: list[dict[str, Any]] = dc_field(default_factory=list)
    agenda: list[dict[str, Any]] = dc_field(default_factory=list)
    projection: list[dict[str, Any]] = dc_field(default_factory=list)
    """The coming days as the balance expects them, for the future half of the charts."""
    irrigation_plan: dict[str, Any] = dc_field(default_factory=dict)
    irrigation_cycle: str | None = None
    """main, germination or syringe while a cycle should be running, else None."""
    irrigation_next_start: str | None = None
    mowing_window: dict[str, Any] = dc_field(default_factory=dict)
    season_phase: str = "dormant"
    soil_temperature_c: float | None = None
    gdd: float = 0.0
    heat_stress: bool = False
    days_to_first_frost: int | None = None
    dollar_spot_probability: float | None = None
    brown_patch_index: float | None = None
    nitrogen_60d_g_m2: float = 0.0
    nitrogen_year_g_m2: float = 0.0
    forecast_rain_reliability: float | None = None
    forecast_tmax_bias: float | None = None
    dry_spell_days: int = 0
    et_anomaly: float | None = None
    irrigation_factor: float = 1.0
    feed_factor: float = 1.0
    activity: str = activity_engine.IDLE
    """What the lawn is busy with, as one value an automation can act on."""
    activity_details: dict[str, Any] = dc_field(default_factory=dict)
    logged_today: list[str] = dc_field(default_factory=list)
    """The kinds of work today's diary page already records."""

    @property
    def next_action(self) -> str | None:
        """Return the code of the most pressing advice, actions before information."""
        for item in self.advice:
            if item["priority"] <= 3:
                return item["code"]
        return self.advice[0]["code"] if self.advice else None

    def has_advice(self, *codes: str) -> bool:
        """Return whether any of the codes is in today's advice."""
        wanted = set(codes)
        return any(item["code"] in wanted for item in self.advice)

    @property
    def irrigation_needed(self) -> bool:
        """Return whether the readily available water is used up."""
        return self.irrigation_needed_mm > 0

    @property
    def irrigation_start(self) -> bool:
        """Return whether a cycle should be running right now."""
        return self.irrigation_cycle is not None

    @property
    def mowing_start(self) -> bool:
        """Return whether the mower should be out right now."""
        return bool(self.mowing_window.get("open"))


class HosekeeperCoordinator(DataUpdateCoordinator[FieldState]):
    """Keep one field's diary current and its analysis fresh."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, field: FieldConfig, diary: Diary
    ) -> None:
        """Bind to a field and its diary."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} {field.name}",
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.field = field
        self.diary = diary
        self._unsubscribe: list[CALLBACK_TYPE] = []
        self._timers: list[CALLBACK_TYPE] = []
        self._forecast_warned = False

    # ------------------------------------------------------------------ lifecycle

    async def async_setup(self) -> None:
        """Start listening to the linked entities and the turn of the day."""
        if self.field.linked_entities:
            self._unsubscribe.append(
                async_track_state_change_event(
                    self.hass, list(self.field.linked_entities), self._handle_state_change
                )
            )
        # Just past midnight, so the first refresh of the new day rolls the balance over
        # before anybody reads yesterday's numbers as today's.
        self._unsubscribe.append(
            async_track_time_change(self.hass, self._handle_midnight, hour=0, minute=0, second=30)
        )
        # The mowing window opens and closes at fixed hours, so those are clock listeners
        # registered once here rather than timers re-armed on every refresh.
        for hour in _MOWING_EDGES:
            self._unsubscribe.append(
                async_track_time_change(
                    self.hass, self._handle_edge, hour=hour.hour, minute=hour.minute, second=5
                )
            )
        # Whatever the sensors say right now is the first sample of the day.
        self._sample_observations(dt_util.now())

    async def async_shutdown(self) -> None:
        """Stop listening and flush the diary. Safe to call twice: a reload does."""
        for unsubscribe in (*self._unsubscribe, *self._timers):
            unsubscribe()
        self._unsubscribe.clear()
        self._timers.clear()
        await self.diary.async_save()
        await super().async_shutdown()

    @callback
    def _handle_midnight(self, _now: dt.datetime) -> None:
        self.hass.async_create_task(self.async_request_refresh())

    # ------------------------------------------------------------------ user actions

    async def async_log_irrigation(self, minutes: float, *, replace_today: bool = False) -> None:
        """Record irrigation for today, adding to it or setting the day's total."""
        mm = self.field.minutes_to_mm(minutes)
        today = self.diary.today()
        if replace_today:
            today["irrigation_min"] = 0.0
            today["irrigation_mm"] = 0.0
        self.diary.add_irrigation(minutes, mm, "manual")
        await self._commit()

    async def async_set_status(self, status: str) -> None:
        """Record how the lawn looks today."""
        self.diary.set_status(status)
        await self._commit()

    async def async_log_maintenance(
        self,
        kind: str,
        details: dict[str, Any] | None = None,
        *,
        at: dt.datetime | None = None,
    ) -> None:
        """Record a maintenance action, done now unless a time is given.

        A person opens the panel in the evening to record the cut they made at five, so the
        hour has to be theirs to set. It also decides which day's page the entry lands on,
        which matters either side of midnight.
        """
        self.diary.add_maintenance(kind, at=at, details=details)
        await self._commit()

    async def async_log_issue(self, issue: str) -> None:
        """Tag today with a problem seen on the lawn."""
        self.diary.add_issue(issue)
        await self._commit()

    async def _commit(self) -> None:
        await self.diary.async_save()
        await self.async_refresh()

    # ------------------------------------------------------------------ state changes

    @callback
    def _handle_state_change(self, event: Event[EventStateChangedData]) -> None:
        entity_id = event.data["entity_id"]
        new = event.data["new_state"]
        old = event.data["old_state"]
        if new is None or new.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return
        now = new.last_updated

        if entity_id == self.field.rain_sensor:
            self._accumulate_rain(new.state, new.attributes)
        elif entity_id == self.field.solar_sensor:
            self._integrate_solar(new.state, now)
        elif entity_id == self.field.valve_entity:
            self._track_valve(new.state, now)
        elif entity_id == self.field.mower_entity:
            self._track_mower(old.state if old else None, new.state, now)

        self._sample_observations(now)
        self.diary.schedule_save()
        self.hass.async_create_task(self.async_request_refresh())

    def _obs(self, now: dt.datetime | None = None) -> dict[str, Any]:
        return self.diary.day(self.diary.today_key(now)).setdefault("obs", {})

    def _sample_observations(self, now: dt.datetime) -> None:
        """Fold the current temperature, humidity and wind into today's running figures."""
        obs = self._obs(now)
        temperature = self._read_temperature_c(self.field.temperature_sensor)
        if temperature is not None:
            obs["tmax"] = max(obs.get("tmax", temperature), temperature)
            obs["tmin"] = min(obs.get("tmin", temperature), temperature)
        humidity = self._read_float(self.field.humidity_sensor)
        if humidity is not None:
            obs["rh_sum"] = obs.get("rh_sum", 0.0) + humidity
            obs["rh_n"] = obs.get("rh_n", 0) + 1
        wind = self._read_wind_ms(self.field.wind_sensor)
        if wind is not None:
            obs["wind_sum"] = obs.get("wind_sum", 0.0) + wind
            obs["wind_n"] = obs.get("wind_n", 0) + 1

    def _accumulate_rain(self, state: str, attributes: dict[str, Any]) -> None:
        value = _to_float(state)
        if value is None:
            return
        unit = attributes.get("unit_of_measurement")
        if unit and unit != UnitOfLength.MILLIMETERS:
            try:
                value = DistanceConverter.convert(value, unit, UnitOfLength.MILLIMETERS)
            except (ValueError, TypeError):
                return
        today = self.diary.today()
        obs = today.setdefault("obs", {})
        last = obs.get("rain_last")
        if last is None:
            # Might be yesterday's carry-over in `obs` from a daily gauge that reset while
            # nobody was listening; the earlier day's record keeps its own `rain_last`.
            previous = self._previous_rain_last()
            if previous is not None and value >= previous:
                delta = value - previous
            elif value <= FIRST_RAIN_AS_TODAY_MAX_MM:
                delta = value
            else:
                delta = 0.0
        elif value >= last:
            delta = value - last
        else:
            # The gauge reset — midnight on a daily total, or a replaced sensor.
            delta = value
        obs["rain_last"] = value
        if delta > 0:
            obs["rain_last_at"] = dt_util.now().isoformat()
        today["rain_mm"] = today.get("rain_mm", 0.0) + delta
        today["rain_source"] = "sensor"

    def _previous_rain_last(self) -> float | None:
        yesterday = (dt_util.now().date() - dt.timedelta(days=1)).isoformat()
        return self.diary.days.get(yesterday, {}).get("obs", {}).get("rain_last")

    def _integrate_solar(self, state: str, now: dt.datetime) -> None:
        watts = _to_float(state)
        if watts is None:
            return
        obs = self._obs(now)
        last_ts = dt_util.parse_datetime(obs.get("rs_last_ts", "") or "")
        last_w = obs.get("rs_last_w")
        if last_ts is not None and last_w is not None and last_ts.date() == now.date():
            seconds = (now - last_ts).total_seconds()
            if 0 < seconds < 3 * 3600:
                # Trapezoid in W·s, then to MJ.
                obs["rs_mj"] = obs.get("rs_mj", 0.0) + (last_w + watts) / 2.0 * seconds / 1e6
        obs["rs_last_ts"] = now.isoformat()
        obs["rs_last_w"] = watts

    def _track_valve(self, state: str, now: dt.datetime) -> None:
        obs = self._obs(now)
        if state in VALVE_OPEN:
            obs.setdefault("valve_on_since", now.isoformat())
            return
        if state not in VALVE_CLOSED:
            return
        since = dt_util.parse_datetime(obs.pop("valve_on_since", "") or "")
        if since is None:
            # Opened yesterday, closed today: the run straddled midnight.
            yesterday = self.diary.days.get((now.date() - dt.timedelta(days=1)).isoformat(), {})
            since = dt_util.parse_datetime(yesterday.get("obs", {}).pop("valve_on_since", "") or "")
        if since is None:
            return
        minutes = max(0.0, (now - since).total_seconds() / 60.0)
        if minutes <= 0:
            return
        mm = self.field.minutes_to_mm(minutes)
        # Which cycle the valve was serving decides which book the run goes in. A seedbed
        # pass and a midday syringing wet the surface and are kept out of the balance, the
        # same way the projection keeps them out; crediting them would tell the balance the
        # root zone was filled and cancel the dawn cycle the turf still needs.
        if self._surface_cycle(since, now):
            self.diary.add_surface_water(minutes, mm, "valve")
        else:
            self.diary.add_irrigation(minutes, mm, "valve")

    def _surface_cycle(self, started: dt.datetime, ended: dt.datetime) -> bool:
        """Return whether a valve run belonged to a seedbed pass or a midday syringing.

        A plan is made for the coming dawn and filed on the page of the day it was decided,
        so the plan covering a run is on that day's page or on the one before it. Looking
        only at the run's own page found tomorrow's plan and matched nothing.
        """
        wanted = started.date().isoformat()
        for offset in (0, 1):
            page = self.diary.day((started.date() - dt.timedelta(days=offset)).isoformat())
            stored = page.get("irrigation_plan")
            if not stored or stored.get("date") != wanted:
                continue
            try:
                plan = schedule.IrrigationPlan.from_dict(stored)
            except (KeyError, TypeError, ValueError):
                return False
            # The middle of the run, so a valve opened a moment early is still judged by the
            # cycle it actually served.
            middle = started + (ended - started) / 2
            return plan.active_cycle(middle) in ("germination", "syringe")
        return False

    def _track_mower(self, old: str | None, new: str, now: dt.datetime) -> None:
        obs = self._obs(now)
        if new == MOWER_ACTIVE:
            obs.setdefault("mow_since", now.isoformat())
            return
        if old != MOWER_ACTIVE or new in MOWER_INTERRUPTED:
            # Paused mowers resume; errors get fixed and resume. Neither ends the session.
            return
        since = dt_util.parse_datetime(obs.pop("mow_since", "") or "")
        minutes = (now - since).total_seconds() / 60.0 if since else None
        details: dict[str, Any] = {}
        if minutes is not None:
            details["duration_min"] = round(minutes, 1)
        self.diary.add_maintenance("mowing", at=now, source="mower", details=details)

    # ------------------------------------------------------------------ reading sensors

    def _read_float(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        return None if state is None else _to_float(state.state)

    def _read_temperature_c(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        value = None if state is None else _to_float(state.state)
        if value is None:
            return None
        unit = state.attributes.get("unit_of_measurement", UnitOfTemperature.CELSIUS)
        if unit == UnitOfTemperature.CELSIUS:
            return value
        try:
            return TemperatureConverter.convert(value, unit, UnitOfTemperature.CELSIUS)
        except (ValueError, TypeError):
            return None

    def _read_wind_ms(self, entity_id: str | None) -> float | None:
        # Taken as measured at 2 m. Consumer stations sit at garden or roof height, and
        # without knowing which, the profile correction (eq. 47) would be a guess in one
        # direction; the error either way is a few percent of ET.
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        value = None if state is None else _to_float(state.state)
        if value is None:
            return None
        return _speed_to_ms(value, state.attributes.get("unit_of_measurement"))

    # ------------------------------------------------------------------ the refresh

    async def _async_update_data(self) -> FieldState:
        now = dt_util.now()
        today_key = self.diary.today_key(now)
        today = self.diary.day(today_key)
        obs = today.setdefault("obs", {})

        forecast = await self._async_forecast()
        forecast_today = _forecast_for(forecast, now.date())
        forecast_tomorrow = _forecast_for(forecast, now.date() + dt.timedelta(days=1))
        # Tomorrow's forecast is kept on tomorrow's page until tomorrow arrives; from then on
        # it is the record of what was promised the day before, to be judged against the day.
        if forecast_tomorrow is not None:
            self.diary.day(self.diary.today_key(now + dt.timedelta(days=1)))["fc"] = {
                "tmax": _to_float(forecast_tomorrow.get("temperature")),
                "tmin": _to_float(forecast_tomorrow.get("templow")),
                "rain": _to_float(forecast_tomorrow.get("precipitation")),
            }

        # Rain: a gauge when there is one; the forecast's estimate for today otherwise.
        if today.get("rain_source") != "sensor":
            if forecast_today and forecast_today.get("precipitation") is not None:
                today["rain_mm"] = float(forecast_today["precipitation"])
                today["rain_source"] = "forecast"
            else:
                today.setdefault("rain_mm", 0.0)
                today.setdefault("rain_source", "none")

        weather_day = self._weather_day(obs, forecast_today, now)

        # Everything the lawn amounts to today is worked out by the engine, from the lawn's
        # description and its diary. The coordinator's job is the parts only Home Assistant
        # can do: reading the sensors above, and publishing the answer below.
        lawn = assess.Lawn(
            name=self.field.name,
            latitude=self.field.latitude,
            soil_type=self.field.soil_type,
            grass_type=self.field.grass_type,
            establishment_method=self.field.establishment_method,
            establishment_date=self.field.establishment_date,
            application_rate_mm_h=self.field.application_rate_mm_h,
            shaded_fraction=self.field.shaded_fraction,
            tree_fraction=self.field.tree_fraction,
            deciduous_trees=self.field.has_deciduous_trees,
            robot_mower=self.field.mower_entity is not None,
            elevation_m=float(self.hass.config.elevation or 0),
        )
        ahead = [
            agenda.DayForecast(
                dt_util.as_local(dt_util.parse_datetime(str(item.get("datetime", "")))).date(),
                _to_float(item.get("temperature")),
                _to_float(item.get("templow")),
                _to_float(item.get("precipitation")),
            )
            for item in forecast
            if dt_util.parse_datetime(str(item.get("datetime", ""))) is not None
        ]
        result = assess.assess(
            lawn,
            self.diary.days,
            today=now.date(),
            weather=weather_day,
            forecast=ahead,
            adaptation_state=self.diary.adaptation,
            plan_state=self.diary.plan,
            radiation_estimated=bool(obs.get("rs_used_estimate")),
            soil_moisture_pct=self._read_float(self.field.soil_moisture_sensor),
        )
        self.diary.schedule_save()

        soil, deficit, needed_mm = result.soil, result.deficit_mm, result.needed_mm
        window = self.diary.recent(7, until=now.date())
        irrigation = self._irrigation_plan(now, today, needed_mm, result)
        self._arm_timers(now, irrigation)
        mowing = schedule.mowing_window(
            now=now,
            due=result.mowing_due,
            rain_today_mm=today.get("rain_mm", 0.0),
            last_rain_at=dt_util.parse_datetime(obs.get("rain_last_at", "") or ""),
            heat_stress=result.phenology.heat_stress,
            irrigating=irrigation.active_cycle(now) is not None,
        )

        # What the day already records, so a job waiting for a person ends when it is done.
        logged = {item.get("type") for item in today.get("maintenance", []) if item.get("type")}
        if today.get("irrigation_mm"):
            logged.add("irrigation")
        doing = activity_engine.current(
            zone=self.field.name,
            entry_id=self.config_entry.entry_id if self.config_entry else None,
            now_iso=now.isoformat(),
            advice=[a.as_dict() for a in result.advice],
            irrigation_cycle=irrigation.active_cycle(now),
            irrigation_plan=irrigation.as_dict(),
            mowing_open=mowing.open,
            mowing_window=mowing.as_dict(),
            mowing_ends=dt.datetime.combine(
                now.date(), schedule.MOW_WINDOW[1], tzinfo=now.tzinfo
            ).isoformat(),
            mow_height_mm=next(
                (
                    a.params.get("height_mm")
                    for a in result.advice
                    if a.category == "mowing" and a.params.get("height_mm")
                ),
                None,
            ),
            logged_today=logged,
            has_valve=self.field.valve_entity is not None,
            has_robot=self.field.mower_entity is not None,
            valve_entity=self.field.valve_entity,
            mower_entity=self.field.mower_entity,
        )

        return FieldState(
            day=today_key,
            et0_mm=round(result.et0_mm, 2),
            etc_mm=round(result.etc_mm, 2),
            et_method=result.et_method,
            kc=round(result.kc, 3),
            tmax=weather_day.tmax if weather_day else None,
            tmin=weather_day.tmin if weather_day else None,
            rh_mean=weather_day.rh_mean if weather_day else None,
            wind_ms=weather_day.wind_2m_ms if weather_day else None,
            rs_mj=weather_day.rs_mj if weather_day else None,
            rain_today_mm=round(today.get("rain_mm", 0.0), 1),
            rain_source=today.get("rain_source", "none"),
            irrigation_today_min=round(today.get("irrigation_min", 0.0), 1),
            irrigation_today_mm=round(today.get("irrigation_mm", 0.0), 1),
            deficit_mm=round(deficit, 1),
            taw_mm=round(soil.taw_mm, 1),
            raw_mm=round(soil.raw_mm, 1),
            root_depth_m=result.root_depth_m,
            available_fraction=soil.available_fraction(deficit),
            irrigation_needed_mm=round(needed_mm, 1),
            irrigation_needed_min=_round_or_none(self.field.mm_to_minutes(needed_mm)),
            forecast_rain_24h_mm=result.forecast_rain_24h_mm,
            forecast_rain_3d_mm=result.forecast_rain_72h_mm,
            rain_7d_mm=round(sum(day.get("rain_mm", 0.0) for _, day in window), 1),
            irrigation_7d_mm=round(sum(day.get("irrigation_mm", 0.0) for _, day in window), 1),
            days_since_mowing=result.context.days_since_mowing,
            days_since_fertilizing=result.context.days_since_fertilizing,
            soil_moisture_pct=result.context.soil_moisture_pct,
            status=today.get("status") or self.diary.last_status(),
            forecast_days=forecast,
            advice=[a.as_dict() for a in result.advice],
            plan=assess.status_of(result.operations, self.diary.days, now.date()),
            agenda=[item.as_dict() for item in result.agenda],
            projection=[day.as_dict() for day in result.projection],
            irrigation_plan=irrigation.as_dict(),
            irrigation_cycle=irrigation.active_cycle(now),
            irrigation_next_start=(
                None
                if irrigation.next_start(now) is None
                else irrigation.next_start(now).isoformat()
            ),
            mowing_window=mowing.as_dict(),
            season_phase=result.phenology.phase,
            soil_temperature_c=result.phenology.soil_temperature_c,
            gdd=result.phenology.gdd_base0,
            heat_stress=result.phenology.heat_stress,
            days_to_first_frost=result.phenology.days_to_first_frost,
            dollar_spot_probability=result.dollar_spot,
            brown_patch_index=result.brown_patch,
            nitrogen_60d_g_m2=result.nitrogen_60d,
            nitrogen_year_g_m2=result.nitrogen_year,
            forecast_rain_reliability=(
                result.skill.rain_hit_rate if result.skill.trusted else None
            ),
            forecast_tmax_bias=result.skill.tmax_bias if result.skill.trusted else None,
            dry_spell_days=result.anomalies.dry_spell_days,
            et_anomaly=result.anomalies.et_anomaly,
            irrigation_factor=result.irrigation_factor,
            feed_factor=result.feed_factor,
            activity=doing.state,
            activity_details=doing.details,
            logged_today=sorted(logged),
        )

    # ------------------------------------------------------------------ the day's timing

    def _irrigation_plan(
        self, now: dt.datetime, today: DayRecord, needed_mm: float, result: assess.Assessment
    ) -> schedule.IrrigationPlan:
        """Return the irrigation plan for the next dawn, decided once and kept for the day.

        The decision is taken the first time the coordinator runs after midnight, so the
        night's balance is what it sees; a heavy rain later in the night cancels a main
        cycle that has not started. Otherwise the plan stands, however the numbers drift.
        """
        sunrise = dt_util.as_local(get_astral_event_next(self.hass, "sunrise", now))
        target_date = sunrise.date()
        stored = today.get("irrigation_plan")
        if stored and stored.get("date") == target_date.isoformat():
            current = schedule.IrrigationPlan.from_dict(stored)
            rained = today.get("rain_mm", 0.0) >= 5.0
            if rained and current.main_start and now < current.main_start and current.main_mm > 0:
                cancelled = schedule.IrrigationPlan(
                    date=current.date,
                    main_mm=0.0,
                    main_minutes=None,
                    main_start=None,
                    main_end=None,
                    syringe=current.syringe,
                    syringe_start=current.syringe_start,
                    syringe_end=current.syringe_end,
                    reasons=(*current.reasons, "cancelled_rain_fell"),
                )
                today["irrigation_plan"] = cancelled.as_dict()
                return cancelled
            return current
        rate = self.field.application_rate_mm_h
        # One valve at a time: the cycles of the fields chain back to back before sunrise.
        # Whoever plans first gets the slot that ends at sunrise; the next ends where that
        # one starts. The chain is kept per dawn in hass.data.
        chain_end = self._chain_end(target_date, sunrise - schedule.DAWN_BUFFER)
        fresh = schedule.irrigation_plan(
            date=target_date,
            sunrise=chain_end + schedule.DAWN_BUFFER,
            needed_mm=needed_mm,
            minutes_per_mm=(60.0 / rate) if rate else None,
            heat_stress=result.phenology.heat_stress,
            forecast_tmax=_max_of(
                *(
                    _to_float(f.get("temperature"))
                    for f in (
                        _forecast_for(self.data.forecast_days if self.data else [], target_date),
                    )
                    if f
                )
            ),
            dormant=result.phenology.phase == "dormant",
            soil_type=self.field.soil_type,
            germinating=result.germinating,
            # The seedbed's passes are on the same valve as everything else, so they queue
            # the same way: this lawn starts where the lawns already booked into the slot
            # finish. Three lawns all starting at eleven means the second and third get
            # whatever pressure is left.
            germination_offset=self._germination_offset(target_date),
        )
        today["irrigation_plan"] = fresh.as_dict()
        self._chain_register(
            target_date,
            fresh.main_start,
            fresh.main_end,
            germination_minutes=(fresh.germination[0].minutes if fresh.germination else 0),
        )
        return fresh

    def _chain(self) -> dict[str, dict[str, dict[str, Any]]]:
        """Return who has booked what, by date and config entry.

        A controller opens one valve at a time, so the lawns share a queue rather than a
        clock. The dawn cycles stack backwards from sunrise; the seedbed passes stack
        forwards from their hour.
        """
        return self.hass.data.setdefault(DOMAIN, {}).setdefault("dawn_chain", {})

    def _chain_end(self, date: dt.date, latest_end: dt.datetime) -> dt.datetime:
        """Return when this field's cycle must end: before every other field's planned start."""
        entry = self.config_entry
        assert entry is not None
        slots = self._chain().get(date.isoformat(), {})
        starts = [
            dt.datetime.fromisoformat(slot["start"])
            for entry_id, slot in slots.items()
            if entry_id != entry.entry_id and slot.get("start")
        ]
        return min([latest_end, *starts]) if starts else latest_end

    def _germination_offset(self, date: dt.date) -> dt.timedelta:
        """Return how long this lawn waits before its seedbed passes: the queue ahead of it."""
        entry = self.config_entry
        assert entry is not None
        slots = self._chain().get(date.isoformat(), {})
        ahead = sum(
            int(slot.get("germination_minutes") or 0)
            for entry_id, slot in slots.items()
            if entry_id != entry.entry_id
        )
        return dt.timedelta(minutes=ahead)

    def _chain_register(
        self,
        date: dt.date,
        start: dt.datetime | None,
        end: dt.datetime | None,
        *,
        germination_minutes: int = 0,
    ) -> None:
        entry = self.config_entry
        assert entry is not None
        chain = self._chain()
        chain[date.isoformat()] = {
            **chain.get(date.isoformat(), {}),
            entry.entry_id: {
                "start": start.isoformat() if start else None,
                "end": end.isoformat() if end else None,
                "germination_minutes": germination_minutes,
            },
        }
        # Yesterday's chain is history.
        for key in [k for k in chain if k < (date - dt.timedelta(days=1)).isoformat()]:
            chain.pop(key, None)

    def _arm_timers(self, now: dt.datetime, irrigation: schedule.IrrigationPlan) -> None:
        """Refresh exactly when a cycle starts or ends, so the start sensors flip on time."""
        for cancel in self._timers:
            cancel()
        self._timers.clear()
        edges = [
            irrigation.main_start,
            irrigation.main_end,
            irrigation.syringe_start if irrigation.syringe else None,
            irrigation.syringe_end if irrigation.syringe else None,
        ]
        for edge in edges:
            if edge is not None and edge > now:
                self._timers.append(
                    async_track_point_in_time(
                        self.hass, self._handle_edge, edge + dt.timedelta(seconds=1)
                    )
                )

    @callback
    def _handle_edge(self, _now: dt.datetime) -> None:
        self.hass.async_create_task(self.async_request_refresh())

    # ------------------------------------------------------------------ the analysis

    def _weather_day(
        self, obs: dict[str, Any], forecast_today: dict[str, Any] | None, now: dt.datetime
    ) -> et.WeatherDay | None:
        """Combine what was measured so far today with what the forecast says the day holds.

        A station on the lawn outranks a forecast for the same place, so the forecast is only
        ever used to fill a gap or to anticipate the part of the day that has not happened
        yet. Once the day is over, what the station recorded is the day, even if the forecast
        disagrees — otherwise a model that called 40 °C would set the water use for a day the
        lawn actually spent at 36.
        """
        measured = self._has_station
        day_over = now.hour >= SOLAR_DAY_COMPLETE_HOUR
        fc_high = _to_float(forecast_today.get("temperature")) if forecast_today else None
        fc_low = _to_float(forecast_today.get("templow")) if forecast_today else None
        if measured and day_over:
            fc_high = fc_low = None
        tmax = _max_of(obs.get("tmax"), fc_high)
        tmin = _min_of(obs.get("tmin"), fc_low)
        if tmax is None or tmin is None:
            return None

        rh = obs["rh_sum"] / obs["rh_n"] if obs.get("rh_n") else None
        if rh is None and forecast_today and not measured:
            rh = _to_float(forecast_today.get("humidity"))

        wind = obs["wind_sum"] / obs["wind_n"] if obs.get("wind_n") else None
        if (
            wind is None
            and not measured
            and forecast_today
            and forecast_today.get("wind_speed") is not None
        ):
            unit = self._weather_attr("wind_speed_unit") or UnitOfSpeed.KILOMETERS_PER_HOUR
            wind = _speed_to_ms(float(forecast_today["wind_speed"]), unit)

        ra = et.extraterrestrial_radiation(self.field.latitude, now.timetuple().tm_yday)
        estimate = et.solar_radiation_from_temperature(tmax, tmin, ra)
        measured = obs.get("rs_mj")
        obs["rs_used_estimate"] = False
        # A pyranometer in the shade of the house, or under dust, reads low all day and
        # every day, and nothing about the number says so. Compared with what the day's
        # temperature range implies, a reading far below it is not weather but siting — and
        # believing it would halve the water the lawn is told it needs.
        shaded = measured is not None and estimate > 0 and measured < SOLAR_PLAUSIBLE * estimate
        obs["rs_looks_shaded"] = bool(shaded)
        if shaded:
            rs: float | None = estimate
            obs["rs_used_estimate"] = True
        elif measured is not None and now.hour >= SOLAR_DAY_COMPLETE_HOUR:
            rs = measured
        elif measured is not None:
            rs = max(measured, estimate)
            obs["rs_used_estimate"] = rs == estimate
        elif rh is not None and wind is not None:
            rs = estimate
            obs["rs_used_estimate"] = True
        else:
            rs = None
        return et.WeatherDay(tmax=tmax, tmin=tmin, rh_mean=rh, wind_2m_ms=wind, rs_mj=rs)

    @property
    def _has_station(self) -> bool:
        """Return whether this field is measured on the ground rather than forecast."""
        return bool(self.field.temperature_sensor)

    def _weather_attr(self, name: str) -> Any:
        state = self.hass.states.get(self.field.weather_entity)
        return None if state is None else state.attributes.get(name)

    async def _async_forecast(self) -> list[dict[str, Any]]:
        if not self.hass.services.has_service("weather", "get_forecasts"):
            return []
        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": self.field.weather_entity, "type": "daily"},
                blocking=True,
                return_response=True,
            )
        # A forecast outage must not stop the balance; whatever the service raised is logged once.
        except Exception as err:
            if not self._forecast_warned:
                _LOGGER.warning("Forecast from %s unavailable: %s", self.field.weather_entity, err)
                self._forecast_warned = True
            return []
        self._forecast_warned = False
        if not isinstance(response, dict):
            return []
        entry = response.get(self.field.weather_entity) or {}
        forecast = entry.get("forecast") if isinstance(entry, dict) else None
        return list(forecast) if isinstance(forecast, list) else []

    def _days_since(self, kind: str, now: dt.datetime) -> int | None:
        last = self.diary.last_maintenance(kind)
        if last is None:
            return None
        return max(0, (now.date() - dt_util.as_local(last).date()).days)


# ---------------------------------------------------------------------- helpers


def _to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_or_none(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def _max_of(*values: float | None) -> float | None:
    present = [v for v in values if v is not None]
    return max(present) if present else None


def _min_of(*values: float | None) -> float | None:
    present = [v for v in values if v is not None]
    return min(present) if present else None


def _speed_to_ms(value: float, unit: str | None) -> float | None:
    if unit in (None, UnitOfSpeed.METERS_PER_SECOND):
        return value
    try:
        return SpeedConverter.convert(value, unit, UnitOfSpeed.METERS_PER_SECOND)
    except (ValueError, TypeError):
        return None


def _forecast_for(forecast: list[dict[str, Any]], date: dt.date) -> dict[str, Any] | None:
    for item in forecast:
        when = dt_util.parse_datetime(str(item.get("datetime", "")))
        if when is not None and dt_util.as_local(when).date() == date:
            return item
    return None


def _sum_precipitation(items: list[dict[str, Any] | None]) -> float | None:
    values = [_to_float(item.get("precipitation")) for item in items if item]
    present = [v for v in values if v is not None]
    return round(sum(present), 1) if present else None


def day_record_for(diary: Diary, key: str) -> DayRecord:
    """Return the record for a day; here so platforms need not know the diary's shape."""
    return diary.day(key)
