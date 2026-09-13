"""The mowing cadence: the third rule, read as days."""

from __future__ import annotations

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

    # And what actually matters is the longest the surface is left alone: both regimes run
    # from nine to five, and the chitted one never leaves a four-hour hole in the middle.
    def longest_gap(regime: programme.SeedbedRegime) -> int:
        minutes = [t.hour * 60 + t.minute for t in regime.times]
        return max(b - a for a, b in pairwise(minutes))

    assert longest_gap(chitted) < longest_gap(programme.STANDARD_SEEDBED)
    # Dark comes at the same hour whatever was sown: damping-off is the worse risk, not the
    # lesser one, on seed that is already open.
    assert max(chitted.times) == max(programme.STANDARD_SEEDBED.times)


def test_once_the_seedlings_are_up_chitted_seed_is_on_the_ordinary_regime() -> None:
    """Five passes a day on rooted seedlings is water spent on the air."""
    up = programme.PRE_GERMINATED_CRITICAL_DAYS + 1
    assert programme.seedbed_regime(pre_germinated=True, days_since_sowing=up) is (
        programme.STANDARD_SEEDBED
    )
    assert programme.seedbed_regime(pre_germinated=False, days_since_sowing=1) is (
        programme.STANDARD_SEEDBED
    )
