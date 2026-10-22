"""Data models for RFC 5545 iCalendar components and properties."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from ics_tools.constants import DEFAULT_PRODID, RFC_VERSION

if TYPE_CHECKING:
    from ics_tools.timezone import TimezoneResolver


@dataclass
class Property:
    """An RFC 5545 content line property."""

    name: str
    value: str
    params: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.name = self.name.strip().upper()
        # Normalize parameter keys to upper case
        normalized_params: dict[str, list[str]] = {}
        for k, v in self.params.items():
            normalized_params[k.strip().upper()] = [str(x) for x in v] if isinstance(v, list) else [str(v)]
        self.params = normalized_params

    def get_param(self, name: str, default: str | None = None) -> str | None:
        """Return the first value of the specified parameter name, or default."""
        values = self.params.get(name.upper())
        if values and len(values) > 0:
            return values[0]
        return default

    def get_param_values(self, name: str) -> list[str]:
        """Return all values for the specified parameter name."""
        return self.params.get(name.upper(), [])

    def set_param(self, name: str, value: str | list[str]) -> None:
        """Set parameter value(s)."""
        key = name.upper()
        if isinstance(value, list):
            self.params[key] = [str(x) for x in value]
        else:
            self.params[key] = [str(value)]

    def remove_param(self, name: str) -> None:
        """Remove a parameter by name."""
        self.params.pop(name.upper(), None)

    def copy(self) -> Property:
        return Property(name=self.name, value=self.value, params=copy.deepcopy(self.params))


@dataclass
class Component:
    """A generic RFC 5545 calendar component (e.g. VCALENDAR, VEVENT, VTIMEZONE)."""

    name: str
    properties: list[Property] = field(default_factory=list)
    subcomponents: list[Component] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.name = self.name.strip().upper()

    def get_property(self, name: str) -> Property | None:
        """Return the first property matching the given name, or None."""
        key = name.upper()
        for prop in self.properties:
            if prop.name == key:
                return prop
        return None

    def get_properties(self, name: str) -> list[Property]:
        """Return all properties matching the given name."""
        key = name.upper()
        return [p for p in self.properties if p.name == key]

    def get_property_value(self, name: str, default: str | None = None) -> str | None:
        """Return the string value of the first property matching name, or default."""
        prop = self.get_property(name)
        if prop is not None:
            return prop.value
        return default

    def add_property(
        self,
        name_or_prop: str | Property,
        value: str | None = None,
        params: dict[str, list[str]] | None = None,
    ) -> Property:
        """Add a property to this component."""
        if isinstance(name_or_prop, Property):
            self.properties.append(name_or_prop)
            return name_or_prop
        prop = Property(name=name_or_prop, value=value or "", params=params or {})
        self.properties.append(prop)
        return prop

    def set_property(
        self,
        name: str,
        value: str,
        params: dict[str, list[str]] | None = None,
    ) -> Property:
        """Replace the first existing property with this name or append a new one."""
        key = name.upper()
        for idx, prop in enumerate(self.properties):
            if prop.name == key:
                prop.value = value
                if params is not None:
                    prop.params = {k.upper(): v if isinstance(v, list) else [v] for k, v in params.items()}
                return prop
        return self.add_property(name, value, params)

    def remove_properties(self, name: str) -> int:
        """Remove all properties matching the given name. Returns count removed."""
        key = name.upper()
        initial_len = len(self.properties)
        self.properties = [p for p in self.properties if p.name != key]
        return initial_len - len(self.properties)

    def get_components(self, name: str | None = None) -> list[Component]:
        """Return subcomponents matching name, or all subcomponents if name is None."""
        if name is None:
            return list(self.subcomponents)
        key = name.upper()
        return [c for c in self.subcomponents if c.name == key]

    def add_component(self, comp: Component) -> None:
        """Add a subcomponent."""
        self.subcomponents.append(comp)

    def copy(self) -> Component:
        return Component(
            name=self.name,
            properties=[p.copy() for p in self.properties],
            subcomponents=[c.copy() for c in self.subcomponents],
        )


@dataclass
class EventOccurrence:
    """An expanded occurrence of a calendar event."""

    uid: str
    start: datetime | date
    end: datetime | date
    summary: str = ""
    description: str = ""
    location: str = ""
    status: str = "CONFIRMED"
    is_all_day: bool = False
    recurrence_id: datetime | date | None = None
    is_overridden: bool = False
    categories: list[str] = field(default_factory=list)
    event: Event | None = None

    @property
    def duration(self) -> timedelta:
        if isinstance(self.start, datetime) and isinstance(self.end, datetime):
            return self.end - self.start
        elif isinstance(self.start, date) and isinstance(self.end, date):
            return timedelta(days=(self.end - self.start).days)
        return timedelta(0)


@dataclass
class Event:
    """High-level abstraction for an RFC 5545 VEVENT component."""

    uid: str
    dtstart: datetime | date
    dtend: datetime | date | None = None
    duration: timedelta | None = None
    summary: str = ""
    description: str = ""
    location: str = ""
    status: str = "CONFIRMED"
    rrule: str | None = None
    exdate: list[datetime | date] = field(default_factory=list)
    rdate: list[datetime | date] = field(default_factory=list)
    recurrence_id: datetime | date | None = None
    sequence: int = 0
    transp: str = "OPAQUE"
    created: datetime | None = None
    last_modified: datetime | None = None
    dtstamp: datetime | None = None
    categories: list[str] = field(default_factory=list)
    url: str | None = None
    alarms: list[Component] = field(default_factory=list)
    extra_properties: list[Property] = field(default_factory=list)
    raw_component: Component | None = None

    @property
    def is_all_day(self) -> bool:
        """Return True if DTSTART is a date rather than a datetime."""
        return not isinstance(self.dtstart, datetime) and isinstance(self.dtstart, date)

    @property
    def effective_end(self) -> datetime | date:
        """Return the effective end date/datetime of the event."""
        if self.dtend is not None:
            return self.dtend
        if self.duration is not None:
            if isinstance(self.dtstart, datetime):
                return self.dtstart + self.duration
            else:
                return self.dtstart + timedelta(days=max(1, self.duration.days))
        if self.is_all_day:
            return self.dtstart + timedelta(days=1)
        return self.dtstart

    @property
    def effective_duration(self) -> timedelta:
        """Return the effective timedelta duration."""
        if self.duration is not None:
            return self.duration
        if self.dtend is not None:
            if isinstance(self.dtstart, datetime) and isinstance(self.dtend, datetime):
                return self.dtend - self.dtstart
            elif isinstance(self.dtstart, date) and isinstance(self.dtend, date):
                return timedelta(days=(self.dtend - self.dtstart).days)
        if self.is_all_day:
            return timedelta(days=1)
        return timedelta(0)

    def to_component(self) -> Component:
        """Serialize this Event back into an RFC 5545 VEVENT Component."""
        from ics_tools.writer import format_date_or_datetime, format_duration

        comp = Component(name="VEVENT")
        comp.add_property("UID", self.uid)

        # DTSTAMP is mandatory in VEVENT
        if self.dtstamp is not None:
            val, params = format_date_or_datetime(self.dtstamp)
            comp.add_property("DTSTAMP", val, params)
        else:
            now_utc = datetime.now(tz=timezone.utc)
            val, params = format_date_or_datetime(now_utc)
            comp.add_property("DTSTAMP", val, params)

        if self.recurrence_id is not None:
            val, params = format_date_or_datetime(self.recurrence_id)
            comp.add_property("RECURRENCE-ID", val, params)

        val, params = format_date_or_datetime(self.dtstart)
        comp.add_property("DTSTART", val, params)

        if self.dtend is not None:
            val, params = format_date_or_datetime(self.dtend)
            comp.add_property("DTEND", val, params)
        elif self.duration is not None:
            comp.add_property("DURATION", format_duration(self.duration))

        if self.summary:
            comp.add_property("SUMMARY", self.summary)
        if self.description:
            comp.add_property("DESCRIPTION", self.description)
        if self.location:
            comp.add_property("LOCATION", self.location)
        if self.status:
            comp.add_property("STATUS", self.status)
        if self.rrule:
            comp.add_property("RRULE", self.rrule)
        if self.sequence != 0:
            comp.add_property("SEQUENCE", str(self.sequence))
        if self.transp:
            comp.add_property("TRANSP", self.transp)
        if self.categories:
            comp.add_property("CATEGORIES", ",".join(self.categories))
        if self.url:
            comp.add_property("URL", self.url)
        if self.created:
            val, params = format_date_or_datetime(self.created)
            comp.add_property("CREATED", val, params)
        if self.last_modified:
            val, params = format_date_or_datetime(self.last_modified)
            comp.add_property("LAST-MODIFIED", val, params)

        for ex in self.exdate:
            val, params = format_date_or_datetime(ex)
            comp.add_property("EXDATE", val, params)

        for rd in self.rdate:
            val, params = format_date_or_datetime(rd)
            comp.add_property("RDATE", val, params)

        # Preserve unknown extra properties
        for prop in self.extra_properties:
            comp.add_property(prop.copy())

        # Include subcomponents such as VALARM
        for alarm in self.alarms:
            comp.add_component(alarm.copy())

        return comp

    @classmethod
    def from_component(cls, comp: Component, tz_resolver: TimezoneResolver | None = None) -> Event:
        """Construct an Event instance from an RFC 5545 VEVENT Component."""
        from ics_tools.parser import parse_date_or_datetime, parse_duration
        from ics_tools.timezone import DEFAULT_RESOLVER

        resolver = tz_resolver or DEFAULT_RESOLVER

        uid = comp.get_property_value("UID", "")
        summary = comp.get_property_value("SUMMARY", "") or ""
        description = comp.get_property_value("DESCRIPTION", "") or ""
        location = comp.get_property_value("LOCATION", "") or ""
        status = comp.get_property_value("STATUS", "CONFIRMED") or "CONFIRMED"
        rrule_str = comp.get_property_value("RRULE")
        transp = comp.get_property_value("TRANSP", "OPAQUE") or "OPAQUE"
        url = comp.get_property_value("URL")

        seq_str = comp.get_property_value("SEQUENCE", "0") or "0"
        try:
            sequence = int(seq_str)
        except ValueError:
            sequence = 0

        # Parse DTSTART (mandatory in RFC 5545)
        dtstart_prop = comp.get_property("DTSTART")
        if dtstart_prop:
            dtstart = parse_date_or_datetime(dtstart_prop, resolver)
        else:
            # Fallback for ill-formed events
            dtstart = date.today()

        # Parse DTEND or DURATION
        dtend: datetime | date | None = None
        duration: timedelta | None = None

        dtend_prop = comp.get_property("DTEND")
        if dtend_prop:
            dtend = parse_date_or_datetime(dtend_prop, resolver)

        duration_prop = comp.get_property("DURATION")
        if duration_prop and duration_prop.value:
            try:
                duration = parse_duration(duration_prop.value)
            except ValueError:
                duration = None

        # Parse RECURRENCE-ID
        rec_id: datetime | date | None = None
        rec_prop = comp.get_property("RECURRENCE-ID")
        if rec_prop:
            rec_id = parse_date_or_datetime(rec_prop, resolver)

        # Parse EXDATE and RDATE
        exdates: list[datetime | date] = []
        for prop in comp.get_properties("EXDATE"):
            for chunk in prop.value.split(","):
                chunk = chunk.strip()
                if chunk:
                    temp_prop = Property(name="EXDATE", value=chunk, params=prop.params)
                    exdates.append(parse_date_or_datetime(temp_prop, resolver))

        rdates: list[datetime | date] = []
        for prop in comp.get_properties("RDATE"):
            for chunk in prop.value.split(","):
                chunk = chunk.strip()
                if chunk:
                    temp_prop = Property(name="RDATE", value=chunk, params=prop.params)
                    rdates.append(parse_date_or_datetime(temp_prop, resolver))

        # Timestamps
        dtstamp: datetime | None = None
        dtstamp_prop = comp.get_property("DTSTAMP")
        if dtstamp_prop:
            val = parse_date_or_datetime(dtstamp_prop, resolver)
            if isinstance(val, datetime):
                dtstamp = val

        created: datetime | None = None
        created_prop = comp.get_property("CREATED")
        if created_prop:
            val = parse_date_or_datetime(created_prop, resolver)
            if isinstance(val, datetime):
                created = val

        last_modified: datetime | None = None
        lm_prop = comp.get_property("LAST-MODIFIED")
        if lm_prop:
            val = parse_date_or_datetime(lm_prop, resolver)
            if isinstance(val, datetime):
                last_modified = val

        # Categories
        categories: list[str] = []
        for cat_prop in comp.get_properties("CATEGORIES"):
            for part in cat_prop.value.split(","):
                part = part.strip()
                if part:
                    categories.append(part)

        # Alarms
        alarms = comp.get_components("VALARM")

        # Known standard properties to exclude from extra_properties
        standard_keys = {
            "UID",
            "DTSTART",
            "DTEND",
            "DURATION",
            "SUMMARY",
            "DESCRIPTION",
            "LOCATION",
            "STATUS",
            "RRULE",
            "EXDATE",
            "RDATE",
            "RECURRENCE-ID",
            "SEQUENCE",
            "TRANSP",
            "CREATED",
            "LAST-MODIFIED",
            "DTSTAMP",
            "CATEGORIES",
            "URL",
        }
        extra_props = [p.copy() for p in comp.properties if p.name not in standard_keys]

        return cls(
            uid=uid,
            dtstart=dtstart,
            dtend=dtend,
            duration=duration,
            summary=summary,
            description=description,
            location=location,
            status=status,
            rrule=rrule_str,
            exdate=exdates,
            rdate=rdates,
            recurrence_id=rec_id,
            sequence=sequence,
            transp=transp,
            created=created,
            last_modified=last_modified,
            dtstamp=dtstamp,
            categories=categories,
            url=url,
            alarms=alarms,
            extra_properties=extra_props,
            raw_component=comp,
        )


@dataclass
class Calendar:
    """High-level abstraction for an RFC 5545 VCALENDAR component."""

    version: str = RFC_VERSION
    prodid: str = DEFAULT_PRODID
    calscale: str = "GREGORIAN"
    method: str | None = None
    events: list[Event] = field(default_factory=list)
    timezones: list[Component] = field(default_factory=list)
    other_components: list[Component] = field(default_factory=list)
    extra_properties: list[Property] = field(default_factory=list)
    raw_component: Component | None = None

    def add_event(self, event: Event) -> None:
        """Add an event to the calendar."""
        self.events.append(event)

    def find_event(self, uid: str, recurrence_id: datetime | date | None = None) -> Event | None:
        """Find an event by UID and optional RECURRENCE-ID."""
        for event in self.events:
            if event.uid == uid and event.recurrence_id == recurrence_id:
                return event
        return None

    def remove_event(self, uid: str, recurrence_id: datetime | date | None = None) -> bool:
        """Remove event matching UID and recurrence_id. Returns True if removed."""
        for i, ev in enumerate(self.events):
            if ev.uid == uid and ev.recurrence_id == recurrence_id:
                del self.events[i]
                return True
        return False

    def to_component(self) -> Component:
        """Convert Calendar into a VCALENDAR Component."""
        comp = Component(name="VCALENDAR")
        comp.add_property("PRODID", self.prodid)
        comp.add_property("VERSION", self.version)
        if self.calscale:
            comp.add_property("CALSCALE", self.calscale)
        if self.method:
            comp.add_property("METHOD", self.method)

        for prop in self.extra_properties:
            comp.add_property(prop.copy())

        for tz in self.timezones:
            comp.add_component(tz.copy())

        for event in self.events:
            comp.add_component(event.to_component())

        for other in self.other_components:
            comp.add_component(other.copy())

        return comp

    @classmethod
    def from_component(cls, comp: Component) -> Calendar:
        """Construct a Calendar from a VCALENDAR Component."""
        from ics_tools.timezone import TimezoneResolver

        version = comp.get_property_value("VERSION", RFC_VERSION) or RFC_VERSION
        prodid = comp.get_property_value("PRODID", DEFAULT_PRODID) or DEFAULT_PRODID
        calscale = comp.get_property_value("CALSCALE", "GREGORIAN") or "GREGORIAN"
        method = comp.get_property_value("METHOD")

        vtimezones = comp.get_components("VTIMEZONE")
        tz_resolver = TimezoneResolver(vtimezones)

        events: list[Event] = []
        for ev_comp in comp.get_components("VEVENT"):
            events.append(Event.from_component(ev_comp, tz_resolver))

        other_components: list[Component] = []
        for sub in comp.subcomponents:
            if sub.name not in ("VEVENT", "VTIMEZONE"):
                other_components.append(sub.copy())

        standard_keys = {"VERSION", "PRODID", "CALSCALE", "METHOD"}
        extra_props = [p.copy() for p in comp.properties if p.name not in standard_keys]

        return cls(
            version=version,
            prodid=prodid,
            calscale=calscale,
            method=method,
            events=events,
            timezones=vtimezones,
            other_components=other_components,
            extra_properties=extra_props,
            raw_component=comp,
        )
