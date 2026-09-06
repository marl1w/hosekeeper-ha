"""Learning from the lawn: two bounded multipliers that move with the tracked condition.

The irrigation factor scales how much (and how early) the engine waters; the feed factor
scales nitrogen down when the lawn is telling us it has had enough. Each weekly evaluation
records why it moved, so the panel can show the reasoning and a user can disagree with it.
The bounds keep a run of bad ratings from ever turning into a flooded or a starved lawn:
research puts acceptable cool-season quality between 60 and 100 % of ET replacement, and the
factor cannot leave that band.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import datetime as dt
from typing import Any

from .rules import STATUS_SCORE

IRRIGATION_BOUNDS = (0.65, 1.3)
FEED_BOUNDS = (0.8, 1.5)
EVALUATION_INTERVAL_DAYS = 7
MIN_RATINGS = 3


@dataclass(frozen=True, slots=True)
class Observation:
    """One day as the adaptation sees it."""

    date: dt.date
    status: str | None
    deficit_mm: float | None
    raw_mm: float
    rain_mm: float
    issues: frozenset[str]


def default_state() -> dict[str, Any]:
    """Return the state a new field starts with."""
    return {
        "irrigation_factor": 1.0,
        "feed_factor": 1.0,
        "last_evaluated": None,
        "history": [],
    }


def due(state: dict[str, Any], today: dt.date) -> bool:
    """Return whether a week has passed since the last evaluation."""
    last = state.get("last_evaluated")
    if not last:
        return True
    return (today - dt.date.fromisoformat(last)).days >= EVALUATION_INTERVAL_DAYS


def evaluate(state: dict[str, Any], days: Sequence[Observation], today: dt.date) -> dict[str, Any]:
    """Return the state after looking at the last weeks, with the reasoning appended."""
    new = dict(state)
    new.setdefault("irrigation_factor", 1.0)
    new.setdefault("feed_factor", 1.0)
    history = list(new.get("history", []))
    recent = [d for d in days if (today - d.date).days < 14]
    older = [d for d in days if 14 <= (today - d.date).days < 28]
    ratings = [STATUS_SCORE[d.status] for d in recent if d.status in STATUS_SCORE]
    changes: list[dict[str, Any]] = []

    if len(ratings) >= MIN_RATINGS:
        score = sum(ratings) / len(ratings)
        with_deficit = [d for d in recent if d.deficit_mm is not None]
        dry_share = (
            sum(1 for d in with_deficit if d.deficit_mm > d.raw_mm) / len(with_deficit)
            if with_deficit
            else 0.0
        )
        wet_share = (
            sum(1 for d in with_deficit if d.deficit_mm < d.raw_mm * 0.25) / len(with_deficit)
            if with_deficit
            else 0.0
        )
        issues = set().union(*(d.issues for d in recent))
        older_ratings = [STATUS_SCORE[d.status] for d in older if d.status in STATUS_SCORE]
        declining = bool(older_ratings) and score < sum(older_ratings) / len(older_ratings) - 0.3

        if score < 2.5 and dry_share >= 0.3:
            changes.append(
                _move(new, "irrigation_factor", +0.1, IRRIGATION_BOUNDS, "dry_and_declining")
            )
        elif score < 2.5 and wet_share >= 0.6 and ({"fungus", "moss"} & issues or declining):
            changes.append(
                _move(new, "irrigation_factor", -0.1, IRRIGATION_BOUNDS, "wet_and_declining")
            )
        elif score >= 3.5 and len(ratings) >= 5 and new["irrigation_factor"] > 0.75:
            changes.append(
                _move(new, "irrigation_factor", -0.05, IRRIGATION_BOUNDS, "thriving_save_water")
            )

        if "fungus" in issues:
            changes.append(_move(new, "feed_factor", +0.15, FEED_BOUNDS, "disease_less_nitrogen"))
        elif score < 2.0 and not issues and new["feed_factor"] > 1.0:
            changes.append(_move(new, "feed_factor", -0.1, FEED_BOUNDS, "poor_without_disease"))

    new["last_evaluated"] = today.isoformat()
    for change in changes:
        if change is not None:
            history.append({"date": today.isoformat(), **change})
    new["history"] = history[-52:]
    return new


def _move(
    state: dict[str, Any], key: str, delta: float, bounds: tuple[float, float], reason: str
) -> dict[str, Any] | None:
    before = float(state[key])
    after = round(max(bounds[0], min(bounds[1], before + delta)), 2)
    if after == before:
        return None
    state[key] = after
    return {"factor": key, "from": before, "to": after, "reason": reason}
