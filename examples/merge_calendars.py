"""Demonstrate merging multiple iCalendar files with conflict deduplication."""

from pathlib import Path

from ics_tools import merge_calendars, parse_calendar, validate_calendar


def main() -> None:
    examples_dir = Path(__file__).resolve().parent
    cal1_path = examples_dir / "demo.ics"
    cal2_path = examples_dir / "team_schedule.ics"

    # Parse both calendar files
    cal1 = parse_calendar(cal1_path)
    cal2 = parse_calendar(cal2_path)

    print(f"Loaded {cal1_path.name}: {len(cal1.events)} events")
    print(f"Loaded {cal2_path.name}: {len(cal2.events)} events")

    # Merge with automatic conflict deduplication by (UID, RECURRENCE-ID)
    merged = merge_calendars([cal1, cal2])
    print(f"Merged total events: {len(merged.events)}")

    # Validate merged result against RFC 5545
    result = validate_calendar(merged)
    print(f"Validation status: {'VALID' if result.is_valid else 'INVALID'}")
    assert result.is_valid

    # Display merged events
    for event in merged.events:
        print(f" - [{event.uid}] {event.summary} (recurrence_id={event.recurrence_id})")


if __name__ == "__main__":
    main()
