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
    assert found[0]["params"]["at"] == ["09:00", "13:00", "17:00"]
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
        # The total is the decided day's own, not the one the agenda projected: the plan that
        # was settled may have landed on a different count from the one the week expected.
        "total_minutes": 12,
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


def test_a_zone_behind_another_waters_its_seedbed_later() -> None:
    """The calendar lays an undecided day out the way the morning will lay it out.

    One valve serves the lawn a zone at a time, so the second zone's passes start where the
    first zone's finish. Drawing every zone at eleven promises something the plan itself
    never makes and nobody could carry out.
    """
    ahead = _build(_state(agenda=_seedbed_agenda(TODAY + dt.timedelta(days=2))))
    behind = _build(
        _state(agenda=_seedbed_agenda(TODAY + dt.timedelta(days=2)), seedbed_queue_min=7)
    )
    first = next(e for e in ahead if e["code"] == "germination_watering")
    second = next(e for e in behind if e["code"] == "germination_watering")
    assert first["params"]["at"] == ["09:00", "13:00", "17:00"]
    assert second["params"]["at"] == ["09:07", "13:07", "17:07"]
    assert second["start"] > first["start"]


def _diary(pages: dict[dt.date, dict[str, Any]]):
    """Return a diary whose days are the ones given, as `build` reads them."""
    return SimpleNamespace(
        recent=lambda count, until=TODAY: [
            (until - dt.timedelta(days=offset), pages.get(until - dt.timedelta(days=offset), {}))
            for offset in range(count - 1, -1, -1)
        ]
    )


def _asked(code: str = "germination_watering", **params: Any) -> dict[str, Any]:
    return {
        "date": (TODAY - dt.timedelta(days=1)).isoformat(),
        "code": code,
        "category": "irrigation",
        "params": {"times": 3, "mm": 2, "hours": ["09:00", "13:00", "17:00"], **params},
        "reasons": ["keep_the_seedbed_damp"],
    }


def test_yesterdays_lines_come_back_to_be_ticked_off() -> None:
    """A job done yesterday and not written down still has the line that asked for it.

    The agenda only looks forward, so at midnight yesterday's lines are gone and there is
    nothing left to confirm. The day keeps its own, and the day after offers them back.
    """
    yesterday = TODAY - dt.timedelta(days=1)
    found = [
        e
        for e in events.build(
            SimpleNamespace(name="South lawn"),
            "abc",
            _diary({yesterday: {"asked": [_asked()]}}),
            _state(),
            TODAY,
            dt.time(6, 55),
            TZ,
            "loam",
        )
        if e["kind"] == "unrecorded"
    ]
    assert len(found) == 1
    assert found[0]["date"] == yesterday.isoformat()
    assert found[0]["code"] == "germination_watering"
    # The hours the passes were asked for, under the name the panel reads them by, so the
    # line says "09:00 · 13:00 · 17:00" on yesterday's page exactly as it did on its own.
    assert found[0]["params"]["at"] == ["09:00", "13:00", "17:00"]
    assert "hours" not in found[0]["params"]
    assert found[0]["reasons"] == ["keep_the_seedbed_damp"]


def test_only_yesterday_is_offered_back() -> None:
    """One day and no further.

    Nobody remembers which Tuesday they mowed on, and a fortnight of unticked boxes is a
    reproach rather than a diary. Older work is entered through Tracking, which asks for the
    date; today's own lines are the agenda's, not the diary's copy of them.
    """
    pages = {TODAY - dt.timedelta(days=offset): {"asked": [_asked()]} for offset in (0, 2, 3, 9)}
    found = [
        e
        for e in events.build(
            SimpleNamespace(name="South lawn"),
            "abc",
            _diary(pages),
            _state(),
            TODAY,
            dt.time(6, 55),
            TZ,
            "loam",
        )
        if e["kind"] == "unrecorded"
    ]
    assert found == []
