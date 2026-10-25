"""Demonstrate filtering iCalendar events by pattern/date and exporting to CSV."""

from datetime import date
from pathlib import Path

from ics_tools import export_to_csv, filter_calendar, parse_calendar


def main() -> None:
    schedule_path = Path(__file__).resolve().parent / "team_schedule.ics"
    calendar = parse_calendar(schedule_path)

    # Filter events matching 'Standup' within January 2026
    start_bound = date(2026, 1, 1)
    end_bound = date(2026, 1, 10)
    filtered = filter_calendar(
        calendar,
        from_dt=start_bound,
        to_dt=end_bound,
        pattern=r"Standup",
    )
    print(f"Matched {len(filtered.events)} event records matching 'Standup'")

    # Export expanded occurrences to CSV with timezone translation
    csv_output = export_to_csv(
        filtered,
        window_start=start_bound,
        window_end=end_bound,
        target_tz="Europe/Istanbul",
    )

    print("\n--- Exported CSV ---")
    print(csv_output.strip())


if __name__ == "__main__":
    main()
