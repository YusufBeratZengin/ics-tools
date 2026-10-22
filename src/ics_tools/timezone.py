"""Timezone resolution according to RFC 5545.

Prefers standard IANA TZID mappings via Python's zoneinfo module.
Provides a documented fallback for embedded VTIMEZONE components and
common legacy or Windows timezone identifiers.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone, tzinfo
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ics_tools.constants import WINDOWS_TO_IANA_TZ

if TYPE_CHECKING:
    from ics_tools.models import Component

logger = logging.getLogger("ics_tools.timezone")


def parse_tzoffset(offset_str: str) -> timedelta:
    """Parse an RFC 5545 timezone offset string such as '+0200' or '-0500' into a timedelta."""
    offset_str = offset_str.strip()
    match = re.match(r"^([+-])(\d{2})(\d{2})(?:(\d{2}))?$", offset_str)
    if not match:
        raise ValueError(f"Invalid timezone offset format: {offset_str!r}")

    sign, hours, minutes, seconds = match.groups()
    total_seconds = int(hours) * 3600 + int(minutes) * 60 + (int(seconds) if seconds else 0)
    if sign == "-":
        total_seconds = -total_seconds
    return timedelta(seconds=total_seconds)


def format_tzoffset(delta: timedelta) -> str:
    """Format a timedelta into an RFC 5545 timezone offset string like '+0300'."""
    total_seconds = int(delta.total_seconds())
    sign = "-" if total_seconds < 0 else "+"
    total_seconds = abs(total_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{sign}{hours:02d}{minutes:02d}"


class EmbeddedVTimezone(tzinfo):
    """Fallback tzinfo derived from embedded RFC 5545 VTIMEZONE component.

    Limitations:
    Embedded VTIMEZONE components may have complex historical transitions
    and recurrence rules that vary across decades. This fallback provides
    support for fixed offsets and standard/daylight dual transitions. For full
    historical accuracy, IANA timezone definitions (preferred) should be used.
    """

    def __init__(
        self,
        tzid: str,
        standard_offset: timedelta,
        daylight_offset: timedelta | None = None,
        standard_name: str | None = None,
        daylight_name: str | None = None,
    ) -> None:
        self._tzid = tzid
        self._standard_offset = standard_offset
        self._daylight_offset = daylight_offset if daylight_offset is not None else standard_offset
        self._standard_name = standard_name or tzid
        self._daylight_name = daylight_name or standard_name or tzid

    @property
    def tzid(self) -> str:
        return self._tzid

    def utcoffset(self, dt: datetime | None) -> timedelta | None:
        if dt is None:
            return None
        # If no distinct daylight offset, return standard
        if self._daylight_offset == self._standard_offset:
            return self._standard_offset

        # Simplified seasonal estimation: daylight saving typically runs
        # from late March to late October in the northern hemisphere.
        month = dt.month
        if 4 <= month <= 9:
            return self._daylight_offset
        if month in (3, 10):
            if (month == 3 and dt.day >= 25) or (month == 10 and dt.day < 25):
                return self._daylight_offset
            return self._standard_offset
        return self._standard_offset

    def dst(self, dt: datetime | None) -> timedelta | None:
        if dt is None or self._daylight_offset == self._standard_offset:
            return timedelta(0)
        offset = self.utcoffset(dt)
        if offset == self._daylight_offset:
            return self._daylight_offset - self._standard_offset
        return timedelta(0)

    def tzname(self, dt: datetime | None) -> str | None:
        if dt is None or self._daylight_offset == self._standard_offset:
            return self._standard_name
        offset = self.utcoffset(dt)
        return self._daylight_name if offset == self._daylight_offset else self._standard_name

    def __repr__(self) -> str:
        return f"EmbeddedVTimezone(tzid={self._tzid!r}, standard={self._standard_offset}, daylight={self._daylight_offset})"


# Fallback table for environments lacking the system IANA tz database (e.g. bare Windows without tzdata package)
# Maps IANA TZID to (standard_offset_hours, daylight_offset_hours_or_None, standard_name, daylight_name)
COMMON_IANA_FALLBACKS: dict[str, tuple[float, float | None, str, str]] = {
    "Europe/Istanbul": (3.0, None, "TRT", "TRT"),
    "Europe/London": (0.0, 1.0, "GMT", "BST"),
    "Europe/Paris": (1.0, 2.0, "CET", "CEST"),
    "Europe/Berlin": (1.0, 2.0, "CET", "CEST"),
    "Europe/Rome": (1.0, 2.0, "CET", "CEST"),
    "Europe/Madrid": (1.0, 2.0, "CET", "CEST"),
    "Europe/Amsterdam": (1.0, 2.0, "CET", "CEST"),
    "Europe/Brussels": (1.0, 2.0, "CET", "CEST"),
    "Europe/Vienna": (1.0, 2.0, "CET", "CEST"),
    "Europe/Warsaw": (1.0, 2.0, "CET", "CEST"),
    "Europe/Prague": (1.0, 2.0, "CET", "CEST"),
    "Europe/Stockholm": (1.0, 2.0, "CET", "CEST"),
    "Europe/Athens": (2.0, 3.0, "EET", "EEST"),
    "Europe/Bucharest": (2.0, 3.0, "EET", "EEST"),
    "Europe/Helsinki": (2.0, 3.0, "EET", "EEST"),
    "Europe/Kiev": (2.0, 3.0, "EET", "EEST"),
    "Europe/Moscow": (3.0, None, "MSK", "MSK"),
    "America/New_York": (-5.0, -4.0, "EST", "EDT"),
    "America/Detroit": (-5.0, -4.0, "EST", "EDT"),
    "America/Chicago": (-6.0, -5.0, "CST", "CDT"),
    "America/Denver": (-7.0, -6.0, "MST", "MDT"),
    "America/Phoenix": (-7.0, None, "MST", "MST"),
    "America/Los_Angeles": (-8.0, -7.0, "PST", "PDT"),
    "America/Anchorage": (-9.0, -8.0, "AKST", "AKDT"),
    "Pacific/Honolulu": (-10.0, None, "HST", "HST"),
    "America/Toronto": (-5.0, -4.0, "EST", "EDT"),
    "America/Vancouver": (-8.0, -7.0, "PST", "PDT"),
    "America/Sao_Paulo": (-3.0, None, "-03", "-03"),
    "America/Buenos_Aires": (-3.0, None, "-03", "-03"),
    "America/Bogota": (-5.0, None, "-05", "-05"),
    "America/Halifax": (-4.0, -3.0, "AST", "ADT"),
    "America/St_Johns": (-3.5, -2.5, "NST", "NDT"),
    "Asia/Tokyo": (9.0, None, "JST", "JST"),
    "Asia/Shanghai": (8.0, None, "CST", "CST"),
    "Asia/Hong_Kong": (8.0, None, "HKT", "HKT"),
    "Asia/Singapore": (8.0, None, "+08", "+08"),
    "Asia/Seoul": (9.0, None, "KST", "KST"),
    "Asia/Kolkata": (5.5, None, "IST", "IST"),
    "Asia/Dubai": (4.0, None, "+04", "+04"),
    "Asia/Riyadh": (3.0, None, "+03", "+03"),
    "Asia/Jerusalem": (2.0, 3.0, "IST", "IDT"),
    "Asia/Bangkok": (7.0, None, "+07", "+07"),
    "Asia/Jakarta": (7.0, None, "WIB", "WIB"),
    "Australia/Sydney": (10.0, 11.0, "AEST", "AEDT"),
    "Australia/Melbourne": (10.0, 11.0, "AEST", "AEDT"),
    "Australia/Brisbane": (10.0, None, "AEST", "AEST"),
    "Australia/Perth": (8.0, None, "AWST", "AWST"),
    "Pacific/Auckland": (12.0, 13.0, "NZST", "NZDT"),
    "Etc/UTC": (0.0, None, "UTC", "UTC"),
    "Etc/GMT": (0.0, None, "GMT", "GMT"),
}


def _create_fallback_tz(tzid: str) -> EmbeddedVTimezone | None:
    """Create a fallback EmbeddedVTimezone from common IANA table if available."""
    spec = COMMON_IANA_FALLBACKS.get(tzid)
    if not spec:
        return None
    std_h, dst_h, std_name, dst_name = spec
    std_offset = timedelta(seconds=int(std_h * 3600))
    dst_offset = timedelta(seconds=int(dst_h * 3600)) if dst_h is not None else std_offset
    return EmbeddedVTimezone(
        tzid=tzid,
        standard_offset=std_offset,
        daylight_offset=dst_offset,
        standard_name=std_name,
        daylight_name=dst_name,
    )


class TimezoneResolver:
    """Resolves RFC 5545 TZID strings to Python tzinfo instances."""

    def __init__(self, embedded_timezones: list[Component] | None = None) -> None:
        self._embedded_map: dict[str, EmbeddedVTimezone] = {}
        if embedded_timezones:
            for vtz in embedded_timezones:
                self.register_vtimezone(vtz)

    def register_vtimezone(self, vtz: Component) -> None:
        """Extract offsets from a VTIMEZONE component and register as fallback."""
        tzid_prop = vtz.get_property("TZID")
        if not tzid_prop or not tzid_prop.value:
            return
        tzid = tzid_prop.value.strip().strip('"')

        standard_offset: timedelta | None = None
        daylight_offset: timedelta | None = None
        standard_name: str | None = None
        daylight_name: str | None = None

        for sub in vtz.subcomponents:
            name = sub.name.upper()
            offset_to_prop = sub.get_property("TZOFFSETTO")
            tzname_prop = sub.get_property("TZNAME")

            if offset_to_prop and offset_to_prop.value:
                try:
                    delta = parse_tzoffset(offset_to_prop.value)
                    if name == "STANDARD":
                        standard_offset = delta
                        if tzname_prop:
                            standard_name = tzname_prop.value
                    elif name == "DAYLIGHT":
                        daylight_offset = delta
                        if tzname_prop:
                            daylight_name = tzname_prop.value
                except ValueError:
                    continue

        if standard_offset is not None or daylight_offset is not None:
            resolved_std = standard_offset if standard_offset is not None else daylight_offset
            assert resolved_std is not None
            self._embedded_map[tzid] = EmbeddedVTimezone(
                tzid=tzid,
                standard_offset=resolved_std,
                daylight_offset=daylight_offset or resolved_std,
                standard_name=standard_name,
                daylight_name=daylight_name,
            )

    def resolve(self, tzid: str) -> tzinfo:
        """Resolve a TZID identifier into a tzinfo instance.

        Order of resolution:
        1. Clean and check for UTC / GMT / Z.
        2. Attempt standard IANA resolution via ZoneInfo.
        3. Attempt fallback resolution via COMMON_IANA_FALLBACKS (for bare Windows without tzdata).
        4. Attempt lookup via Windows timezone mapping table.
        5. Attempt lookup via embedded VTIMEZONE fallback.
        6. If timezone cannot be resolved, return UTC with warning log.
        """
        clean_tzid = tzid.strip().strip('"')

        # Fast path for common UTC representations
        if clean_tzid.upper() in {"UTC", "GMT", "Z", "ETC/UTC", "ETC/GMT"}:
            return timezone.utc

        # 1. Prefer standard IANA mapping via ZoneInfo
        try:
            return ZoneInfo(clean_tzid)
        except (ZoneInfoNotFoundError, ValueError, Exception):
            pass

        # 2. Check common IANA fallback table (useful on Windows without tzdata package)
        fallback = _create_fallback_tz(clean_tzid)
        if fallback is not None:
            return fallback

        # 3. Windows timezone name mapping
        iana_name = WINDOWS_TO_IANA_TZ.get(clean_tzid)
        if iana_name:
            try:
                return ZoneInfo(iana_name)
            except (ZoneInfoNotFoundError, ValueError, Exception):
                pass
            fallback = _create_fallback_tz(iana_name)
            if fallback is not None:
                return fallback

        # 4. Strip common leading slashes or prefixes (e.g. '/freeassociation.sourceforge.net/Europe/Istanbul')
        if "/" in clean_tzid:
            parts = clean_tzid.split("/")
            if len(parts) >= 2:
                sub_candidate = f"{parts[-2]}/{parts[-1]}"
                try:
                    return ZoneInfo(sub_candidate)
                except (ZoneInfoNotFoundError, ValueError, Exception):
                    pass
                fallback = _create_fallback_tz(sub_candidate)
                if fallback is not None:
                    return fallback

            try:
                return ZoneInfo(parts[-1])
            except (ZoneInfoNotFoundError, ValueError, Exception):
                pass
            fallback = _create_fallback_tz(parts[-1])
            if fallback is not None:
                return fallback

        # 5. Fallback to embedded VTIMEZONE rules
        if clean_tzid in self._embedded_map:
            return self._embedded_map[clean_tzid]

        logger.warning(
            "Unknown or unsupported timezone %r; falling back to UTC. "
            "Embedded VTIMEZONE definition was either missing or insufficient.",
            clean_tzid,
        )
        return timezone.utc


# Global default resolver
DEFAULT_RESOLVER = TimezoneResolver()
