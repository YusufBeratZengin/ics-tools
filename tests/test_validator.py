"""Tests for RFC 5545 validator engine."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ics_tools.validator import validate_calendar

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestValidator(unittest.TestCase):
    def test_fixtures_are_valid(self):
        valid_fixtures = [
            "google_calendar.ics",
            "apple_calendar.ics",
            "outlook_calendar.ics",
            "thunderbird_calendar.ics",
            "recurring_override.ics",
            "multiday_events.ics",
        ]
        for name in valid_fixtures:
            path = FIXTURES_DIR / name
            content = path.read_text(encoding="utf-8-sig")
            result = validate_calendar(content)
            self.assertTrue(result.is_valid, f"Fixture {name} failed validation: {result.errors}")

    def test_invalid_calendar_fixture(self):
        path = FIXTURES_DIR / "invalid_calendar.ics"
        content = path.read_text(encoding="utf-8-sig")
        result = validate_calendar(content)
        self.assertFalse(result.is_valid)

        messages = " ".join(e.message for e in result.errors)
        self.assertIn("VERSION", messages)
        self.assertIn("DTSTART", messages)
        self.assertIn("both DTEND and DURATION", messages)

    def test_missing_vcalendar_delimiters(self):
        bad_stream = "BEGIN:VEVENT\r\nUID:123\r\nDTSTART:20261101T100000Z\r\nEND:VEVENT\r\n"
        result = validate_calendar(bad_stream)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("BEGIN:VCALENDAR" in e.message for e in result.errors))

    def test_rrule_validation_errors(self):
        bad_rrule = (
            "BEGIN:VCALENDAR\r\n"
            "PRODID:-//Test//EN\r\n"
            "VERSION:2.0\r\n"
            "BEGIN:VEVENT\r\n"
            "UID:test-rrule-1\r\n"
            "DTSTART:20261101T100000Z\r\n"
            "RRULE:FREQ=INVALIDFREQ\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )
        result = validate_calendar(bad_rrule)
        self.assertFalse(result.is_valid)
        self.assertTrue(any("Invalid RRULE FREQ" in e.message for e in result.errors))


if __name__ == "__main__":
    unittest.main()
