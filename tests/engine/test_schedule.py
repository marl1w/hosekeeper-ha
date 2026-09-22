"""Dawn irrigation, midday syringing and the mowing window."""

from __future__ import annotations

import datetime as dt

from custom_components.hosekeeper.engine import schedule
from custom_components.hosekeeper.engine.knowledge import programme

TZ = dt.timezone(dt.timedelta(hours=2))
WINDOW = programme.seedbed_window(dt.time(7, 20), dt.time(19, 24))
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
        seedbed_depths=[programme.STANDARD_SEEDBED.mm] * programme.STANDARD_SEEDBED.passes,
    )
    assert len(plan.cycles) == 1, "the established turf still gets its deep watering"
    assert [c.start.time() for c in plan.germination] == list(schedule.GERMINATION_TIMES)
    assert all(c.mm == schedule.GERMINATION_MM for c in plan.germination)
    assert plan.germination[-1].end.time() < dt.time(18, 0), "the leaf must dry before dark"
    assert "keep_the_seedbed_damp" in plan.reasons
    assert plan.active_cycle(dt.datetime(2026, 9, 7, 13, 2, tzinfo=TZ)) == "germination"
    assert plan.next_start(dt.datetime(2026, 9, 7, 8, 0, tzinfo=TZ)).time() == dt.time(9, 0)


def test_seedbed_passes_can_be_queued_behind_another_lawn() -> None:
    """A controller opens one valve at a time, so the lawns share a queue, not a clock.

    Three lawns all starting at eleven means the second and third get whatever pressure is
    left, or nothing at all.
    """
    day = dt.date(2026, 9, 6)
    tz = dt.timezone(dt.timedelta(hours=2))
    depths = [programme.STANDARD_SEEDBED.mm] * programme.STANDARD_SEEDBED.passes
    first = schedule.germination_cycles(day, tz, 3.0, depths=depths)
    second = schedule.germination_cycles(
        day, tz, 3.0, offset=dt.timedelta(minutes=6), depths=depths
    )
    assert [c.start.strftime("%H:%M") for c in first] == ["09:00", "13:00", "17:00"]
    assert [c.start.strftime("%H:%M") for c in second] == ["09:06", "13:06", "17:06"]
    # Queued, not overlapping: the second lawn starts when the first one is done.
    assert second[0].start >= first[0].end
    assert [c.minutes for c in second] == [c.minutes for c in first]


def test_a_settled_watering_is_decided_again_only_when_the_day_has_moved() -> None:
    """The same test the month's plan gets: a material change re-decides, drift does not.

    A figure that moves with every refresh is a figure nobody can act on, so the depth is
    settled in the morning and kept. But an afternoon of rain nobody forecast, or a forecast
    that fills up afterwards, leaves the lawn being given water it no longer needs.
    """
    assert not schedule.worth_rethinking(12.0, 10.0)  # two millimetres is drift
    assert schedule.worth_rethinking(12.0, 0.0)  # the rain came instead
    assert schedule.worth_rethinking(12.0, 8.0)  # a third of it is not drift
    # A watering cancelled earlier is taken up again if the day turns dry enough to need one.
    assert schedule.worth_rethinking(0.0, 4.0)
    assert not schedule.worth_rethinking(0.0, 2.0)


def test_a_revised_plan_says_which_way_the_day_went() -> None:
    plan = schedule.IrrigationPlan(date=dt.date(2026, 9, 8), cycles=(), reasons=("planned",))
    assert "revised_rain_since" in schedule.revised(plan, wetter=True).reasons
    assert "revised_drier_since" in schedule.revised(plan, wetter=False).reasons


def test_a_chitted_seedbed_gets_more_passes_and_lighter_ones() -> None:
    """Seed already open cannot be left to dry between two long gaps."""
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
        seedbed=programme.CHITTED_SEEDBED,
        seedbed_depths=[programme.CHITTED_SEEDBED.mm] * programme.CHITTED_SEEDBED.passes,
        seedbed_window=WINDOW,
    )
    assert [c.start.time() for c in plan.germination] == list(
        programme.seedbed_times(programme.CHITTED_SEEDBED.min_passes, WINDOW)
    )
    assert all(c.mm == programme.CHITTED_SEEDBED.mm for c in plan.germination)
    assert len(plan.germination) > programme.STANDARD_SEEDBED.min_passes
    # The leaf still has to dry before dark, and the deep cycle the surrounding turf needs
    # is untouched by any of it.
    assert plan.germination[-1].end.time() < dt.time(18, 0)
    assert plan.cycles, "the turf around the seed still has deep roots"
    assert "chitted_seed_cannot_dry" in plan.reasons
    assert "keep_the_seedbed_damp" in plan.reasons


def test_the_seedbed_a_settled_plan_gains_is_the_regime_the_day_is_on() -> None:
    """Seed goes down after the morning's plan was made; which seed it was still counts."""
    settled = schedule.irrigation_plan(
        date=dt.date(2026, 9, 7),
        sunrise=SUNRISE,
        needed_mm=10.0,
        minutes_per_mm=4.0,
        heat_stress=False,
        forecast_tmax=24.0,
        dormant=False,
        soil_type="loam",
    )
    assert not settled.germination
    sown = schedule.with_germination(
        settled,
        TZ,
        4.0,
        dt.timedelta(),
        programme.CHITTED_SEEDBED,
        [programme.CHITTED_SEEDBED.mm] * programme.CHITTED_SEEDBED.passes,
    )
    assert len(sown.germination) == programme.CHITTED_SEEDBED.passes
    assert "chitted_seed_cannot_dry" in sown.reasons
    # And the watering that was decided this morning is still exactly the one decided.
    assert sown.cycles == settled.cycles
    assert sown.main_mm == settled.main_mm


def test_a_seedbed_day_refuses_the_syringing_a_hot_forecast_offers_it() -> None:
    """The passes already cross the afternoon; a syringing would be the same water twice."""
    seedbed = schedule.irrigation_plan(
        date=dt.date(2026, 9, 7),
        sunrise=SUNRISE,
        needed_mm=10.0,
        minutes_per_mm=4.0,
        heat_stress=False,
        forecast_tmax=24.0,
        dormant=False,
        soil_type="loam",
        germinating=True,
        seedbed_whole_zone=True,
        seedbed_depths=[programme.STANDARD_SEEDBED.mm] * programme.STANDARD_SEEDBED.passes,
    )
    assert seedbed.seedbed_day and not seedbed.syringe
    assert schedule.with_syringe(seedbed, TZ, 4.0) is seedbed


def test_a_syringing_can_be_taken_back_off_a_plan_that_should_not_have_one() -> None:
    """A day that has become a seedbed keeps its passes and loses the midday run."""
    hot = schedule.irrigation_plan(
        date=dt.date(2026, 9, 7),
        sunrise=SUNRISE,
        needed_mm=10.0,
        minutes_per_mm=4.0,
        heat_stress=True,
        forecast_tmax=34.0,
        dormant=False,
        soil_type="loam",
    )
    assert hot.syringe
    cooled = schedule.without_syringe(hot)
    assert cooled.syringe is False
    assert cooled.syringe_start is None and cooled.syringe_end is None
    assert "midday_syringing_heat" not in cooled.reasons
    # Everything else the day was told to do is untouched.
    assert cooled.cycles == hot.cycles
