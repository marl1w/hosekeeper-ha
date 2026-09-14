"""The rules, one situation at a time."""

from __future__ import annotations

import datetime as dt
from typing import Any

from custom_components.hosekeeper.engine import agenda, climate, rules, water
from custom_components.hosekeeper.engine.knowledge import programme
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


def test_patching_bare_spots_keeps_the_deep_cycle_and_adds_seedbed_watering() -> None:
    """Seed in a few bare spots does not turn the lawn around them into a seedbed."""
    advice = rules.evaluate(_ctx(days_since_sowing=3, sowing_kind="repair", deficit_mm=25.0))
    codes = _codes(advice)
    assert "irrigate_now" in codes, "the turf around the seed still has deep roots"
    seedbed = next(a for a in advice if a.code == "germination_watering")
    assert seedbed.params["days_left"] == 11
    assert seedbed.horizon == "today"


def test_a_lawn_sown_all_over_is_not_told_to_water_twice() -> None:
    """The passes are the day's watering, so the dawn cycle must not be advised as well."""
    advice = rules.evaluate(_ctx(days_since_sowing=3, sowing_kind="overseed", deficit_mm=25.0))
    codes = _codes(advice)
    assert "germination_watering" in codes
    assert "irrigate_now" not in codes
    assert "irrigation_due_soon" not in codes


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


def test_pre_germinated_seed_is_watered_more_often_than_dry_seed() -> None:
    """Chitted seed has no reserve: the advice has to ask for more passes, not the same three."""
    chitted = rules.evaluate(_ctx(days_since_sowing=2, sown_pre_germinated=True, deficit_mm=25.0))
    seedbed = next(a for a in chitted if a.code == "germination_watering")
    assert seedbed.params["times"] == programme.CHITTED_SEEDBED.passes
    assert seedbed.params["mm"] >= programme.CHITTED_SEEDBED.mm, "never below the damp floor"
    assert "chitted_seed_cannot_dry" in seedbed.reasons

    dry = rules.evaluate(_ctx(days_since_sowing=2, deficit_mm=25.0))
    ordinary = next(a for a in dry if a.code == "germination_watering")
    assert ordinary.params["times"] == programme.STANDARD_SEEDBED.passes
    assert "chitted_seed_cannot_dry" not in ordinary.reasons
    # Same water to put back either way; the chitted day divides it into more, smaller goes.
    assert seedbed.params["mm"] < ordinary.params["mm"]


def test_a_lawn_sown_all_over_is_watered_by_its_seedbed_and_not_at_dawn_as_well() -> None:
    """The passes are the day's watering, sized from the deficit, not two millimetres of damp."""
    whole = _ctx(days_since_sowing=2, sowing_kind="overseed", deficit_mm=12.0)
    assert whole.seedbed_covers_zone
    assert whole.seedbed_target_mm == 12.0
    seedbed = next(a for a in rules.evaluate(whole) if a.code == "germination_watering")
    assert seedbed.params["daily_mm"] == 12.0, "the day's passes cover what the root zone lost"
    assert seedbed.params["minutes"] == 16, "4 mm a pass at 4 minutes a millimetre"
    assert "seedbed_day_replaces_dawn_cycle" in seedbed.reasons

    # A few patches sown into standing turf is the other job: the passes stay surface water
    # and the lawn around them keeps the deep cycle it still needs.
    patches = _ctx(days_since_sowing=2, sowing_kind="repair", deficit_mm=25.0)
    assert not patches.seedbed_covers_zone
    # The dawn cycle does the root zone, so the patches owe only the damp floor -- the
    # deficit, however deep, is none of their business.
    assert patches.seedbed_target_mm == programme.STANDARD_SEEDBED.daily_mm
    advice = rules.evaluate(patches)
    patched = next(a for a in advice if a.code == "germination_watering")
    assert patched.params["mm"] == programme.STANDARD_SEEDBED.mm
    assert "seedbed_day_replaces_dawn_cycle" not in patched.reasons
    assert "irrigate_now" in _codes(advice), "the turf around the patches has deep roots"


def test_a_seedbed_pass_is_never_heavy_enough_to_move_the_seed() -> None:
    """A dry spell does not turn three light passes into three runs that wash the seed about."""
    parched = _ctx(days_since_sowing=2, sowing_kind="overseed", deficit_mm=40.0)
    depths = parched.seedbed_depths_mm
    assert max(depths) <= water.max_seedbed_application("loam")
    # What will not fit is not forced into the day; the balance carries it to tomorrow.
    assert sum(depths) < parched.seedbed_target_mm


def test_chitted_seed_drops_back_to_the_ordinary_regime_once_it_is_up() -> None:
    up = programme.PRE_GERMINATED_CRITICAL_DAYS + 2
    advice = rules.evaluate(_ctx(days_since_sowing=up, sown_pre_germinated=True, deficit_mm=25.0))
    seedbed = next(a for a in advice if a.code == "germination_watering")
    assert seedbed.params["times"] == programme.STANDARD_SEEDBED.passes


def test_an_overseeding_is_taken_at_its_word_when_the_lawn_has_no_birthday() -> None:
    """The recorded kind beats the arithmetic, which needs an establishment date to work.

    A blank establishment date used to turn every overseeding into a bare-soil sowing and
    hold the mower for three weeks over turf that had to keep being cut, or it shades the
    seedlings it was sown into out.
    """
    sown = _ctx(
        days_since_sowing=4,
        establishment_age_days=None,
        sowing_kind="overseed",
        days_since_mowing=6,
    )
    assert sown.overseeded
    assert not rules.mower_held(sown)
    assert "hold_mowing_after_sowing" not in _codes(rules.evaluate(sown))

    # And a lawn sown from bare soil says so, and keeps the mower off.
    bare = _ctx(days_since_sowing=4, establishment_age_days=None, sowing_kind="new_lawn")
    assert not bare.overseeded
    assert rules.mower_held(bare)


def test_a_lawn_scalped_before_seed_is_walked_back_up_not_left_there() -> None:
    """20 mm is right for getting seed to the soil and wrong for a fescue to live at."""
    scalped = _ctx(last_mow_height_mm=20, days_since_mowing=1)
    advice = rules.evaluate(scalped)
    climb = next(a for a in advice if a.code == "raise_height_after_low_cut")
    assert climb.params["kept_mm"] == 20
    assert climb.params["target_mm"] == 75, "the middle of the 60-90 range this fescue wants"
    assert climb.params["height_mm"] == 30, "half again, not the whole way in one cut"
    assert "cut_below_species_range" in climb.reasons
    assert "mowing_height" not in _codes(advice)


def test_the_cut_that_was_made_sets_the_interval_not_the_one_that_was_wanted() -> None:
    """The wait is the distance from where the lawn stands to where a cut takes a third off.

    Both these lawns are cut to the same 75 mm and both were last cut three days ago; what
    differs is where they are standing, which is the one thing the advice used not to know.
    The third rule trips at half again the height being cut to, so the lawn left long is
    nearly there and the lawn taken low has most of the distance still to grow.
    """
    standing_tall = _ctx(last_mow_height_mm=90, days_since_mowing=3)
    standing_low = _ctx(last_mow_height_mm=60, days_since_mowing=3)
    assert standing_tall.kept_height_mm == 90
    assert standing_low.kept_height_mm == 60

    sooner = next(a for a in rules.evaluate(standing_tall) if a.code == "mowing_height")
    later = next(a for a in rules.evaluate(standing_low) if a.code == "mowing_height")
    assert sooner.params["next_in_days"] < later.params["next_in_days"]

    # With nothing recorded the target is still the best guess there is.
    assert _ctx().kept_height_mm == 75


def test_rain_expected_tomorrow_takes_passes_off_the_seedbed() -> None:
    """The passes are watering, and watering that rain has already done is waste.

    Worse than waste on a seedbed: water on a canopy at an hour nothing will dry it is what
    damping-off and dollar spot want, and running sprinklers into rain is the thing that
    makes somebody stop trusting the advice.
    """
    dry = _ctx(days_since_sowing=3, sowing_kind="overseed", deficit_mm=6.2)
    assert len(dry.seedbed_depths_mm) == programme.STANDARD_SEEDBED.passes

    # A shower takes the morning off the day and leaves the late pass, because a daily total
    # says nothing about the hour it fell at.
    shower = _ctx(
        days_since_sowing=3, sowing_kind="overseed", deficit_mm=0.0, forecast_rain_tomorrow_mm=6.0
    )
    assert len(shower.seedbed_depths_mm) == 1
    advice = next(a for a in rules.evaluate(shower) if a.code == "germination_watering")
    assert advice.params["times"] == 1
    assert "rain_covers_part_of_the_day" in advice.reasons

    # A real soaking takes the whole day, and says so rather than going quiet.
    soaked = _ctx(
        days_since_sowing=3, sowing_kind="overseed", deficit_mm=0.0, forecast_rain_tomorrow_mm=25.0
    )
    assert soaked.seedbed_depths_mm == []
    rained = next(a for a in rules.evaluate(soaked) if a.code == "seedbed_rain_enough")
    assert rained.params["expected_mm"] > 0
    assert "rain_keeps_the_seedbed_damp" in rained.reasons
    assert "germination_watering" not in _codes(rules.evaluate(soaked))


def test_the_seedbed_reads_tomorrows_rain_not_this_afternoons() -> None:
    """The passes run in tomorrow's daylight, and the plan is made the evening before.

    The 24-hour figure is today and tomorrow together, which is the right window for a cycle
    that runs before tomorrow's dawn and the wrong one here: rain forecast for this afternoon
    is in the balance by the time these passes run, and counting it twice leaves a seedbed
    dry on the strength of rain that already fell.
    """
    today_only = _ctx(
        days_since_sowing=3,
        sowing_kind="overseed",
        deficit_mm=6.2,
        forecast_rain_24h_mm=20.0,
        forecast_rain_tomorrow_mm=0.0,
    )
    assert today_only.seedbed_rain_mm == 0.0
    assert len(today_only.seedbed_depths_mm) == programme.STANDARD_SEEDBED.passes


def test_a_patch_repair_is_rained_off_too_but_keeps_its_dawn_cycle() -> None:
    """Rain wets a patch of seed as well as it wets a whole lawn."""
    soaked = _ctx(
        days_since_sowing=3, sowing_kind="repair", deficit_mm=25.0, forecast_rain_tomorrow_mm=25.0
    )
    assert soaked.seedbed_depths_mm == []
    codes = _codes(rules.evaluate(soaked))
    assert "seedbed_rain_enough" in codes
    # The root zone is still 25 mm down and the turf around the patches still has roots in it.
    assert "irrigate_now" in codes or "hold_irrigation_rain_coming" in codes


def test_a_recovery_cut_made_late_is_made_higher_not_at_the_height_it_was_due_at() -> None:
    """Half again the last cut is where the climb is going, not what today is allowed to do.

    A sward taken to 20 mm before seed is due its next cut at 30 mm four days later. Left a
    week, it is standing near 60 mm, and 30 mm then takes half the leaf off -- a scalp, on
    grass that is also carrying new seed. The climb sets the floor; the leaf standing there
    sets the floor under that, and the higher of the two is what the deck is set to.
    """
    on_time = _ctx(last_mow_height_mm=20, days_since_mowing=4)
    assert rules.mowing_plan(on_time).height_mm == 30

    late = _ctx(last_mow_height_mm=20, days_since_mowing=7)
    cut = rules.mowing_plan(late)
    assert cut.height_mm == 45, "two thirds of the leaf standing after a week of autumn growth"
    assert cut.due_height_mm == 30, "and the climb it is still on says where it is going"
    assert cut.height_mm % 5 == 0, "a deck is set in notches, not in millimetres"
    # The cut does not fall due any later for being made higher.
    assert cut.interval_days == rules.mowing_plan(on_time).interval_days


def test_a_lawn_with_no_push_mower_is_told_what_it_can_actually_do() -> None:
    """Telling somebody who owns only a robot to use the push mower is not advice.

    The cut still has to be made -- the old grass shades the seedlings out -- so the answer
    is the other thing that can be done: one pass, high, on dry grass, off the schedule.
    """
    robot_only = _ctx(
        days_since_sowing=7,
        establishment_age_days=92,
        days_since_mowing=9,
        robot_mower=True,
        hand_mower=False,
    )
    advice = rules.evaluate(robot_only)
    one_pass = next(a for a in advice if a.code == "mow_one_robot_pass_while_seed_roots")
    assert one_pass.params["days_left"] == 7
    assert "no_hand_mower" in one_pass.reasons
    assert "robot_wheels_tear_seedlings" in one_pass.reasons
    assert "mow_by_hand_while_seed_roots" not in _codes(advice)

    # With a push mower in the shed the advice is still to use it.
    with_hand = _ctx(
        days_since_sowing=7, establishment_age_days=92, days_since_mowing=9, robot_mower=True
    )
    assert "mow_by_hand_while_seed_roots" in _codes(rules.evaluate(with_hand))
