"""Tests for the RFC 5545 parser engine."""

from pathlib import Path
import sys
import unittest
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ics_tools.exceptions import ParseError
from ics_tools.models import Property
from ics_tools.parser import parse_calendar, parse_content_line, parse_date_or_datetime, parse_duration

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestParser(unittest.TestCase):
    def test_parse_content_line_simple(self):
        line = "SUMMARY:Team Sync"
        prop = parse_content_line(line)
        self.assertEqual(prop.name, "SUMMARY")
        self.assertEqual(prop.value, "Team Sync")
        self.assertEqual(prop.params, {})

    def test_parse_content_line_with_params(self):
        line = 'DTSTART;TZID="America/New_York";VALUE=DATE-TIME:20261101T090000'
        prop = parse_content_line(line)
        self.assertEqual(prop.name, "DTSTART")
        self.assertEqual(prop.value, "20261101T090000")
        self.assertEqual(prop.get_param("TZID"), "America/New_York")
        self.assertEqual(prop.get_param("VALUE"), "DATE-TIME")

    def test_parse_content_line_with_colons_in_quotes(self):
        line = 'ATTENDEE;CN="John:Doe";ROLE=REQ-PARTICIPANT:mailto:johndoe@example.com'
        prop = parse_content_line(line)
        self.assertEqual(prop.name, "ATTENDEE")
        self.assertEqual(prop.value, "mailto:johndoe@example.com")
        self.assertEqual(prop.get_param("CN"), "John:Doe")
        self.assertEqual(prop.get_param("ROLE"), "REQ-PARTICIPANT")

    def test_parse_duration(self):
        self.assertEqual(parse_duration("PT1H30M"), timedelta(hours=1, minutes=30))
        self.assertEqual(parse_duration("P2D"), timedelta(days=2))
        self.assertEqual(parse_duration("P1W"), timedelta(weeks=1))
        self.assertEqual(parse_duration("-PT15M"), timedelta(minutes=-15))
        self.assertEqual(parse_duration("PT45S"), timedelta(seconds=45))

    def test_parse_date_and_datetime(self):
        # DATE
        p_date = Property(name="DTSTART", value="20261105", params={"VALUE": ["DATE"]})
        d_val = parse_date_or_datetime(p_date)
        self.assertEqual(d_val, date(2026, 11, 5))

        # UTC DATETIME
        p_utc = Property(name="DTSTART", value="20261105T143000Z")
        utc_val = parse_date_or_datetime(p_utc)
        self.assertEqual(utc_val, datetime(2026, 11, 5, 14, 30, 0, tzinfo=timezone.utc))

        # Floating DATETIME
        p_float = Property(name="DTSTART", value="20261105T143000")
        flt_val = parse_date_or_datetime(p_float)
        self.assertEqual(flt_val, datetime(2026, 11, 5, 14, 30, 0))
        self.assertIsNone(flt_val.tzinfo)

    def test_parse_google_calendar_fixture(self):
        path = FIXTURES_DIR / "google_calendar.ics"
        cal = parse_calendar(path)
        self.assertEqual(cal.version, "2.0")
        self.assertIn("Google", cal.prodid)
        self.assertEqual(len(cal.events), 2)

        ev1 = cal.events[0]
        self.assertEqual(ev1.uid, "google-event-101@google.com")
        self.assertEqual(ev1.summary, "Q4 Sprint Planning")
        self.assertEqual(ev1.dtstart, datetime(2026, 11, 1, 9, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(ev1.dtend, datetime(2026, 11, 1, 10, 0, 0, tzinfo=timezone.utc))
        self.assertEqual(len(ev1.alarms), 1)

        ev2 = cal.events[1]
        self.assertEqual(ev2.summary, "Architecture Design Review")
        self.assertEqual(ev2.location, "Meeting Room 3B")

    def test_parse_apple_calendar_fixture(self):
        path = FIXTURES_DIR / "apple_calendar.ics"
        cal = parse_calendar(path)
        self.assertEqual(len(cal.events), 2)
        self.assertEqual(len(cal.timezones), 1)

        ev = cal.events[0]
        self.assertEqual(ev.summary, "Product Keynote Rehearsal")
        self.assertEqual(ev.location, "Bosphorus Hall")
        # Timezone Europe/Istanbul
        self.assertIsNotNone(ev.dtstart.tzinfo)

    def test_parse_outlook_calendar_fixture(self):
        path = FIXTURES_DIR / "outlook_calendar.ics"
        cal = parse_calendar(path)
        self.assertEqual(len(cal.events), 1)
        ev = cal.events[0]
        self.assertEqual(ev.summary, "Q4 Executive Business Review")
        # Unescaped comma in description
        self.assertIn("accomplishments, key metrics, and roadmaps.", ev.description)

    def test_parse_multiday_fixture(self):
        path = FIXTURES_DIR / "multiday_events.ics"
        cal = parse_calendar(path)
        self.assertEqual(len(cal.events), 2)

        all_day_ev = cal.events[0]
        self.assertTrue(all_day_ev.is_all_day)
        self.assertEqual(all_day_ev.dtstart, date(2026, 11, 10))
        self.assertEqual(all_day_ev.dtend, date(2026, 11, 12))
        self.assertEqual(all_day_ev.effective_duration, timedelta(days=2))

        duration_ev = cal.events[1]
        self.assertFalse(duration_ev.is_all_day)
        self.assertEqual(duration_ev.duration, timedelta(hours=1, minutes=30))
        self.assertEqual(duration_ev.effective_end, datetime(2026, 11, 15, 15, 30, tzinfo=timezone.utc))

    def test_unclosed_component_raises(self):
        bad_ics = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//EN\r\nBEGIN:VEVENT\r\nUID:123\r\n"
        with self.assertRaises(ParseError):
            parse_calendar(bad_ics)

    def test_mismatched_end_raises(self):
        bad_ics = "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//Test//EN\r\nBEGIN:VEVENT\r\nUID:123\r\nEND:VTODO\r\nEND:VCALENDAR\r\n"
        with self.assertRaises(ParseError):
            parse_calendar(bad_ics)


if __name__ == "__main__":
    unittest.main()
