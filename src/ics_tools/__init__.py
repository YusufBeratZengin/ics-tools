"""ics-tools: Python library and CLI to parse, merge, filter and validate iCalendar (.ics) files.

Includes full RFC 5545 line folding/unfolding, parameter handling, VTIMEZONE resolution,
and recurrence expansion (RRULE).
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "Yusuf Berat Zengin"

from ics_tools.constants import DEFAULT_PRODID, RFC_VERSION
from ics_tools.csv_export import CSV_COLUMNS, export_to_csv
from ics_tools.exceptions import (
    ICSError,
    ParseError,
    RRuleError,
    TimezoneError,
    ValidationError,
)
from ics_tools.filter import filter_calendar
from ics_tools.merger import merge_calendars
from ics_tools.models import Calendar, Component, Event, EventOccurrence, Property
from ics_tools.parser import (
    parse_calendar,
    parse_content_line,
    parse_date_or_datetime,
    parse_duration,
    unescape_text,
    unfold_lines,
)
from ics_tools.rrule import (
    ByDaySpec,
    RecurrenceRule,
    expand_event,
    generate_recurrence_dates,
    parse_rrule,
)
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
    "CSV_COLUMNS",
    "DEFAULT_PRODID",
    "DEFAULT_RESOLVER",
    "RFC_VERSION",
    "ByDaySpec",
    "Calendar",
    "Component",
    "EmbeddedVTimezone",
    "Event",
    "EventOccurrence",
    "ICSError",
    "ParseError",
    "Property",
    "RRuleError",
    "RecurrenceRule",
    "TimezoneError",
    "TimezoneResolver",
    "ValidationError",
    "ValidationIssue",
    "ValidationResult",
    "__version__",
    "escape_text",
    "expand_event",
    "export_to_csv",
    "filter_calendar",
    "fold_line",
    "format_date_or_datetime",
    "format_duration",
    "generate_recurrence_dates",
    "merge_calendars",
    "parse_calendar",
    "parse_content_line",
    "parse_date_or_datetime",
    "parse_duration",
    "parse_rrule",
    "serialize_calendar",
    "serialize_calendar_bytes",
    "serialize_component",
    "serialize_property",
    "unescape_text",
    "unfold_lines",
    "validate_calendar",
]
