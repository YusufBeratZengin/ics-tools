"""Command-line interface for ics-tools."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ics_tools.constants import DEFAULT_PRODID
from ics_tools.csv_export import export_to_csv
from ics_tools.filter import filter_calendar
from ics_tools.merger import merge_calendars
from ics_tools.parser import parse_calendar
from ics_tools.rrule import expand_event
from ics_tools.validator import validate_calendar
from ics_tools.writer import serialize_calendar


def _parse_iso_date_or_datetime(val_str: str) -> datetime | date:
    """Parse an ISO date or datetime string (e.g. 2026-10-22 or 2026-10-22T19:00:00)."""
    val_str = val_str.strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", val_str):
            return date.fromisoformat(val_str)
        if re.fullmatch(r"\d{8}", val_str):
            return date(int(val_str[:4]), int(val_str[4:6]), int(val_str[6:8]))
        return datetime.fromisoformat(val_str.replace("Z", "+00:00"))
    except ValueError as err:
        raise argparse.ArgumentTypeError(f"Invalid date/datetime value: {val_str!r}") from err


def _parse_window_param(val_str: str) -> timedelta:
    """Parse a window shorthand like 30d, 2w, 24h, 3m into a timedelta."""
    val_str = val_str.strip().lower()
    match = re.match(r"^(\d+)([dhwm])$", val_str)
    if not match:
        raise argparse.ArgumentTypeError(
            f"Invalid window format: {val_str!r}. Expected e.g. '30d', '7d', '2w', '24h', '1m'"
        )
    try:
        num, unit = int(match.group(1)), match.group(2)
        hours_per_unit = {"d": 24, "w": 168, "h": 1, "m": 720}
        return timedelta(hours=num * hours_per_unit[unit])
    except (ValueError, OverflowError) as err:
        raise argparse.ArgumentTypeError(f"Window duration is too large: {val_str!r}") from err


def _parse_timezone(value: str) -> str:
    """Validate an explicit CLI timezone without changing file TZID fallback."""
    from ics_tools.timezone import DEFAULT_RESOLVER

    try:
        DEFAULT_RESOLVER._resolve(value, strict=True)
    except ValueError as err:
        raise argparse.ArgumentTypeError(str(err)) from err
    return value


def _parse_pattern(value: str) -> str:
    """Reject invalid regular expressions before reading calendar input."""
    try:
        re.compile(value, re.IGNORECASE)
    except (re.error, ValueError, OverflowError, RecursionError) as err:
        raise argparse.ArgumentTypeError(f"Invalid regex: {err}") from err
    return value


def _window_end(start: datetime | date, duration: timedelta) -> datetime | date:
    """Preserve sub-day precision when a window starts on a date."""
    if isinstance(start, datetime):
        return start + duration
    if duration.seconds or duration.microseconds:
        return datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc) + duration
    return start + duration


def cmd_merge(args: argparse.Namespace) -> int:
    """Merge multiple iCalendar files into one with deduplication."""
    calendars = []
    for filepath in args.files:
        path = Path(filepath)
        if filepath != "-" and not path.is_file():
            sys.stderr.write(f"Error: file not found: {filepath}\n")
            return 1
        try:
            content = sys.stdin.read() if filepath == "-" else path.read_text(encoding="utf-8-sig")
            cal = parse_calendar(content)
            calendars.append(cal)
        except Exception as err:  # noqa: BLE001 - Public boundary reports errors without a traceback.
            sys.stderr.write(f"Error parsing {filepath}: {err}\n")
            return 1

    merged = merge_calendars(calendars, prodid=DEFAULT_PRODID)
    output_text = serialize_calendar(merged)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_text, encoding="utf-8", newline="")
    else:
        sys.stdout.write(output_text)

    return 0


def cmd_filter(args: argparse.Namespace) -> int:
    """Filter an iCalendar file by date range or regex pattern."""
    content: str
    if args.file and args.file != "-":
        path = Path(args.file)
        if not path.is_file():
            sys.stderr.write(f"Error: file not found: {args.file}\n")
            return 1
        content = path.read_text(encoding="utf-8-sig")
    else:
        content = sys.stdin.read()

    try:
        cal = parse_calendar(content)
    except Exception as err:  # noqa: BLE001 - Public boundary reports errors without a traceback.
        sys.stderr.write(f"Error parsing iCalendar stream: {err}\n")
        return 1

    filtered = filter_calendar(
        cal,
        from_dt=args.from_dt,
        to_dt=args.to_dt,
        pattern=args.match,
        case_sensitive=args.case_sensitive,
    )

    output_text = serialize_calendar(filtered)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_text, encoding="utf-8", newline="")
    else:
        sys.stdout.write(output_text)

    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """List expanded calendar events within a time window."""
    content: str
    if args.file and args.file != "-":
        path = Path(args.file)
        if not path.is_file():
            sys.stderr.write(f"Error: file not found: {args.file}\n")
            return 1
        content = path.read_text(encoding="utf-8-sig")
    else:
        content = sys.stdin.read()

    try:
        cal = parse_calendar(content)
    except Exception as err:  # noqa: BLE001 - Public boundary reports errors without a traceback.
        sys.stderr.write(f"Error parsing iCalendar: {err}\n")
        return 1

    # Determine time window
    now = datetime.now(tz=timezone.utc)
    window_start = args.from_dt or now.date()

    if args.to_dt:
        window_end = args.to_dt
    elif args.window is not None:
        window_end = _window_end(window_start, args.window)
    else:
        window_end = (now + timedelta(days=30)).date()

    target_tz = None
    if args.tz:
        from ics_tools.timezone import DEFAULT_RESOLVER
        target_tz = DEFAULT_RESOLVER.resolve(args.tz)

    # Collect and sort occurrences
    overrides = {(ev.uid, ev.recurrence_id.isoformat()): ev for ev in cal.events if ev.recurrence_id}
    all_occurrences = []

    for ev in cal.events:
        if ev.recurrence_id:
            continue
        occs = expand_event(ev, window_start=window_start, window_end=window_end, overrides=overrides)
        all_occurrences.extend(occs)

    def _sort_key(occ):
        st = occ.start
        if isinstance(st, datetime):
            return st.astimezone(timezone.utc) if st.tzinfo else st.replace(tzinfo=timezone.utc)
        return datetime.combine(st, datetime.min.time(), tzinfo=timezone.utc)

    all_occurrences.sort(key=_sort_key)

    if not all_occurrences:
        sys.stdout.write(f"No events found between {window_start} and {window_end}.\n")
        return 0

    # Display table format
    header = f"{'START':<20} {'END':<20} {'SUMMARY':<30} {'LOCATION':<20}"
    sys.stdout.write(header + "\n")
    sys.stdout.write("-" * len(header) + "\n")

    for occ in all_occurrences:
        st = occ.start
        et = occ.end
        if target_tz and isinstance(st, datetime):
            st = st.astimezone(target_tz)
        if target_tz and isinstance(et, datetime):
            et = et.astimezone(target_tz)

        st_str = st.strftime("%Y-%m-%d %H:%M") if isinstance(st, datetime) else f"{st} (All day)"
        et_str = et.strftime("%Y-%m-%d %H:%M") if isinstance(et, datetime) else f"{et}"
        summary = (occ.summary[:28] + "..") if len(occ.summary) > 30 else occ.summary
        loc = (occ.location[:18] + "..") if len(occ.location) > 20 else occ.location

        sys.stdout.write(f"{st_str:<20} {et_str:<20} {summary:<30} {loc:<20}\n")

    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Validate RFC 5545 compliance of one or more files."""
    has_errors = False

    for filepath in args.files:
        path = Path(filepath)
        if filepath != "-" and not path.is_file():
            sys.stderr.write(f"File not found: {filepath}\n")
            has_errors = True
            continue

        raw = sys.stdin.read() if filepath == "-" else path.read_text(encoding="utf-8-sig")
        result = validate_calendar(raw)

        if result.is_valid:
            sys.stdout.write(f"VALID: {filepath}")
            if result.warnings:
                sys.stdout.write(f" ({len(result.warnings)} warnings)")
            sys.stdout.write("\n")
            for w in result.warnings:
                sys.stdout.write(f"  {w}\n")
        else:
            has_errors = True
            sys.stderr.write(f"INVALID: {filepath} ({len(result.errors)} errors, {len(result.warnings)} warnings)\n")
            for e in result.errors:
                sys.stderr.write(f"  {e}\n")
            for w in result.warnings:
                sys.stderr.write(f"  {w}\n")

    return 1 if has_errors else 0


def cmd_to_csv(args: argparse.Namespace) -> int:
    """Export calendar events to CSV."""
    content: str
    if args.file and args.file != "-":
        path = Path(args.file)
        if not path.is_file():
            sys.stderr.write(f"Error: file not found: {args.file}\n")
            return 1
        content = path.read_text(encoding="utf-8-sig")
    else:
        content = sys.stdin.read()

    try:
        cal = parse_calendar(content)
    except Exception as err:  # noqa: BLE001 - Public boundary reports errors without a traceback.
        sys.stderr.write(f"Error parsing iCalendar: {err}\n")
        return 1

    window_start = args.from_dt
    window_end = args.to_dt

    if args.window is not None and window_end is None:
        now = datetime.now(tz=timezone.utc).date()
        if window_start is None:
            window_start = now
        window_end = _window_end(window_start, args.window)

    csv_data = export_to_csv(
        cal,
        window_start=window_start,
        window_end=window_end,
        target_tz=args.tz,
        expand_recurrence=not args.raw,
    )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(csv_data, encoding="utf-8")
    else:
        sys.stdout.write(csv_data)

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Construct argument parser for CLI commands."""
    parser = argparse.ArgumentParser(
        prog="ics",
        description="RFC 5545 iCalendar utility library and CLI tool.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # merge command
    p_merge = subparsers.add_parser("merge", help="Merge multiple calendar files with deduplication")
    p_merge.add_argument("files", nargs="+", help="Input iCalendar files to merge; use '-' once for stdin")
    p_merge.add_argument("-o", "--output", help="Output file path (default stdout)")

    # filter command
    p_filter = subparsers.add_parser("filter", help="Filter calendar by date range or regex")
    p_filter.add_argument("file", nargs="?", default="-", help="Input .ics file or '-' for stdin")
    p_filter.add_argument("-o", "--output", help="Output file path (default stdout)")
    p_filter.add_argument(
        "--from", dest="from_dt", type=_parse_iso_date_or_datetime,
        help="Start of time window (ISO 8601 date or datetime)",
    )
    p_filter.add_argument(
        "--to", dest="to_dt", type=_parse_iso_date_or_datetime,
        help="End of time window (ISO 8601 date or datetime)",
    )
    p_filter.add_argument("--match", type=_parse_pattern, help="Regex pattern matching summary, description, or location")
    p_filter.add_argument("-i", "--case-sensitive", action="store_true", help="Perform case-sensitive regex search")

    # list command
    p_list = subparsers.add_parser("list", help="List expanded calendar events within a time window")
    p_list.add_argument("file", nargs="?", default="-", help="Input .ics file or '-' for stdin")
    p_list.add_argument("--window", type=_parse_window_param, help="Window duration (e.g. 30d, 7d, 2w, 1m)")
    p_list.add_argument(
        "--from", dest="from_dt", type=_parse_iso_date_or_datetime,
        help="Start of window (ISO date or datetime)",
    )
    p_list.add_argument(
        "--to", dest="to_dt", type=_parse_iso_date_or_datetime,
        help="End of window (ISO date or datetime)",
    )
    p_list.add_argument("--tz", type=_parse_timezone, help="Timezone for listing output (e.g. Europe/Istanbul)")

    # validate command
    p_validate = subparsers.add_parser("validate", help="Validate RFC 5545 compliance of calendar files")
    p_validate.add_argument("files", nargs="+", help="One or more .ics files to validate; use '-' once for stdin")

    # to-csv command
    p_csv = subparsers.add_parser("to-csv", help="Export calendar events to CSV format")
    p_csv.add_argument("file", nargs="?", default="-", help="Input .ics file or '-' for stdin")
    p_csv.add_argument("-o", "--output", help="Output CSV file path (default stdout)")
    p_csv.add_argument("--window", type=_parse_window_param, help="Window duration (e.g. 30d, 7d, 2w, 1m)")
    p_csv.add_argument(
        "--from", dest="from_dt", type=_parse_iso_date_or_datetime,
        help="Start of window (ISO date or datetime)",
    )
    p_csv.add_argument(
        "--to", dest="to_dt", type=_parse_iso_date_or_datetime,
        help="End of window (ISO date or datetime)",
    )
    p_csv.add_argument("--tz", type=_parse_timezone, help="Convert datetimes to specified timezone (e.g. Europe/Istanbul)")
    p_csv.add_argument("--raw", action="store_true", help="Export raw events without recurrence expansion")

    for command_parser in (p_merge, p_filter, p_list, p_validate, p_csv):
        command_parser.set_defaults(_parser=command_parser)

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if hasattr(args, "files") and args.files.count("-") > 1:
        args._parser.error("stdin ('-') may only be read once")

    commands = {
        "merge": cmd_merge,
        "filter": cmd_filter,
        "list": cmd_list,
        "validate": cmd_validate,
        "to-csv": cmd_to_csv,
    }
    try:
        return commands[args.command](args)
    except (ValueError, OverflowError, re.error) as err:
        args._parser.error(str(err))
    except OSError as err:
        sys.stderr.write(f"Error: {err}\n")
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
