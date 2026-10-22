# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Regression tests for frequency filters, ordinal rules, empty periods, CSV streams, and sub-day CLI windows.
- Synthetic runnable demo, bilingual usage documentation, community templates, and tag-based trusted publishing.
- Linux/Windows Python 3.10–3.13 CI with lint, typing, tests, and package checks.

### Fixed
- Recurrence bounds now apply alongside COUNT and stop even when periods have no matching candidates.
- DAILY filters, YEARLY expansion across months, annual ordinals, and BYSETPOS ordering and deduplication.
- Overrides moved into the window from a later instance are included.
- CSV and list windows preserve sub-day precision; fixed UTC offsets survive serialization.
- Duplicate/nested calendar roots and invalid recurrence ranges are reported.
- Missing DTSTAMP is assigned once on serialization for stable subsequent writes.
- Ruff and mypy errors without changing the established error-reporting and timezone fallback boundaries.

### Changed
- Standardized build metadata on Hatchling with SPDX licensing and complete development dependencies.

## [0.1.0] - 2026-10-22

### Added
- Core RFC 5545 iCalendar parser with byte-level line unfolding, escaping/unescaping, and parameter parsing.
- Byte-stable iCalendar serializer with 75-octet UTF-8 safe line folding and CRLF endings.
- RRULE recurrence expansion engine supporting FREQ (DAILY, WEEKLY, MONTHLY, YEARLY), INTERVAL, COUNT, UNTIL, BYDAY (with numeric ordinals), BYMONTHDAY, BYMONTH, BYSETPOS, EXDATE, and RDATE within bounded time windows.
- Overridden recurring instance handling via RECURRENCE-ID.
- VTIMEZONE support preferring standard IANA TZID mapping via Python stdlib `zoneinfo` with a documented fallback resolver for embedded VTIMEZONE components and Windows timezone name mappings.
- CLI tool `ics` with subcommands:
  - `ics merge`: merge multiple calendar files with deduplication by UID + RECURRENCE-ID.
  - `ics filter`: filter events by date range and regex matching across summary, description, and location.
  - `ics list`: display expanded events within a time window with optional timezone translation.
  - `ics validate`: validate RFC 5545 conformance, required properties, and date-time consistency.
  - `ics to-csv`: export calendar events or expanded occurrences to CSV format.
- Comprehensive test suite compatible with both `pytest` and standard library `unittest`.
