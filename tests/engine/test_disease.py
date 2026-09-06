"""The two disease models against their published thresholds."""

from __future__ import annotations

import pytest

from custom_components.hosekeeper.engine import disease


def test_smith_kerns_is_low_in_cool_dry_weather_and_high_in_warm_humid() -> None:
    cool = disease.dollar_spot_probability([50] * 5, [12] * 5)
    humid = disease.dollar_spot_probability([85] * 5, [22] * 5)
    assert cool is not None and cool < 0.05
    assert humid is not None and humid > 0.5


def test_smith_kerns_published_point() -> None:
    # By hand: -11.4041 + 0.0894 * 75 + 0.1932 * 20 = -0.835, a probability of 0.30.
    p = disease.dollar_spot_probability([75] * 5, [20] * 5)
    assert p == pytest.approx(0.303, abs=0.005)


def test_smith_kerns_needs_three_days() -> None:
    assert disease.dollar_spot_probability([80, 80], [20, 20]) is None


def test_fidanza_index_crosses_six_on_a_muggy_night() -> None:
    assert disease.brown_patch_index(60, 12) < disease.BROWN_PATCH_WARNING_INDEX
    assert disease.brown_patch_index(90, 21) >= disease.BROWN_PATCH_WARNING_INDEX
    assert disease.brown_patch_index(None, 21) is None
