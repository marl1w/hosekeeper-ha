"""A calendar per lawn: what was done, what the week projects, what the month plans.

It appears in Home Assistant's own calendar dashboard beside the family's, and its events
can trigger automations like any other calendar's.
"""

from __future__ import annotations

import datetime as dt

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import HosekeeperConfigEntry
from .entity import HosekeeperEntity
from .events import build, summary
from .websocket import sunrise_hint


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HosekeeperConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the calendar for one field."""
    for zone_id in entry.runtime_data.zones:
        async_add_entities([LawnCalendar(entry, zone_id)], config_subentry_id=zone_id)


class LawnCalendar(HosekeeperEntity, CalendarEntity):
    """The lawn's calendar."""

    def __init__(self, entry: HosekeeperConfigEntry, zone_id: str) -> None:
        """Bind to one zone of the lawn."""
        super().__init__(entry.runtime_data.zones[zone_id].coordinator, "calendar")
        self._entry = entry
        self._zone_id = zone_id

    def _events(self) -> list[CalendarEvent]:
        zone = self._entry.runtime_data.zones[self._zone_id]
        today = dt_util.now().date()
        raw = build(
            zone.field,
            self._zone_id,
            zone.diary,
            zone.coordinator.data,
            today,
            sunrise_hint(self.hass),
        )
        language = self.hass.config.language
        out: list[CalendarEvent] = []
        for event in raw:
            if event["all_day"] or not event["start"]:
                day = dt.date.fromisoformat(event["date"])
                out.append(
                    CalendarEvent(
                        start=day,
                        end=day + dt.timedelta(days=1),
                        summary=summary(event, language),
                        uid=event["uid"],
                    )
                )
            else:
                start = dt.datetime.fromisoformat(event["start"])
                end = (
                    dt.datetime.fromisoformat(event["end"])
                    if event.get("end")
                    else start + dt.timedelta(minutes=30)
                )
                out.append(
                    CalendarEvent(
                        start=start, end=end, summary=summary(event, language), uid=event["uid"]
                    )
                )
        return out

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next event, or the one running now."""
        now = dt_util.now()
        upcoming = [
            e
            for e in self._events()
            if (e.end if isinstance(e.end, dt.datetime) else dt_util.start_of_local_day(e.end))
            > now
        ]
        return min(upcoming, key=lambda e: e.start_datetime_local) if upcoming else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: dt.datetime, end_date: dt.datetime
    ) -> list[CalendarEvent]:
        """Return the events between two instants."""
        return [
            e
            for e in self._events()
            if e.start_datetime_local < end_date and e.end_datetime_local > start_date
        ]
