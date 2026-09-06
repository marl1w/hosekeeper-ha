"""What the lawn is busy with right now, as one value an automation can act on.

Eleven sensors is a good way to answer eleven questions and a poor way to answer the only
one an automation asks: what should be happening on this lawn at this moment, and is a
machine doing it or am I? So there is one state, and the detail is in its attributes.

The states split on two axes. What the job is — watering, cutting, feeding — and who does
it. A lawn with a valve on it waters itself, and the state lasts exactly as long as the run
the coordinator timed. A lawn without one is watered by hand, and the state lasts until the
diary says it was done, however long that takes. Automations key on the first and the
second and need nothing else from Hosekeeper.

Nothing here imports Home Assistant, so the preview shows the same states the box will.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from typing import Any

IDLE = "idle"

# The state, as an automation reads it. The kind of work first, then who is doing it.
STATES: tuple[str, ...] = (
    IDLE,
    "irrigating_automatic",
    "irrigating_manual",
    "mowing_automatic",
    "mowing_manual",
    "fertilizing_manual",
    "seeding_manual",
    "weeding_manual",
    "aeration_manual",
    "treatment_manual",
    "leaf_clearing_manual",
)

# The rules can ask for a job by hand on a lawn that has the machine for it. A robot is kept
# off new seed while its wheels would tear the seedlings up, and the cut is still due: the
# state has to say "you", not "the robot", or the automation runs the very machine the advice
# is holding back.
BY_HAND_ANYWAY: frozenset[str] = frozenset({"mow_by_hand_while_seed_roots"})

# Which advice codes mean a job is waiting for a person, and what the diary has to record
# before that job counts as done. The kind is per code, not per state, because watering the
# seedbed and refilling the root zone are the same category and different work: confirming
# one must not silence the other.
MANUAL_WORK: tuple[tuple[str, dict[str, str]], ...] = (
    (
        "irrigating_manual",
        {
            "irrigate_now": "irrigation",
            "irrigate_dormant_drought": "irrigation",
            "establish_sod_water_daily": "irrigation",
            "germination_watering": "seedbed_watering",
            "establish_seed_keep_moist": "seedbed_watering",
        },
    ),
    (
        "mowing_manual",
        {
            "mow_by_hand_while_seed_roots": "mowing",
            "mow_now_third_rule": "mowing",
            "mow_soon": "mowing",
            "establish_first_mow_high": "mowing",
        },
    ),
    ("fertilizing_manual", {"feed_now": "fertilizing", "establish_starter_feed": "fertilizing"}),
    ("seeding_manual", {"overseed_now": "sowing"}),
    (
        "weeding_manual",
        {
            "weed_control_broadleaf_now": "weeding",
            "weed_control_grassy_now": "weeding",
            "moss_control_now": "weeding",
        },
    ),
    (
        "aeration_manual",
        {"aerate_now": "aeration", "scarify_now": "scarifying", "top_dress_now": "top_dressing"},
    ),
    (
        "treatment_manual",
        {"disease_preventive_now": "treatment", "fungus_seen_measures": "treatment"},
    ),
    ("leaf_clearing_manual", {"clear_leaves": "leaf_clearing"}),
)


@dataclass(frozen=True, slots=True)
class Activity:
    """One state and the detail behind it."""

    state: str
    details: dict[str, Any] = dc_field(default_factory=dict)

    @property
    def mode(self) -> str | None:
        """Return automatic, manual, or nothing at all when the lawn is idle."""
        if self.state == IDLE:
            return None
        return "automatic" if self.state.endswith("_automatic") else "manual"

    @property
    def kind(self) -> str | None:
        """Return the work itself, without who is doing it."""
        if self.state == IDLE:
            return None
        return self.state.rsplit("_", 1)[0]


def _cycle_detail(plan: dict[str, Any], cycle: str, now_iso: str) -> dict[str, Any]:
    """Return the run that is under way, so an automation knows when it ends."""
    runs = plan.get("germination" if cycle == "germination" else "cycles") or []
    for index, run in enumerate(runs):
        if run.get("start") and run.get("end") and run["start"] <= now_iso <= run["end"]:
            detail = {
                "started": run["start"],
                "ends": run["end"],
                "minutes": run.get("minutes"),
                "mm": run.get("mm"),
            }
            if len(runs) > 1:
                detail |= {"run": index + 1, "of": len(runs)}
            return detail
    if cycle == "syringe" and plan.get("syringe_start"):
        return {"started": plan["syringe_start"], "ends": plan.get("syringe_end")}
    return {}


def current(
    *,
    zone: str,
    zone_id: str | None = None,
    config_entry_id: str | None = None,
    now_iso: str,
    advice: list[dict[str, Any]],
    irrigation_cycle: str | None,
    irrigation_plan: dict[str, Any],
    mowing_open: bool,
    mowing_window: dict[str, Any],
    mowing_ends: str | None = None,
    mow_height_mm: int | None = None,
    logged_today: set[str],
    has_valve: bool,
    has_robot: bool,
    valve_entity: str | None = None,
    mower_entity: str | None = None,
) -> Activity:
    """Return what this lawn is busy with, machine work first.

    A run that is happening beats a job that is merely due, and a machine's run beats a
    person's, because the machine's is the one with an end time on it. Everything else waits
    its turn behind them in the order the rules rank it.
    """
    # Every state names the same things in the same places: which zone this is, which lawn it
    # belongs to, and what to act on. One template then works for watering, cutting and
    # everything after them, which a `valve` key on one state and a `mower` key on another
    # does not allow. The zone is what the diary and the panel are keyed on; the entry is the
    # lawn, which is what `config_entry_id` means everywhere else in Home Assistant.
    base: dict[str, Any] = {
        "zone": zone,
        "zone_id": zone_id,
        "config_entry_id": config_entry_id,
    }
    # What is wrong, beside what to do. A lawn watering at dawn under a dollar spot warning
    # has one state and two facts, and an automation that had to read a second entity for the
    # second fact would be back to the row of booleans this replaced.
    base["alerts"] = [
        item["code"]
        for item in advice
        if item.get("category") == "disease" and item["priority"] <= 2
    ]
    # Every machine this lawn has, by the job it does, whatever is happening at this moment.
    # `target_entity_id` answers "what do I act on now" and is null between jobs; this answers
    # "what has this lawn got", which is what an automation needs when it is deciding whether
    # to run at all, or wants to turn a valve off that a cancelled cycle left open. Both keys
    # are always present, so a template never has to test for the shape.
    base["target_entity_ids"] = {"valve": valve_entity, "mower": mower_entity}

    if irrigation_cycle is not None and has_valve:
        return Activity(
            "irrigating_automatic",
            base
            | {
                "mode": "automatic",
                "activity": "irrigating",
                "cycle": irrigation_cycle,
                "target_entity_id": valve_entity,
                **_cycle_detail(irrigation_plan, irrigation_cycle, now_iso),
            },
        )
    if mowing_open and has_robot:
        return Activity(
            "mowing_automatic",
            base
            | {
                "mode": "automatic",
                "activity": "mowing",
                "target_entity_id": mower_entity,
                "ends": mowing_ends,
                "height_mm": mow_height_mm,
                "reasons": list(mowing_window.get("reasons") or ()),
            },
        )

    by_code = {item["code"]: item for item in advice}
    for state, codes in MANUAL_WORK:
        hit = next(
            (
                by_code[code]
                for code, kind in codes.items()
                if code in by_code and kind not in logged_today
            ),
            None,
        )
        if hit is None:
            continue
        kind = codes[hit["code"]]
        # A lawn that waters or mows itself does not ask a person to do it, unless the rules
        # are deliberately keeping the machine off.
        machine = (state == "irrigating_manual" and has_valve) or (
            state == "mowing_manual" and has_robot
        )
        if machine and hit["code"] not in BY_HAND_ANYWAY:
            continue
        # A machine being deliberately held back is still the machine in question, and an
        # automation wants to know which one it is not to run.
        target = None
        if state == "irrigating_manual":
            target = valve_entity
        elif state == "mowing_manual":
            target = mower_entity
        return Activity(
            state,
            base
            | {
                "mode": "manual",
                "activity": kind,
                "awaiting_confirmation": True,
                "advice": hit["code"],
                "target_entity_id": target,
                **(hit.get("params") or {}),
            },
        )
    return Activity(IDLE, base | {"mode": None, "activity": None, "target_entity_id": None})
