# ics-tools

Python library and command-line interface to parse, merge, filter, and validate iCalendar (.ics) files, including RFC 5545 recurring event (RRULE) expansion.

Zero runtime dependencies. Built on the Python standard library with `zoneinfo`.

Read this documentation in Turkish: [README.tr.md](README.tr.md).

## Features

- **RFC 5545 Parser and Lexer**: Unfolds lines, parses property parameters and quoted values, and unescapes text according to section 3.3.11.
- **Byte-Stable Serializer**: Deterministic output with strict CRLF line endings and UTF-8 safe line folding at 75 octets.
- **Recurrence Engine (RRULE)**: Expands occurrences within bounded time windows supporting `FREQ` (`DAILY`, `WEEKLY`, `MONTHLY`, `YEARLY`), `INTERVAL`, `COUNT`, `UNTIL`, `BYDAY` (including numeric ordinals like `2TU` and `-1SU`), `BYMONTHDAY`, `BYMONTH`, `BYSETPOS`, `EXDATE`, `RDATE`, and overridden events via `RECURRENCE-ID`.
- **Timezone Resolution**: Prefers standard IANA `TZID` mapping via `zoneinfo`. Includes built-in fallbacks for embedded `VTIMEZONE` components and legacy Windows timezone names.
- **CLI Commands**:
  - `ics merge`: Combine multiple calendars with deduplication by `(UID, RECURRENCE-ID)` and sequence-aware conflict resolution.
  - `ics filter`: Filter events by date range and regex pattern matching.
  - `ics list`: Display expanded occurrences within a time window with optional timezone translation.
  - `ics validate`: Strict RFC 5545 compliance validation reporting errors and warnings.
  - `ics to-csv`: Export events or expanded occurrences to CSV format.

## Requirements

- Python >= 3.10
- Zero runtime dependencies

## Installation

```bash
pip install ics-tools
```

Or install in editable mode from source:

```bash
git clone https://github.com/YusufBeratZengin/ics-tools.git
cd ics-tools
pip install -e .
```

## CLI Usage

### 1. Merge Calendars with Deduplication

Merges multiple iCalendar files into one. Duplicate events sharing the same `UID` and `RECURRENCE-ID` are resolved in favor of higher `SEQUENCE` or newer `LAST-MODIFIED` timestamps. Duplicate `VTIMEZONE` blocks are consolidated.

```bash
ics merge calendar1.ics calendar2.ics -o merged.ics
```

### 2. Filter Events

Filter events matching a regular expression (across summary, description, and location) or falling within a specific date/time window:

```bash
# Filter by date range (ISO 8601)
ics filter --from 2026-11-01 --to 2026-11-30 input.ics -o filtered.ics

# Filter by regex match
ics filter --match "Sprint Planning" input.ics -o planning.ics

# Read from stdin and pipe to file
cat input.ics | ics filter --match "Design" > output.ics
```

### 3. List Expanded Occurrences

List upcoming event occurrences within a specified duration window (e.g., `30d`, `2w`, `24h`), automatically expanding recurring series and converting times to a target timezone:

```bash
ics list --window 30d --tz Europe/Istanbul input.ics
```

Example output:

```text
START                END                  SUMMARY                        LOCATION            
---------------------------------------------------------------------------------------------
2026-11-01 12:00     2026-11-01 13:00     Q4 Sprint Planning             Meeting Room 3B     
2026-11-02 17:00     2026-11-02 18:00     Developer Office Hours         Online Zoom         
```

### 4. Validate RFC 5545 Compliance

Check one or more `.ics` files against RFC 5545 requirements, verifying structural delimiters, required properties, date-time formats, and RRULE syntax:

```bash
ics validate calendar.ics
```

Exit code is `0` when all files are valid, and `1` when syntax or semantic errors are encountered.

### 5. Export to CSV

Export calendar occurrences to CSV format for analysis in spreadsheets or data pipelines:

```bash
ics to-csv input.ics -o events.csv --window 30d --tz Europe/Istanbul
```

CSV fields include: `UID`, `Summary`, `Description`, `Location`, `Start`, `End`, `Duration`, `AllDay`, `Status`, `RecurrenceId`.

To export raw event records without expanding recurrences, add the `--raw` flag:

```bash
ics to-csv input.ics -o raw_events.csv --raw
```

## Python Library Usage

### Parsing an iCalendar Stream

```python
from ics_tools import parse_calendar

with open("schedule.ics", "r", encoding="utf-8") as f:
    calendar = parse_calendar(f)

for event in calendar.events:
    print(f"{event.summary} | Start: {event.dtstart} | Duration: {event.effective_duration}")
```

### Expanding Recurring Events (RRULE)

```python
from datetime import datetime, timezone
from ics_tools import parse_calendar, expand_event

calendar = parse_calendar(open("schedule.ics", "r", encoding="utf-8"))

window_start = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
window_end = datetime(2026, 11, 30, 23, 59, tzinfo=timezone.utc)

for event in calendar.events:
    if event.rrule:
        occurrences = expand_event(event, window_start, window_end)
        for occ in occurrences:
            print(f"Occurrence: {occ.start} -> {occ.end} ({occ.summary})")
```

### Creating and Serializing Calendars

```python
from datetime import datetime, timezone
from ics_tools import Calendar, Event, serialize_calendar

cal = Calendar(prodid="-//Custom App//EN")

event = Event(
    uid="unique-id-12345@example.com",
    summary="Architecture Review",
    description="Reviewing RFC 5545 serialization engine.",
    dtstart=datetime(2026, 11, 15, 14, 0, tzinfo=timezone.utc),
    dtend=datetime(2026, 11, 15, 15, 30, tzinfo=timezone.utc),
    location="Conference Room Alpha",
)

cal.add_event(event)

ics_content = serialize_calendar(cal)
with open("output.ics", "w", encoding="utf-8", newline="") as f:
    f.write(ics_content)
```

### Merging and Filtering via Python API

```python
from ics_tools import merge_calendars, filter_calendar, parse_calendar

cal1 = parse_calendar(open("work.ics", "r", encoding="utf-8"))
cal2 = parse_calendar(open("personal.ics", "r", encoding="utf-8"))

# Merge with deduplication
merged = merge_calendars([cal1, cal2])

# Filter by regex
filtered = filter_calendar(merged, pattern="Planning")
```

### Validating iCalendar Content

```python
from ics_tools import validate_calendar

result = validate_calendar(open("test.ics", "r", encoding="utf-8").read())
if result.is_valid:
    print("Calendar is RFC 5545 compliant.")
else:
    for err in result.errors:
        print(f"Error: {err}")
```

## Architecture and RFC 5545 Conformance

- **Line Folding**: RFC 5545 Section 3.1 states content lines should not exceed 75 octets. The serializer cuts text at valid UTF-8 boundaries to prevent corrupting multibyte characters and prepends continuation lines with a single ASCII space.
- **Line Endings**: Serialized files strictly use CRLF (`\r\n`).
- **Timezones**: Timezone identifiers (`TZID`) are resolved using Python's standard `zoneinfo.ZoneInfo`. If an IANA database is unavailable in the environment (e.g. Windows without tzdata), a documented fallback maps common timezones and extracts offsets from embedded `VTIMEZONE` components.
- **Recurrence Engine**: Supports RFC 5545 rule components: `FREQ`, `INTERVAL`, `COUNT`, `UNTIL`, `BYDAY` (with numeric ordinals), `BYMONTHDAY`, `BYMONTH`, `BYSETPOS`, `EXDATE`, `RDATE`, and `RECURRENCE-ID` overrides.

## Running Tests

Run the test suite using pytest:

```bash
python -m pytest -v
```

Or run directly with the Python standard library unittest runner (no extra packages needed):

```bash
python -m unittest discover -s tests -v
```

## License

MIT License. Copyright (c) 2026 Yusuf Berat Zengin. See [LICENSE](LICENSE) for details.
