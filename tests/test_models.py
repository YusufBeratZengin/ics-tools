"""Tests for data models (Property, Component, Event, Calendar)."""

import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ics_tools.models import Calendar, Component, Event, EventOccurrence, Property


class TestPropertyModel(unittest.TestCase):
    def test_property_params_manipulation(self):
        prop = Property(name="ATTENDEE", value="mailto:user@example.invalid")
        self.assertEqual(prop.get_param_values("ROLE"), [])

        prop.set_param("ROLE", "REQ-PARTICIPANT")
        self.assertEqual(prop.get_param("ROLE"), "REQ-PARTICIPANT")
        self.assertEqual(prop.get_param_values("ROLE"), ["REQ-PARTICIPANT"])

        # Multi-value param
        prop.set_param("MEMBER", ["group1", "group2"])
        self.assertEqual(prop.get_param_values("MEMBER"), ["group1", "group2"])
        self.assertEqual(prop.get_param("MEMBER"), "group1")

        # Remove param
        prop.remove_param("ROLE")
        self.assertIsNone(prop.get_param("ROLE"))
        self.assertEqual(prop.get_param_values("ROLE"), [])

        # Copy
        prop_copy = prop.copy()
        self.assertEqual(prop_copy.name, prop.name)
        self.assertEqual(prop_copy.value, prop.value)
        self.assertEqual(prop_copy.params, prop.params)
        prop_copy.set_param("NEW", "VAL")
        self.assertNotIn("NEW", prop.params)


class TestComponentModel(unittest.TestCase):
    def test_component_properties_manipulation(self):
        comp = Component(name="VEVENT")
        comp.add_property("SUMMARY", "Initial Summary")
        self.assertEqual(comp.get_property_value("SUMMARY"), "Initial Summary")

        # Replace existing property via set_property
        comp.set_property("SUMMARY", "Updated Summary", params={"LANGUAGE": ["en"]})
        self.assertEqual(comp.get_property_value("SUMMARY"), "Updated Summary")
        prop = comp.get_property("SUMMARY")
        self.assertIsNotNone(prop)
        assert prop is not None
        self.assertEqual(prop.get_param("LANGUAGE"), "en")

        # Add new property via set_property
        comp.set_property("LOCATION", "Room 101")
        self.assertEqual(comp.get_property_value("LOCATION"), "Room 101")

        # Remove properties
        removed = comp.remove_properties("SUMMARY")
        self.assertEqual(removed, 1)
        self.assertIsNone(comp.get_property("SUMMARY"))

        # Subcomponents
        alarm = Component(name="VALARM")
        comp.add_component(alarm)
        self.assertEqual(len(comp.get_components()), 1)
        self.assertEqual(len(comp.get_components("VALARM")), 1)
        self.assertEqual(len(comp.get_components("VTODO")), 0)


class TestEventModel(unittest.TestCase):
    def test_all_day_event_duration_and_end(self):
        start_date = date(2026, 6, 1)
        ev = Event(
            uid="all-day-1",
            dtstart=start_date,
            duration=timedelta(days=3),
        )
        self.assertTrue(ev.is_all_day)
        self.assertEqual(ev.effective_end, date(2026, 6, 4))
        self.assertEqual(ev.effective_duration, timedelta(days=3))

    def test_occurrence_duration_with_dates(self):
        occ = EventOccurrence(
            uid="occ-1",
            start=date(2026, 3, 1),
            end=date(2026, 3, 5),
            summary="Multi-day",
            is_all_day=True,
        )
        self.assertEqual(occ.duration, timedelta(days=4))


class TestCalendarModel(unittest.TestCase):
    def test_calendar_events_manipulation(self):
        cal = Calendar(prodid="-//Test//EN")
        ev1 = Event(uid="e1@example.invalid", dtstart=date(2026, 1, 1), summary="First")
        ev2 = Event(
            uid="e1@example.invalid",
            dtstart=datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc),
            recurrence_id=datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc),
            summary="Override",
        )

        cal.add_event(ev1)
        cal.add_event(ev2)
        self.assertEqual(len(cal.events), 2)

        # find_event
        found_master = cal.find_event("e1@example.invalid")
        self.assertIsNotNone(found_master)
        assert found_master is not None
        self.assertEqual(found_master.summary, "First")

        found_override = cal.find_event("e1@example.invalid", recurrence_id=datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc))
        self.assertIsNotNone(found_override)
        assert found_override is not None
        self.assertEqual(found_override.summary, "Override")

        self.assertIsNone(cal.find_event("nonexistent"))

        # remove_event
        removed = cal.remove_event("e1@example.invalid", recurrence_id=datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc))
        self.assertTrue(removed)
        self.assertEqual(len(cal.events), 1)
        self.assertFalse(cal.remove_event("nonexistent"))

    def test_calendar_other_components_roundtrip(self):
        cal = Calendar(prodid="-//Test//EN")
        todo = Component(name="VTODO")
        todo.add_property("UID", "todo-1@example.invalid")
        todo.add_property("SUMMARY", "Task 1")
        cal.other_components.append(todo)

        comp = cal.to_component()
        self.assertEqual(len(comp.get_components("VTODO")), 1)

        cal_recovered = Calendar.from_component(comp)
        self.assertEqual(len(cal_recovered.other_components), 1)
        self.assertEqual(cal_recovered.other_components[0].name, "VTODO")
        self.assertEqual(cal_recovered.other_components[0].get_property_value("SUMMARY"), "Task 1")


if __name__ == "__main__":
    unittest.main()
