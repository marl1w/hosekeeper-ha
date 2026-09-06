"""Dawn irrigation, midday syringing and the mowing window."""

from __future__ import annotations

import datetime as dt

from custom_components.hosekeeper.engine import schedule

TZ = dt.timezone(dt.timedelta(hours=2))
SUNRISE = dt.datetime(2026, 9, 7, 6, 58, tzinfo=TZ)


def test_one_watering_the_soil_can_take_is_a_single_run() -> None:
    # 10 mm on loam is inside what an hour of infiltration allows, so it goes on in one go.
    plan = schedule.irrigation_plan(
        date=dt.date(2026, 9, 7),
        sunrise=SUNRISE,
        needed_mm=10.0,
        minutes_per_mm=4.0,
        heat_stress=False,
        forecast_tmax=28.0,
        dormant=False,
        soil_type="loam",
    )
    assert len(plan.cycles) == 1
    assert plan.main_minutes == 40
    assert plan.main_end == dt.datetime(2026, 9, 7, 6, 48, tzinfo=TZ)
    assert plan.main_start == dt.datetime(2026, 9, 7, 6, 8, tzinfo=TZ)
    assert "cycle_and_soak" not in plan.reasons
    assert plan.active_cycle(dt.datetime(2026, 9, 7, 6, 30, tzinfo=TZ)) == "main"
    assert plan.active_cycle(dt.datetime(2026, 9, 7, 7, 0, tzinfo=TZ)) is None
    assert plan.next_start(dt.datetime(2026, 9, 7, 3, 0, tzinfo=TZ)) == plan.main_start


def test_a_deep_watering_is_split_and_soaked() -> None:
    # 30 mm on loam is more than the soil takes at once: three runs of 10 mm, soaking
    # between, the last still finishing at sunrise.
    plan = schedule.irrigation_plan(
        date=dt.date(2026, 9, 7),
        sunrise=SUNRISE,
        needed_mm=30.0,
        minutes_per_mm=4.0,
        heat_stress=False,
        forecast_tmax=28.0,
        dormant=False,
        soil_type="loam",
    )
    assert len(plan.cycles) == 3
    assert plan.main_mm == 30.0
    assert plan.main_minutes == 120
    assert plan.cycles[-1].end == dt.datetime(2026, 9, 7, 6, 48, tzinfo=TZ)
    gaps = {(plan.cycles[i + 1].start - plan.cycles[i].end) for i in range(len(plan.cycles) - 1)}
    assert gaps == {schedule.SOAK}
    assert "cycle_and_soak" in plan.reasons
    assert plan.active_cycle(plan.cycles[1].start) == "main"
    assert plan.active_cycle(plan.cycles[0].end + dt.timedelta(minutes=5)) is None


def test_clay_takes_water_more_slowly_than_sand() -> None:
    def cycles(soil: str) -> int:
        return len(
            schedule.irrigation_plan(
                date=dt.date(2026, 9, 7),
                sunrise=SUNRISE,
                needed_mm=18.0,
                minutes_per_mm=4.0,
                heat_stress=False,
                forecast_tmax=25.0,
                dormant=False,
                soil_type=soil,
            ).cycles
        )

    assert cycles("sandy") == 1
    assert cycles("loam") == 2
    assert cycles("clay") == 3


def test_heat_adds_a_midday_syringing_and_the_night_has_a_floor() -> None:
    plan = schedule.irrigation_plan(
        date=dt.date(2026, 9, 7),
        sunrise=SUNRISE,
        needed_mm=30.0,
        minutes_per_mm=4.0,
        heat_stress=True,
        forecast_tmax=34.0,
        dormant=False,
    )
    assert plan.syringe_start == dt.datetime(2026, 9, 7, 13, 0, tzinfo=TZ)
    assert plan.syringe_end == dt.datetime(2026, 9, 7, 13, 6, tzinfo=TZ)
    assert plan.active_cycle(dt.datetime(2026, 9, 7, 13, 3, tzinfo=TZ)) == "syringe"
    assert schedule.IrrigationPlan.from_dict(plan.as_dict()) == plan


def test_a_refill_too_big_for_the_night_says_so() -> None:
    # 60 mm on clay would be ten runs; four fit, and the rest waits for the next dawn.
    plan = schedule.irrigation_plan(
        date=dt.date(2026, 9, 7),
        sunrise=SUNRISE,
        needed_mm=60.0,
        minutes_per_mm=6.0,
        heat_stress=False,
        forecast_tmax=25.0,
        dormant=False,
        soil_type="clay",
    )
    assert len(plan.cycles) <= schedule.MAX_CYCLES
    assert plan.cycles[0].start.time() >= schedule.EARLIEST_START
    assert "run_capped_split_tomorrow" in plan.reasons


def test_no_water_needed_means_no_main_cycle() -> None:
    plan = schedule.irrigation_plan(
        date=dt.date(2026, 9, 7),
        sunrise=SUNRISE,
        needed_mm=0.0,
        minutes_per_mm=4.0,
        heat_stress=False,
        forecast_tmax=25.0,
        dormant=False,
    )
    assert plan.main_start is None and plan.main_minutes is None
    assert plan.cycles == ()
    assert plan.next_start(SUNRISE) is None


def test_mowing_window_opens_on_dry_due_daytime() -> None:
    noon = dt.datetime(2026, 9, 7, 12, 0, tzinfo=TZ)
    ok = schedule.mowing_window(
        now=noon,
        due=True,
        rain_today_mm=0.0,
        last_rain_at=None,
        heat_stress=False,
        irrigating=False,
    )
    assert ok.open and ok.reasons == ("due_and_dry",)
    assert not schedule.mowing_window(
        now=noon,
        due=False,
        rain_today_mm=0.0,
        last_rain_at=None,
        heat_stress=False,
        irrigating=False,
    ).open
    wet = schedule.mowing_window(
        now=noon,
        due=True,
        rain_today_mm=4.0,
        last_rain_at=noon - dt.timedelta(hours=2),
        heat_stress=False,
        irrigating=False,
    )
    assert "grass_wet_after_rain" in wet.reasons
    hot = schedule.mowing_window(
        now=dt.datetime(2026, 9, 7, 14, 0, tzinfo=TZ),
        due=True,
        rain_today_mm=0.0,
        last_rain_at=None,
        heat_stress=True,
        irrigating=False,
    )
    assert "heat_of_the_day" in hot.reasons
    night = schedule.mowing_window(
        now=dt.datetime(2026, 9, 7, 21, 0, tzinfo=TZ),
        due=True,
        rain_today_mm=0.0,
        last_rain_at=None,
        heat_stress=False,
        irrigating=False,
    )
    assert "outside_daytime_window" in night.reasons


def test_a_sown_lawn_keeps_its_dawn_cycle_and_gets_the_seedbed_damp() -> None:
    plan = schedule.irrigation_plan(
        date=dt.date(2026, 9, 7),
        sunrise=SUNRISE,
        needed_mm=10.0,
        minutes_per_mm=4.0,
        heat_stress=False,
        forecast_tmax=24.0,
        dormant=False,
        soil_type="loam",
        germinating=True,
    )
    assert len(plan.cycles) == 1, "the established turf still gets its deep watering"
    assert [c.start.time() for c in plan.germination] == list(schedule.GERMINATION_TIMES)
    assert all(c.mm == schedule.GERMINATION_MM for c in plan.germination)
    assert plan.germination[-1].end.time() < dt.time(18, 0), "the leaf must dry before dark"
    assert "keep_the_seedbed_damp" in plan.reasons
    assert plan.active_cycle(dt.datetime(2026, 9, 7, 14, 2, tzinfo=TZ)) == "germination"
    assert plan.next_start(dt.datetime(2026, 9, 7, 8, 0, tzinfo=TZ)).time() == dt.time(11, 0)


def test_seedbed_passes_can_be_queued_behind_another_lawn() -> None:
    """A controller opens one valve at a time, so the lawns share a queue, not a clock.

    Three lawns all starting at eleven means the second and third get whatever pressure is
    left, or nothing at all.
    """
    day = dt.date(2026, 9, 6)
    tz = dt.timezone(dt.timedelta(hours=2))
    first = schedule.germination_cycles(day, tz, minutes_per_mm=3.0)
    second = schedule.germination_cycles(
        day, tz, minutes_per_mm=3.0, offset=dt.timedelta(minutes=6)
    )
    assert [c.start.strftime("%H:%M") for c in first] == ["11:00", "14:00", "17:00"]
    assert [c.start.strftime("%H:%M") for c in second] == ["11:06", "14:06", "17:06"]
    # Queued, not overlapping: the second lawn starts when the first one is done.
    assert second[0].start >= first[0].end
    assert [c.minutes for c in second] == [c.minutes for c in first]
