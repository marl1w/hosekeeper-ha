"""The rules, one situation at a time."""

from __future__ import annotations

import datetime as dt
from typing import Any

from custom_components.hosekeeper.engine import agenda, climate, rules
from custom_components.hosekeeper.engine.phenology import Phenology


def _ctx(**overrides: Any) -> rules.Context:
    base: dict[str, Any] = {
        "today": dt.date(2026, 9, 6),
        "cool_season": True,
        "northern_hemisphere": True,
        "grass_type": "tall_fescue",
        "soil_type": "loam",
        "establishment_method": "sod",
        "establishment_age_days": 500,
        "mow_height_mm": (60, 90),
        "phenology": Phenology(20.0, 2500.0, "autumn_active", False, False, 60),
        "deficit_mm": 10.0,
        "taw_mm": 45.0,
        "raw_mm": 22.5,
        "etc_today_mm": 4.0,
        "rain_today_mm": 0.0,
        "irrigation_today_mm": 0.0,
        "can_convert_minutes": True,
        "minutes_per_mm": 4.0,
        "forecast_rain_24h_mm": 0.0,
        "forecast_rain_72h_mm": 0.0,
        "forecast_tmax_3d": 26.0,
        "forecast_tmin_3d": 14.0,
        "skill": climate.NEUTRAL_SKILL,
        "anomalies": climate.Anomalies(4.0, 4.0, 1.0, 3, 40.0, 0),
        "days_since_mowing": 3,
        "days_since_fertilizing": 60,
        "days_since_aeration": None,
        "days_since_scarifying": None,
        "days_since_sowing": None,
        "nitrogen_60d_g_m2": 0.0,
        "nitrogen_year_g_m2": 9.0,
        "feeds_done_this_year": set(),
        "statuses_14d": ["good", "good", "fair"],
        "issues_30d": set(),
        "dollar_spot_probability": 0.05,
        "brown_patch_index": 0.0,
    }
    base.update(overrides)
    return rules.Context(**base)


def _codes(advice: list[rules.Advice]) -> list[str]:
    return [a.code for a in advice]


def test_quiet_september_day_asks_to_overseed_and_nothing_else_urgent() -> None:
    advice = rules.evaluate(_ctx())
    codes = _codes(advice)
    assert "overseed_now" in codes
    assert "feed_now" not in codes  # September is for seeding; the feed comes in October
    assert "irrigate_now" not in codes
    assert "aerate_now" in codes  # optional autumn aeration, the soil is moist enough
    seed = next(a for a in advice if a.code == "overseed_now")
    assert seed.horizon == "week"
    assert seed.params["starter_feed"]["npk_class"] == "1-2-1"
    assert "pro_programme_september_overseed" in seed.reasons


def test_october_feed_names_the_product_class_and_dose() -> None:
    advice = rules.evaluate(_ctx(today=dt.date(2026, 10, 5)))
    feed = next(a for a in advice if a.code == "feed_now")
    assert feed.params["window"] == "feed_october_autumn"
    assert feed.params["npk_class"] == "1-0-1"
    assert feed.params["preset"] == "bottos_autumn_k"
    assert feed.params["dose_g_m2"] == 25
    assert feed.horizon == "week"
    assert "planned_this_month" in feed.reasons
    assert "research_late_autumn_potassium_hardiness" in feed.reasons


def test_the_class_does_not_move_with_the_weather_within_the_month() -> None:
    # A hot spell in October: the feed waits, but stays the autumn potassium feed.
    hot = Phenology(22.0, 3000.0, "autumn_active", True, False, 30)
    advice = rules.evaluate(_ctx(today=dt.date(2026, 10, 5), phenology=hot))
    wait = next(a for a in advice if a.code == "feed_wait")
    assert wait.params["npk_class"] == "1-0-1"
    assert "heat_stress" in wait.reasons


def test_deficit_past_raw_means_irrigate_with_minutes() -> None:
    advice = rules.evaluate(_ctx(deficit_mm=25.0))
    irrigate = next(a for a in advice if a.code == "irrigate_now")
    assert irrigate.params["mm"] == 25
    assert irrigate.params["minutes"] == 100
    assert "deficit_past_raw" in irrigate.reasons


def test_reliable_rain_holds_irrigation_and_unreliable_rain_does_not() -> None:
    honest = rules.evaluate(_ctx(deficit_mm=25.0, forecast_rain_24h_mm=24.0))
    assert "hold_irrigation_rain_coming" in _codes(honest)

    liar = climate.ForecastSkill(
        pairs=20, rain_ratio=0.3, rain_hit_rate=0.3, tmax_bias=0, tmin_bias=0
    )
    doubted = rules.evaluate(_ctx(deficit_mm=25.0, forecast_rain_24h_mm=24.0, skill=liar))
    irrigate = next(a for a in doubted if a.code == "irrigate_now")
    assert "forecast_rain_unreliable" in irrigate.reasons
    assert irrigate.params["mm"] == 23  # 25 - 24 * 0.3 * 0.3


def test_adaptation_factor_waters_earlier_and_more() -> None:
    advice = rules.evaluate(_ctx(deficit_mm=20.0, irrigation_factor=1.2))
    irrigate = next(a for a in advice if a.code == "irrigate_now")
    assert irrigate.params["mm"] == 24
    assert "adapted_more_water" in irrigate.reasons


def test_heat_stress_blocks_feeding_and_delays_mowing() -> None:
    hot = Phenology(26.0, 2500.0, "summer_stress", True, False, 60)
    advice = rules.evaluate(_ctx(phenology=hot, today=dt.date(2026, 7, 20), days_since_mowing=10))
    codes = _codes(advice)
    assert "feed_wait" in codes
    assert "delay_mowing_stress" in codes
    wait = next(a for a in advice if a.code == "feed_wait")
    assert "heat_stress" in wait.reasons


def test_heat_delays_a_cut_but_does_not_cancel_it() -> None:
    """Three weeks of 33 °C is not three weeks of no mowing.

    Heat is already in the interval: the summer phase grows slowly, so the third rule
    stretches with it. Dropping the cut on top of that leaves the grass to reach twice its
    height and be scalped at the end of the spell, which is what the rule exists to prevent.
    """
    hot = Phenology(26.0, 2500.0, "summer_stress", True, False, 60)
    # Nine days after the last cut, at 90 mm in the heat, the grass is still inside its
    # allowance: the cut waits, and the advice says how long for.
    waiting = rules.evaluate(_ctx(phenology=hot, today=dt.date(2026, 7, 20), days_since_mowing=9))
    delay = next(a for a in waiting if a.code == "delay_mowing_stress")
    assert "heat_stress" in delay.reasons
    assert delay.params["next_in_days"] == 2

    # Past it, the cut is asked for whatever the weather, high and with the heat named.
    due = rules.evaluate(_ctx(phenology=hot, today=dt.date(2026, 7, 20), days_since_mowing=12))
    mow = next(a for a in due if a.category == "mowing")
    assert mow.code == "mow_soon"
    assert mow.reasons == ("interval_reached", "heat_stress")
    assert mow.params["height_mm"] == 90  # the top of the range: the leaf shades its own soil


def test_the_week_still_dates_cuts_through_a_hot_spell() -> None:
    hot = Phenology(26.0, 2500.0, "summer_stress", True, False, 60)
    ctx = _ctx(phenology=hot, today=dt.date(2026, 7, 20), days_since_mowing=9)
    week = agenda.build(ctx, [], rules.evaluate(ctx), latitude=45.0, minutes_per_mm=4.0)
    assert [i.date for i in week if i.code == "mow"], "a hot week with no cut on it at all"


def test_heavy_rain_forecast_blocks_feeding() -> None:
    advice = rules.evaluate(_ctx(today=dt.date(2026, 10, 5), forecast_rain_72h_mm=30.0))
    wait = next(a for a in advice if a.code == "feed_wait")
    assert "heavy_rain_forecast" in wait.reasons


def test_recent_feed_satisfies_the_window() -> None:
    advice = rules.evaluate(_ctx(days_since_fertilizing=10, nitrogen_60d_g_m2=5.0))
    assert "feed_recently_done" in _codes(advice)
    assert "feed_now" not in _codes(advice)


def test_mowing_follows_the_interval() -> None:
    assert "mow_soon" in _codes(rules.evaluate(_ctx(days_since_mowing=6)))
    assert "mow_now_third_rule" in _codes(rules.evaluate(_ctx(days_since_mowing=9)))
    assert "mowing_height" in _codes(rules.evaluate(_ctx(days_since_mowing=2)))


def test_a_lawn_cut_low_comes_round_sooner_than_one_cut_high() -> None:
    """The third rule is about height, so the interval cannot be a table of days alone.

    The grass may reach half again the height it is kept at, so the growth allowed between
    cuts is half that height: at 60 mm a lawn is due after 30 mm of growth and at 90 mm
    after 45. Six days for both is right for neither.
    """
    low = rules.evaluate(_ctx(mow_height_mm=(60, 60), days_since_mowing=5))
    high = rules.evaluate(_ctx(mow_height_mm=(90, 90), days_since_mowing=5))
    assert "mow_soon" in _codes(low), "a 60 mm lawn is due after five days in the autumn flush"
    assert "mowing_height" in _codes(high), "a 90 mm lawn is not"
    waiting = next(a for a in high if a.code == "mowing_height")
    assert waiting.params["next_in_days"] == 2


def _robot_cuts(**overrides: Any) -> list[str]:
    ctx = _ctx(robot_mower=True, days_since_mowing=0, **overrides)
    week = agenda.build(ctx, [], [], latitude=45.0, minutes_per_mm=4.0)
    return [item.date for item in week if item.code == "mow"]


def test_a_robot_on_the_manufacturer_s_schedule_ignores_the_height() -> None:
    """Out every day whatever it cuts to: it takes a few millimetres at a time."""
    assert _robot_cuts(mow_height_mm=(60, 60), robot_cadence="frequent") == _robot_cuts(
        mow_height_mm=(90, 90), robot_cadence="frequent"
    )
    assert len(_robot_cuts(robot_cadence="frequent")) >= 6


def test_a_gentler_robot_is_out_on_fewer_days() -> None:
    """Every pass has the lawn busy for hours and goes over the same ground.

    Daily is what the machine can do rather than what the grass needs, so the cadence is a
    choice: the manufacturer's schedule, half the growth the third rule allows, or the whole
    of it, which is the least disturbance the lawn can be kept in condition with.
    """
    frequent = _robot_cuts(robot_cadence="frequent")
    balanced = _robot_cuts(robot_cadence="balanced")
    gentle = _robot_cuts(robot_cadence="gentle")
    assert len(frequent) > len(balanced) > len(gentle)
    assert balanced, "a gentler cadence still cuts the grass"


def test_bare_spots_in_september_mean_overseed() -> None:
    advice = rules.evaluate(_ctx(issues_30d={"bare_spots"}))
    seed = next(a for a in advice if a.code == "overseed_now")
    assert "bare_or_thin_areas_seen" in seed.reasons
    assert seed.priority == 2
    # But not with only 30 days to the first frost.
    late = Phenology(14.0, 3000.0, "autumn_active", False, False, 30)
    late_advice = rules.evaluate(_ctx(issues_30d={"bare_spots"}, phenology=late))
    assert "overseed_now" not in _codes(late_advice)
    wait = next(a for a in late_advice if a.code == "overseed_wait")
    assert "too_close_to_frost" in wait.reasons


def test_pre_emergent_window_in_march() -> None:
    spring = Phenology(11.0, 200.0, "spring_greenup", False, False, 240)
    advice = rules.evaluate(
        _ctx(today=dt.date(2026, 3, 15), phenology=spring, issues_30d={"weeds"})
    )
    pre = next(a for a in advice if a.code == "pre_emergent_window")
    assert pre.priority == 2
    assert "weeds_seen" in pre.reasons
    # Also planned that month: the starter feed.
    feed = next(a for a in advice if a.code == "feed_now")
    assert feed.params["preset"] == "bottos_pro_start"


def test_disease_models_alert_on_the_second_day_over_threshold() -> None:
    first_day = rules.evaluate(
        _ctx(dollar_spot_probability=0.35, brown_patch_index=7.0, nitrogen_60d_g_m2=5.0)
    )
    assert "dollar_spot_risk" not in _codes(first_day)
    second_day = rules.evaluate(
        _ctx(
            dollar_spot_probability=0.35,
            brown_patch_index=7.0,
            nitrogen_60d_g_m2=5.0,
            disease_risk_yesterday={"dollar_spot", "brown_patch"},
        )
    )
    ds = next(a for a in second_day if a.code == "dollar_spot_risk")
    bp = next(a for a in second_day if a.code == "brown_patch_risk")
    assert ds.params["probability"] == 35
    assert "high_nitrogen_favours_brown_patch" in bp.reasons


def test_weed_passes_wait_for_dry_mild_days_and_grown_leaves() -> None:
    may = Phenology(16.0, 900.0, "spring_active", False, False, 200)
    ready = rules.evaluate(_ctx(today=dt.date(2026, 5, 10), phenology=may, issues_30d={"weeds"}))
    assert "weed_control_broadleaf_now" in _codes(ready)
    just_mowed = rules.evaluate(
        _ctx(today=dt.date(2026, 5, 10), phenology=may, issues_30d={"weeds"}, days_since_mowing=1)
    )
    wait = next(a for a in just_mowed if a.code == "weed_control_wait")
    assert "just_mowed" in wait.reasons
    july = Phenology(24.0, 1800.0, "summer_stress", False, False, 120)
    grassy = rules.evaluate(_ctx(today=dt.date(2026, 7, 10), phenology=july, forecast_tmax_3d=26.0))
    assert "weed_control_grassy_now" in _codes(grassy)


def test_new_sod_gets_its_own_programme() -> None:
    advice = rules.evaluate(_ctx(establishment_age_days=5, days_since_fertilizing=None))
    codes = _codes(advice)
    assert "establish_sod_water_daily" in codes
    assert "establish_no_mowing" in codes
    assert "establish_starter_feed" in codes
    assert "irrigate_now" not in codes
    assert "feed_now" not in codes


def test_dormant_lawn_is_left_alone() -> None:
    winter = Phenology(3.0, 0.0, "dormant", False, True, 300)
    advice = rules.evaluate(_ctx(today=dt.date(2026, 1, 10), phenology=winter, deficit_mm=30.0))
    codes = _codes(advice)
    assert "no_irrigation_dormant" in codes
    assert "no_mowing_dormant" in codes
    assert "feed_now" not in codes


def test_poor_lawn_gets_a_diagnosis() -> None:
    advice = rules.evaluate(_ctx(statuses_14d=["poor", "poor", "fair"], deficit_mm=25.0))
    diag = next(a for a in advice if a.code == "lawn_poor_diagnosis")
    assert "under_watered" in diag.reasons
    assert "under_fed" in diag.reasons


def test_every_code_the_rules_emit_is_registered() -> None:
    from pathlib import Path
    import re

    source = Path(rules.__file__).read_text()
    emitted = set(re.findall(r'Advice\(\s*"([a-z_]+)"', source))
    emitted |= set(rules.WEED_ADVICE.values()) | set(rules.SOIL_WORK_ADVICE.values())
    assert emitted <= set(rules.ADVICE_CODES)
    assert set(rules.ADVICE_CODES) <= emitted


def test_shade_changes_the_mix_the_height_and_the_autumn_chores() -> None:
    shaded = _ctx(shaded_fraction=0.4, tree_fraction=0.4, deciduous_trees=True, days_since_mowing=2)
    advice = rules.evaluate(shaded)
    seed = next(a for a in advice if a.code == "overseed_now")
    assert seed.params["seed_mix"] == "shade_tolerant_fine_fescue"
    assert "shade_tolerant_mix" in seed.reasons
    height = next(a for a in advice if a.code == "mowing_height")
    assert height.params["height_mm"] == 90

    october = rules.evaluate(
        _ctx(
            today=dt.date(2026, 10, 12),
            shaded_fraction=0.4,
            tree_fraction=0.4,
            deciduous_trees=True,
        )
    )
    assert "clear_leaves" in _codes(october)
    open_lawn = rules.evaluate(_ctx(today=dt.date(2026, 10, 12)))
    assert "clear_leaves" not in _codes(open_lawn)

    february = Phenology(4.0, 40.0, "dormant", False, True, 250)
    moss = rules.evaluate(_ctx(today=dt.date(2026, 2, 12), phenology=february, shaded_fraction=0.4))
    assert "moss_control_now" in _codes(moss)


def test_overseeding_keeps_the_deep_cycle_and_adds_seedbed_watering() -> None:
    # Seed sown into an established lawn three days ago.
    advice = rules.evaluate(_ctx(days_since_sowing=3, deficit_mm=25.0))
    codes = _codes(advice)
    assert "irrigate_now" in codes, "the turf around the seed still has deep roots"
    seedbed = next(a for a in advice if a.code == "germination_watering")
    assert seedbed.params["days_left"] == 11
    assert seedbed.horizon == "today"


def test_a_brand_new_seeded_lawn_only_gets_the_seedbed_regime() -> None:
    advice = rules.evaluate(
        _ctx(establishment_method="seed", establishment_age_days=5, deficit_mm=25.0)
    )
    codes = _codes(advice)
    assert "establish_seed_keep_moist" in codes
    assert "irrigate_now" not in codes
    assert "germination_watering" not in codes


def test_the_mower_is_held_off_a_lawn_sown_last_week() -> None:
    """A lawn sown from bare soil is not cut: there is nothing to cut but the seedlings."""
    sown = _ctx(days_since_sowing=7, establishment_age_days=7, days_since_mowing=9)
    advice = rules.evaluate(sown)
    hold = next(a for a in advice if a.code == "hold_mowing_after_sowing")
    assert hold.priority == 1, "a robot mowing seedlings is today's problem, not this week's"
    assert hold.params["days_left"] == 14
    assert "mow_now_third_rule" not in _codes(advice)

    # Three weeks on, the first cut is due again.
    grown = _ctx(days_since_sowing=22, establishment_age_days=22)
    assert "hold_mowing_after_sowing" not in _codes(rules.evaluate(grown))


def test_an_overseeded_lawn_is_still_mown() -> None:
    """The turf around the seed goes on growing, and uncut it shades the seedlings out.

    This is the difference between two jobs that share a word. Holding the mower for three
    weeks after an overseeding, as the engine used to, buries the new seed under the old
    grass in the very fortnight it needs light.
    """
    ctx = _ctx(days_since_sowing=7, establishment_age_days=92, days_since_mowing=9)
    codes = _codes(rules.evaluate(ctx))
    assert "hold_mowing_after_sowing" not in codes
    assert "mow_now_third_rule" in codes


def test_the_robot_waits_for_the_seed_to_root_but_the_lawn_is_still_cut() -> None:
    """The blade passes above the seedlings; it is the wheels that pull them out."""
    ctx = _ctx(
        days_since_sowing=7, establishment_age_days=92, days_since_mowing=9, robot_mower=True
    )
    advice = rules.evaluate(ctx)
    by_hand = next(a for a in advice if a.code == "mow_by_hand_while_seed_roots")
    assert by_hand.params["days_left"] == 7
    assert "mow_now_third_rule" not in _codes(advice)

    # Once the seed is up, the robot goes back out.
    rooted = _ctx(
        days_since_sowing=15, establishment_age_days=100, days_since_mowing=9, robot_mower=True
    )
    assert "mow_by_hand_while_seed_roots" not in _codes(rules.evaluate(rooted))
