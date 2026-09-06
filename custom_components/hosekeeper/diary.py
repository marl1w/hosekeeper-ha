"""The per-field diary: one record per day, kept in Home Assistant's storage.

The recorder is not used for this. It purges after ten days by default and the analysis
needs seasons, so the diary is its own file that outlives whatever the recorder keeps.
"""

from __future__ import annotations

import datetime as dt
from typing import Any, TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DIARY_STORAGE_KEY, DIARY_STORAGE_VERSION


class MaintenanceRecord(TypedDict, total=False):
    """One maintenance action."""

    type: str
    at: str
    source: str
    details: dict[str, Any]


class DayRecord(TypedDict, total=False):
    """Everything known about one day of one field."""

    irrigation_min: float
    irrigation_mm: float
    irrigation_source: str
    rain_mm: float
    rain_source: str
    et0_mm: float
    etc_mm: float
    et_method: str
    kc: float
    tmax: float
    tmin: float
    rh_mean: float
    fc: dict[str, float | None]
    """The forecast issued the day before for this day: tmax, tmin, rain."""
    status: str
    issues: list[str]
    maintenance: list[MaintenanceRecord]
    deficit_mm: float
    disease_flags: list[str]
    irrigation_plan: dict[str, Any]
    obs: dict[str, Any]
    """Intraday accumulators owned by the coordinator: running extremes, means, integrals."""


class DiaryData(TypedDict):
    """The stored shape."""

    days: dict[str, DayRecord]
    adaptation: dict[str, Any]


SAVE_DELAY_S = 30


def _empty() -> DiaryData:
    return {"days": {}, "adaptation": {}}


class Diary:
    """Load, query and append to one zone's diary."""

    def __init__(self, hass: HomeAssistant, zone_id: str) -> None:
        """Bind to the storage file for one zone."""
        self._hass = hass
        self._store: Store[DiaryData] = Store(
            hass, DIARY_STORAGE_VERSION, f"{DIARY_STORAGE_KEY}.{zone_id}"
        )
        self._data: DiaryData = _empty()

    async def async_load(self) -> None:
        """Read the file; a missing file is an empty diary."""
        self._data = await self._store.async_load() or _empty()
        self._data.setdefault("plan", {})
        self._data.setdefault("adaptation", {})

    async def async_save(self) -> None:
        """Write the file."""
        await self._store.async_save(self._data)

    def schedule_save(self) -> None:
        """Write the file soon, coalescing the bursts a weather station produces."""
        self._store.async_delay_save(lambda: self._data, SAVE_DELAY_S)

    async def async_remove(self) -> None:
        """Delete the file, for when the config entry is removed."""
        await self._store.async_remove()

    # ------------------------------------------------------------------ reading

    @staticmethod
    def today_key(now: dt.datetime | None = None) -> str:
        """Return the diary key for today in the instance's time zone."""
        return (now or dt_util.now()).date().isoformat()

    @property
    def days(self) -> dict[str, DayRecord]:
        """Every stored day, keyed by ISO date."""
        return self._data["days"]

    @property
    def adaptation(self) -> dict[str, Any]:
        """Per-field adjustment state owned by the adaptation engine."""
        return self._data["adaptation"]

    @property
    def plan(self) -> dict[str, Any]:
        """The month plan as last generated: {"generated": "YYYY-MM", "operations": [...]}."""
        return self._data["plan"]

    def day(self, key: str) -> DayRecord:
        """Return the record for a day, created empty on first access."""
        return self._data["days"].setdefault(key, {})

    def today(self) -> DayRecord:
        """Return the record for today."""
        return self.day(self.today_key())

    def recent(self, days: int, until: dt.date | None = None) -> list[tuple[dt.date, DayRecord]]:
        """Return the last `days` days ending today, oldest first, gaps as empty records."""
        end = until or dt_util.now().date()
        out: list[tuple[dt.date, DayRecord]] = []
        for offset in range(days - 1, -1, -1):
            date = end - dt.timedelta(days=offset)
            out.append((date, self._data["days"].get(date.isoformat(), {})))
        return out

    def last_status(self) -> str | None:
        """Return the most recent status recorded on any day, or None."""
        for key in sorted(self._data["days"], reverse=True):
            status = self._data["days"][key].get("status")
            if status:
                return status
        return None

    def last_deficit(self, before: str, within_days: int = 7) -> float | None:
        """Return the deficit stored on the latest day before `before`, if recent enough.

        A gap of a week or more means the balance is stale — the instance was off, or the
        field was just created — and the caller starts again from a full profile.
        """
        limit = (dt.date.fromisoformat(before) - dt.timedelta(days=within_days)).isoformat()
        for key in sorted(self._data["days"], reverse=True):
            if key >= before:
                continue
            if key < limit:
                return None
            deficit = self._data["days"][key].get("deficit_mm")
            if deficit is not None:
                return float(deficit)
        return None

    def last_maintenance(self, kind: str) -> dt.datetime | None:
        """When `kind` was last done, or None."""
        latest: dt.datetime | None = None
        for record in self._data["days"].values():
            for item in record.get("maintenance", []):
                if item.get("type") != kind:
                    continue
                at = dt_util.parse_datetime(item.get("at", ""))
                if at and (latest is None or at > latest):
                    latest = at
        return latest

    # ------------------------------------------------------------------ writing

    def add_irrigation(
        self, minutes: float, mm: float | None, source: str, at: dt.datetime | None = None
    ) -> None:
        """Add an irrigation run, to today or to the day it actually happened.

        A watering is kept as a day's total rather than as a moment, so `at` chooses the
        page rather than the hour. It is what makes a season already watered by hand
        enterable after the fact.
        """
        today = self.day(self.today_key(at)) if at else self.today()
        today["irrigation_min"] = today.get("irrigation_min", 0.0) + minutes
        if mm is not None:
            today["irrigation_mm"] = today.get("irrigation_mm", 0.0) + mm
        today["irrigation_source"] = source

    def add_surface_water(self, minutes: float, mm: float | None, source: str) -> None:
        """Add a watering that wets the surface and not the root zone.

        The seedbed's light passes and a midday syringing are water on the lawn, and the
        charts show them as such, but they are kept out of `irrigation_mm` on purpose. Two
        millimetres on a warm afternoon damps the top centimetre and mostly goes back to the
        air; counting it would tell the balance the roots were filled and cancel the deep
        dawn cycle the turf around the seed still needs.
        """
        today = self.today()
        today["seedbed_min"] = today.get("seedbed_min", 0.0) + minutes
        if mm is not None:
            today["seedbed_mm"] = today.get("seedbed_mm", 0.0) + mm
        today["seedbed_source"] = source

    def set_status(self, status: str) -> None:
        """Record how the lawn looks today."""
        self.today()["status"] = status

    def add_issue(self, issue: str) -> None:
        """Tag today with a problem seen on the lawn."""
        issues = self.today().setdefault("issues", [])
        if issue not in issues:
            issues.append(issue)

    def add_maintenance(
        self,
        kind: str,
        *,
        at: dt.datetime | None = None,
        source: str = "manual",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record a maintenance action on the day it happened.

        Recording the same job by hand twice on one day is somebody correcting themselves --
        they wrote down the cut and then remembered the height, or the mix they used -- so
        the second entry amends the first rather than claiming the job was done twice. A
        machine's records always stand on their own: a robot that goes out twice in a day
        really did go out twice, and each session has its own length.
        """
        when = at or dt_util.now()
        record: MaintenanceRecord = {"type": kind, "at": when.isoformat(), "source": source}
        if details:
            record["details"] = details
        entries = self.day(self.today_key(when)).setdefault("maintenance", [])
        if source == "manual":
            for existing in entries:
                if existing.get("type") == kind and existing.get("source") == "manual":
                    existing["at"] = record["at"]
                    if details:
                        existing["details"] = {**existing.get("details", {}), **details}
                    return
        entries.append(record)
