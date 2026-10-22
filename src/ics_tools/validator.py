"""Validation engine for RFC 5545 compliance."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from ics_tools.constants import FREQUENCIES, RFC_VERSION, WEEKDAY_TO_INT
from ics_tools.models import Calendar, Component
from ics_tools.parser import unfold_lines


@dataclass
class ValidationIssue:
    """An issue detected during RFC 5545 validation."""

    message: str
    line_number: int | None = None
    component: str | None = None
    property_name: str | None = None
    is_error: bool = True

    def __str__(self) -> str:
        prefix = "ERROR" if self.is_error else "WARNING"
        location_parts: list[str] = []
        if self.line_number is not None:
            location_parts.append(f"line {self.line_number}")
        if self.component:
            location_parts.append(f"in {self.component}")
        if self.property_name:
            location_parts.append(f"prop {self.property_name}")

        loc_str = f" ({', '.join(location_parts)})" if location_parts else ""
        return f"[{prefix}]{loc_str}: {self.message}"


@dataclass
class ValidationResult:
    """The result of validating an iCalendar calendar."""

    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return True if there are zero validation errors (warnings allowed)."""
        return not any(issue.is_error for issue in self.issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.is_error]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if not i.is_error]

    def add_error(
        self,
        message: str,
        line_number: int | None = None,
        component: str | None = None,
        property_name: str | None = None,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                message=message,
                line_number=line_number,
                component=component,
                property_name=property_name,
                is_error=True,
            )
        )

    def add_warning(
        self,
        message: str,
        line_number: int | None = None,
        component: str | None = None,
        property_name: str | None = None,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                message=message,
                line_number=line_number,
                component=component,
                property_name=property_name,
                is_error=False,
            )
        )


def _validate_date_value(val: str, result: ValidationResult, comp_name: str, prop_name: str) -> None:
    """Validate RFC 5545 DATE format YYYYMMDD."""
    if not re.match(r"^\d{8}$", val):
        result.add_error(f"Invalid DATE format {val!r}; expected YYYYMMDD", component=comp_name, property_name=prop_name)
        return
    try:
        year, month, day = int(val[0:4]), int(val[4:6]), int(val[6:8])
        date(year, month, day)
    except ValueError as err:
        result.add_error(f"Invalid calendar date components {val!r}: {err}", component=comp_name, property_name=prop_name)


def _validate_datetime_value(val: str, result: ValidationResult, comp_name: str, prop_name: str) -> None:
    """Validate RFC 5545 DATE-TIME format YYYYMMDDTHHMMSS[Z]."""
    match = re.match(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(Z)?$", val)
    if not match:
        result.add_error(
            f"Invalid DATE-TIME format {val!r}; expected YYYYMMDDTHHMMSS[Z]",
            component=comp_name,
            property_name=prop_name,
        )
        return
    year, month, day, hour, minute, second, _ = match.groups()
    try:
        # RFC 5545 allows leap seconds (second 60)
        sec = int(second)
        if sec == 60:
            sec = 59
        datetime(int(year), int(month), int(day), int(hour), int(minute), sec)
    except ValueError as err:
        result.add_error(
            f"Invalid calendar date-time values {val!r}: {err}",
            component=comp_name,
            property_name=prop_name,
        )


def _validate_rrule(rrule_val: str, result: ValidationResult, comp_name: str) -> None:
    """Validate RFC 5545 RRULE syntax and constraints."""
    from ics_tools.exceptions import ParseError, RRuleError
    from ics_tools.rrule import parse_rrule

    try:
        parse_rrule(rrule_val)
    except (ParseError, RRuleError, ValueError) as err:
        result.add_error(str(err), component=comp_name, property_name="RRULE")
    parts = rrule_val.split(";")
    kv: dict[str, str] = {}
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            result.add_error(f"Malformed RRULE part {part!r}", component=comp_name, property_name="RRULE")
            continue
        k, v = part.split("=", 1)
        kv[k.upper()] = v

    if "FREQ" not in kv:
        result.add_error("RRULE missing mandatory FREQ part", component=comp_name, property_name="RRULE")
    elif kv["FREQ"].upper() not in FREQUENCIES:
        result.add_error(f"Invalid RRULE FREQ: {kv['FREQ']!r}", component=comp_name, property_name="RRULE")

    if "COUNT" in kv and "UNTIL" in kv:
        result.add_error("RRULE cannot specify both COUNT and UNTIL", component=comp_name, property_name="RRULE")

    if "INTERVAL" in kv:
        try:
            val = int(kv["INTERVAL"])
            if val < 1:
                result.add_error(f"INTERVAL must be >= 1, got {val}", component=comp_name, property_name="RRULE")
        except ValueError:
            result.add_error(f"Invalid integer for INTERVAL: {kv['INTERVAL']!r}", component=comp_name, property_name="RRULE")

    if "COUNT" in kv:
        try:
            val = int(kv["COUNT"])
            if val < 1:
                result.add_error(f"COUNT must be >= 1, got {val}", component=comp_name, property_name="RRULE")
        except ValueError:
            result.add_error(f"Invalid integer for COUNT: {kv['COUNT']!r}", component=comp_name, property_name="RRULE")

    if "BYDAY" in kv:
        for item in kv["BYDAY"].split(","):
            item = item.strip().upper()
            if not re.match(r"^([+-]?\d+)?(MO|TU|WE|TH|FR|SA|SU)$", item):
                result.add_error(f"Invalid BYDAY specifier {item!r}", component=comp_name, property_name="RRULE")

    if "WKST" in kv and kv["WKST"].upper() not in WEEKDAY_TO_INT:
        result.add_error(f"Invalid WKST day code: {kv['WKST']!r}", component=comp_name, property_name="RRULE")


def validate_calendar_component(comp: Component, result: ValidationResult) -> None:
    """Recursively validate an RFC 5545 Component and its children."""
    if comp.name == "VCALENDAR":
        # Check required VCALENDAR properties
        prodid = comp.get_properties("PRODID")
        if not prodid:
            result.add_error("VCALENDAR missing mandatory PRODID property", component="VCALENDAR")
        elif len(prodid) > 1:
            result.add_error("VCALENDAR contains multiple PRODID properties", component="VCALENDAR")

        version = comp.get_properties("VERSION")
        if not version:
            result.add_error("VCALENDAR missing mandatory VERSION property", component="VCALENDAR")
        elif len(version) > 1:
            result.add_error("VCALENDAR contains multiple VERSION properties", component="VCALENDAR")
        elif version[0].value.strip() != RFC_VERSION:
            result.add_warning(
                f"VCALENDAR VERSION is {version[0].value!r}, expected {RFC_VERSION}",
                component="VCALENDAR",
                property_name="VERSION",
            )

        calscale = comp.get_property_value("CALSCALE")
        if calscale and calscale.upper() != "GREGORIAN":
            result.add_warning(f"Non-standard CALSCALE {calscale!r}", component="VCALENDAR", property_name="CALSCALE")

    elif comp.name == "VEVENT":
        # Check required VEVENT properties
        uid_props = comp.get_properties("UID")
        if not uid_props:
            result.add_error("VEVENT missing mandatory UID property", component="VEVENT")
        elif len(uid_props) > 1:
            result.add_error("VEVENT has multiple UID properties", component="VEVENT")

        dtstamp_props = comp.get_properties("DTSTAMP")
        if not dtstamp_props:
            result.add_warning("VEVENT missing recommended DTSTAMP property", component="VEVENT")

        dtstart_props = comp.get_properties("DTSTART")
        if not dtstart_props:
            result.add_error("VEVENT missing mandatory DTSTART property", component="VEVENT")
        elif len(dtstart_props) > 1:
            result.add_error("VEVENT has multiple DTSTART properties", component="VEVENT")
        else:
            dtstart = dtstart_props[0]
            val_type = dtstart.get_param("VALUE", "").upper()
            if val_type == "DATE" or (len(dtstart.value.strip()) == 8 and "T" not in dtstart.value):
                _validate_date_value(dtstart.value.strip(), result, "VEVENT", "DTSTART")
            else:
                _validate_datetime_value(dtstart.value.strip(), result, "VEVENT", "DTSTART")

        # Mutually exclusive DTEND and DURATION
        has_dtend = bool(comp.get_properties("DTEND"))
        has_duration = bool(comp.get_properties("DURATION"))
        if has_dtend and has_duration:
            result.add_error("VEVENT cannot have both DTEND and DURATION properties", component="VEVENT")

        if has_dtend:
            dtend_prop = comp.get_property("DTEND")
            assert dtend_prop is not None
            val_type = dtend_prop.get_param("VALUE", "").upper()
            if val_type == "DATE" or (len(dtend_prop.value.strip()) == 8 and "T" not in dtend_prop.value):
                _validate_date_value(dtend_prop.value.strip(), result, "VEVENT", "DTEND")
            else:
                _validate_datetime_value(dtend_prop.value.strip(), result, "VEVENT", "DTEND")

        # Validate RRULE if present
        for rrule_prop in comp.get_properties("RRULE"):
            _validate_rrule(rrule_prop.value, result, "VEVENT")

    # Recurse into subcomponents
    for sub in comp.subcomponents:
        validate_calendar_component(sub, result)


def validate_calendar(source: str | bytes | Calendar) -> ValidationResult:
    """Validate an iCalendar string, bytes, or parsed Calendar against RFC 5545 rules."""
    result = ValidationResult()

    if isinstance(source, Calendar):
        comp = source.to_component()
        validate_calendar_component(comp, result)
        return result

    # Validate raw stream
    try:
        raw_lines = unfold_lines(source)
    except Exception as err:  # noqa: BLE001 - Public boundary reports errors without a traceback.
        result.add_error(f"Failed to unfold stream: {err}")
        return result

    if not raw_lines:
        result.add_error("Stream is empty")
        return result

    # Check top-level BEGIN/END
    first_no, first_line = raw_lines[0]
    if first_line.strip() != "BEGIN:VCALENDAR":
        result.add_error(f"First line must be 'BEGIN:VCALENDAR', found {first_line!r}", line_number=first_no)

    last_no, last_line = raw_lines[-1]
    if last_line.strip() != "END:VCALENDAR":
        result.add_error(f"Last line must be 'END:VCALENDAR', found {last_line!r}", line_number=last_no)

    # Parse and validate components structurally
    from ics_tools.parser import parse_raw_component

    try:
        raw_comp = parse_raw_component(source)
        validate_calendar_component(raw_comp, result)
    except Exception as err:  # noqa: BLE001 - Public boundary reports errors without a traceback.
        result.add_error(f"Stream parsing error: {err}")

    return result
