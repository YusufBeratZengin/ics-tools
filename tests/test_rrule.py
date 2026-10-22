"""Comprehensive tests for RRULE recurrence expansion."""

import sys
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ics_tools.parser import parse_calendar
from ics_tools.rrule import (
    expand_event,
    generate_recurrence_dates,
    parse_rrule,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestRRule(unittest.TestCase):
    def test_parse_rrule_all_fields(self):
        rule_str = "FREQ=MONTHLY;INTERVAL=2;COUNT=10;BYDAY=2TU,-1SU;BYMONTHDAY=1,15,-1;BYMONTH=3,9;BYSETPOS=1;WKST=SU"
        rule = parse_rrule(rule_str)
        self.assertEqual(rule.freq, "MONTHLY")
        self.assertEqual(rule.interval, 2)
        self.assertEqual(rule.count, 10)
        self.assertEqual(len(rule.byday), 2)
        self.assertEqual(rule.byday[0].ordinal, 2)
        self.assertEqual(rule.byday[0].day, "TU")
        self.assertEqual(rule.byday[1].ordinal, -1)
        self.assertEqual(rule.byday[1].day, "SU")
        self.assertEqual(rule.bymonthday, [1, 15, -1])
        self.assertEqual(rule.bymonth, [3, 9])
        self.assertEqual(rule.bysetpos, [1])
        self.assertEqual(rule.wkst, "SU")

    def test_daily_recurrence_with_count(self):
        start = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)
        rule = parse_rrule("FREQ=DAILY;INTERVAL=2;COUNT=4")
        dates = list(generate_recurrence_dates(start, rule))

        expected = [
            datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc),
            datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc),
            datetime(2026, 11, 5, 9, 0, tzinfo=timezone.utc),
            datetime(2026, 11, 7, 9, 0, tzinfo=timezone.utc),
        ]
        self.assertEqual(dates, expected)

    def test_daily_recurrence_with_until(self):
        start = date(2026, 11, 1)
        rule = parse_rrule("FREQ=DAILY;UNTIL=20261104")
        dates = list(generate_recurrence_dates(start, rule))
        expected = [
            date(2026, 11, 1),
            date(2026, 11, 2),
            date(2026, 11, 3),
            date(2026, 11, 4),
        ]
        self.assertEqual(dates, expected)

    def test_weekly_recurrence_byday(self):
        # 2026-11-02 is Monday
        start = datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc)
        rule = parse_rrule("FREQ=WEEKLY;INTERVAL=1;COUNT=5;BYDAY=MO,WE,FR")
        dates = list(generate_recurrence_dates(start, rule))

        expected = [
            datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc),  # Mon
            datetime(2026, 11, 4, 10, 0, tzinfo=timezone.utc),  # Wed
            datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc),  # Fri
            datetime(2026, 11, 9, 10, 0, tzinfo=timezone.utc),  # Mon
            datetime(2026, 11, 11, 10, 0, tzinfo=timezone.utc), # Wed
        ]
        self.assertEqual(dates, expected)

    def test_monthly_by_day_of_month(self):
        # 15th of every month
        start = date(2026, 1, 15)
        rule = parse_rrule("FREQ=MONTHLY;INTERVAL=1;COUNT=4;BYMONTHDAY=15")
        dates = list(generate_recurrence_dates(start, rule))

        expected = [
            date(2026, 1, 15),
            date(2026, 2, 15),
            date(2026, 3, 15),
            date(2026, 4, 15),
        ]
        self.assertEqual(dates, expected)

    def test_monthly_by_ordinal_day(self):
        # 2nd Tuesday of each month
        # In Nov 2026: 1st Tue is Nov 3, 2nd Tue is Nov 10
        # In Dec 2026: 1st Tue is Dec 1, 2nd Tue is Dec 8
        start = date(2026, 11, 10)
        rule = parse_rrule("FREQ=MONTHLY;COUNT=2;BYDAY=2TU")
        dates = list(generate_recurrence_dates(start, rule))

        expected = [
            date(2026, 11, 10),
            date(2026, 12, 8),
        ]
        self.assertEqual(dates, expected)

    def test_monthly_last_sunday(self):
        # Last Sunday of the month (-1SU)
        # Nov 2026: Nov 29
        # Dec 2026: Dec 27
        start = date(2026, 11, 29)
        rule = parse_rrule("FREQ=MONTHLY;COUNT=2;BYDAY=-1SU")
        dates = list(generate_recurrence_dates(start, rule))

        expected = [
            date(2026, 11, 29),
            date(2026, 12, 27),
        ]
        self.assertEqual(dates, expected)

    def test_monthly_bysetpos_first_weekday(self):
        # First weekday of each month: BYDAY=MO,TU,WE,TH,FR; BYSETPOS=1
        # Nov 2026: Nov 1 is Sunday, so first weekday is Nov 2 (Mon)
        # Dec 2026: Dec 1 is Tuesday, so first weekday is Dec 1 (Tue)
        start = date(2026, 11, 2)
        rule = parse_rrule("FREQ=MONTHLY;COUNT=2;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=1")
        dates = list(generate_recurrence_dates(start, rule))

        expected = [
            date(2026, 11, 2),
            date(2026, 12, 1),
        ]
        self.assertEqual(dates, expected)

    def test_yearly_recurrence_thanksgiving(self):
        # 4th Thursday of November
        # 2026: Nov 26
        # 2027: Nov 25
        start = date(2026, 11, 26)
        rule = parse_rrule("FREQ=YEARLY;INTERVAL=1;COUNT=2;BYMONTH=11;BYDAY=4TH")
        dates = list(generate_recurrence_dates(start, rule))

        expected = [
            date(2026, 11, 26),
            date(2027, 11, 25),
        ]
        self.assertEqual(dates, expected)

    def test_exdate_and_override_expansion(self):
        # Read recurring_override fixture
        path = FIXTURES_DIR / "recurring_override.ics"
        cal = parse_calendar(path)

        master_event = next(e for e in cal.events if not e.recurrence_id)
        overrides = {(e.uid, e.recurrence_id.isoformat()): e for e in cal.events if e.recurrence_id}

        window_start = datetime(2026, 11, 1, tzinfo=timezone.utc)
        window_end = datetime(2026, 11, 10, tzinfo=timezone.utc)

        occs = expand_event(master_event, window_start, window_end, overrides=overrides)

        # Master rule is DAILY;COUNT=5 (Nov 2, 3, 4, 5, 6)
        # Nov 4 is EXDATE -> excluded!
        # Nov 3 is overridden -> moved to 11:00 with summary "Rescheduled Design Sync"
        self.assertEqual(len(occs), 4)

        dates = [o.start for o in occs]
        self.assertEqual(dates[0], datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc))
        self.assertEqual(dates[1], datetime(2026, 11, 3, 11, 0, tzinfo=timezone.utc))
        self.assertEqual(occs[1].summary, "Rescheduled Design Sync")
        self.assertTrue(occs[1].is_overridden)

        # Nov 4 must NOT be in dates
        nov_4 = datetime(2026, 11, 4, 9, 0, tzinfo=timezone.utc)
        self.assertNotIn(nov_4, dates)

        self.assertEqual(dates[2], datetime(2026, 11, 5, 9, 0, tzinfo=timezone.utc))
        self.assertEqual(dates[3], datetime(2026, 11, 6, 9, 0, tzinfo=timezone.utc))

    def test_infinite_recurrence_bounded_by_window(self):
        # Rule without COUNT or UNTIL
        start = date(2026, 1, 1)
        rule = parse_rrule("FREQ=DAILY;INTERVAL=1")
        window_end = date(2026, 1, 5)

        dates = list(generate_recurrence_dates(start, rule, window_end=window_end))
        self.assertEqual(len(dates), 5)
        self.assertEqual(dates[-1], date(2026, 1, 5))


if __name__ == "__main__":
    unittest.main()
