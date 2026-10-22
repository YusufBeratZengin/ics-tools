"""Tests for the CLI interface."""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ics_tools.cli import main
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


if __name__ == "__main__":
    unittest.main()
