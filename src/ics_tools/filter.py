"""Calendar filtering by date range and regex patterns."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import TYPE_CHECKING

from ics_tools.constants import DEFAULT_PRODID, RFC_VERSION
from ics_tools.models import Calendar, Event
from ics_tools.rrule import _to_comparable_datetime, expand_event

if TYPE_CHECKING:
    from ics_tools.timezone import TimezoneResolver


def filter_calendar(
    calendar: Calendar,
    from_dt: datetime | date | None = None,
    to_dt: datetime | date | None = None,
    pattern: str | None = None,
    case_sensitive: bool = False,
    tz_resolver: TimezoneResolver | None = None,
) -> Calendar:
    """Filter calendar events by time window and/or regex pattern.

    Returns a new Calendar containing only the matching events.
    """
    regex = None
    if pattern:
        flags = 0 if case_sensitive else re.IGNORECASE
        regex = re.compile(pattern, flags)

    # Build overrides map for recurring events in this calendar
    overrides: dict[tuple[str, str], Event] = {}
    for ev in calendar.events:
        if ev.recurrence_id is not None:
            overrides[(ev.uid, ev.recurrence_id.isoformat())] = ev

    matched_events: list[Event] = []

    for event in calendar.events:
        # 1. Regex check
        if regex:
            text_corpus = " ".join([
                event.summary,
                event.description,
                event.location,
                " ".join(event.categories),
            ])
            if not regex.search(text_corpus):
                continue

        # 2. Date window check
        if from_dt is not None or to_dt is not None:
            # If from_dt or to_dt is missing, use sensible bounds
            lower = from_dt if from_dt is not None else date(1970, 1, 1)
            upper = to_dt if to_dt is not None else date(2099, 12, 31)

            if event.rrule or event.rdate:
                # Expand occurrences to check for overlap
                occs = expand_event(event, window_start=lower, window_end=upper, overrides=overrides, tz_resolver=tz_resolver)
                if not occs:
                    continue
            else:
                # Direct interval overlap check: start <= upper and end >= lower
                lower_dt = _to_comparable_datetime(lower)
                upper_dt = _to_comparable_datetime(upper)
                ev_start_dt = _to_comparable_datetime(event.dtstart)
                ev_end_dt = _to_comparable_datetime(event.effective_end)

                if ev_start_dt > upper_dt or ev_end_dt < lower_dt:
                    continue

        matched_events.append(event)

    return Calendar(
        version=RFC_VERSION,
        prodid=calendar.prodid or DEFAULT_PRODID,
        calscale=calendar.calscale,
        method=calendar.method,
        events=matched_events,
        timezones=[tz.copy() for tz in calendar.timezones],
        other_components=[c.copy() for c in calendar.other_components],
    )
