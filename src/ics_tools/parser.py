"""RFC 5545 iCalendar stream parser."""

from __future__ import annotations

import io
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import TextIO

from ics_tools.constants import TEXT_PROPERTIES
from ics_tools.exceptions import ParseError
from ics_tools.models import Calendar, Component, Property
from ics_tools.timezone import DEFAULT_RESOLVER, TimezoneResolver

# Regex for ISO 8601 / RFC 5545 duration: [+|-]P[nD][T[nH][nM][nS]] or [+|-]P[nW]
_DURATION_REGEX = re.compile(
    r"^(?P<sign>[+-])?P(?:(?P<weeks>\d+)W|(?P<days>\d+D)?(?:T(?P<hours>\d+H)?(?P<minutes>\d+M)?(?P<seconds>\d+S)?)?)$"
)


def unescape_text(text: str) -> str:
    r"""Unescape an RFC 5545 TEXT value.

    Replaces \, \; \\ \N \n with their literal representations.
    """
    if not text:
        return ""
    result: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n:
            nxt = text[i + 1]
            if nxt in (",", ";", "\\"):
                result.append(nxt)
                i += 2
                continue
            elif nxt in ("n", "N"):
                result.append("\n")
                i += 2
                continue
            else:
                # Unknown escape sequence; preserve backslash and next char
                result.append(c)
                result.append(nxt)
                i += 2
                continue
        result.append(c)
        i += 1
    return "".join(result)


def unfold_lines(raw: str | bytes) -> list[tuple[int, str]]:
    """Unfold folded lines according to RFC 5545 Section 3.1.

    Returns a list of (start_line_number, unfolded_content_line).
    """
    if isinstance(raw, bytes):
        # Decode UTF-8 and strip UTF-8 BOM if present
        text = raw.decode("utf-8-sig")
    else:
        text = raw
        if text.startswith("\ufeff"):
            text = text[1:]

    # Normalize line breaks to \n while preserving positions
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    unfolded: list[tuple[int, str]] = []
    current_line = ""
    current_line_no = 1

    for line_idx, line in enumerate(lines, start=1):
        if not line:
            # Skip empty lines
            continue

        # Check for RFC 5545 continuation: leading space or tab
        if line[0] in (" ", "\t"):
            if not current_line:
                # Continuation at the very start of input; treat as standalone
                current_line = line[1:]
                current_line_no = line_idx
            else:
                current_line += line[1:]
        else:
            if current_line:
                unfolded.append((current_line_no, current_line))
            current_line = line
            current_line_no = line_idx

    if current_line:
        unfolded.append((current_line_no, current_line))

    return unfolded


def parse_content_line(line: str, line_no: int | None = None) -> Property:
    """Parse a single unfolded RFC 5545 content line into a Property.

    Format: name *(";" param-name "=" param-value *("," param-value) ) ":" value
    """
    # Find the property delimiter ':' outside of quoted strings
    colon_idx = -1
    in_quotes = False
    for i, char in enumerate(line):
        if char == '"':
            in_quotes = not in_quotes
        elif char == ":" and not in_quotes:
            colon_idx = i
            break

    if colon_idx == -1:
        raise ParseError("Missing ':' delimiter in content line", line_number=line_no, line_content=line)

    left = line[:colon_idx].strip()
    raw_value = line[colon_idx + 1 :]

    # Parse name and parameters from left
    # Parameters are delimited by ';' outside quotes
    parts: list[str] = []
    current_part: list[str] = []
    in_quotes = False
    for char in left:
        if char == '"':
            in_quotes = not in_quotes
            current_part.append(char)
        elif char == ";" and not in_quotes:
            parts.append("".join(current_part).strip())
            current_part = []
        else:
            current_part.append(char)
    if current_part:
        parts.append("".join(current_part).strip())

    if not parts or not parts[0]:
        raise ParseError("Empty property name in content line", line_number=line_no, line_content=line)

    prop_name = parts[0].upper()
    params: dict[str, list[str]] = {}

    for param_token in parts[1:]:
        if not param_token:
            continue
        eq_idx = param_token.find("=")
        if eq_idx == -1:
            # Parameter without value; assign empty string
            param_name = param_token.upper()
            params[param_name] = [""]
            continue

        param_name = param_token[:eq_idx].strip().upper()
        param_val_str = param_token[eq_idx + 1 :].strip()

        # Parse comma-separated parameter values, taking quotes into account
        val_tokens: list[str] = []
        cur_val: list[str] = []
        in_q = False
        for ch in param_val_str:
            if ch == '"':
                in_q = not in_q
            elif ch == "," and not in_q:
                val_tokens.append("".join(cur_val).strip().strip('"'))
                cur_val = []
                continue
            cur_val.append(ch)
        if cur_val:
            val_tokens.append("".join(cur_val).strip().strip('"'))

        params[param_name] = val_tokens

    # Unescape TEXT properties
    if prop_name in TEXT_PROPERTIES or params.get("VALUE") == ["TEXT"]:
        value = unescape_text(raw_value)
    else:
        value = raw_value

    return Property(name=prop_name, value=value, params=params)


def parse_date_or_datetime(
    prop: Property,
    tz_resolver: TimezoneResolver | None = None,
) -> datetime | date:
    """Parse an RFC 5545 DATE or DATE-TIME property value."""
    val = prop.value.strip()
    val_param = prop.get_param("VALUE", "").upper()
    resolver = tz_resolver or DEFAULT_RESOLVER

    # 1. Date only: YYYYMMDD
    if val_param == "DATE" or (re.match(r"^\d{8}$", val) and "T" not in val):
        try:
            return date(int(val[0:4]), int(val[4:6]), int(val[6:8]))
        except ValueError as err:
            raise ParseError(f"Invalid DATE value: {val!r}") from err

    # 2. Date-time: YYYYMMDDTHHMMSS or YYYYMMDDTHHMMSSZ
    match = re.match(r"^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(Z)?$", val)
    if not match:
        raise ParseError(f"Invalid DATE-TIME value: {val!r}")

    year, month, day, hour, minute, second, is_utc = match.groups()
    try:
        dt = datetime(
            int(year),
            int(month),
            int(day),
            int(hour),
            int(minute),
            int(second),
        )
    except ValueError as err:
        raise ParseError(f"Invalid date/time components: {val!r}") from err

    if is_utc:
        return dt.replace(tzinfo=timezone.utc)

    # Check for TZID parameter
    tzid = prop.get_param("TZID")
    if tzid:
        resolved_tz = resolver.resolve(tzid)
        return dt.replace(tzinfo=resolved_tz)

    # Floating date-time (naive)
    return dt


def parse_duration(val: str) -> timedelta:
    """Parse an RFC 5545 DURATION string into a timedelta."""
    val = val.strip()
    match = _DURATION_REGEX.match(val)
    if not match:
        raise ValueError(f"Invalid DURATION format: {val!r}")

    sign = -1 if match.group("sign") == "-" else 1
    weeks_str = match.group("weeks")

    if weeks_str:
        return timedelta(days=sign * int(weeks_str) * 7)

    days = int(match.group("days")[:-1]) if match.group("days") else 0
    hours = int(match.group("hours")[:-1]) if match.group("hours") else 0
    minutes = int(match.group("minutes")[:-1]) if match.group("minutes") else 0
    seconds = int(match.group("seconds")[:-1]) if match.group("seconds") else 0

    total_seconds = days * 86400 + hours * 3600 + minutes * 60 + seconds
    return timedelta(seconds=sign * total_seconds)


def parse_raw_component(
    source: str | bytes | Path | TextIO,
) -> Component:
    """Parse an iCalendar stream into a raw Component tree without semantic type conversion."""
    if isinstance(source, Path):
        content = source.read_text(encoding="utf-8-sig")
    elif isinstance(source, (io.TextIOBase, io.StringIO)):
        content = source.read()
    elif isinstance(source, (io.RawIOBase, io.BufferedIOBase)):
        content = source.read().decode("utf-8-sig")
    elif isinstance(source, (str, bytes)):
        content = source
    else:
        raise TypeError(f"Unsupported source type: {type(source).__name__}")

    lines = unfold_lines(content)
    if not lines:
        raise ParseError("Empty iCalendar stream")

    stack: list[Component] = []
    root_component: Component | None = None

    for line_no, raw_line in lines:
        line_clean = raw_line.strip()
        if not line_clean:
            continue

        if line_clean.startswith("BEGIN:"):
            comp_name = line_clean[6:].strip().upper()
            new_comp = Component(name=comp_name)
            stack.append(new_comp)
            continue

        if line_clean.startswith("END:"):
            comp_name = line_clean[4:].strip().upper()
            if not stack:
                raise ParseError(f"Unexpected 'END:{comp_name}' without preceding BEGIN", line_number=line_no)
            top = stack[-1]
            if top.name != comp_name:
                raise ParseError(
                    f"Mismatched component end: expected 'END:{top.name}', found 'END:{comp_name}'",
                    line_number=line_no,
                )
            popped = stack.pop()
            if stack:
                stack[-1].add_component(popped)
            else:
                root_component = popped
            continue

        # Normal property line
        if not stack:
            raise ParseError("Content line found outside of any BEGIN/END component", line_number=line_no, line_content=raw_line)

        prop = parse_content_line(raw_line, line_no=line_no)
        stack[-1].add_property(prop)

    if stack:
        unclosed = ", ".join(c.name for c in stack)
        raise ParseError(f"Unclosed components at end of stream: {unclosed}")

    if root_component is None:
        raise ParseError("No component found in iCalendar stream")

    return root_component


def parse_calendar(
    source: str | bytes | Path | TextIO,
    tz_resolver: TimezoneResolver | None = None,
) -> Calendar:
    """Parse an iCalendar stream from string, bytes, file path, or file-like object."""
    root_comp = parse_raw_component(source)
    if root_comp.name != "VCALENDAR":
        raise ParseError(f"Root component must be VCALENDAR, found {root_comp.name}")
    return Calendar.from_component(root_comp)
