"""Byte-stable RFC 5545 iCalendar serializer."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ics_tools.constants import CRLF, MAX_OCTETS_PER_LINE, TEXT_PROPERTIES
from ics_tools.models import Calendar, Component, Property


def escape_text(text: str) -> str:
    r"""Escape an RFC 5545 TEXT value.

    Escapes \, ;, ,, and newlines with \n.
    """
    if not text:
        return ""
    # RFC 5545: backslash must be escaped first
    res = text.replace("\\", "\\\\")
    res = res.replace(";", r"\;")
    res = res.replace(",", r"\,")
    res = res.replace("\r\n", r"\n").replace("\r", r"\n").replace("\n", r"\n")
    return res


def fold_line(line: str, max_octets: int = MAX_OCTETS_PER_LINE) -> str:
    """Fold a single content line at max_octets boundaries in a UTF-8 safe manner.

    RFC 5545 Section 3.1: Lines of text SHOULD NOT be longer than 75 octets,
    excluding the line break. Long lines are folded by inserting CRLF immediately
    followed by a single linear white space character (space 0x20).
    """
    encoded = line.encode("utf-8")
    if len(encoded) <= max_octets:
        return line + CRLF

    parts: list[str] = []
    offset = 0
    total_len = len(encoded)

    while offset < total_len:
        # Continuation lines start with a single space (1 octet)
        chunk_limit = max_octets if offset == 0 else (max_octets - 1)
        remaining = total_len - offset

        if remaining <= chunk_limit:
            chunk_bytes = encoded[offset:]
            offset = total_len
        else:
            cut = offset + chunk_limit
            # In UTF-8, continuation bytes have bit pattern 10xxxxxx (0x80..0xBF)
            while cut > offset and (encoded[cut] & 0xC0) == 0x80:
                cut -= 1

            # Safety fallback: ensure at least one byte advance if cut == offset
            if cut == offset:
                cut = offset + chunk_limit

            chunk_bytes = encoded[offset:cut]
            offset = cut

        part_str = chunk_bytes.decode("utf-8")
        if parts:
            parts.append(" " + part_str)
        else:
            parts.append(part_str)

    return CRLF.join(parts) + CRLF


def format_date_or_datetime(
    dt: date | datetime,
) -> tuple[str, dict[str, list[str]]]:
    """Format a Python date or datetime into RFC 5545 string and parameters."""
    if not isinstance(dt, datetime) and isinstance(dt, date):
        # VALUE=DATE: YYYYMMDD
        val = f"{dt.year:04d}{dt.month:02d}{dt.day:02d}"
        return val, {"VALUE": ["DATE"]}

    # datetime instance
    assert isinstance(dt, datetime)
    val = f"{dt.year:04d}{dt.month:02d}{dt.day:02d}T{dt.hour:02d}{dt.minute:02d}{dt.second:02d}"

    if dt.tzinfo is None:
        # Floating date-time
        return val, {}

    # Check for UTC
    if isinstance(dt.tzinfo, timezone) or dt.utcoffset() == timedelta(0):
        # Format as UTC with trailing 'Z'
        dt_utc = dt.astimezone(timezone.utc)
        utc_val = f"{dt_utc.year:04d}{dt_utc.month:02d}{dt_utc.day:02d}T{dt_utc.hour:02d}{dt_utc.minute:02d}{dt_utc.second:02d}Z"
        return utc_val, {}

    # Local date-time with TZID
    tz_name: str | None = None
    if isinstance(dt.tzinfo, ZoneInfo):
        tz_name = dt.tzinfo.key
    elif hasattr(dt.tzinfo, "tzid"):
        tz_name = dt.tzinfo.tzid
    elif hasattr(dt.tzinfo, "zone"):
        tz_name = dt.tzinfo.zone
    else:
        tz_name = dt.tzname()

    if tz_name:
        return val, {"TZID": [tz_name]}

    return val, {}


def format_duration(delta: timedelta) -> str:
    """Format a timedelta into an RFC 5545 DURATION string."""
    total_seconds = int(delta.total_seconds())
    if total_seconds == 0:
        return "PT0S"

    sign = "-" if total_seconds < 0 else ""
    total_seconds = abs(total_seconds)

    days = total_seconds // 86400
    rem = total_seconds % 86400
    hours = rem // 3600
    rem = rem % 3600
    minutes = rem // 60
    seconds = rem % 60

    parts: list[str] = [f"{sign}P"]
    if days > 0:
        parts.append(f"{days}D")

    if hours > 0 or minutes > 0 or seconds > 0:
        parts.append("T")
        if hours > 0:
            parts.append(f"{hours}H")
        if minutes > 0:
            parts.append(f"{minutes}M")
        if seconds > 0 or (hours == 0 and minutes == 0 and days == 0):
            parts.append(f"{seconds}S")

    return "".join(parts)


def serialize_property(prop: Property) -> str:
    """Serialize a single Property to a folded RFC 5545 content line."""
    name = prop.name.upper()

    # Format parameters deterministically (alphabetical by parameter key)
    param_strs: list[str] = []
    for key in sorted(prop.params.keys()):
        vals = prop.params[key]
        formatted_vals: list[str] = []
        for v in vals:
            # Check if parameter value needs quoting (contains :, ;, or ,)
            if any(ch in v for ch in (":", ";", ",")) or " " in v:
                formatted_vals.append(f'"{v}"')
            else:
                formatted_vals.append(v)
        param_strs.append(f"{key}={','.join(formatted_vals)}")

    param_suffix = f";{';'.join(param_strs)}" if param_strs else ""

    # Check if value needs escaping
    if name in TEXT_PROPERTIES or prop.get_param("VALUE") == "TEXT":
        escaped_value = escape_text(prop.value)
    else:
        escaped_value = prop.value

    raw_line = f"{name}{param_suffix}:{escaped_value}"
    return fold_line(raw_line)


def _sort_properties(comp_name: str, properties: list[Property]) -> list[Property]:
    """Sort component properties deterministically."""
    if comp_name == "VCALENDAR":
        order = ["PRODID", "VERSION", "CALSCALE", "METHOD"]
    elif comp_name == "VEVENT":
        order = [
            "UID",
            "DTSTAMP",
            "RECURRENCE-ID",
            "SEQUENCE",
            "DTSTART",
            "DTEND",
            "DURATION",
            "RRULE",
            "SUMMARY",
            "DESCRIPTION",
            "LOCATION",
            "STATUS",
            "TRANSP",
            "CREATED",
            "LAST-MODIFIED",
            "CATEGORIES",
            "URL",
        ]
    elif comp_name in ("STANDARD", "DAYLIGHT"):
        order = ["TZOFFSETFROM", "TZOFFSETTO", "TZNAME", "DTSTART", "RRULE", "RDATE"]
    elif comp_name == "VTIMEZONE":
        order = ["TZID", "LAST-MODIFIED", "TZURL"]
    else:
        order = []

    priority_map = {k: i for i, k in enumerate(order)}
    return sorted(properties, key=lambda p: (priority_map.get(p.name, 999), p.name, p.value))


def _sort_subcomponents(subcomponents: list[Component]) -> list[Component]:
    """Sort subcomponents deterministically."""
    # VTIMEZONEs first, then VEVENTs, then others
    type_priority = {"VTIMEZONE": 1, "STANDARD": 2, "DAYLIGHT": 3, "VEVENT": 4, "VALARM": 5}

    def key_fn(comp: Component) -> tuple:
        prio = type_priority.get(comp.name, 10)
        uid = comp.get_property_value("UID", "") or ""
        tzid = comp.get_property_value("TZID", "") or ""
        dtstart = comp.get_property_value("DTSTART", "") or ""
        rec_id = comp.get_property_value("RECURRENCE-ID", "") or ""
        return (prio, comp.name, tzid, dtstart, uid, rec_id)

    return sorted(subcomponents, key=key_fn)


def serialize_component(comp: Component) -> str:
    """Serialize a Component and all its children into RFC 5545 string."""
    lines: list[str] = [fold_line(f"BEGIN:{comp.name}")]

    for prop in _sort_properties(comp.name, comp.properties):
        lines.append(serialize_property(prop))

    for sub in _sort_subcomponents(comp.subcomponents):
        lines.append(serialize_component(sub))

    lines.append(fold_line(f"END:{comp.name}"))
    return "".join(lines)


def serialize_calendar(calendar: Calendar) -> str:
    """Serialize a Calendar instance to an RFC 5545 formatted string."""
    comp = calendar.to_component()
    return serialize_component(comp)


def serialize_calendar_bytes(calendar: Calendar) -> bytes:
    """Serialize a Calendar instance to UTF-8 encoded bytes."""
    return serialize_calendar(calendar).encode("utf-8")
