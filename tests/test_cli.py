"""Tests for the CLI interface."""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ics_tools.cli import (
    _parse_iso_date_or_datetime,
    _parse_window_param,
    _window_end,
    main,
)
from ics_tools.parser import parse_calendar

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestCLI(unittest.TestCase):
    def test_cli_validate(self):
        google_ics = str(FIXTURES_DIR / "google_calendar.ics")
        invalid_ics = str(FIXTURES_DIR / "invalid_calendar.ics")

        # Validate valid file -> code 0
        buf_out = io.StringIO()
        with redirect_stdout(buf_out):
            code = main(["validate", google_ics])
        self.assertEqual(code, 0)
        self.assertIn("VALID", buf_out.getvalue())

        # Validate invalid file -> code 1
        buf_err = io.StringIO()
        with redirect_stderr(buf_err):
            code = main(["validate", invalid_ics])
        self.assertEqual(code, 1)
        self.assertIn("INVALID", buf_err.getvalue())

    def test_cli_merge(self):
        f1 = str(FIXTURES_DIR / "google_calendar.ics")
        f2 = str(FIXTURES_DIR / "thunderbird_calendar.ics")

        with tempfile.NamedTemporaryFile(suffix=".ics", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            code = main(["merge", f1, f2, "-o", tmp_path])
            self.assertEqual(code, 0)

            # Check merged file
            cal = parse_calendar(Path(tmp_path))
            # 2 events from google + 1 from thunderbird = 3
            self.assertEqual(len(cal.events), 3)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_cli_filter_by_match(self):
        google_ics = str(FIXTURES_DIR / "google_calendar.ics")

        buf_out = io.StringIO()
        with redirect_stdout(buf_out):
            code = main(["filter", google_ics, "--match", "Planning"])
        self.assertEqual(code, 0)

        cal = parse_calendar(buf_out.getvalue())
        self.assertEqual(len(cal.events), 1)
        self.assertEqual(cal.events[0].summary, "Q4 Sprint Planning")

    def test_cli_filter_by_date_range(self):
        google_ics = str(FIXTURES_DIR / "google_calendar.ics")

        buf_out = io.StringIO()
        with redirect_stdout(buf_out):
            code = main(["filter", google_ics, "--from", "2026-11-01", "--to", "2026-11-01T23:59:59Z"])
        self.assertEqual(code, 0)

        cal = parse_calendar(buf_out.getvalue())
        self.assertEqual(len(cal.events), 1)
        self.assertEqual(cal.events[0].summary, "Q4 Sprint Planning")

    def test_cli_list(self):
        google_ics = str(FIXTURES_DIR / "google_calendar.ics")

        buf_out = io.StringIO()
        with redirect_stdout(buf_out):
            code = main(["list", google_ics, "--from", "2026-11-01", "--to", "2026-11-05", "--tz", "Europe/Istanbul"])
        self.assertEqual(code, 0)
        output = buf_out.getvalue()
        self.assertIn("START", output)
        self.assertIn("Q4 Sprint Planning", output)
        self.assertIn("Architecture Design Review", output)

    def test_cli_to_csv(self):
        google_ics = str(FIXTURES_DIR / "google_calendar.ics")

        buf_out = io.StringIO()
        with redirect_stdout(buf_out):
            code = main(["to-csv", google_ics, "--raw"])
        self.assertEqual(code, 0)
        csv_text = buf_out.getvalue()
        self.assertIn("UID,Summary,Description,Location", csv_text)
        self.assertIn("Q4 Sprint Planning", csv_text)
        self.assertIn("google-event-101@google.com", csv_text)

    def test_cli_version(self):
        buf_out = io.StringIO()
        with redirect_stdout(buf_out), self.assertRaises(SystemExit) as cm:
            main(["--version"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("ics 0.1.0", buf_out.getvalue())

    def test_cli_no_args(self):
        buf_err = io.StringIO()
        with redirect_stderr(buf_err), self.assertRaises(SystemExit) as cm:
            main([])
        self.assertEqual(cm.exception.code, 2)

    def test_cli_merge_missing_file(self):
        buf_err = io.StringIO()
        with redirect_stderr(buf_err):
            code = main(["merge", "non_existent_file_123.ics"])
        self.assertEqual(code, 1)
        self.assertIn("file not found", buf_err.getvalue())

    def test_cli_merge_stdout(self):
        f1 = str(FIXTURES_DIR / "google_calendar.ics")
        buf_out = io.StringIO()
        with redirect_stdout(buf_out):
            code = main(["merge", f1])
        self.assertEqual(code, 0)
        self.assertIn("BEGIN:VCALENDAR", buf_out.getvalue())

    def test_cli_merge_invalid_file(self):
        f_invalid = str(FIXTURES_DIR / "invalid_calendar.ics")
        buf_err = io.StringIO()
        with redirect_stderr(buf_err):
            code = main(["merge", f_invalid])
        self.assertEqual(code, 1)
        self.assertIn("Error parsing", buf_err.getvalue())

    def test_cli_filter_missing_file(self):
        buf_err = io.StringIO()
        with redirect_stderr(buf_err):
            code = main(["filter", "non_existent_file_123.ics"])
        self.assertEqual(code, 1)
        self.assertIn("file not found", buf_err.getvalue())

    def test_cli_filter_stdin_and_output_file(self):
        sample_ics = (FIXTURES_DIR / "google_calendar.ics").read_text(encoding="utf-8")
        with tempfile.NamedTemporaryFile(suffix=".ics", delete=False) as tmp:
            tmp_path = tmp.name

        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO(sample_ics)
            code = main(["filter", "-", "--match", "Planning", "-o", tmp_path])
            self.assertEqual(code, 0)
            cal = parse_calendar(Path(tmp_path))
            self.assertEqual(len(cal.events), 1)
        finally:
            sys.stdin = old_stdin
            Path(tmp_path).unlink(missing_ok=True)

    def test_cli_list_missing_file(self):
        buf_err = io.StringIO()
        with redirect_stderr(buf_err):
            code = main(["list", "non_existent_file_123.ics"])
        self.assertEqual(code, 1)

    def test_cli_list_no_events(self):
        google_ics = str(FIXTURES_DIR / "google_calendar.ics")
        buf_out = io.StringIO()
        with redirect_stdout(buf_out):
            code = main(["list", google_ics, "--from", "2099-01-01", "--window", "7d"])
        self.assertEqual(code, 0)
        self.assertIn("No events found", buf_out.getvalue())

    def test_cli_validate_missing_file(self):
        buf_err = io.StringIO()
        with redirect_stderr(buf_err):
            code = main(["validate", "non_existent_file_123.ics"])
        self.assertEqual(code, 1)
        self.assertIn("File not found", buf_err.getvalue())

    def test_cli_to_csv_missing_file(self):
        buf_err = io.StringIO()
        with redirect_stderr(buf_err):
            code = main(["to-csv", "non_existent_file_123.ics"])
        self.assertEqual(code, 1)

    def test_cli_to_csv_window_and_file(self):
        google_ics = str(FIXTURES_DIR / "google_calendar.ics")
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            code = main(["to-csv", google_ics, "--from", "2026-11-01", "--window", "24h", "-o", tmp_path])
            self.assertEqual(code, 0)
            csv_content = Path(tmp_path).read_text(encoding="utf-8")
            self.assertIn("UID,Summary", csv_content)
            self.assertIn("Q4 Sprint Planning", csv_content)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_cli_helpers(self):
        import argparse
        # Date parsing YYYYMMDD
        d = _parse_iso_date_or_datetime("20261101")
        self.assertEqual(d.year, 2026)
        self.assertEqual(d.month, 11)
        self.assertEqual(d.day, 1)

        # Invalid date
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_iso_date_or_datetime("not-a-date")

        # Window parsing
        from datetime import date, datetime, timedelta
        self.assertEqual(_parse_window_param("7d"), timedelta(days=7))
        self.assertEqual(_parse_window_param("2w"), timedelta(weeks=2))
        self.assertEqual(_parse_window_param("24h"), timedelta(hours=24))
        self.assertEqual(_parse_window_param("1m"), timedelta(days=30))
        with self.assertRaises(argparse.ArgumentTypeError):
            _parse_window_param("bad-window")

        # Window end helper
        dt_start = date(2026, 1, 1)
        subday_end = _window_end(dt_start, timedelta(hours=12))
        self.assertIsInstance(subday_end, datetime)
        assert isinstance(subday_end, datetime)
        self.assertEqual(subday_end.hour, 12)


class TestCLIUsageErrors(unittest.TestCase):
    def assert_usage_error(self, argv, message="error:"):
        output, error = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(error), self.assertRaises(SystemExit) as exc:
            main(argv)
        self.assertEqual(exc.exception.code, 2)
        self.assertIn(message, error.getvalue())
        self.assertNotIn("Traceback", error.getvalue())
        self.assertEqual(output.getvalue(), "")

    def test_invalid_dates(self):
        for command in ("filter", "list", "to-csv"):
            for option in ("--from", "--to"):
                for value in ("notadate", "2026-02-30", "20260230", "2026-13-01", "0000-01-01"):
                    with self.subTest(command=command, option=option, value=value), patch("sys.stdin") as stdin:
                        self.assert_usage_error([command, option, value], "Invalid date/datetime")
                        stdin.read.assert_not_called()

    def test_invalid_windows(self):
        for command in ("list", "to-csv"):
            for value in ("abc", "-1d", "1.5h", "999999999999999999999w", "9" * 5000 + "d"):
                with self.subTest(command=command, value=value), patch("sys.stdin") as stdin:
                    self.assert_usage_error([command, f"--window={value}"])
                    stdin.read.assert_not_called()

    def test_unknown_explicit_timezones(self):
        for command in ("list", "to-csv"):
            for value in ("Mars/X", "NonExistent/Zone", ""):
                with self.subTest(command=command, value=value), patch("sys.stdin") as stdin:
                    self.assert_usage_error([command, "--tz", value], "Unknown or unsupported timezone")
                    stdin.read.assert_not_called()

    def test_invalid_regex(self):
        for pattern in ("[", "(", "*", "(?invalid)", "a{99999999999999999999}", "(" * 2000):
            with self.subTest(pattern=pattern):
                self.assert_usage_error(["filter", "--match", pattern], "Invalid regex")

    def test_window_past_maximum_date(self):
        raw = (FIXTURES_DIR / "google_calendar.ics").read_text(encoding="utf-8")
        for command in ("list", "to-csv"):
            with self.subTest(command=command), patch("sys.stdin", io.StringIO(raw)):
                self.assert_usage_error([command, "--from", "9999-12-31", "--window", "2d"])

    def test_missing_or_unknown_arguments(self):
        for argv in (["list", "--from"], ["list", "--tz"], ["list", "--window"],
                     ["filter", "--match"], ["validate"], ["merge"], ["unknown"],
                     ["list", "--unknown"]):
            with self.subTest(argv=argv):
                self.assert_usage_error(argv)

    def test_stdin_combined_with_files(self):
        filepath = FIXTURES_DIR / "google_calendar.ics"
        for command in ("merge", "validate"):
            with (
                self.subTest(command=command),
                patch("sys.stdin", io.StringIO(filepath.read_text(encoding="utf-8"))),
                redirect_stdout(io.StringIO()) as output,
                redirect_stderr(io.StringIO()) as error,
            ):
                self.assertEqual(main([command, "-", str(filepath)]), 0)
                self.assertEqual(error.getvalue(), "")
                if command == "merge":
                    self.assertEqual(len(parse_calendar(output.getvalue()).events), 2)
                else:
                    self.assertIn("VALID: -", output.getvalue())
                    self.assertIn(f"VALID: {filepath}", output.getvalue())

    def test_invalid_stdin_reports_calendar_error(self):
        for command in ("merge", "validate"):
            with (
                self.subTest(command=command),
                patch("sys.stdin", io.StringIO("garbage")),
                redirect_stderr(io.StringIO()) as error,
            ):
                self.assertEqual(main([command, "-"]), 1)
                self.assertNotIn("File not found", error.getvalue())
                self.assertNotIn("Traceback", error.getvalue())
                self.assertIn("INVALID: -" if command == "validate" else "Error parsing -", error.getvalue())

    def test_repeated_stdin_rejected(self):
        for command in ("merge", "validate"):
            with self.subTest(command=command), patch("sys.stdin") as stdin:
                self.assert_usage_error([command, "-", "-"], "may only be read once")
                stdin.read.assert_not_called()

    def test_explicit_timezone_conversion(self):
        for command in ("list", "to-csv"):
            for tz in ("UTC", "Europe/Istanbul", "Turkey Standard Time"):
                with (
                    self.subTest(command=command, tz=tz),
                    redirect_stdout(io.StringIO()) as output,
                    redirect_stderr(io.StringIO()) as error,
                ):
                    self.assertEqual(main([command, "examples/demo.ics", "--from", "2026-01-01",
                                           "--window", "7d", "--tz", tz]), 0)
                    self.assertEqual(error.getvalue(), "")
                    self.assertIn("Demo sync", output.getvalue())
                    if tz != "UTC":
                        self.assertIn("12:00", output.getvalue())  # demo starts at 09:00 UTC

    def test_file_timezone_keeps_utc_fallback(self):
        raw = "\r\n".join([
            "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CLI test//EN",
            "BEGIN:VEVENT", "UID:synthetic", "DTSTAMP:20260101T000000Z",
            "DTSTART;TZID=Mars/X:20260101T090000", "SUMMARY:Fallback demo",
            "END:VEVENT", "END:VCALENDAR", "",
        ])
        for command in ("list", "to-csv"):
            with (
                self.subTest(command=command),
                patch("sys.stdin", io.StringIO(raw)),
                redirect_stdout(io.StringIO()) as output,
                self.assertLogs("ics_tools.timezone", level="WARNING") as logs,
            ):
                self.assertEqual(main([command, "-", "--from", "2026-01-01", "--window", "7d"]), 0)
                self.assertIn("Fallback demo", output.getvalue())
                self.assertIn("falling back to UTC", " ".join(logs.output))

    def test_output_directory_reports_io_error(self):
        for command in ("filter", "merge", "to-csv"):
            with self.subTest(command=command), redirect_stderr(io.StringIO()) as error:
                self.assertEqual(main([command, "examples/demo.ics", "-o", "."]), 1)
                self.assertIn("Error:", error.getvalue())
                self.assertNotIn("Traceback", error.getvalue())


if __name__ == "__main__":
    unittest.main()
