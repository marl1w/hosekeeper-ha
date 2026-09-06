"""The two factors move for the right reasons and stay in their bounds."""

from __future__ import annotations

import datetime as dt

from custom_components.hosekeeper.engine import adaptation

TODAY = dt.date(2026, 9, 6)


def _obs(
    days_ago: int, status: str | None, deficit: float, issues: set[str] | None = None
) -> adaptation.Observation:
    return adaptation.Observation(
        TODAY - dt.timedelta(days=days_ago), status, deficit, 22.5, 0.0, frozenset(issues or ())
    )


def test_due_weekly() -> None:
    assert adaptation.due(adaptation.default_state(), TODAY)
    assert not adaptation.due({"last_evaluated": "2026-09-03"}, TODAY)
    assert adaptation.due({"last_evaluated": "2026-08-30"}, TODAY)


def test_dry_and_declining_waters_more() -> None:
    days = [_obs(i, "poor" if i % 2 else "fair", 30.0) for i in range(1, 8)]
    state = adaptation.evaluate(adaptation.default_state(), days, TODAY)
    assert state["irrigation_factor"] == 1.1
    assert state["history"][-1]["reason"] == "dry_and_declining"
    assert state["last_evaluated"] == TODAY.isoformat()


def test_wet_and_diseased_waters_less_and_feeds_less() -> None:
    days = [_obs(i, "fair", 2.0, {"fungus"}) for i in range(1, 8)]
    state = adaptation.evaluate(adaptation.default_state(), days, TODAY)
    assert state["irrigation_factor"] == 0.9
    assert state["feed_factor"] == 1.15
    reasons = {h["reason"] for h in state["history"]}
    assert reasons == {"wet_and_declining", "disease_less_nitrogen"}


def test_thriving_lawn_saves_water_slowly_and_never_below_the_floor() -> None:
    state = adaptation.default_state()
    for week in range(20):
        when = TODAY + dt.timedelta(weeks=week)
        days = [
            adaptation.Observation(
                when - dt.timedelta(days=i), "excellent", 10.0, 22.5, 0.0, frozenset()
            )
            for i in range(1, 8)
        ]
        state = adaptation.evaluate(state, days, when)
    assert state["irrigation_factor"] == 0.75


def test_too_few_ratings_change_nothing() -> None:
    days = [_obs(1, "poor", 30.0), _obs(2, None, 30.0)]
    state = adaptation.evaluate(adaptation.default_state(), days, TODAY)
    assert state["irrigation_factor"] == 1.0
    assert state["history"] == []
