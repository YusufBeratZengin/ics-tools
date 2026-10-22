"""Tests for byte-stable serialization and lossless roundtripping."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ics_tools.parser import parse_calendar
from ics_tools.writer import serialize_calendar

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestRoundtrip(unittest.TestCase):
    def _verify_byte_stable(self, fixture_name: str):
        path = FIXTURES_DIR / fixture_name
        cal1 = parse_calendar(path)

        out1 = serialize_calendar(cal1)

        # Check line endings strictly CRLF
        self.assertTrue(out1.endswith("\r\n"))
        for line in out1.split("\r\n"):
            self.assertLessEqual(len(line.encode("utf-8")), 75)

        # Re-parse serialized output
        cal2 = parse_calendar(out1)
        out2 = serialize_calendar(cal2)

        # Idempotence: serialize(cal2) == serialize(cal1)
        self.assertEqual(out1, out2)

    def test_roundtrip_google_calendar(self):
        self._verify_byte_stable("google_calendar.ics")

    def test_roundtrip_apple_calendar(self):
        self._verify_byte_stable("apple_calendar.ics")

    def test_roundtrip_outlook_calendar(self):
        self._verify_byte_stable("outlook_calendar.ics")

    def test_roundtrip_thunderbird_calendar(self):
        self._verify_byte_stable("thunderbird_calendar.ics")

    def test_roundtrip_recurring_override(self):
        self._verify_byte_stable("recurring_override.ics")

    def test_roundtrip_multiday_events(self):
        self._verify_byte_stable("multiday_events.ics")


if __name__ == "__main__":
    unittest.main()
