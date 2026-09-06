"""Compositions become grams of nitrogen."""

from __future__ import annotations

import pytest

from custom_components.hosekeeper.engine.knowledge import fertilizers


def test_bottos_slow_green_at_label_rate() -> None:
    product = fertilizers.PRESETS["bottos_slow_green"]
    # 27.5 g/m² at 22 % N is 6 g N/m².
    assert product.nitrogen_g_m2(product.default_dose_g_m2) == pytest.approx(6.05)


def test_resolve_prefers_preset_then_custom_then_generic() -> None:
    assert fertilizers.resolve("bottos_slow_k", None, None, None).id == "bottos_slow_k"
    custom = fertilizers.resolve("something_else", 15, 5, 5)
    assert custom.id == "custom" and custom.n == 15
    assert fertilizers.resolve(None, None, None, None).id == "slow_release"
