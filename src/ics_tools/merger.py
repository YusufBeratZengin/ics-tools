"""Calendar merging with deduplication by UID + RECURRENCE-ID."""

from __future__ import annotations

from ics_tools.constants import DEFAULT_PRODID, RFC_VERSION
from ics_tools.models import Calendar, Component, Event


def _event_key(event: Event) -> tuple[str, str]:
    """Generate a unique key for an event based on UID and RECURRENCE-ID."""
    rec_str = event.recurrence_id.isoformat() if event.recurrence_id is not None else ""
    return (event.uid, rec_str)


def _should_replace(existing: Event, candidate: Event) -> bool:
    """Determine if candidate event should replace an existing duplicate event.

    Precedence:
    1. Higher SEQUENCE number.
    2. Later LAST-MODIFIED timestamp.
    3. Later DTSTAMP timestamp.
    4. Otherwise, candidate replaces existing.
    """
    if candidate.sequence > existing.sequence:
        return True
    if candidate.sequence < existing.sequence:
        return False

    # Sequences are equal; check LAST-MODIFIED
    if candidate.last_modified and existing.last_modified:
        if candidate.last_modified > existing.last_modified:
            return True
        if candidate.last_modified < existing.last_modified:
            return False

    # Check DTSTAMP
    if candidate.dtstamp and existing.dtstamp:
        if candidate.dtstamp > existing.dtstamp:
            return True
        if candidate.dtstamp < existing.dtstamp:
            return False

    return True


def merge_calendars(
    calendars: list[Calendar],
    prodid: str = DEFAULT_PRODID,
) -> Calendar:
    """Merge multiple Calendar instances into a single Calendar.

    Deduplicates events by (UID, RECURRENCE-ID) with conflict resolution
    by SEQUENCE and LAST-MODIFIED. Deduplicates VTIMEZONE components by TZID.
    """
    if not calendars:
        return Calendar(prodid=prodid, version=RFC_VERSION)

    merged_events: dict[tuple[str, str], Event] = {}
    merged_timezones: dict[str, Component] = {}
    merged_other: list[Component] = []

    for cal in calendars:
        # Merge timezones
        for tz in cal.timezones:
            tzid_prop = tz.get_property("TZID")
            tzid = tzid_prop.value.strip() if tzid_prop and tzid_prop.value else ""
            if tzid and tzid not in merged_timezones:
                merged_timezones[tzid] = tz.copy()

        # Merge other components
        for other in cal.other_components:
            merged_other.append(other.copy())

        # Merge events with deduplication
        for ev in cal.events:
            key = _event_key(ev)
            if key in merged_events:
                if _should_replace(merged_events[key], ev):
                    merged_events[key] = ev
            else:
                merged_events[key] = ev

    return Calendar(
        version=RFC_VERSION,
        prodid=prodid,
        calscale="GREGORIAN",
        method=calendars[0].method if calendars else None,
        events=list(merged_events.values()),
        timezones=list(merged_timezones.values()),
        other_components=merged_other,
    )
