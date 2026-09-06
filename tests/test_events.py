"""The shape of the calendar: what one job looks like, whatever day it falls on."""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from typing import Any

from custom_components.hosekeeper import events

TZ = dt.timezone(dt.timedelta(hours=2))
TODAY = dt.date(2026, 9, 6)


def _cycle(hour: int, minutes: int, mm: float) -> dict[str, Any]:
    start = dt.datetime.combine(TODAY, dt.time(hour, 0), tzinfo=TZ)
    return {
        "start": start.isoformat(),
        "end": (start + dt.timedelta(minutes=minutes)).isoformat(),
        "mm": mm,
        "minutes": minutes,
    }


def _build(state: SimpleNamespace) -> list[dict[str, Any]]:
    field = SimpleNamespace(name="South lawn")
    diary = SimpleNamespace(recent=lambda count, until=TODAY: [])
    return events.build(field, "abc", diary, state, TODAY, dt.time(6, 55), TZ, "loam")


def _state(**kwargs: Any) -> SimpleNamespace:
    base: dict[str, Any] = {
        "irrigation_plan": {},
        "agenda": [],
        "plan": [],
        "heat_stress": False,
    }
    return SimpleNamespace(**(base | kwargs))


def _seedbed_agenda(date: dt.date) -> list[dict[str, Any]]:
    return [
        {
            "date": date.isoformat(),
            "code": "germination_watering",
            "category": "irrigation",
            "params": {"times": 3, "mm": 2},
        }
    ]


def test_seedbed_watering_is_one_entry_carrying_its_hours() -> None:
    """A day of light waterings is one line, and the line names the three hours."""
    found = [
        e
        for e in _build(_state(agenda=_seedbed_agenda(TODAY + dt.timedelta(days=2))))
        if e["code"] == "germination_watering"
    ]
    assert len(found) == 1
    assert found[0]["params"]["at"] == ["11:00", "14:00", "17:00"]
    assert not found[0]["all_day"]


def test_the_decided_day_keeps_the_same_shape() -> None:
    """The day whose runs are already timed reads like every other day, not as three rows."""
    plan = {
        "date": TODAY.isoformat(),
        "germination": [_cycle(11, 4, 2.0), _cycle(14, 4, 2.0), _cycle(17, 4, 2.0)],
    }
    found = [
        e
        for e in _build(_state(agenda=_seedbed_agenda(TODAY), irrigation_plan=plan))
        if e["code"] == "germination_watering"
    ]
    assert len(found) == 1
    assert found[0]["params"] == {
        "times": 3,
        "mm": 2.0,
        "minutes": 4,
        "at": ["11:00", "14:00", "17:00"],
    }


def test_a_planned_month_is_filed_on_the_first() -> None:
    """A month-long job is dated by its month; the panel prints no day for it."""
    plan = [
        {
            "month": "2026-10",
            "code": "feed_october_autumn",
            "category": "fertilizing",
            "status": "planned",
            "optional": False,
            "params": {"preset": "bottos_autumn_k", "npk_class": "1-0-1"},
        }
    ]
    found = [e for e in _build(_state(plan=plan)) if e["kind"] == "planned"]
    assert [(e["date"], e["params"]["operation"]) for e in found] == [
        ("2026-10-01", "feed_october_autumn")
    ]
    assert found[0]["all_day"]
