"""Regression coverage for the original feature specification."""

import csv
import io
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta, timezone
from itertools import islice
from pathlib import Path
from unittest.mock import patch

from ics_tools import (
    Calendar,
    Event,
    expand_event,
    export_to_csv,
    parse_calendar,
    serialize_calendar,
)
from ics_tools.cli import main
from ics_tools.exceptions import (
    ICSError,
    ParseError,
    RRuleError,
    TimezoneError,
    ValidationError,
)
from ics_tools.rrule import generate_recurrence_dates, parse_rrule
from ics_tools.validator import validate_calendar


class TestRecurrenceSpec(unittest.TestCase):
    def dates(self, rule, start=date(2026, 1, 1), end=date(2026, 12, 31)):
        return list(generate_recurrence_dates(start, parse_rrule(rule), window_end=end))

    def test_daily_filters_intersect(self):
        self.assertEqual(
            self.dates(
                "FREQ=DAILY;COUNT=3;BYDAY=MO;BYMONTHDAY=1,2,3,4,5,6,7;BYMONTH=2,3,4"
            ),
            [date(2026, 2, 2), date(2026, 3, 2), date(2026, 4, 6)],
        )

    def test_daily_setpos_filters_single_day(self):
        self.assertEqual(self.dates("FREQ=DAILY;COUNT=3;BYSETPOS=2"), [])

    def test_count_and_window_both_bound_generation(self):
        for freq in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY"):
            with self.subTest(freq=freq):
                self.assertEqual(
                    self.dates(f"FREQ={freq};COUNT=20", end=date(2026, 1, 1)),
                    [date(2026, 1, 1)],
                )

    def test_empty_months_stop_at_until(self):
        with patch(
            "ics_tools.rrule._get_matching_days_for_month",
            side_effect=[[]] * 12 + [RuntimeError("unbounded")],
        ):
            self.assertEqual(
                self.dates(
                    "FREQ=MONTHLY;UNTIL=20260131;BYMONTH=2;BYMONTHDAY=30", end=None
                ),
                [],
            )

    def test_empty_years_stop_at_until(self):
        with patch(
            "ics_tools.rrule._get_matching_days_for_month",
            side_effect=[[]] * 12 + [RuntimeError("unbounded")],
        ):
            self.assertEqual(
                self.dates(
                    "FREQ=YEARLY;UNTIL=20261231;BYMONTH=2;BYMONTHDAY=30", end=None
                ),
                [],
            )

    def test_monthly_setpos_applies_before_dtstart_cutoff(self):
        self.assertEqual(
            self.dates(
                "FREQ=MONTHLY;COUNT=2;BYDAY=MO,TU,WE,TH,FR;BYSETPOS=1",
                start=date(2026, 1, 15),
            ),
            [date(2026, 2, 2), date(2026, 3, 2)],
        )

    def test_yearly_monthday_expands_across_all_months(self):
        self.assertEqual(
            self.dates("FREQ=YEARLY;COUNT=3;BYMONTHDAY=1"),
            [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)],
        )

    def test_yearly_ordinal_without_bymonth_uses_whole_year(self):
        self.assertEqual(
            self.dates("FREQ=YEARLY;COUNT=1;BYDAY=-1MO"),
            [date(2026, 12, 28)],
        )

    def test_yearly_candidates_are_sorted_and_unique(self):
        self.assertEqual(
            self.dates("FREQ=YEARLY;COUNT=2;BYMONTH=12,2,2;BYMONTHDAY=1"),
            [date(2026, 2, 1), date(2026, 12, 1)],
        )

    def test_setpos_duplicates_do_not_consume_count(self):
        self.assertEqual(
            self.dates("FREQ=MONTHLY;COUNT=2;BYMONTHDAY=1;BYSETPOS=1,-1"),
            [date(2026, 1, 1), date(2026, 2, 1)],
        )

    def test_timed_recurrences_preserve_time_and_offset(self):
        start = datetime(2026, 1, 1, 9, 30, tzinfo=timezone(timedelta(hours=3)))
        dates = self.dates("FREQ=MONTHLY;COUNT=2", start=start)
        self.assertEqual(dates, [start, start.replace(month=2)])

    def test_until_only_yearly_rule_terminates_between_candidates(self):
        self.assertEqual(
            self.dates("FREQ=YEARLY;UNTIL=20260101;BYMONTH=2", end=None), []
        )

    def test_unbounded_generator_can_be_consumed_lazily(self):
        dates = list(
            islice(
                generate_recurrence_dates(date(2026, 1, 1), parse_rrule("FREQ=DAILY")),
                2,
            )
        )
        self.assertEqual(dates, [date(2026, 1, 1), date(2026, 1, 2)])

    def test_rdate_exdate_and_cancelled_override(self):
        event = Event(
            uid="synthetic",
            dtstart=date(2026, 1, 1),
            rrule="FREQ=DAILY;COUNT=3",
            exdate=[date(2026, 1, 2)],
            rdate=[date(2026, 1, 3), date(2026, 1, 5)],
        )
        cancelled = Event(
            uid="synthetic",
            dtstart=date(2026, 1, 3),
            recurrence_id=date(2026, 1, 3),
            status="CANCELLED",
        )
        occurrences = expand_event(
            event,
            date(2026, 1, 1),
            date(2026, 1, 6),
            overrides={("synthetic", "2026-01-03"): cancelled},
        )
        self.assertEqual(
            [occ.start for occ in occurrences], [date(2026, 1, 1), date(2026, 1, 5)]
        )

    def test_override_moved_into_window_from_future(self):
        master = Event(uid="synthetic", dtstart=date(2026, 1, 1), rrule="FREQ=MONTHLY")
        override = Event(
            uid="synthetic", dtstart=date(2026, 1, 5), recurrence_id=date(2026, 2, 1)
        )
        occurrences = expand_event(
            master,
            date(2026, 1, 4),
            date(2026, 1, 6),
            overrides={("synthetic", "2026-02-01"): override},
        )
        self.assertEqual([occ.start for occ in occurrences], [date(2026, 1, 5)])
        self.assertTrue(occurrences[0].is_overridden)


class TestStreamSpec(unittest.TestCase):
    def test_multiple_roots_are_rejected(self):
        stream = (
            "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:synthetic\r\nEND:VCALENDAR\r\n"
        )
        with self.assertRaises(ParseError):
            parse_calendar(stream + stream)

    def test_nested_calendar_is_rejected(self):
        stream = (
            "BEGIN:VCALENDAR\r\nBEGIN:VCALENDAR\r\nEND:VCALENDAR\r\nEND:VCALENDAR\r\n"
        )
        self.assertFalse(validate_calendar(stream).is_valid)

    def test_binary_and_text_input_match(self):
        raw = serialize_calendar(
            Calendar(events=[Event(uid="synthetic", dtstart=date(2026, 1, 1))])
        )
        self.assertEqual(
            parse_calendar(raw).events, parse_calendar(raw.encode()).events
        )

    def test_csv_string_and_external_stream_match(self):
        calendar = Calendar(
            events=[
                Event(
                    uid="synthetic",
                    dtstart=date(2026, 1, 1),
                    summary='Comma, newline\nquote"',
                )
            ]
        )
        expected = export_to_csv(calendar, expand_recurrence=False)
        output = io.StringIO()
        self.assertEqual(
            export_to_csv(calendar, output=output, expand_recurrence=False), ""
        )
        self.assertEqual(output.getvalue(), expected)
        self.assertEqual(
            next(iter(csv.DictReader(io.StringIO(expected))))["Summary"],
            calendar.events[0].summary,
        )

    def test_csv_export_with_timezone_conversions(self):
        cal = Calendar(
            events=[
                Event(
                    uid="tz-test-1",
                    dtstart=datetime(2026, 6, 1, 10, 0, tzinfo=timezone.utc),
                    summary="Aware event",
                ),
                Event(
                    uid="tz-test-2",
                    dtstart=datetime(2026, 6, 1, 10, 0),
                    summary="Naive event",
                ),
            ]
        )
        csv_out = export_to_csv(cal, target_tz="Europe/Istanbul", expand_recurrence=False)
        self.assertIn("+03:00", csv_out)

        # Invalid target_tz gracefully handled
        csv_invalid_tz = export_to_csv(cal, target_tz="Invalid/TZ_Name", expand_recurrence=False)
        self.assertIn("tz-test-1", csv_invalid_tz)

    def test_main_module_execution(self):
        import runpy
        google_ics = str(Path(__file__).parent / "fixtures" / "google_calendar.ics")
        with (
            patch("sys.argv", ["ics", "validate", google_ics]),
            redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as cm,
        ):
            runpy.run_module("ics_tools", run_name="__main__")
        self.assertEqual(cm.exception.code, 0)

    def test_exceptions_formatting(self):
        pe = ParseError("syntax error", line_number=42, line_content="BAD:LINE")
        self.assertIn("Line 42", str(pe))
        self.assertIn("BAD:LINE", str(pe))
        self.assertEqual(pe.line_number, 42)
        self.assertEqual(pe.line_content, "BAD:LINE")

        ve = ValidationError("validation error", component="VEVENT", property_name="DTSTART")
        self.assertEqual(ve.component, "VEVENT")
        self.assertEqual(ve.property_name, "DTSTART")

        self.assertIsInstance(RRuleError("bad rrule"), ICSError)
        self.assertIsInstance(TimezoneError("bad tz"), ICSError)

    def test_fixed_offset_roundtrip_preserves_instant(self):
        start = datetime(2026, 1, 1, 9, tzinfo=timezone(timedelta(hours=3)))
        calendar = Calendar(events=[Event(uid="synthetic", dtstart=start)])
        self.assertEqual(
            parse_calendar(serialize_calendar(calendar)).events[0].dtstart, start
        )

    def test_subday_cli_windows_keep_hours(self):
        calendar = Calendar(
            events=[
                Event(
                    uid="synthetic",
                    dtstart=datetime(2026, 1, 1, 1, tzinfo=timezone.utc),
                    summary="Early demo",
                )
            ]
        )
        raw = serialize_calendar(calendar)
        for command in ("list", "to-csv"):
            with (
                self.subTest(command=command),
                patch("sys.stdin", io.StringIO(raw)),
                redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(
                    main([command, "--from", "2026-01-01", "--window", "2h"]), 0
                )
                self.assertIn("Early demo", output.getvalue())

    def test_serialization_without_dtstamp_is_stable(self):
        calendar = Calendar(events=[Event(uid="synthetic", dtstart=date(2026, 1, 1))])

        class MovingClock(datetime):
            calls = 0

            @classmethod
            def now(cls, tz=None):
                cls.calls += 1
                return datetime(2026, 1, cls.calls, tzinfo=tz)

        with patch("ics_tools.models.datetime", MovingClock):
            first = serialize_calendar(calendar)
            self.assertEqual(serialize_calendar(calendar), first)

    def test_invalid_rrule_ranges_are_reported(self):
        for rule in (
            "FREQ=MONTHLY;BYMONTH=13",
            "FREQ=MONTHLY;BYMONTHDAY=0",
            "FREQ=MONTHLY;BYDAY=0MO",
            "FREQ=MONTHLY;BYSETPOS=367",
            "FREQ=DAILY;UNTIL=20260230",
        ):
            with self.subTest(rule=rule):
                calendar = Calendar(
                    events=[
                        Event(uid="synthetic", dtstart=date(2026, 1, 1), rrule=rule)
                    ]
                )
                self.assertFalse(validate_calendar(calendar).is_valid)

    def test_csv_export_with_recurring_overrides(self):
        fixture_path = Path(__file__).parent / "fixtures" / "recurring_override.ics"
        cal = parse_calendar(fixture_path)
        csv_out = export_to_csv(cal, window_start=date(2026, 11, 1), window_end=date(2026, 11, 10))
        self.assertIn("Rescheduled Design Sync", csv_out)
        self.assertIn("Daily Design Sync", csv_out)

    def test_filter_with_recurring_overrides(self):
        from ics_tools.filter import filter_calendar
        fixture_path = Path(__file__).parent / "fixtures" / "recurring_override.ics"
        cal = parse_calendar(fixture_path)
        # Window with no occurrences
        filtered_empty = filter_calendar(cal, from_dt=date(2026, 1, 1), to_dt=date(2026, 1, 2))
        self.assertEqual(len(filtered_empty.events), 0)
        # Window containing the occurrences
        filtered = filter_calendar(cal, from_dt=date(2026, 11, 1), to_dt=date(2026, 11, 10))
        self.assertEqual(len(filtered.events), 2)
