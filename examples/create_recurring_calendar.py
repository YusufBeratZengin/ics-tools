"""Demonstrate programmatically creating, validating, and serializing a recurring calendar."""

from datetime import datetime, timedelta, timezone

from ics_tools import (
    Calendar,
    Event,
    expand_event,
    serialize_calendar,
    validate_calendar,
)


def main() -> None:
    # 1. Construct an Event with recurrence (every Tuesday and Thursday for 4 occurrences)
    start_time = datetime(2026, 2, 3, 14, 0, 0, tzinfo=timezone.utc)
    end_time = start_time + timedelta(hours=1)

    event = Event(
        uid="workshop-series-2026@example.invalid",
        dtstart=start_time,
        dtend=end_time,
        summary="Technical Workshop Series",
        description="Bi-weekly engineering deep dives.",
        location="Lab 42",
        rrule="FREQ=WEEKLY;BYDAY=TU,TH;COUNT=4",
        status="CONFIRMED",
    )

    # 2. Add to Calendar
    cal = Calendar(
        prodid="-//ics-tools//Synthetic Workshop Calendar//EN",
        events=[event],
    )

    # 3. Serialize to RFC 5545 format with line folding and CRLF endings
    ics_text = serialize_calendar(cal)
    print("--- Serialized iCalendar ---")
    print(ics_text.strip())

    # 4. Validate RFC 5545 conformance
    result = validate_calendar(ics_text)
    print(f"\nValidation: {'VALID' if result.is_valid else 'INVALID'}")
    assert result.is_valid

    # 5. Expand occurrences
    occurrences = expand_event(
        event,
        window_start=datetime(2026, 2, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 2, 28, tzinfo=timezone.utc),
    )
    print(f"\nExpanded {len(occurrences)} occurrences:")
    for occ in occurrences:
        print(f" - {occ.start.strftime('%Y-%m-%d %H:%M %Z')} -> {occ.summary} at {occ.location}")


if __name__ == "__main__":
    main()
