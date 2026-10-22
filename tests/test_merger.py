"""Tests for calendar merging and deduplication."""

from pathlib import Path
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ics_tools.merger import merge_calendars
from ics_tools.models import Calendar, Component, Event


class TestMerger(unittest.TestCase):
    def test_merge_disjoint_calendars(self):
        ev1 = Event(
            uid="uid-1",
            dtstart=datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc),
            summary="Event 1",
        )
        ev2 = Event(
            uid="uid-2",
            dtstart=datetime(2026, 11, 2, 11, 0, tzinfo=timezone.utc),
            summary="Event 2",
        )
        cal1 = Calendar(events=[ev1])
        cal2 = Calendar(events=[ev2])

        merged = merge_calendars([cal1, cal2])
        self.assertEqual(len(merged.events), 2)
        uids = {e.uid for e in merged.events}
        self.assertEqual(uids, {"uid-1", "uid-2"})

    def test_deduplication_by_uid_and_sequence(self):
        # Event with sequence 0
        ev_old = Event(
            uid="uid-conflict",
            dtstart=datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc),
            summary="Old Title",
            sequence=0,
        )
        # Event with sequence 1 (updated)
        ev_new = Event(
            uid="uid-conflict",
            dtstart=datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc),
            summary="Updated Title",
            sequence=1,
        )

        cal1 = Calendar(events=[ev_old])
        cal2 = Calendar(events=[ev_new])

        merged = merge_calendars([cal1, cal2])
        self.assertEqual(len(merged.events), 1)
        self.assertEqual(merged.events[0].summary, "Updated Title")

        # Reverse input order: higher sequence still wins
        merged_rev = merge_calendars([cal2, cal1])
        self.assertEqual(len(merged_rev.events), 1)
        self.assertEqual(merged_rev.events[0].summary, "Updated Title")

    def test_deduplication_by_last_modified(self):
        ev1 = Event(
            uid="uid-lm",
            dtstart=datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc),
            summary="Earlier Version",
            sequence=0,
            last_modified=datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc),
        )
        ev2 = Event(
            uid="uid-lm",
            dtstart=datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc),
            summary="Later Version",
            sequence=0,
            last_modified=datetime(2026, 10, 15, 12, 0, tzinfo=timezone.utc),
        )
        merged = merge_calendars([Calendar(events=[ev1]), Calendar(events=[ev2])])
        self.assertEqual(len(merged.events), 1)
        self.assertEqual(merged.events[0].summary, "Later Version")

    def test_recurrence_id_distinct_keys(self):
        # Master recurring event
        master = Event(
            uid="series-1",
            dtstart=datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc),
            summary="Series Master",
        )
        # Overridden instance with RECURRENCE-ID
        override = Event(
            uid="series-1",
            recurrence_id=datetime(2026, 11, 2, 9, 0, tzinfo=timezone.utc),
            dtstart=datetime(2026, 11, 2, 10, 0, tzinfo=timezone.utc),
            summary="Series Override",
        )

        cal1 = Calendar(events=[master])
        cal2 = Calendar(events=[override])

        merged = merge_calendars([cal1, cal2])
        # Both must be kept because RECURRENCE-ID makes them distinct
        self.assertEqual(len(merged.events), 2)

    def test_vtimezone_deduplication(self):
        tz1 = Component(name="VTIMEZONE")
        tz1.add_property("TZID", "Europe/Istanbul")
        tz2 = Component(name="VTIMEZONE")
        tz2.add_property("TZID", "Europe/Istanbul")

        cal1 = Calendar(timezones=[tz1])
        cal2 = Calendar(timezones=[tz2])

        merged = merge_calendars([cal1, cal2])
        self.assertEqual(len(merged.timezones), 1)


if __name__ == "__main__":
    unittest.main()
