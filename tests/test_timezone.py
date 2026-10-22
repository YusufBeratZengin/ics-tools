"""Tests for timezone resolution and VTIMEZONE handling."""

from pathlib import Path
import sys
import unittest
from datetime import datetime, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ics_tools.models import Component, Property
from ics_tools.timezone import (
    TimezoneResolver,
    format_tzoffset,
    parse_tzoffset,
)


class TestTimezone(unittest.TestCase):
    def test_parse_and_format_tzoffset(self):
        delta = parse_tzoffset("+0300")
        self.assertEqual(delta, timedelta(hours=3))
        self.assertEqual(format_tzoffset(delta), "+0300")

        neg_delta = parse_tzoffset("-0500")
        self.assertEqual(neg_delta, timedelta(hours=-5))
        self.assertEqual(format_tzoffset(neg_delta), "-0500")

    def test_iana_resolution(self):
        resolver = TimezoneResolver()
        tz = resolver.resolve("Europe/Istanbul")
        self.assertIsInstance(tz, (ZoneInfo, tzinfo))
        dt = datetime(2026, 11, 1, 12, 0, tzinfo=tz)
        self.assertEqual(dt.utcoffset(), timedelta(hours=3))

        utc_tz = resolver.resolve("UTC")
        self.assertEqual(utc_tz, timezone.utc)

    def test_windows_timezone_mapping(self):
        resolver = TimezoneResolver()
        tz = resolver.resolve("Eastern Standard Time")
        self.assertIsInstance(tz, (ZoneInfo, tzinfo))
        # Eastern Standard Time standard offset is UTC-5
        dt = datetime(2026, 1, 15, 12, 0, tzinfo=tz)
        self.assertEqual(dt.utcoffset(), timedelta(hours=-5))

        tz_turkey = resolver.resolve("Turkey Standard Time")
        self.assertIsInstance(tz_turkey, (ZoneInfo, tzinfo))
        dt_tr = datetime(2026, 11, 1, 12, 0, tzinfo=tz_turkey)
        self.assertEqual(dt_tr.utcoffset(), timedelta(hours=3))

    def test_prefixed_tzid_mapping(self):
        resolver = TimezoneResolver()
        tz = resolver.resolve("/freeassociation.sourceforge.net/Europe/Berlin")
        self.assertIsInstance(tz, (ZoneInfo, tzinfo))
        dt = datetime(2026, 1, 15, 12, 0, tzinfo=tz)
        self.assertEqual(dt.utcoffset(), timedelta(hours=1))

    def test_embedded_vtimezone_fallback(self):
        # Create an artificial embedded VTIMEZONE with custom non-standard name
        vtz = Component(name="VTIMEZONE")
        vtz.add_property("TZID", "CustomTz/TestOffset")

        std = Component(name="STANDARD")
        std.add_property("TZOFFSETFROM", "+0400")
        std.add_property("TZOFFSETTO", "+0400")
        std.add_property("TZNAME", "TESTSTD")
        vtz.add_component(std)

        resolver = TimezoneResolver([vtz])
        resolved = resolver.resolve("CustomTz/TestOffset")
        self.assertEqual(resolved.tzid, "CustomTz/TestOffset")

        dt = datetime(2026, 11, 1, 12, 0, tzinfo=resolved)
        self.assertEqual(dt.utcoffset(), timedelta(hours=4))
        self.assertEqual(dt.tzname(), "TESTSTD")


if __name__ == "__main__":
    unittest.main()
