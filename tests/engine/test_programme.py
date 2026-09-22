"""The mowing cadence: the third rule, read as days."""

from __future__ import annotations

import datetime as dt
from itertools import pairwise

from custom_components.hosekeeper.engine.knowledge import programme


def test_the_classic_intervals_come_back_at_the_middle_of_the_range() -> None:
    """The growth rates are calibrated from the intervals a home lawn is usually given.

    Ten days in the spring green-up, six in each flush, nine through the summer and twelve in
    the late autumn, at 75 mm. If a rate is ever retuned, this is what says what it costs.
    """
    assert [
        programme.mow_interval_days(phase, 75)
        for phase in (
            "spring_greenup",
            "spring_active",
            "summer_stress",
            "autumn_active",
            "late_autumn",
        )
    ] == [10, 6, 9, 6, 12]


def test_the_interval_follows_the_height() -> None:
    assert programme.mow_interval_days("autumn_active", 60) == 5
    assert programme.mow_interval_days("autumn_active", 90) == 7


def test_a_dormant_lawn_is_not_cut_at_all() -> None:
    assert programme.mow_interval_days("dormant", 60) is None


def test_a_very_low_cut_is_not_asked_for_every_other_day() -> None:
    """Bermuda at 25 mm would be due every second day, which nobody does and no rule needs."""
    assert programme.mow_interval_days("spring_active", 25) == programme.MOW_INTERVAL_BOUNDS[0]


def test_the_working_height_is_the_middle_of_what_the_mower_can_reach() -> None:
    assert programme.cutting_height((60, 90)) == 75
    assert programme.cutting_height((60, 90), taller=True) == 90
    assert programme.cutting_height((60, 90), lower=True) == 67
    # A deck that can only make one height makes it whatever is asked for.
    assert programme.cutting_height((60, 60), taller=True) == 60
    assert programme.cutting_height((60, 60), lower=True) == 60


def test_growing_into_a_height_is_the_general_form_of_the_interval() -> None:
    """A lawn is not always cut at the height it is standing at, and then days are a distance."""
    # The ordinary interval is this with the third rule as its target.
    assert programme.days_to_grow("autumn_active", 75, 1.5 * 75) == programme.mow_interval_days(
        "autumn_active", 75
    )
    # A sward scalped to 20 mm and wanted at 45 is waiting to grow, not on any interval.
    assert programme.days_to_grow("autumn_active", 20, 45) == 4
    # Already past the height asked for: the cut is owed now, not in negative days.
    assert programme.days_to_grow("autumn_active", 90, 60) == programme.MOW_INTERVAL_BOUNDS[0]
    assert programme.days_to_grow("dormant", 20, 45) is None


def test_a_scalped_lawn_climbs_back_half_again_at_a_time() -> None:
    """Raising the deck is free; growing the leaf to stand up at the new height is not."""
    assert programme.recovery_height(20, 75) == 30
    assert programme.recovery_height(30, 75) == 45
    assert programme.recovery_height(45, 75) == 68
    # And it never overshoots the height that was wanted all along.
    assert programme.recovery_height(68, 75) == 75
    assert programme.recovery_height(75, 75) == 75


def test_chitted_seed_is_wetted_more_often_and_more_lightly_until_it_is_up() -> None:
    """A radicle already out of the coat has no reserve: the surface may not dry at all."""
    chitted = programme.seedbed_regime(pre_germinated=True, days_since_sowing=1)
    assert chitted is programme.CHITTED_SEEDBED
    assert chitted.passes == 5
    assert chitted.mm < programme.STANDARD_SEEDBED.mm
    # Lighter, but not so light that a pass is gone before it has wetted anything: a
    # millimetre and a half is what a syringing puts down and about the least that reaches
    # the top centimetre on a warm afternoon.
    assert chitted.mm >= 1.5
    # So the floor under the day is higher than the ordinary regime's, in smaller amounts.
    # That is the trade chitted seed asks for and the reason it is not left running once the
    # seedlings are up.
    assert chitted.daily_mm > programme.STANDARD_SEEDBED.daily_mm

    # And what actually matters is the longest the surface is left alone. Both regimes are
    # spread across the same window -- the day the sun gives them -- so the one with more
    # passes in it is the one that never leaves a four-hour hole in the middle.
    window = programme.seedbed_window(dt.time(7, 20), dt.time(19, 24))

    def longest_gap(regime: programme.SeedbedRegime) -> int:
        times = programme.seedbed_times(regime.min_passes, window)
        minutes = [t.hour * 60 + t.minute for t in times]
        return max(b - a for a, b in pairwise(minutes))

    assert longest_gap(chitted) < longest_gap(programme.STANDARD_SEEDBED)
    # Dark comes at the same hour whatever was sown: damping-off is the worse risk, not the
    # lesser one, on seed that is already open.
    assert (
        programme.seedbed_times(chitted.min_passes, window)[-1]
        == programme.seedbed_times(programme.STANDARD_SEEDBED.min_passes, window)[-1]
    )


def test_a_seedbed_is_watered_against_the_sun_and_not_the_clock() -> None:
    """Nine in the morning is right in June and waters wet grass in late September."""
    june = programme.seedbed_window(dt.time(5, 43), dt.time(21, 20))
    september = programme.seedbed_window(dt.time(7, 20), dt.time(19, 24))
    assert june[0] < september[0], "the dew lifts later as the year turns"
    assert june[1] > september[1], "and the light goes sooner"
    # The first pass waits for the dew and the last leaves the leaf time to dry standing up.
    assert september[0] == dt.time(10, 20)
    assert september[1] == dt.time(16, 24)


def test_a_short_day_keeps_the_dew_margin_and_gives_up_the_drying_one() -> None:
    """In December there is no span left; a pass onto a wet leaf is the worse of the two."""
    first, last = programme.seedbed_window(dt.time(8, 6), dt.time(16, 52))
    assert first == dt.time(11, 6), "the dew margin is kept whole"
    assert last > first, "and the day still has passes in it"
    assert last <= dt.time(16, 52), "never after the sun has gone"


def test_a_day_that_dries_faster_is_wetted_more_often() -> None:
    """What kills a seedbed is the longest gap, and that follows the drying rate."""
    ordinary = programme.STANDARD_SEEDBED
    assert ordinary.passes_for(None) == ordinary.min_passes, "no weather, no opinion"
    assert ordinary.passes_for(1.2) == 3, "a cool overcast day holds on three"
    assert ordinary.passes_for(2.8) == 4
    assert ordinary.passes_for(4.0) == 5
    # Never more than a controller can be set to, however hot it gets.
    assert ordinary.passes_for(12.0) == programme.SEEDBED_MAX_PASSES
    assert programme.CHITTED_SEEDBED.passes_for(1.0) == 5, "chitted seed keeps its floor"


def test_more_water_means_more_passes_and_never_a_heavier_one() -> None:
    """A pass is one size. It was the other way about, and the run length moved every day.

    What makes a pass the right size is the soil and the seed -- two millimetres wets the top
    centimetre and does not float seed -- not the arithmetic of the day's remainder.
    """
    ordinary = programme.STANDARD_SEEDBED
    for owed in (6.0, 8.0, 12.0, 30.0):
        passes = programme.seedbed_passes(ordinary, owed, 6.0)
        assert set(passes) == {ordinary.mm}, f"one size of pass, {owed} mm owed"

    # The day varies by how many of them it gets, up to what a controller can be set to.
    assert len(programme.seedbed_passes(ordinary, 6.0, 6.0)) == 3
    assert len(programme.seedbed_passes(ordinary, 12.0, 6.0)) == 6
    assert len(programme.seedbed_passes(ordinary, 30.0, 6.0)) == programme.SEEDBED_MAX_PASSES

    # A day that owes almost nothing gets one proper pass rather than a round of token ones.
    assert len(programme.seedbed_passes(ordinary, 1.0, 6.0)) == 1
    assert programme.seedbed_passes(ordinary, 0.0, 6.0) == []

    # Soil that cannot take a whole pass at once holds the depth down, and then it is the
    # depth that gives way -- seed floated off the surface is not a trade worth making.
    tight = programme.seedbed_passes(ordinary, 6.0, 1.2)
    assert set(tight) == {1.2}


def test_once_the_seedlings_are_up_chitted_seed_is_on_the_ordinary_regime() -> None:
    """Five passes a day on rooted seedlings is water spent on the air."""
    up = programme.PRE_GERMINATED_CRITICAL_DAYS + 1
    assert programme.seedbed_regime(pre_germinated=True, days_since_sowing=up) is (
        programme.STANDARD_SEEDBED
    )
    assert programme.seedbed_regime(pre_germinated=False, days_since_sowing=1) is (
        programme.STANDARD_SEEDBED
    )


def test_the_passes_land_on_the_half_hour_so_a_controller_can_be_set_to_them() -> None:
    """These times are typed in by hand; a schedule that drifts is one nobody keeps."""
    window = programme.seedbed_window(dt.time(7, 20), dt.time(19, 24))
    times = programme.seedbed_times(4, window)
    assert all(at.minute in (0, 30) for at in times)
    # Inward at both ends: never before the dew has lifted, never past the drying margin.
    assert times[0] >= window[0]
    assert times[-1] <= window[1]


def test_a_schedule_does_not_move_because_the_sun_did() -> None:
    """Consecutive days land on the same times, which is the whole point of the grid."""
    monday = programme.seedbed_window(dt.time(7, 20), dt.time(19, 24))
    tuesday = programme.seedbed_window(dt.time(7, 21), dt.time(19, 22))
    assert programme.seedbed_times(4, monday) == programme.seedbed_times(4, tuesday)


def test_a_window_with_too_few_half_hours_gets_the_passes_it_has_room_for() -> None:
    """Two runs in one slot are one run; the water goes in fewer, heavier passes."""
    narrow = (dt.time(11, 0), dt.time(12, 0))
    assert len(programme.seedbed_times(6, narrow)) == 3
    assert programme.seedbed_times(6, narrow) == (dt.time(11, 0), dt.time(11, 30), dt.time(12, 0))


def test_the_lawns_own_humidity_outranks_the_three_hour_rule_of_thumb() -> None:
    """A hygrometer on the lawn knows when the dew went; the constant only guesses."""
    sunrise, sunset = dt.time(7, 20), dt.time(19, 24)
    assumed = programme.seedbed_window(sunrise, sunset)
    assert assumed[0] == dt.time(10, 20), "three hours after sunrise, with nothing observed"

    # A lawn that dries early is watered earlier, and one that holds its dew later.
    early = programme.seedbed_window(sunrise, sunset, dt.time(9, 15))
    late = programme.seedbed_window(sunrise, sunset, dt.time(11, 30))
    assert early[0] == dt.time(9, 15)
    assert late[0] == dt.time(11, 30)


def test_an_observed_hour_is_still_held_to_what_a_canopy_can_actually_do() -> None:
    """One reading from a hygrometer in a hedge does not get to set the whole day."""
    sunrise, sunset = dt.time(7, 20), dt.time(19, 24)
    # Nothing dries in the first few minutes of daylight, whatever the sensor says.
    assert programme.seedbed_window(sunrise, sunset, dt.time(7, 25))[0] == dt.time(8, 20)
    # And a morning that never dried does not push the first pass into the afternoon.
    assert programme.seedbed_window(sunrise, sunset, dt.time(16, 0))[0] == dt.time(13, 20)


def test_a_shaded_zone_dries_later_and_stops_drying_sooner() -> None:
    """The same hours of daylight, fewer of them with any drying power in them."""
    sunrise, sunset = dt.time(7, 20), dt.time(19, 24)
    open_ground = programme.seedbed_window(sunrise, sunset)
    shaded = programme.seedbed_window(sunrise, sunset, shaded_fraction=0.3)
    assert shaded[0] > open_ground[0], "dew holds on under a wall"
    assert shaded[1] < open_ground[1], "and the drying stops sooner in the evening"
    # Proportional, so a zone with a corner in shadow is not treated as a wood.
    full = programme.seedbed_window(sunrise, sunset, shaded_fraction=1.0)
    assert _minutes(full[0]) - _minutes(open_ground[0]) > _minutes(shaded[0]) - _minutes(
        open_ground[0]
    )


def test_shade_moves_an_observed_hour_too_because_the_station_stands_in_the_open() -> None:
    """The hygrometer reports when open ground dried, not when the shaded corner did."""
    sunrise, sunset = dt.time(7, 20), dt.time(19, 24)
    observed = dt.time(9, 40)
    assert programme.seedbed_window(sunrise, sunset, observed)[0] == observed
    shaded = programme.seedbed_window(sunrise, sunset, observed, shaded_fraction=0.3)
    assert shaded[0] == dt.time(10, 7)


def test_deep_shade_on_a_short_day_still_leaves_a_window_to_water_in() -> None:
    """Both margins widening can close the day; the seedbed still has to be wetted."""
    first, last = programme.seedbed_window(dt.time(8, 6), dt.time(16, 52), shaded_fraction=1.0)
    assert last > first
    assert last <= dt.time(16, 52), "never after the sun has gone"


def _minutes(at: dt.time) -> int:
    return at.hour * 60 + at.minute
