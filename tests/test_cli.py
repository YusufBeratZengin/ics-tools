"""Tests for the CLI interface."""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

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

    def test_cli_list_unknown_tz(self):
        google_ics = str(FIXTURES_DIR / "google_calendar.ics")
        buf_out = io.StringIO()
        with redirect_stdout(buf_out):
            code = main(["list", google_ics, "--from", "2026-11-01", "--window", "2w", "--tz", "NonExistent/Zone"])
        self.assertEqual(code, 0)
        self.assertIn("Q4 Sprint Planning", buf_out.getvalue())

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


if __name__ == "__main__":
    unittest.main()
