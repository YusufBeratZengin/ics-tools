"""Export iCalendar events to CSV format."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from ics_tools.models import Calendar, Event
from ics_tools.rrule import expand_event
from ics_tools.timezone import DEFAULT_RESOLVER

if TYPE_CHECKING:
    from ics_tools.timezone import TimezoneResolver

CSV_COLUMNS = [
    "UID",
    "Summary",
    "Description",
    "Location",
    "Start",
    "End",
    "Duration",
    "AllDay",
    "Status",
    "RecurrenceId",
]


def _format_csv_dt(val: datetime | date, target_tz: tzinfo | None = None) -> str:
    """Format date or datetime for CSV output, converting to target_tz if applicable."""
    if not isinstance(val, datetime) and isinstance(val, date):
        return val.isoformat()

    assert isinstance(val, datetime)
    if target_tz is not None:
        if val.tzinfo is None:
            # Assume local/target or UTC
            dt_aware = val.replace(tzinfo=timezone.utc).astimezone(target_tz)
        else:
            dt_aware = val.astimezone(target_tz)
        return dt_aware.isoformat()

    return val.isoformat()


def export_to_csv(
    calendar: Calendar,
    output: io.TextIOBase | None = None,
    window_start: datetime | date | None = None,
    window_end: datetime | date | None = None,
    target_tz: str | None = None,
    expand_recurrence: bool = True,
    tz_resolver: TimezoneResolver | None = None,
) -> str:
    """Export calendar events to CSV format.

    If output is provided, writes directly to it; returns the CSV string.
    """
    buffer = output if output is not None else io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)

    resolver = tz_resolver or DEFAULT_RESOLVER
    tz_obj: tzinfo | None = None
    if target_tz:
        try:
            tz_obj = resolver.resolve(target_tz)
        except Exception:
            tz_obj = None

    # Overrides map
    overrides: dict[tuple[str, str], Event] = {}
    for ev in calendar.events:
        if ev.recurrence_id is not None:
            overrides[(ev.uid, ev.recurrence_id.isoformat())] = ev

    if expand_recurrence and (window_start is not None or window_end is not None):
        start_w = window_start if window_start is not None else date(1970, 1, 1)
        end_w = window_end if window_end is not None else date(2099, 12, 31)

        for event in calendar.events:
            if event.recurrence_id is not None:
                # Overridden instances are processed as part of master expansion
                continue

            occurrences = expand_event(
                event,
                window_start=start_w,
                window_end=end_w,
                overrides=overrides,
                tz_resolver=tz_resolver,
            )
            for occ in occurrences:
                writer.writerow([
                    occ.uid,
                    occ.summary,
                    occ.description,
                    occ.location,
                    _format_csv_dt(occ.start, tz_obj),
                    _format_csv_dt(occ.end, tz_obj),
                    str(occ.duration),
                    "TRUE" if occ.is_all_day else "FALSE",
                    occ.status,
                    occ.recurrence_id.isoformat() if occ.recurrence_id else "",
                ])
    else:
        # Export raw events without expansion
        for event in calendar.events:
            writer.writerow([
                event.uid,
                event.summary,
                event.description,
                event.location,
                _format_csv_dt(event.dtstart, tz_obj),
                _format_csv_dt(event.effective_end, tz_obj),
                str(event.effective_duration),
                "TRUE" if event.is_all_day else "FALSE",
                event.status,
                event.recurrence_id.isoformat() if event.recurrence_id else "",
            ])

    if output is None:
        return buffer.getvalue()
    return ""
