# ics-tools Examples

This directory contains synthetic iCalendar fixtures and runnable Python examples demonstrating core features of `ics-tools`.

All examples run completely offline using only the Python standard library.

## Files

| File | Type | Description |
| --- | --- | --- |
| [`demo.ics`](demo.ics) | Synthetic Calendar | Single recurring event with `COUNT`, `EXDATE`, and `RDATE`. |
| [`team_schedule.ics`](team_schedule.ics) | Synthetic Calendar | Realistic team calendar with multi-day events, weekly syncs, and `RECURRENCE-ID` overrides. |
| [`demo.py`](demo.py) | Python Script | Basic calendar parsing and recurrence expansion walkthrough. |
| [`merge_calendars.py`](merge_calendars.py) | Python Script | Merging multiple calendar files with deterministic conflict resolution and deduplication. |
| [`filter_and_export_csv.py`](filter_and_export_csv.py) | Python Script | Regex and date range filtering, recurrence expansion, and timezone-converted CSV export. |
| [`create_recurring_calendar.py`](create_recurring_calendar.py) | Python Script | Programmatic calendar construction, RFC 5545 serialization, validation, and recurrence expansion. |

## Running Examples

Run any script directly using Python 3.10+:

```sh
# Basic demo
python examples/demo.py

# Merging multiple calendars with deduplication
python examples/merge_calendars.py

# Filtering and CSV export with timezone conversion
python examples/filter_and_export_csv.py

# Programmatically creating and serializing a calendar
python examples/create_recurring_calendar.py
```

## Equivalent CLI Commands

Each Python API capability is also accessible directly via the `ics` command-line interface:

```sh
# Validate RFC 5545 conformance
ics validate examples/team_schedule.ics

# List expanded occurrences in a 14-day window
ics list examples/team_schedule.ics --from 2026-01-01 --window 14d

# Merge calendars with deduplication
ics merge examples/demo.ics examples/team_schedule.ics

# Filter by regex and export to CSV
ics to-csv examples/team_schedule.ics --from 2026-01-01 --window 14d --tz Europe/Istanbul
```
