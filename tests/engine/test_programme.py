"""The mowing cadence: the third rule, read as days."""

from __future__ import annotations

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
