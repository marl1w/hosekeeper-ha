"""The N-P-K class follows the lawn and the weather, not only the calendar."""

from __future__ import annotations

import datetime as dt

from custom_components.hosekeeper.engine import nutrition, plan
from custom_components.hosekeeper.engine.knowledge import programme
from tests.engine.test_rules import _ctx

FEEDS = {w.code: w for w in programme.COOL_SEASON_FEEDS}
MARCH = FEEDS["feed_march_starter"]
APRIL = FEEDS["feed_april_greening"]
JUNE = FEEDS["feed_june_summer"]
OCTOBER = FEEDS["feed_october_autumn"]
NOVEMBER = FEEDS["feed_november_autumn"]


def test_october_feed_is_potassium_led_autumn_k() -> None:
    feed = nutrition.plan(_ctx(), OCTOBER)
    assert feed.role == "autumn"
    assert feed.ratio == (1, 0, 1)
    assert feed.n_g_m2 == 5.0  # 5.5 asked, capped at the 5 g ceiling per pass
    assert feed.preset == "bottos_autumn_k"
    assert feed.dose_g_m2 == 25  # 5 g N at 21 % is 23.8 g, lifted to the label floor
    assert not feed.split


def test_april_greening_is_dark_green() -> None:
    feed = nutrition.plan(_ctx(today=dt.date(2026, 4, 10)), APRIL)
    assert feed.role == "greening"
    assert feed.ratio == (1, 0, 0)
    assert feed.preset == "bottos_dark_green"
    assert feed.dose_g_m2 == 30  # 3.3 g N at 11 %


def test_june_feed_is_summer_k() -> None:
    feed = nutrition.plan(_ctx(), JUNE)
    assert feed.role == "stress"
    assert feed.preset == "bottos_summer_k"
    assert feed.dose_g_m2 == 35  # 3.5 g N at 10 %


def test_heat_ahead_turns_a_greening_feed_into_potassium() -> None:
    feed = nutrition.plan(_ctx(forecast_tmax_3d=31.0), APRIL)
    assert feed.role == "stress"
    assert feed.ratio == (2, 1, 3)
    assert feed.n_g_m2 == 2.5
    assert feed.slow_fraction_min == 0.5
    assert feed.preset == "bottos_summer_k"  # fully coated: the slow-release requirement picks it
    assert "heat_ahead_potassium_slow_nitrogen" in feed.reasons


def test_a_lawn_still_establishing_gets_a_starter() -> None:
    # Seven weeks old: still building roots, so phosphorus rather than a greening feed.
    feed = nutrition.plan(_ctx(establishment_age_days=50), APRIL)
    assert feed.role == "starter"
    assert feed.ratio == (1, 2, 1)
    assert feed.preset == "bottos_pro_start"


def test_disease_cuts_nitrogen_and_sandy_soil_splits_it() -> None:
    feed = nutrition.plan(_ctx(issues_30d={"fungus"}, soil_type="sandy"), APRIL)
    assert feed.n_g_m2 == 2.3
    assert feed.split
    assert feed.slow_fraction_min == 0.5
    assert {"disease_less_nitrogen", "sandy_soil_split_slow"} <= set(feed.reasons)


def test_declining_lawn_in_season_gets_more() -> None:
    feed = nutrition.plan(_ctx(statuses_14d=["poor", "fair", "poor"]), APRIL)
    assert feed.n_g_m2 == 4.0  # 3.3 * 1.2
    assert "lawn_declining_more_nitrogen" in feed.reasons


def test_november_is_potassium_for_hardiness() -> None:
    feed = nutrition.plan(_ctx(), NOVEMBER)
    assert feed.role == "autumn"
    assert "autumn_potassium_hardiness" in feed.reasons


def test_plan_follows_the_professional_calendar() -> None:
    ctx = _ctx(issues_30d={"bare_spots"})
    ops = plan.build(ctx)
    by_month: dict[str, list[str]] = {}
    for op in ops:
        by_month.setdefault(op.month, []).append(op.code)
    # Every growing month carries its mowing, so the plan never reads as though the grass
    # stopped growing between the milestones.
    assert by_month["2026-09"] == ["mow_routine", "overseed", "aeration_autumn"]
    assert by_month["2026-10"] == [
        "mow_routine",
        "weed_control_broadleaf",
        "feed_october_autumn",
        "top_dressing",
    ]
    assert by_month["2026-11"] == ["feed_november_autumn", "last_mow_lower"]
    assert by_month["2027-03"] == ["feed_march_starter", "pre_emergent", "first_mow"]
    assert by_month["2027-04"] == [
        "mow_routine",
        "feed_april_greening",
    ]  # spring aeration only with compaction
    assert by_month["2027-05"] == [
        "weed_control_broadleaf",
        "feed_may_greening",
        "raise_mowing_height",
    ]
    assert by_month["2027-07"] == [
        "mow_routine",
        "feed_july_summer",
        "weed_control_grassy",
        "summer_watch",
    ]
    assert by_month["2027-08"] == ["mow_routine", "summer_rest", "prepare_overseeding"]
    # No month has two mowing lines: the milestone months carry their own.
    for month, codes in by_month.items():
        mowing = [c for c in codes if c.startswith(("mow_", "first_mow", "last_mow", "raise_"))]
        assert len(mowing) <= 1, f"{month} has {mowing}"
    assert "moss_control" not in by_month.get("2027-02", [])

    overseed = next(op for op in ops if op.code == "overseed")
    assert not overseed.optional
    assert "bare_or_thin_areas_seen" in overseed.tailoring
    assert overseed.params["starter_feed"]["npk_class"] == "1-2-1"
    assert "pro_programme_september_overseed" in overseed.basis
    october = next(op for op in ops if op.code == "feed_october_autumn")
    assert october.params["npk_class"] == "1-0-1"
    assert "research_late_autumn_potassium_hardiness" in october.basis


def test_dense_weed_free_lawn_makes_the_optional_passes_optional() -> None:
    ops = plan.build(_ctx(statuses_14d=["excellent"] * 5))
    overseed = next(op for op in ops if op.code == "overseed")
    assert overseed.optional
    weeds = next(op for op in ops if op.code == "weed_control_broadleaf")
    assert weeds.optional


def test_plan_status_comes_from_the_diary() -> None:
    ctx = _ctx()
    ops = plan.build(ctx)
    october = next(op for op in ops if op.code == "feed_october_autumn")
    assert plan.status_of(october, ctx.today, {}) == "upcoming"
    assert plan.status_of(october, dt.date(2026, 10, 3), {}) == "open"
    assert plan.status_of(october, dt.date(2026, 10, 3), {"2026-10": {"fertilizing"}}) == "done"
    assert plan.status_of(october, dt.date(2026, 11, 3), {}) == "missed"
    aeration = next(op for op in ops if op.code == "aeration_autumn")
    assert plan.status_of(aeration, dt.date(2026, 10, 3), {}) == "skipped"


def test_missed_feed_is_carried_into_a_free_month() -> None:
    ops = plan.build(_ctx())
    # November's feed was missed and December has none of its own.
    carried = plan.carry_over(ops, dt.date(2026, 12, 3), {})
    assert carried is not None
    assert carried.code == "feed_november_autumn" and carried.month == "2026-12"
    assert "carried_over_from_last_month" in carried.tailoring
    # November has its own feed, so October's miss is not carried there.
    assert plan.carry_over(ops, dt.date(2026, 11, 3), {}) is None


def test_the_autumn_feed_is_never_turned_into_a_starter() -> None:
    # Sod laid four months ago and overseeded five weeks ago: October is still the autumn
    # potassium feed, because winter hardiness is what the plant is short of.
    october = nutrition.plan(
        _ctx(establishment_age_days=120, days_since_sowing=35), FEEDS["feed_october_autumn"]
    )
    assert october.role == "autumn"
    assert october.preset == "bottos_autumn_k"

    # Even in the establishing window, autumn stays autumn.
    fresh = nutrition.plan(
        _ctx(establishment_age_days=40, days_since_sowing=5), FEEDS["feed_october_autumn"]
    )
    assert fresh.role == "autumn"

    # While a spring feed on a lawn that age does become a starter.
    spring = nutrition.plan(_ctx(establishment_age_days=40), FEEDS["feed_april_greening"])
    assert spring.role == "starter"

    # And a lawn four months old is past the establishing window.
    grown = nutrition.plan(_ctx(establishment_age_days=120), FEEDS["feed_april_greening"])
    assert grown.role == "greening"


def _codes(ctx, month: str) -> list[str]:
    return [op.code for op in plan.build(ctx) if op.month == month]


def test_a_robot_is_asked_for_frequency_not_for_a_hard_cut() -> None:
    """A robot takes a few millimetres at a time, so it keeps up by going out often.

    Often, but not every day by default: a pass has the lawn occupied for hours and goes over
    the same ground, and half the growth the third rule allows keeps the clippings short
    without that. Whoever wants the machine's own schedule asks for it.
    """
    ctx = _ctx(robot_mower=True)
    autumn = next(op for op in plan.build(ctx) if op.month == "2026-10" and op.category == "mowing")
    assert autumn.code == "mow_routine_robot"
    assert autumn.params["interval_days"] == 3
    summer = next(op for op in plan.build(ctx) if op.month == "2027-07" and op.category == "mowing")
    assert summer.code == "mow_routine_robot"
    assert summer.params["interval_days"] == 6  # half of eleven days at 90 mm in the heat
    assert summer.params["height_mm"] == 90  # the top of the range through the heat


def test_the_manufacturer_s_daily_schedule_is_still_there_for_whoever_wants_it() -> None:
    ctx = _ctx(robot_mower=True, robot_cadence="frequent")
    autumn = next(op for op in plan.build(ctx) if op.month == "2026-10" and op.category == "mowing")
    assert autumn.code == "mow_routine_robot_daily"
    assert autumn.params["interval_days"] == 1


def test_the_gentlest_cadence_is_the_most_the_third_rule_allows() -> None:
    """Least disturbance: the robot goes out no oftener than a hand mower would."""
    ctx = _ctx(robot_mower=True, robot_cadence="gentle")
    autumn = next(op for op in plan.build(ctx) if op.month == "2026-10" and op.category == "mowing")
    by_hand = next(
        op
        for op in plan.build(_ctx(robot_mower=False))
        if op.month == "2026-10" and op.category == "mowing"
    )
    assert autumn.params["interval_days"] == by_hand.params["interval_days"]


def test_a_push_mower_keeps_the_third_rule() -> None:
    autumn = next(
        op for op in plan.build(_ctx()) if op.month == "2026-10" and op.category == "mowing"
    )
    assert autumn.code == "mow_routine"
    assert autumn.params["interval_days"] == 6


def test_the_herbicide_waits_for_the_seedlings_then_comes_back() -> None:
    """The wait runs from the sowing, not from the lawn's birthday.

    A lawn overseeded at the start of September is sprayable by the middle of October,
    which is exactly what the professional calendar does. Blocking it for the whole first
    year, as the plan used to, silently dropped an operation the gardener performs.
    """
    week_old = _ctx(days_since_sowing=7, establishment_age_days=92)
    assert "weed_control_broadleaf" not in _codes(week_old, "2026-09")
    assert "weed_control_broadleaf" in _codes(week_old, "2026-10")
    october = next(op for op in plan.build(week_old) if op.code == "weed_control_broadleaf")
    assert "young_grass_spot_treat" in october.tailoring


def test_turf_still_rooting_in_gets_no_herbicide() -> None:
    """Sod is mature grass, so it waits only to root; seed waits for its third mow."""
    just_laid = _ctx(
        today=dt.date(2027, 5, 1),
        establishment_age_days=2,
        establishment_method="sod",
        days_since_sowing=None,
    )
    assert "weed_control_broadleaf" not in _codes(just_laid, "2027-05")
    rooted = _ctx(
        today=dt.date(2027, 5, 1),
        establishment_age_days=40,
        establishment_method="sod",
        days_since_sowing=None,
    )
    assert "weed_control_broadleaf" in _codes(rooted, "2027-05")


def test_a_job_done_in_the_run_up_to_a_month_counts_for_it() -> None:
    """Overseeding on 30 August is the September overseeding, done two days early.

    The plan is a season's shape, not a calendar puzzle, and the first of the month does not
    undo the work. Counting only the operation's own month left the plan asking for a job the
    diary on the next page already recorded, a week after it was done.
    """
    events = plan.month_events({"2026-08-30": {"maintenance": [{"type": "sowing"}]}})
    assert "sowing" in events["2026-08"]
    assert "sowing" in events["2026-09"]

    op = plan.Operation("2026-09", "overseed", "seeding", True, {}, ())
    assert plan.status_of(op, dt.date(2026, 9, 7), events) == "done"


def test_a_job_done_a_month_before_does_not_count_for_it() -> None:
    """Early August is not September: the grace is for the run-up, not for the whole month."""
    events = plan.month_events({"2026-08-05": {"maintenance": [{"type": "sowing"}]}})
    assert "2026-09" not in events

    op = plan.Operation("2026-09", "overseed", "seeding", True, {}, ())
    assert plan.status_of(op, dt.date(2026, 9, 7), events) == "open"


def test_a_fortnight_by_hand_does_not_make_a_hand_mown_month() -> None:
    """A month line says how the month is cut, and one lawn's week is not that.

    Seed sown at the end of August holds the robot off the first week of September and no
    longer. Calling the whole month hand-mown leaves the plan reading as two different jobs
    on lawns that are cut the same way at the same height on the same interval, for a
    difference that is over by the middle of it. The days the robot is held off are the day's
    own advice, which counts them down.
    """
    sown = _ctx(
        today=dt.date(2026, 9, 7),
        robot_mower=True,
        days_since_sowing=8,
        establishment_age_days=78,
    )
    bare = _ctx(today=dt.date(2026, 9, 7), robot_mower=True, establishment_age_days=78)

    def september(ctx):
        return next(
            op for op in plan.build(ctx) if op.month == "2026-09" and op.category == "mowing"
        )

    assert september(sown).code == september(bare).code == "mow_routine_robot"
    assert september(sown).params == september(bare).params
    # The month still says the robot waits at first; it is the same job either way.
    assert "robot_wheels_tear_seedlings" in september(sown).tailoring

    # Sown yesterday, though, and the robot is off it for most of what is left of the month.
    fresh = _ctx(
        today=dt.date(2026, 9, 7),
        robot_mower=True,
        days_since_sowing=1,
        establishment_age_days=78,
    )
    assert september(fresh).code == "mow_routine"


def test_a_sowing_asks_for_its_own_feed() -> None:
    """Seedlings root on phosphorus, and the programme's next feed is potassium.

    The starter went out as a parameter of the overseeding operation, which was fine while
    the overseeding was still to do and vanished with it the moment it was ticked off. So a
    lawn that was sown a week ago had nothing asking it to feed the seed, and the next line
    it would be given is October's autumn feed -- potassium to harden the turf for winter,
    which is the wrong thing for grass still putting a root down.
    """
    ctx = _ctx(
        today=dt.date(2026, 9, 7),
        days_since_sowing=8,
        days_since_fertilizing=None,
        establishment_age_days=78,
    )
    starter = next(
        op for op in plan.build(ctx) if op.code == "feed_after_seeding" and op.month == "2026-09"
    )
    assert starter.optional is False
    assert starter.params["role"] == "starter"
    assert starter.params["n_g_m2"] > 0
    # Phosphorus is the point of it: the class is not the autumn feed's.
    assert starter.params["npk_class"] != "1-0-1"


def test_a_lawn_fed_since_it_was_sown_is_not_asked_again() -> None:
    fed = _ctx(
        today=dt.date(2026, 9, 7),
        days_since_sowing=8,
        days_since_fertilizing=3,
        establishment_age_days=78,
    )
    assert not [op for op in plan.build(fed) if op.code == "feed_after_seeding"]


def test_a_sowing_a_season_ago_is_not_a_starter_feed() -> None:
    old = _ctx(
        today=dt.date(2026, 9, 7),
        days_since_sowing=90,
        days_since_fertilizing=None,
        establishment_age_days=400,
    )
    assert not [op for op in plan.build(old) if op.code == "feed_after_seeding"]
