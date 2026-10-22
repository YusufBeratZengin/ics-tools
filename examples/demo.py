"""Run a deterministic example using synthetic calendar data."""

from datetime import date
from pathlib import Path

from ics_tools import expand_event, parse_calendar


def main() -> None:
    calendar = parse_calendar(Path(__file__).with_name("demo.ics"))
    print(f"Parsed {len(calendar.events)} event")
    for event in calendar.events:
        for occurrence in expand_event(event, date(2026, 1, 1), date(2026, 1, 7)):
            print(f"{occurrence.start.isoformat()} | {occurrence.summary}")


if __name__ == "__main__":
    main()
