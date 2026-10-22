# ics-tools
[![CI](https://github.com/YusufBeratZengin/ics-tools/actions/workflows/ci.yml/badge.svg)](https://github.com/YusufBeratZengin/ics-tools/actions/workflows/ci.yml) [![PyPI](https://img.shields.io/pypi/v/ics-tools)](https://pypi.org/project/ics-tools/) [![MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml) [![Dependencies](https://img.shields.io/badge/runtime_dependencies-0-green)](pyproject.toml)

Parse, merge, filter, validate, and export iCalendar (.ics) files, with recurring event expansion.
A typed Python library and CLI with zero runtime dependencies; calendar processing stays local.
[English](README.md) | [Türkçe](README.tr.md)

Install from a checkout: `python -m pip install .`
Try it: `python -m ics_tools validate examples/demo.ics`

## Demo

Run the included synthetic calendar example:

```sh
python examples/demo.py
```

Actual output (DAILY with COUNT, EXDATE, and RDATE):

```text
Parsed 1 event
2026-01-01T09:00:00+00:00 | Demo sync
2026-01-03T09:00:00+00:00 | Demo sync
2026-01-05T09:00:00+00:00 | Demo sync
```

## Install

Requires Python 3.10 or later. Run the install command above from the repository root.
The build uses Hatchling; installation needs an available package index or a provisioned build backend.
The PyPI badge reflects registry availability; adding a publish workflow does not itself create a release.
The installed `ics` command is equivalent to `python -m ics_tools`.

## Usage

### CLI

Merge deduplicates by `(UID, RECURRENCE-ID)`, preferring higher SEQUENCE, then newer
LAST-MODIFIED and DTSTAMP, then the later input. Filter searches summary, description,
location, and categories (case insensitive by default). List expands recurring instances.
Validation returns 0 for valid input and 1 for errors; warnings alone do not fail it.
All examples use synthetic data and write generated files under `is/`.

```sh
python -m ics_tools merge examples/demo.ics examples/demo.ics -o is/merged.ics
python -m ics_tools filter examples/demo.ics --from 2026-01-01 --to 2026-01-07 --match Demo -o is/filtered.ics
python -m ics_tools list examples/demo.ics --from 2026-01-01 --window 30d --tz Europe/Istanbul
python -m ics_tools validate examples/demo.ics
python -m ics_tools to-csv examples/demo.ics --from 2026-01-01 --window 30d --tz Europe/Istanbul -o is/events.csv
python -m ics_tools to-csv examples/demo.ics --raw -o is/events-raw.csv
```

Filter, list, and to-csv accept `-` or omitted input to read stdin. Omit `-o` for stdout.
CSV columns are UID, Summary, Description, Location, Start, End, Duration, AllDay,
Status, and RecurrenceId. CSV expands recurrences when a date bound or window is supplied;
without bounds it exports raw records. `--raw` always exports raw records.

### Python API

```python
from datetime import date
from pathlib import Path
from ics_tools import (
    expand_event, export_to_csv, filter_calendar, merge_calendars,
    parse_calendar, serialize_calendar, validate_calendar,
)

calendar = parse_calendar(Path("examples/demo.ics"))
occurrences = expand_event(calendar.events[0], date(2026, 1, 1), date(2026, 1, 7))
assert len(occurrences) == 3
merged = merge_calendars([calendar, calendar])
filtered = filter_calendar(merged, pattern="Demo")
assert validate_calendar(serialize_calendar(filtered)).is_valid
csv_text = export_to_csv(filtered, window_start=date(2026, 1, 1), window_end=date(2026, 1, 7))
assert "Demo sync" in csv_text
```

`parse_calendar` accepts text, UTF-8 bytes, a `Path`, or a text stream.
`Calendar` and `Event` can also be constructed directly. `serialize_calendar` returns
CRLF text; use `serialize_calendar_bytes` or open text output with `newline=""` to preserve it.
`export_to_csv` returns text; when passed `output`, it writes to the stream and returns an empty string.

## Examples

[examples/demo.py](examples/demo.py) and [examples/demo.ics](examples/demo.ics) are runnable,
synthetic examples. The test fixtures imitate common Google, Apple, Outlook, and Thunderbird exports;
they are authored test data, not actual user exports.

## Configuration / options

| Option or rule | Behavior |
| --- | --- |
| `--from`, `--to` | ISO date or datetime bounds; a date denotes midnight |
| `--window` | `30d`, `2w`, `24h`, or `1m` (30 days); explicit `--to` takes priority |
| `--tz` | IANA or supported Windows timezone name for list / CSV output |
| `--match`, `--case-sensitive` | Regex filter, optionally case sensitive |
| `-o`, `--output` | Output file; parent directories are created |
| `--raw` | CSV records without recurrence expansion |
| RRULE | DAILY, WEEKLY, MONTHLY, YEARLY; INTERVAL, COUNT, UNTIL, BYDAY, BYMONTHDAY, BYMONTH, BYSETPOS, WKST |
| Exceptions | EXDATE, RDATE (DATE / DATE-TIME), and RECURRENCE-ID overrides, including cancellations |

## How it works

The parser unfolds lines, handles escaped text and quoted parameters, and preserves unknown properties.
The writer orders properties deterministically, folds UTF-8 at 75 octets, and emits CRLF.
A missing Event DTSTAMP is assigned on its first serialization and reused on subsequent writes.
Recurrence filters operate on each frequency period before BYSETPOS. COUNT, UNTIL, and the
expansion window all bound generation. IANA timezone data takes priority over fallbacks.

## Limitations / privacy

Processing is offline; no calendar data is uploaded. Keep private calendars out of issues and fixtures.
This is a practical RFC 5545 subset, not a complete RFC compliance checker: expansion supports
DAILY through YEARLY, and RDATE PERIOD values, BYHOUR/BYMINUTE/BYSECOND/BYYEARDAY/BYWEEKNO,
and RANGE=THISANDFUTURE are unsupported. Validation checks structure, key required fields,
date syntax, and supported recurrence ranges; it does not validate every RFC constraint.

Embedded VTIMEZONE fallback extracts offsets and uses an approximate northern-hemisphere daylight-saving season;
it does not interpret historical transitions or the component's transition RRULEs. Common timezone
fallbacks have the same limits when the system IANA database is missing (often on Windows).
Unknown TZIDs log a warning and use UTC. Floating datetimes use UTC for comparisons;
provide aware datetimes for predictable conversions. Date window bounds are inclusive with interval
overlap; use a datetime for the end of a full day. Unbounded generators must be consumed lazily
or supplied with a COUNT, UNTIL, or window end. Expansion scans from DTSTART; very old series
with large windows can be expensive.

## Development

From a checkout, install the development extras and run:

```sh
python -m pip install -e ".[dev]"
python -m ruff check .
python -m mypy src
python -m pytest -q
python -m build
python -m twine check dist/*
```

CI covers Python 3.10–3.13 on Linux and Windows. Tests use no network.
The optional pytest cache plugin is disabled to support restricted workspaces.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for checks, commit conventions, and the maintainer's
release procedure. See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for community expectations
and [SECURITY.md](SECURITY.md) for private vulnerability reports.

## License

[MIT](LICENSE). Copyright (c) 2026 Yusuf Berat Zengin.
