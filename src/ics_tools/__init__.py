"""ics-tools: Python library and CLI to parse, merge, filter and validate iCalendar (.ics) files.

Includes full RFC 5545 line folding/unfolding, parameter handling, VTIMEZONE resolution,
and recurrence expansion (RRULE).
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "Yusuf Berat Zengin"

from ics_tools.constants import DEFAULT_PRODID, RFC_VERSION
from ics_tools.csv_export import CSV_COLUMNS, export_to_csv
from ics_tools.exceptions import ICSError, ParseError, RRuleError, TimezoneError, ValidationError
from ics_tools.filter import filter_calendar
from ics_tools.merger import merge_calendars
from ics_tools.models import Calendar, Component, Event, EventOccurrence, Property
from ics_tools.parser import parse_calendar, parse_content_line, parse_date_or_datetime, parse_duration, unescape_text, unfold_lines
from ics_tools.rrule import ByDaySpec, RecurrenceRule, expand_event, generate_recurrence_dates, parse_rrule
from ics_tools.timezone import DEFAULT_RESOLVER, EmbeddedVTimezone, TimezoneResolver
from ics_tools.validator import ValidationIssue, ValidationResult, validate_calendar
from ics_tools.writer import (
    escape_text,
    fold_line,
    format_date_or_datetime,
    format_duration,
    serialize_calendar,
    serialize_calendar_bytes,
    serialize_component,
    serialize_property,
)

__all__ = [
    "__version__",
    "Calendar",
    "Component",
    "Property",
    "Event",
    "EventOccurrence",
    "RecurrenceRule",
    "ByDaySpec",
    "TimezoneResolver",
    "DEFAULT_RESOLVER",
    "EmbeddedVTimezone",
    "ValidationResult",
    "ValidationIssue",
    "ICSError",
    "ParseError",
    "ValidationError",
    "RRuleError",
    "TimezoneError",
    "parse_calendar",
    "unfold_lines",
    "unescape_text",
    "parse_content_line",
    "parse_date_or_datetime",
    "parse_duration",
    "serialize_calendar",
    "serialize_calendar_bytes",
    "serialize_component",
    "serialize_property",
    "fold_line",
    "escape_text",
    "format_date_or_datetime",
    "format_duration",
    "merge_calendars",
    "filter_calendar",
    "validate_calendar",
    "export_to_csv",
    "parse_rrule",
    "expand_event",
    "generate_recurrence_dates",
    "DEFAULT_PRODID",
    "RFC_VERSION",
    "CSV_COLUMNS",
]
