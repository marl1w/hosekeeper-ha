"""The week ahead: irrigation from the projected balance, mowing, the month's operations."""

from __future__ import annotations

import datetime as dt
import itertools

from custom_components.hosekeeper.engine import agenda, rules
from tests.engine.test_rules import _ctx

TODAY = dt.date(2026, 10, 5)


def _forecast(
    rain_by_offset: dict[int, float] | None = None, tmax: float = 22.0
) -> list[agenda.DayForecast]:
    rain_by_offset = rain_by_offset or {}
    return [
        agenda.DayForecast(
            TODAY + dt.timedelta(days=i), tmax, tmax - 10, rain_by_offset.get(i, 0.0)
        )
        for i in range(7)
    ]


def test_irrigation_lands_where_the_balance_runs_out() -> None:
    ctx = _ctx(today=TODAY, deficit_mm=14.0, etc_today_mm=3.0)
    # A warm dry October week: about 3 mm of crop ET a day.
    items = agenda.build(
        ctx, _forecast(tmax=30.0), rules.evaluate(ctx), latitude=45.0, minutes_per_mm=4.0
    )
    irrigations = [i for i in items if i.code == "irrigate"]
    assert irrigations, items
    first = irrigations[0]
    # 14 mm down, 2 to 3 mm a day: the readily available 22.5 mm runs out around the fourth day.
    assert first.date in ("2026-10-08", "2026-10-09", "2026-10-10")
    assert first.params["mm"] >= 18
    assert first.params["minutes"] == first.params["mm"] * 4


def test_reliable_rain_pushes_irrigation_back() -> None:
    ctx = _ctx(today=TODAY, deficit_mm=14.0, etc_today_mm=3.0)
    wet = _forecast({2: 20.0})
    items = agenda.build(ctx, wet, rules.evaluate(ctx), latitude=45.0, minutes_per_mm=4.0)
    irrigations = [i for i in items if i.code == "irrigate"]
    assert not irrigations or irrigations[0].date > "2026-10-08"


def test_mowing_follows_the_interval_and_dodges_rain() -> None:
    ctx = _ctx(today=TODAY, days_since_mowing=4)  # autumn interval is 6 days
    items = agenda.build(
        ctx, _forecast({2: 8.0}), rules.evaluate(ctx), latitude=45.0, minutes_per_mm=4.0
    )
    mows = [i for i in items if i.code == "mow"]
    assert mows[0].date == "2026-10-08"  # the 7th is wet, so the day after
    assert mows[0].params["height_mm"] == 75


def test_what_the_rules_advise_today_lands_on_today() -> None:
    # Weeds seen and the last cut two days ago: the rules say to treat them now, so the week
    # must put that on today rather than projecting it onto a later day.
    ctx = _ctx(today=TODAY, days_since_mowing=2, issues_30d={"weeds"})
    advice = rules.evaluate(ctx)
    assert "weed_control_broadleaf_now" in {a.code for a in advice}
    items = agenda.build(ctx, _forecast(), advice, latitude=45.0, minutes_per_mm=4.0)
    weeding = next(i for i in items if i.params.get("operation") == "weed_control_broadleaf")
    assert weeding.date == TODAY.isoformat()
    assert "advised_today" in weeding.reasons


def test_an_operation_the_rules_hold_back_gets_the_best_day() -> None:
    # Mown today, so the herbicide has to wait, and tomorrow is wet.
    ctx = _ctx(today=TODAY, days_since_mowing=0, issues_30d={"weeds"})
    items = agenda.build(
        ctx, _forecast({1: 6.0}), rules.evaluate(ctx), latitude=45.0, minutes_per_mm=4.0
    )
    ops = {i.params["operation"]: i for i in items if i.code == "operation"}
    assert "feed_october_autumn" in ops
    weed_day = dt.date.fromisoformat(ops["weed_control_broadleaf"].date)
    mow_days = [dt.date.fromisoformat(i.date) for i in items if i.code == "mow"]
    assert all(abs((weed_day - m).days) >= 2 for m in mow_days)
    assert weed_day != TODAY + dt.timedelta(days=1)


def test_a_hot_wet_week_has_no_good_day_for_the_herbicide() -> None:
    ctx = _ctx(today=TODAY, days_since_mowing=0, issues_30d={"weeds"})
    bad = _forecast({i: 4.0 for i in range(7)}, tmax=30.0)
    items = agenda.build(ctx, bad, rules.evaluate(ctx), latitude=45.0, minutes_per_mm=4.0)
    nogo = [
        i
        for i in items
        if i.code == "no_good_day" and i.params["operation"] == "weed_control_broadleaf"
    ]
    assert nogo and nogo[0].date == "2026-10-11"


def test_dormant_lawn_has_an_empty_water_agenda() -> None:
    from custom_components.hosekeeper.engine.phenology import Phenology

    winter = Phenology(3.0, 0.0, "dormant", False, True, 300)
    ctx = _ctx(today=dt.date(2026, 1, 10), phenology=winter, deficit_mm=30.0)
    items = agenda.build(ctx, [], rules.evaluate(ctx), latitude=45.0, minutes_per_mm=4.0)
    assert not [i for i in items if i.category in ("irrigation", "mowing")]


def test_the_seedbed_is_watered_every_day_until_the_seed_is_up() -> None:
    # Sown three days ago into an established lawn: eleven days of the fortnight are left,
    # and every one of them carries the light waterings, not just the days the forecast
    # happens to reach.
    ctx = _ctx(today=TODAY, days_since_sowing=3)
    items = agenda.build(ctx, _forecast(), rules.evaluate(ctx), latitude=45.0, minutes_per_mm=4.0)
    seedbed = [i for i in items if i.code == "germination_watering"]
    assert len(seedbed) == 11
    assert seedbed[0].date == TODAY.isoformat()
    assert seedbed[0].params["times"] == 3

    # Sown twelve days ago: only the last two days of the fortnight remain.
    late = _ctx(today=TODAY, days_since_sowing=12)
    items = agenda.build(late, _forecast(), rules.evaluate(late), latitude=45.0, minutes_per_mm=4.0)
    assert len([i for i in items if i.code == "germination_watering"]) == 2

    # Nothing sown: nothing to keep damp.
    dry = _ctx(today=TODAY)
    items = agenda.build(dry, _forecast(), rules.evaluate(dry), latitude=45.0, minutes_per_mm=4.0)
    assert not [i for i in items if i.code == "germination_watering"]


def test_a_lawn_overseeded_last_week_is_not_sown_again_but_is_still_mown() -> None:
    # September plans an overseeding, but seed went down a week ago. The week must not
    # propose a second one. It must still propose the cut: the established grass around the
    # seed goes on growing, and standing tall it shades the seedlings out.
    ctx = _ctx(
        today=dt.date(2026, 9, 6),
        days_since_sowing=7,
        establishment_age_days=92,
        days_since_mowing=9,
    )
    items = agenda.build(ctx, _forecast(), rules.evaluate(ctx), latitude=45.0, minutes_per_mm=4.0)
    assert not [i for i in items if i.params.get("operation") == "overseed"]
    assert [i for i in items if i.code == "mow"]
    assert [i for i in items if i.code == "germination_watering"]


def test_a_lawn_sown_on_bare_soil_is_not_mown_at_all() -> None:
    # Nothing to cut but the seedlings, and a mower would tear them out.
    ctx = _ctx(
        today=dt.date(2026, 9, 6),
        days_since_sowing=7,
        establishment_age_days=7,
        days_since_mowing=9,
    )
    items = agenda.build(ctx, _forecast(), rules.evaluate(ctx), latitude=45.0, minutes_per_mm=4.0)
    assert not [i for i in items if i.code == "mow"]

    # Three weeks on, the first cut is due.
    later = _ctx(
        today=dt.date(2026, 9, 6),
        days_since_sowing=31,
        establishment_age_days=31,
        days_since_mowing=9,
    )
    items = agenda.build(
        later, _forecast(), rules.evaluate(later), latitude=45.0, minutes_per_mm=4.0
    )
    assert [i for i in items if i.code == "mow"]


def test_the_month_does_not_go_blank_after_the_forecast_runs_out() -> None:
    """A cut is on a cadence, not on the weather, so it is laid out for the month.

    The agenda used to stop at the seventh day, which left every calendar empty from the
    middle of one month to the first of the next: the only thing in it was the month's own
    banner, and nothing said when to be in the garden.
    """
    ctx = _ctx(today=TODAY, days_since_mowing=4)
    items = agenda.build(ctx, _forecast(), rules.evaluate(ctx), latitude=45.0, minutes_per_mm=4.0)
    mows = [dt.date.fromisoformat(i.date) for i in items if i.code == "mow"]
    assert len(mows) >= 4, mows
    assert max(mows) >= TODAY + dt.timedelta(days=21)
    # Six days apart, every time: the interval the autumn flush asks for.
    assert all((b - a).days == 6 for a, b in itertools.pairwise(mows))


def test_the_balance_is_run_past_the_forecast_but_not_forever() -> None:
    """A fortnight of water, because past that it is climate, not weather."""
    ctx = _ctx(today=TODAY, deficit_mm=14.0, etc_today_mm=3.0)
    days = agenda.project(ctx, _forecast(tmax=30.0), rules.evaluate(ctx), latitude=45.0)
    assert len(days) == agenda.BALANCE_DAYS
    assert days[-1].date == TODAY + dt.timedelta(days=agenda.BALANCE_DAYS - 1)


def test_the_seedbed_watering_is_drawn_but_not_credited_to_the_root_zone() -> None:
    """The chart must agree with the agenda about what goes on the lawn.

    Three light waterings a day were in the agenda and missing from the projection, so the
    picture showed a lawn getting nothing on days it was being watered six millimetres. They
    are shown now. They are still not subtracted from the deficit: two millimetres on a warm
    afternoon wets the top centimetre and mostly goes back to the air, and crediting it would
    stop the dawn cycle the established turf around the seed still needs.
    """
    ctx = _ctx(today=TODAY, days_since_sowing=3, deficit_mm=4.0, etc_today_mm=3.0)
    days = agenda.project(ctx, _forecast(), rules.evaluate(ctx), latitude=45.0)
    assert days[0].seedbed_mm == 6.0
    assert days[11].seedbed_mm == 0.0, "the fortnight is over by then"
    # The deficit still grows: the seedbed water is not in the balance.
    dry = agenda.project(
        _ctx(today=TODAY, deficit_mm=4.0, etc_today_mm=3.0), _forecast(), [], latitude=45.0
    )
    assert [d.deficit_mm for d in days] == [d.deficit_mm for d in dry]


def test_the_projection_says_where_the_forecast_stopped() -> None:
    """Past the last forecast day the numbers are the season's rate, not a forecast."""
    days = agenda.project(_ctx(today=TODAY), _forecast(), [], latitude=45.0)
    assert all(d.forecast for d in days[:7])
    assert not any(d.forecast for d in days[7:])


def test_a_robot_is_scheduled_on_its_own_cadence_not_the_push_mower_s() -> None:
    """Deciding when the grass is best cut is the engine's job for a robot too.

    What changes is how often: a robot takes a few millimetres at a time and keeps up by
    going often. The calendar used the third rule's interval whatever the machine, so it
    dated a cut every six days beside a month line reading "robot out every day".
    """
    push = _ctx(today=TODAY, days_since_mowing=9)
    by_hand = [
        dt.date.fromisoformat(i.date)
        for i in agenda.build(
            push, _forecast(), rules.evaluate(push), latitude=45.0, minutes_per_mm=4.0
        )
        if i.code == "mow"
    ]
    robot_ctx = _ctx(today=TODAY, days_since_mowing=9, robot_mower=True)
    robot = [
        dt.date.fromisoformat(i.date)
        for i in agenda.build(
            robot_ctx, _forecast(), rules.evaluate(robot_ctx), latitude=45.0, minutes_per_mm=4.0
        )
        if i.code == "mow"
    ]
    assert by_hand and robot, "both machines must still be told when to cut"
    # October is autumn growth: by hand every six days, the robot on the balanced cadence
    # every three, which is oftener without being out on the lawn every single day.
    assert all((b - a).days == 6 for a, b in itertools.pairwise(by_hand))
    assert all((b - a).days == 3 for a, b in itertools.pairwise(robot))
    assert len(robot) > len(by_hand)

    # And on the manufacturer's own schedule, every day, for whoever wants that.
    daily_ctx = _ctx(today=TODAY, days_since_mowing=9, robot_mower=True, robot_cadence="frequent")
    daily = [
        dt.date.fromisoformat(i.date)
        for i in agenda.build(
            daily_ctx, _forecast(), rules.evaluate(daily_ctx), latitude=45.0, minutes_per_mm=4.0
        )
        if i.code == "mow"
    ]
    assert all((b - a).days == 1 for a, b in itertools.pairwise(daily))
