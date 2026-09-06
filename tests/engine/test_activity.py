"""One state an automation can act on, and what ends it."""

from __future__ import annotations

import pathlib
from typing import Any

from custom_components.hosekeeper.engine import activity

NOW = "2026-09-06T05:00:00+02:00"


def _current(**overrides: Any) -> activity.Activity:
    base: dict[str, Any] = {
        "zone": "North lawn",
        "zone_id": "zone1",
        "config_entry_id": "abc123",
        "now_iso": NOW,
        "advice": [],
        "irrigation_cycle": None,
        "irrigation_plan": {},
        "mowing_open": False,
        "mowing_window": {},
        "logged_today": set(),
        "has_valve": False,
        "has_robot": False,
    }
    return activity.current(**(base | overrides))


def test_an_idle_lawn_says_so() -> None:
    doing = _current()
    assert doing.state == "idle"
    assert doing.mode is None
    assert doing.details["zone"] == "North lawn"
    assert doing.details["target_entity_id"] is None


def test_every_state_names_the_lawn_and_what_to_act_on() -> None:
    """One template has to work for every state, so the two keys are always in the same place.

    A `valve` key on watering and a `mower` key on cutting means two automations where one
    would do, and nothing at all to act on for the states that have neither.
    """
    cases = [
        _current(),
        _current(
            irrigation_cycle="main",
            irrigation_plan={"cycles": []},
            has_valve=True,
            valve_entity="switch.zona1",
        ),
        _current(mowing_open=True, has_robot=True, mower_entity="lawn_mower.robot"),
        _current(advice=[{"code": "feed_now", "params": {}}]),
        _current(advice=[{"code": "irrigate_now", "params": {}}]),
    ]
    for doing in cases:
        assert "target_entity_id" in doing.details, doing.state
        assert doing.details["config_entry_id"] == "abc123", doing.state
        assert doing.details["zone_id"] == "zone1", doing.state
        assert doing.details["zone"] == "North lawn", doing.state
    assert cases[1].details["target_entity_id"] == "switch.zona1"
    assert cases[2].details["target_entity_id"] == "lawn_mower.robot"
    assert cases[3].details["target_entity_id"] is None  # a feed has no machine


def test_the_lawn_lists_every_machine_it_has_whatever_it_is_doing() -> None:
    """`target_entity_id` says what to act on now; this says what the lawn has got.

    An automation deciding whether to run at all, or closing a valve a cancelled cycle left
    open, needs the second question answered when the first one is null.
    """
    idle = _current(valve_entity="switch.zona1", mower_entity="lawn_mower.robot")
    assert idle.state == "idle"
    assert idle.details["target_entity_id"] is None
    assert idle.details["target_entity_ids"] == {
        "valve": "switch.zona1",
        "mower": "lawn_mower.robot",
    }

    # A lawn with no machine on it says so rather than leaving the key out.
    bare = _current()
    assert bare.details["target_entity_ids"] == {"valve": None, "mower": None}


def test_a_held_back_machine_is_still_named() -> None:
    """An automation wants to know which mower it is being told not to run."""
    doing = _current(
        advice=[{"code": "mow_by_hand_while_seed_roots", "params": {"days_left": 7}}],
        has_robot=True,
        mower_entity="lawn_mower.robot",
    )
    assert doing.state == "mowing_manual"
    assert doing.details["target_entity_id"] == "lawn_mower.robot"


def test_a_valve_run_carries_its_own_end() -> None:
    """The automation needs to know how long to hold the valve open, per zone."""
    plan = {
        "cycles": [
            {
                "start": "2026-09-06T04:00:00+02:00",
                "end": "2026-09-06T04:12:00+02:00",
                "mm": 3,
                "minutes": 12,
            },
            {
                "start": "2026-09-06T04:57:00+02:00",
                "end": "2026-09-06T05:09:00+02:00",
                "mm": 3,
                "minutes": 12,
            },
        ]
    }
    doing = _current(
        irrigation_cycle="main", irrigation_plan=plan, has_valve=True, valve_entity="switch.zona1"
    )
    assert doing.state == "irrigating_automatic"
    assert doing.mode == "automatic"
    assert doing.details["ends"] == "2026-09-06T05:09:00+02:00"
    assert doing.details["run"] == 2
    assert doing.details["of"] == 2
    assert doing.details["target_entity_id"] == "switch.zona1"


def test_a_lawn_watered_by_hand_waits_for_the_confirmation() -> None:
    """No valve, so the state stands until the diary says it was done."""
    advice = [{"code": "irrigate_now", "params": {"mm": 8, "minutes": 24}}]
    doing = _current(advice=advice)
    assert doing.state == "irrigating_manual"
    assert doing.details["awaiting_confirmation"] is True
    assert doing.details["minutes"] == 24

    done = _current(advice=advice, logged_today={"irrigation"})
    assert done.state == "idle"


def test_the_seedbed_and_the_root_zone_are_different_work() -> None:
    """They share a category and confirming one must not silence the other.

    Damping a seedbed three times is not refilling the root zone, and a state that cleared
    on either would hide the watering the established turf around the seed still needs.
    """
    both = [
        {"code": "germination_watering", "params": {"times": 3, "mm": 2}},
        {"code": "irrigate_now", "params": {"mm": 8, "minutes": 24}},
    ]
    # The root-zone cycle is the more pressing of the two, so it is what the state names.
    assert _current(advice=both).details["advice"] == "irrigate_now"

    # Watering by hand and saying so leaves the seedbed still asking.
    left = _current(advice=both, logged_today={"irrigation"})
    assert left.state == "irrigating_manual"
    assert left.details["advice"] == "germination_watering"

    # Both recorded, nothing left.
    assert _current(advice=both, logged_today={"irrigation", "seedbed_watering"}).state == "idle"


def test_a_lawn_with_a_valve_is_never_asked_to_water_by_hand() -> None:
    advice = [{"code": "irrigate_now", "params": {"mm": 8}}]
    assert _current(advice=advice, has_valve=True).state == "idle"


def test_the_robot_beats_a_job_merely_due() -> None:
    """A run happening now outranks work that is only waiting for someone."""
    advice = [{"code": "feed_now", "params": {"preset": "bottos_autumn_k"}}]
    doing = _current(
        advice=advice,
        mowing_open=True,
        has_robot=True,
        mower_entity="lawn_mower.robot",
        mowing_ends="2026-09-06T20:00:00+02:00",
        mow_height_mm=65,
    )
    assert doing.state == "mowing_automatic"
    assert doing.details["ends"] == "2026-09-06T20:00:00+02:00"
    assert doing.details["height_mm"] == 65

    # With the robot docked the feed is what is outstanding.
    assert _current(advice=advice).state == "fertilizing_manual"


def test_every_state_it_can_return_is_declared() -> None:
    """The sensor's enum options come from STATES, so nothing may fall outside them."""
    declared = set(activity.STATES)
    assert {state for state, _ in activity.MANUAL_WORK} <= declared
    assert {"idle", "irrigating_automatic", "mowing_automatic"} <= declared


def test_a_cut_the_robot_is_held_off_still_asks_a_person() -> None:
    """Held-back machine work is manual work.

    Otherwise the automation runs the very machine the advice is keeping in its dock.
    """
    advice = [{"code": "mow_by_hand_while_seed_roots", "params": {"days_left": 7, "height_mm": 65}}]
    doing = _current(advice=advice, has_robot=True, mower_entity="lawn_mower.robot")
    assert doing.state == "mowing_manual"
    assert doing.details["advice"] == "mow_by_hand_while_seed_roots"
    assert doing.details["days_left"] == 7

    # An ordinary cut on the same lawn is the robot's job and asks nobody.
    assert _current(advice=[{"code": "mow_soon", "params": {}}], has_robot=True).state == "idle"


def test_every_issue_a_person_can_report_is_one_the_engine_reads() -> None:
    """An issue nobody acts on is a question that wastes the reader's attention.

    "thin" was the reverse of this: the plan read it in three places and it was not on the
    list of what could be reported, so those branches could never fire.
    """
    from custom_components.hosekeeper.const import ISSUES
    from custom_components.hosekeeper.engine import nutrition, plan, rules

    source = "\n".join(
        (pathlib.Path(m.__file__).read_text() for m in (rules, plan, nutrition)),
    )
    inert = {issue for issue in ISSUES if f'"{issue}"' not in source}
    # Pests are recorded for the diary and no rule acts on them; everything else must.
    assert inert == {"pests"}, inert
