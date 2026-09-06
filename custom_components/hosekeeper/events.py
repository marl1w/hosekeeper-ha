"""Everything that happened or should happen on a lawn, as calendar events.

One list feeds both the `calendar` entity and the panel: what was logged (from the diary),
what the week's agenda projects, what the month plan still owes, and the alerts standing
today. Times are attached where they mean something — a dawn cycle, a mowing window — and
everything else is an all-day event.
"""

from __future__ import annotations

import contextlib
import datetime as dt
from typing import Any

from homeassistant.util import dt as dt_util

from .diary import Diary
from .engine import schedule
from .field import FieldConfig

PAST_DAYS = 62
LOGGED_DETAIL_KEYS = ("height_mm", "n_g_m2", "dose_g_m2", "product", "name", "kind")
TITLES: dict[str, dict[str, str]] = {
    # Calendar entity summaries. The panel has its own, richer, tables.
    "en": {
        "irrigate": "Irrigate {mm} mm",
        "irrigation_done": "Irrigated {mm} mm",
        "syringe": "Midday syringing",
        "mow": "Mow at {height_mm} mm",
        "mowing": "Mowing",
        "fertilizing": "Fertilizing",
        "sowing": "Sowing",
        "weeding": "Weeding",
        "aeration": "Aeration",
        "scarifying": "Scarifying",
        "top_dressing": "Top dressing",
        "treatment": "Treatment",
        "leaf_clearing": "Leaf clearing",
        "rating": "Lawn rated {status}",
        "issue": "Issue seen: {issue}",
        "no_good_day": "No good day this week: {operation}",
        "planned_month": "This month: {operation}",
        "dollar_spot_risk": "Dollar spot risk",
        "brown_patch_risk": "Brown patch risk",
        "fungus_seen_measures": "Fungus: adjust care",
        "disease_preventive_now": "Preventive fungicide",
        # operations
        "winter_rest": "Winter rest",
        "summer_rest": "Summer rest",
        "moss_control": "Moss control",
        "pre_emergent": "Pre-emergent herbicide",
        "first_mow": "First mow",
        "feed_march_starter": "Starter feed",
        "feed_april_greening": "Greening feed",
        "feed_may_greening": "Greening feed",
        "feed_june_summer": "Summer potassium feed",
        "feed_july_summer": "Summer potassium feed",
        "feed_october_autumn": "Autumn potassium feed",
        "feed_november_autumn": "Autumn potassium feed",
        "feed_spring_start": "Spring feed",
        "feed_late_spring": "Late spring feed",
        "feed_summer_stress": "Summer feed",
        "feed_early_autumn": "Early autumn feed",
        "feed_late_autumn": "Late autumn feed",
        "aeration_spring": "Aeration",
        "aeration_autumn": "Aeration",
        "scarify_dethatch": "Scarifying",
        "weed_control_broadleaf": "Broadleaf weed control",
        "weed_control_grassy": "Grassy weed control",
        "mow_routine": "Mowing, every {interval_days} days at {height_mm} mm",
        "mow_routine_robot": "Robot out every {interval_days} days, {height_mm} mm",
        "mow_routine_robot_daily": "Robot out every day, {height_mm} mm",
        "raise_mowing_height": "Raise mowing height",
        "last_mow_lower": "Last mow, lower",
        "disease_preventive": "Preventive fungicide",
        "irrigation_deep_infrequent": "Deep, infrequent irrigation",
        "summer_watch": "Summer watch",
        "prepare_overseeding": "Prepare overseeding",
        "overseed": "Overseeding",
        "clear_leaves": "Clear leaves",
    },
    "it": {
        "irrigate": "Irriga {mm} mm",
        "irrigation_done": "Irrigato {mm} mm",
        "syringe": "Rinfrescata di mezzogiorno",
        "mow": "Taglio a {height_mm} mm",
        "mowing": "Taglio",
        "fertilizing": "Concimazione",
        "sowing": "Semina",
        "weeding": "Diserbo",
        "aeration": "Arieggiatura",
        "scarifying": "Scarificatura",
        "top_dressing": "Top dressing",
        "treatment": "Trattamento",
        "leaf_clearing": "Raccolta foglie",
        "rating": "Prato valutato {status}",
        "issue": "Problema: {issue}",
        "no_good_day": "Nessun giorno adatto questa settimana: {operation}",
        "planned_month": "Questo mese: {operation}",
        "dollar_spot_risk": "Rischio dollar spot",
        "brown_patch_risk": "Rischio brown patch",
        "fungus_seen_measures": "Fungo: adegua le cure",
        "disease_preventive_now": "Fungicida preventivo",
        "winter_rest": "Riposo invernale",
        "summer_rest": "Riposo estivo",
        "moss_control": "Antimuschio",
        "pre_emergent": "Antigerminello",
        "first_mow": "Primo taglio",
        "feed_march_starter": "Concimazione starter",
        "feed_april_greening": "Concimazione rinverdente",
        "feed_may_greening": "Concimazione rinverdente",
        "feed_june_summer": "Concimazione potassica estiva",
        "feed_july_summer": "Concimazione potassica estiva",
        "feed_october_autumn": "Concimazione potassica autunnale",
        "feed_november_autumn": "Concimazione potassica autunnale",
        "feed_spring_start": "Concimazione primaverile",
        "feed_late_spring": "Concimazione di fine primavera",
        "feed_summer_stress": "Concimazione estiva",
        "feed_early_autumn": "Concimazione di inizio autunno",
        "feed_late_autumn": "Concimazione di fine autunno",
        "aeration_spring": "Arieggiatura",
        "aeration_autumn": "Arieggiatura",
        "scarify_dethatch": "Scarificatura",
        "weed_control_broadleaf": "Diserbo foglia larga",
        "weed_control_grassy": "Diserbo foglia stretta",
        "mow_routine": "Sfalcio, ogni {interval_days} giorni a {height_mm} mm",
        "mow_routine_robot": "Robot ogni {interval_days} giorni, {height_mm} mm",
        "mow_routine_robot_daily": "Robot tutti i giorni, {height_mm} mm",
        "raise_mowing_height": "Alza l'altezza di taglio",
        "last_mow_lower": "Ultimo taglio, più basso",
        "disease_preventive": "Fungicida preventivo",
        "irrigation_deep_infrequent": "Irrigazioni abbondanti e rade",
        "summer_watch": "Vigilanza estiva",
        "prepare_overseeding": "Prepara la trasemina",
        "overseed": "Trasemina",
        "clear_leaves": "Raccolta foglie",
    },
}
STATUS_TEXT = {
    "en": {"excellent": "excellent", "good": "good", "fair": "fair", "poor": "poor"},
    "it": {"excellent": "ottimo", "good": "buono", "fair": "discreto", "poor": "scadente"},
}
ISSUE_TEXT = {
    "en": {
        "brown_patches": "brown patches",
        "weeds": "weeds",
        "moss": "moss",
        "bare_spots": "bare spots",
        "fungus": "fungus",
        "pests": "pests",
        "thatch": "thatch",
    },
    "it": {
        "brown_patches": "chiazze secche",
        "weeds": "infestanti",
        "moss": "muschio",
        "bare_spots": "zone diradate",
        "fungus": "malattia fungina",
        "pests": "parassiti",
        "thatch": "feltro",
    },
}


def summary(event: dict[str, Any], language: str) -> str:
    """Return a one-line title for the calendar entity."""
    lang = "it" if (language or "en").lower().startswith("it") else "en"
    table = TITLES[lang]
    params = dict(event.get("params", {}))
    if "status" in params:
        params["status"] = STATUS_TEXT[lang].get(params["status"], params["status"])
    if "issue" in params:
        params["issue"] = ISSUE_TEXT[lang].get(params["issue"], params["issue"])
    if "operation" in params:
        # An operation's own name may carry placeholders of its own — a mowing line names
        # its height and how often — and they are filled from the same parameters.
        named = table.get(params["operation"], params["operation"])
        with contextlib.suppress(KeyError, IndexError):
            named = named.format(**params)
        params["operation"] = named
    template = table.get(event["code"], event["code"])
    try:
        return template.format(**params)
    except (KeyError, IndexError):
        return template


def build(
    field: FieldConfig,
    entry_id: str,
    diary: Diary,
    state: Any,
    today: dt.date,
    sunrise_hint: dt.time,
    tzinfo: dt.tzinfo | None = None,
    soil_type: str = "loam",
) -> list[dict[str, Any]]:
    """Return the field's events from the past two months to the end of the plan."""
    zone = {"zone": field.name, "entry_id": entry_id}
    out: list[dict[str, Any]] = []

    # --- what was logged --------------------------------------------------------------------
    for date, record in diary.recent(PAST_DAYS, until=today):
        key = date.isoformat()
        for i, item in enumerate(record.get("maintenance", [])):
            details = item.get("details") or {}
            out.append(
                {
                    "uid": f"{entry_id}:{key}:m{i}",
                    "date": key,
                    "start": item.get("at"),
                    "end": None,
                    "all_day": not item.get("at"),
                    "code": item.get("type", "maintenance"),
                    "category": _category(item.get("type", "")),
                    "kind": "logged",
                    # The mower's run time is deliberately left out: one robot serves
                    # several lawns, so the minutes it spent belong to none of them, and
                    # that it mowed is the fact worth keeping.
                    "params": {k: v for k, v in details.items() if k in LOGGED_DETAIL_KEYS},
                    **zone,
                }
            )
        if record.get("irrigation_mm"):
            out.append(
                {
                    "uid": f"{entry_id}:{key}:irr",
                    "date": key,
                    "start": None,
                    "end": None,
                    "all_day": True,
                    "code": "irrigation_done",
                    "category": "irrigation",
                    "kind": "logged",
                    "params": {
                        "mm": round(record["irrigation_mm"], 1),
                        "minutes": round(record.get("irrigation_min", 0)),
                    },
                    **zone,
                }
            )
        if record.get("status"):
            out.append(
                {
                    "uid": f"{entry_id}:{key}:st",
                    "date": key,
                    "start": None,
                    "end": None,
                    "all_day": True,
                    "code": "rating",
                    "category": "general",
                    # An observation, not a job: the calendar must not badge it "done".
                    "kind": "noted",
                    "params": {"status": record["status"]},
                    **zone,
                }
            )
        for issue in record.get("issues", []):
            out.append(
                {
                    "uid": f"{entry_id}:{key}:is:{issue}",
                    "date": key,
                    "start": None,
                    "end": None,
                    "all_day": True,
                    "code": "issue",
                    "category": "general",
                    "kind": "noted",
                    "params": {"issue": issue},
                    **zone,
                }
            )

    if state is None:
        return out

    tz = tzinfo or dt_util.get_default_time_zone()

    # --- the coming week, from the agenda; tomorrow's dawn from the decided plan -----------
    plan = state.irrigation_plan or {}
    for item in state.agenda:
        date = item["date"]
        params = dict(item["params"])
        start = end = None
        all_day = True
        if item["code"] == "irrigate":
            if plan.get("date") == date and plan.get("cycles"):
                # The decided plan wins over the projection, one entry per run so the
                # calendar shows the soak between them rather than one long block.
                out.extend(
                    _cycle_event(entry_id, date, index, cycle, len(plan["cycles"]), plan, zone)
                    for index, cycle in enumerate(plan["cycles"])
                )
                continue
            # A day whose plan is not decided yet is laid out the same way it will be, so
            # the calendar never promises one long run that the morning will split in three.
            finish = (
                dt.datetime.combine(dt.date.fromisoformat(date), sunrise_hint, tzinfo=tz)
                - schedule.DAWN_BUFFER
            )
            minutes = item["params"].get("minutes") or 30
            depth = float(item["params"].get("mm") or 0)
            per_mm = minutes / depth if depth else None
            projected, _ = schedule.lay_out_cycles(depth, per_mm, soil_type, finish)
            if projected:
                out.extend(
                    _cycle_event(entry_id, date, index, cycle.as_dict(), len(projected), plan, zone)
                    for index, cycle in enumerate(projected)
                )
                continue
            start = (finish - dt.timedelta(minutes=minutes)).isoformat()
            end = finish.isoformat()
            all_day = False
        elif item["code"] == "germination_watering":
            # One entry a day, whatever the day: three short waterings are one job done
            # three times, and the hours are what the reader needs. The runs themselves are
            # in the irrigation plan, which is what a valve is driven from.
            day = dt.date.fromisoformat(date)
            decided = plan.get("germination") if plan.get("date") == date else None
            if decided:
                clock = [cycle["start"][11:16] for cycle in decided]
                start, end = decided[0]["start"], decided[-1]["end"]
                params |= {
                    "times": len(decided),
                    "mm": decided[0]["mm"],
                    "minutes": decided[0]["minutes"],
                }
            else:
                clock = [at.strftime("%H:%M") for at in schedule.GERMINATION_TIMES]
                first, last = schedule.GERMINATION_TIMES[0], schedule.GERMINATION_TIMES[-1]
                start = dt.datetime.combine(day, first, tzinfo=tz).isoformat()
                end = dt.datetime.combine(day, last, tzinfo=tz).isoformat()
            params["at"] = clock
            all_day = False
        elif item["code"] == "mow":
            # The afternoon, once the dew has gone: a wet cut tears the leaf instead of
            # slicing it, smears the clippings and carries disease across the lawn.
            slot_start, slot_end = schedule.preferred_mow_slot(
                heat_stress=bool(getattr(state, "heat_stress", False))
            )
            day = dt.date.fromisoformat(date)
            start = dt.datetime.combine(day, slot_start, tzinfo=tz).isoformat()
            end = dt.datetime.combine(day, slot_end, tzinfo=tz).isoformat()
            all_day = False
        out.append(
            {
                "uid": f"{entry_id}:{date}:{item['code']}:{item['params'].get('operation', '')}",
                "date": date,
                "start": start,
                "end": end,
                "all_day": all_day,
                "code": item["code"] if item["code"] != "operation" else params["operation"],
                "category": item["category"],
                "kind": "alert"
                if item["category"] == "disease"
                and item["code"] not in ("operation", "no_good_day")
                else "projected",
                "params": params,
                "reasons": item.get("reasons", []),
                **zone,
            }
        )
    if plan.get("syringe") and plan.get("syringe_start"):
        out.append(
            {
                "uid": f"{entry_id}:{plan['date']}:syringe",
                "date": plan["date"],
                "start": plan["syringe_start"],
                "end": plan["syringe_end"],
                "all_day": False,
                "code": "syringe",
                "category": "irrigation",
                "kind": "projected",
                "params": {},
                **zone,
            }
        )

    # --- the plan beyond the week: all-day on the first of its month --------------------------
    placed = {e["code"] for e in out if e["kind"] == "projected"}
    for op in state.plan:
        if op["status"] in ("done", "missed", "skipped"):
            continue
        if op["code"] in placed and op["month"] == today.strftime("%Y-%m"):
            continue
        if op["code"] in ("winter_rest", "summer_rest", "summer_watch"):
            continue
        # A month-long job is filed on the first of its month, except in the month already
        # under way: dated in the past it falls off the list of what is coming, which is
        # exactly where a routine that runs all month needs to be seen.
        first = max(f"{op['month']}-01", today.isoformat())
        out.append(
            {
                "uid": f"{entry_id}:{op['month']}:{op['code']}",
                "date": first,
                "start": None,
                "end": None,
                "all_day": True,
                "code": "planned_month",
                "category": op["category"],
                "kind": "planned",
                "params": {
                    "operation": op["code"],
                    "optional": op["optional"],
                    **op.get("params", {}),
                },
                "reasons": [*op.get("basis", []), *op.get("tailoring", [])],
                **zone,
            }
        )
    return sorted(out, key=lambda e: (e["date"], e["start"] or ""))


def _cycle_event(
    entry_id: str,
    date: str,
    index: int,
    cycle: dict[str, Any],
    total: int,
    plan: dict[str, Any],
    zone: dict[str, Any],
) -> dict[str, Any]:
    """Return one run of a watering as its own event."""
    params: dict[str, Any] = {"mm": cycle["mm"], "minutes": cycle["minutes"]}
    if total > 1:
        params |= {"cycle": index + 1, "of": total}
    return {
        "uid": f"{entry_id}:{date}:irrigate:{index}",
        "date": date,
        "start": cycle["start"],
        "end": cycle["end"],
        "all_day": False,
        "code": "irrigate",
        "category": "irrigation",
        "kind": "projected",
        "params": params,
        "reasons": plan.get("reasons", []),
        **zone,
    }


def _category(kind: str) -> str:
    return {
        "mowing": "mowing",
        "fertilizing": "fertilizing",
        "sowing": "seeding",
        "weeding": "weeds",
        "aeration": "aeration",
        "scarifying": "aeration",
        "top_dressing": "aeration",
        "treatment": "disease",
        "leaf_clearing": "general",
        "seedbed_watering": "irrigation",
        "syringing": "irrigation",
    }.get(kind, "general")
