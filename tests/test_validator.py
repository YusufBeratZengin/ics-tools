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

    def test_date_and_datetime_validation(self):
        cal_bad_date = (
            "BEGIN:VCALENDAR\r\n"
            "PRODID:-//Test//EN\r\n"
            "VERSION:2.0\r\n"
            "BEGIN:VEVENT\r\n"
            "UID:test-date-1\r\n"
            "DTSTART;VALUE=DATE:2026-11-01\r\n"
            "SUMMARY:Test\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )
        res = validate_calendar(cal_bad_date)
        self.assertFalse(res.is_valid)
        self.assertTrue(any("Invalid DATE format" in e.message for e in res.errors))

        cal_bad_day = (
            "BEGIN:VCALENDAR\r\n"
            "PRODID:-//Test//EN\r\n"
            "VERSION:2.0\r\n"
            "BEGIN:VEVENT\r\n"
            "UID:test-date-2\r\n"
            "DTSTART;VALUE=DATE:20260230\r\n"
            "SUMMARY:Test\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )
        res2 = validate_calendar(cal_bad_day)
        self.assertFalse(res2.is_valid)
        self.assertTrue(any("Invalid calendar date components" in e.message for e in res2.errors))

        # Leap second valid DATE-TIME
        cal_leap = (
            "BEGIN:VCALENDAR\r\n"
            "PRODID:-//Test//EN\r\n"
            "VERSION:2.0\r\n"
            "BEGIN:VEVENT\r\n"
            "UID:test-leap-1\r\n"
            "DTSTART:20261231T235960Z\r\n"
            "SUMMARY:Test\r\n"
            "END:VEVENT\r\n"
            "END:VCALENDAR\r\n"
        )
        res_leap = validate_calendar(cal_leap)
        self.assertTrue(res_leap.is_valid)

    def test_rrule_advanced_validation(self):
        # Both COUNT and UNTIL
        bad_both = (
            "BEGIN:VCALENDAR\r\nPRODID:-//Test//EN\r\nVERSION:2.0\r\n"
            "BEGIN:VEVENT\r\nUID:1\r\nDTSTART:20260101T090000Z\r\n"
            "RRULE:FREQ=DAILY;COUNT=5;UNTIL=20260110T090000Z\r\nSUMMARY:T\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        self.assertFalse(validate_calendar(bad_both).is_valid)

        # Missing FREQ
        bad_nofreq = (
            "BEGIN:VCALENDAR\r\nPRODID:-//Test//EN\r\nVERSION:2.0\r\n"
            "BEGIN:VEVENT\r\nUID:1\r\nDTSTART:20260101T090000Z\r\n"
            "RRULE:INTERVAL=2\r\nSUMMARY:T\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        self.assertFalse(validate_calendar(bad_nofreq).is_valid)

        # Invalid INTERVAL (<1 and non-int)
        bad_interval = (
            "BEGIN:VCALENDAR\r\nPRODID:-//Test//EN\r\nVERSION:2.0\r\n"
            "BEGIN:VEVENT\r\nUID:1\r\nDTSTART:20260101T090000Z\r\n"
            "RRULE:FREQ=DAILY;INTERVAL=0\r\nSUMMARY:T\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        self.assertFalse(validate_calendar(bad_interval).is_valid)

        # Invalid BYDAY
        bad_byday = (
            "BEGIN:VCALENDAR\r\nPRODID:-//Test//EN\r\nVERSION:2.0\r\n"
            "BEGIN:VEVENT\r\nUID:1\r\nDTSTART:20260101T090000Z\r\n"
            "RRULE:FREQ=WEEKLY;BYDAY=FOO\r\nSUMMARY:T\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        self.assertFalse(validate_calendar(bad_byday).is_valid)

        # Missing SUMMARY produces warning
        no_summary = (
            "BEGIN:VCALENDAR\r\nPRODID:-//Test//EN\r\nVERSION:2.0\r\n"
            "BEGIN:VEVENT\r\nUID:1\r\nDTSTART:20260101T090000Z\r\n"
            "END:VEVENT\r\nEND:VCALENDAR\r\n"
        )
        res_no_sum = validate_calendar(no_summary)
        self.assertTrue(res_no_sum.is_valid)
        self.assertTrue(len(res_no_sum.warnings) > 0)


if __name__ == "__main__":
    unittest.main()
