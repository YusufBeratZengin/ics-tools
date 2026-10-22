"""Recurrence rule (RRULE) parser and expansion engine according to RFC 5545."""

from __future__ import annotations

import calendar
import re
from collections.abc import Generator
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import TYPE_CHECKING

from ics_tools.constants import FREQUENCIES, WEEKDAY_TO_INT
from ics_tools.exceptions import RRuleError
from ics_tools.models import Event, EventOccurrence

if TYPE_CHECKING:
    from ics_tools.timezone import TimezoneResolver


@dataclass
class ByDaySpec:
    """Represents a BYDAY rule item with an optional numeric ordinal (e.g. 2TU, -1SU)."""

    day: str
    ordinal: int | None = None

    @property
    def weekday_int(self) -> int:
        return WEEKDAY_TO_INT[self.day]

    def __str__(self) -> str:
        if self.ordinal is not None:
            return f"{self.ordinal}{self.day}"
        return self.day


@dataclass
class RecurrenceRule:
    """Parsed representation of an RFC 5545 RRULE property."""

    freq: str
    interval: int = 1
    count: int | None = None
    until: datetime | date | None = None
    byday: list[ByDaySpec] = field(default_factory=list)
    bymonthday: list[int] = field(default_factory=list)
    bymonth: list[int] = field(default_factory=list)
    bysetpos: list[int] = field(default_factory=list)
    wkst: str = "MO"

    def __post_init__(self) -> None:
        self.freq = self.freq.upper()
        if self.freq not in FREQUENCIES:
            raise RRuleError(f"Invalid RRULE frequency: {self.freq!r}")
        if self.interval < 1:
            raise RRuleError(f"RRULE INTERVAL must be >= 1, got {self.interval}")
        if self.count is not None and self.count < 1:
            raise RRuleError(f"RRULE COUNT must be >= 1, got {self.count}")
        if self.wkst.upper() not in WEEKDAY_TO_INT:
            raise RRuleError(f"Invalid RRULE WKST: {self.wkst!r}")
        self.wkst = self.wkst.upper()


def parse_rrule(rrule_str: str, tz_resolver: TimezoneResolver | None = None) -> RecurrenceRule:
    """Parse an RFC 5545 RRULE string into a RecurrenceRule instance."""
    from ics_tools.models import Property
    from ics_tools.parser import parse_date_or_datetime

    parts = rrule_str.strip().split(";")
    kv_pairs: dict[str, str] = {}
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        kv_pairs[k.strip().upper()] = v.strip()

    if "FREQ" not in kv_pairs:
        raise RRuleError("RRULE missing mandatory FREQ part")

    freq = kv_pairs["FREQ"]

    interval = 1
    if "INTERVAL" in kv_pairs:
        try:
            interval = int(kv_pairs["INTERVAL"])
        except ValueError as err:
            raise RRuleError(f"Invalid INTERVAL value: {kv_pairs['INTERVAL']!r}") from err

    count: int | None = None
    if "COUNT" in kv_pairs:
        try:
            count = int(kv_pairs["COUNT"])
        except ValueError as err:
            raise RRuleError(f"Invalid COUNT value: {kv_pairs['COUNT']!r}") from err

    until: datetime | date | None = None
    if "UNTIL" in kv_pairs:
        temp_prop = Property(name="UNTIL", value=kv_pairs["UNTIL"])
        until = parse_date_or_datetime(temp_prop, tz_resolver)

    byday: list[ByDaySpec] = []
    if "BYDAY" in kv_pairs:
        for token in kv_pairs["BYDAY"].split(","):
            token = token.strip().upper()
            if not token:
                continue
            match = re.match(r"^([+-]?\d+)?(MO|TU|WE|TH|FR|SA|SU)$", token)
            if not match:
                raise RRuleError(f"Invalid BYDAY token: {token!r}")
            ord_str, day_code = match.groups()
            ordinal = int(ord_str) if ord_str else None
            if ordinal is not None and (ordinal == 0 or abs(ordinal) > 53):
                raise RRuleError(f"Invalid BYDAY ordinal: {token!r}")
            byday.append(ByDaySpec(day=day_code, ordinal=ordinal))

    bymonthday: list[int] = []
    if "BYMONTHDAY" in kv_pairs:
        for token in kv_pairs["BYMONTHDAY"].split(","):
            token = token.strip()
            if not token:
                continue
            try:
                val = int(token)
                if val == 0 or val < -31 or val > 31:
                    raise ValueError()
                bymonthday.append(val)
            except ValueError as err:
                raise RRuleError(f"Invalid BYMONTHDAY value: {token!r}") from err

    bymonth: list[int] = []
    if "BYMONTH" in kv_pairs:
        for token in kv_pairs["BYMONTH"].split(","):
            token = token.strip()
            if not token:
                continue
            try:
                val = int(token)
                if val < 1 or val > 12:
                    raise ValueError()
                bymonth.append(val)
            except ValueError as err:
                raise RRuleError(f"Invalid BYMONTH value: {token!r}") from err

    bysetpos: list[int] = []
    if "BYSETPOS" in kv_pairs:
        for token in kv_pairs["BYSETPOS"].split(","):
            token = token.strip()
            if not token:
                continue
            try:
                val = int(token)
                if val == 0 or abs(val) > 366:
                    raise ValueError()
                bysetpos.append(val)
            except ValueError as err:
                raise RRuleError(f"Invalid BYSETPOS value: {token!r}") from err

    wkst = kv_pairs.get("WKST", "MO")

    return RecurrenceRule(
        freq=freq,
        interval=interval,
        count=count,
        until=until,
        byday=byday,
        bymonthday=bymonthday,
        bymonth=bymonth,
        bysetpos=bysetpos,
        wkst=wkst,
    )


def _to_comparable_datetime(val: datetime | date, default_tz: tzinfo = timezone.utc) -> datetime:
    """Normalize date or datetime to an aware datetime for comparison."""
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=default_tz)
        return val.astimezone(timezone.utc)
    return datetime.combine(val, time.min, tzinfo=default_tz).astimezone(timezone.utc)


def _apply_setpos(candidates: list[datetime | date], setpos_list: list[int]) -> list[datetime | date]:
    """Filter sorted candidates using 1-based BYSETPOS indices."""
    if not setpos_list or not candidates:
        return candidates
    result: list[datetime | date] = []
    n = len(candidates)
    for pos in setpos_list:
        if pos > 0 and pos <= n:
            result.append(candidates[pos - 1])
        elif pos < 0 and abs(pos) <= n:
            result.append(candidates[n + pos])
    return sorted(set(result), key=lambda x: _to_comparable_datetime(x))


def _get_matching_days_for_month(
    year: int,
    month: int,
    byday: list[ByDaySpec],
    bymonthday: list[int],
) -> list[int]:
    """Calculate day numbers of a month matching BYDAY and BYMONTHDAY constraints."""
    first_weekday, num_days = calendar.monthrange(year, month)

    if not byday and not bymonthday:
        return []

    # If bymonthday specified, determine candidates
    monthday_candidates: set[int] | None = None
    if bymonthday:
        monthday_candidates = set()
        for d in bymonthday:
            if d > 0 and d <= num_days:
                monthday_candidates.add(d)
            elif d < 0 and (num_days + 1 + d) >= 1:
                monthday_candidates.add(num_days + 1 + d)

    # If byday specified, determine matching days
    byday_candidates: set[int] | None = None
    if byday:
        byday_candidates = set()
        for spec in byday:
            matching = [
                d for d in range(1, num_days + 1)
                if (first_weekday + d - 1) % 7 == spec.weekday_int
            ]
            if spec.ordinal is None:
                byday_candidates.update(matching)
            elif spec.ordinal > 0 and spec.ordinal <= len(matching):
                byday_candidates.add(matching[spec.ordinal - 1])
            elif spec.ordinal < 0 and abs(spec.ordinal) <= len(matching):
                byday_candidates.add(matching[len(matching) + spec.ordinal])

    if monthday_candidates is not None and byday_candidates is not None:
        return sorted(monthday_candidates.intersection(byday_candidates))
    elif monthday_candidates is not None:
        return sorted(monthday_candidates)
    elif byday_candidates is not None:
        return sorted(byday_candidates)
    return []


def _create_instance_date(base: datetime | date, year: int, month: int, day: int) -> datetime | date | None:
    """Create a new date or datetime preserving original time and timezone."""
    try:
        if isinstance(base, datetime):
            return base.replace(year=year, month=month, day=day)
        return date(year, month, day)
    except ValueError:
        return None


def _period_candidates(
    dtstart: datetime | date,
    period: date,
    rrule: RecurrenceRule,
) -> list[datetime | date]:
    """Build the full frequency period before applying BYSETPOS and DTSTART."""
    days: list[date] = []
    if rrule.freq == "DAILY":
        if rrule.bymonth and period.month not in rrule.bymonth:
            return []
        if rrule.byday and period.weekday() not in {spec.weekday_int for spec in rrule.byday}:
            return []
        if rrule.bymonthday and period.day not in _get_matching_days_for_month(
            period.year, period.month, [], rrule.bymonthday
        ):
            return []
        days = [period]
    elif rrule.freq == "WEEKLY":
        weekdays = {spec.weekday_int for spec in rrule.byday} if rrule.byday else {dtstart.weekday()}
        for offset in range(min(7, (date.max - period).days + 1)):
            day = period + timedelta(days=offset)
            if day.weekday() in weekdays and (not rrule.bymonth or day.month in rrule.bymonth):
                days.append(day)
    else:
        if rrule.freq == "MONTHLY":
            months = [period.month] if not rrule.bymonth or period.month in rrule.bymonth else []
        elif rrule.bymonth:
            months = sorted(set(rrule.bymonth))
        elif rrule.byday or rrule.bymonthday:
            months = list(range(1, 13))
        else:
            months = [dtstart.month]

        # Without BYMONTH, YEARLY ordinal BYDAY refers to the whole year.
        yearly_byday = rrule.freq == "YEARLY" and not rrule.bymonth and bool(rrule.byday)
        month_byday = [] if yearly_byday else rrule.byday
        for month in months:
            if month_byday or rrule.bymonthday:
                numbers = _get_matching_days_for_month(period.year, month, month_byday, rrule.bymonthday)
            elif yearly_byday:
                numbers = list(range(1, calendar.monthrange(period.year, month)[1] + 1))
            else:
                numbers = [dtstart.day] if dtstart.day <= calendar.monthrange(period.year, month)[1] else []
            days.extend(date(period.year, month, number) for number in numbers)

        if yearly_byday:
            selected: set[date] = set()
            for spec in rrule.byday:
                year_days = [
                    date(period.year, 1, 1) + timedelta(days=offset)
                    for offset in range(366 if calendar.isleap(period.year) else 365)
                    if (date(period.year, 1, 1).weekday() + offset) % 7 == spec.weekday_int
                ]
                if spec.ordinal is None:
                    selected.update(year_days)
                elif abs(spec.ordinal) <= len(year_days):
                    selected.add(year_days[spec.ordinal - 1 if spec.ordinal > 0 else spec.ordinal])
            days = [day for day in days if day in selected]

    candidates: list[datetime | date] = [
        datetime.combine(day, dtstart.timetz()) if isinstance(dtstart, datetime) else day
        for day in days
    ]
    return _apply_setpos(candidates, rrule.bysetpos)


def generate_recurrence_dates(
    dtstart: datetime | date,
    rrule: RecurrenceRule,
    window_end: datetime | date | None = None,
) -> Generator[datetime | date, None, None]:
    """Generate DAILY through YEARLY recurrences bounded by COUNT, UNTIL and window_end."""
    if rrule.freq not in {"DAILY", "WEEKLY", "MONTHLY", "YEARLY"}:
        raise RRuleError(f"Unsupported expansion frequency: {rrule.freq!r}")

    start_day = dtstart.date() if isinstance(dtstart, datetime) else dtstart
    period = start_day
    if rrule.freq == "WEEKLY":
        offset = (start_day.weekday() - WEEKDAY_TO_INT[rrule.wkst]) % 7
        period -= timedelta(days=min(offset, (period - date.min).days))
    elif rrule.freq == "MONTHLY":
        period = period.replace(day=1)
    elif rrule.freq == "YEARLY":
        period = period.replace(month=1, day=1)

    bounds = [_to_comparable_datetime(value) for value in (rrule.until, window_end) if value is not None]
    limit = min(bounds) if bounds else None
    start_cmp = _to_comparable_datetime(dtstart)
    count = 0
    while True:
        period_start = datetime.combine(period, dtstart.timetz()) if isinstance(dtstart, datetime) else period
        if limit is not None and _to_comparable_datetime(period_start) > limit:
            return
        for candidate in _period_candidates(dtstart, period, rrule):
            comparable = _to_comparable_datetime(candidate)
            if comparable < start_cmp:
                continue
            if limit is not None and comparable > limit:
                return
            yield candidate
            count += 1
            if rrule.count is not None and count >= rrule.count:
                return

        try:
            if rrule.freq == "DAILY":
                period += timedelta(days=rrule.interval)
            elif rrule.freq == "WEEKLY":
                period += timedelta(weeks=rrule.interval)
            elif rrule.freq == "MONTHLY":
                month_index = period.year * 12 + period.month - 1 + rrule.interval
                period = date(month_index // 12, month_index % 12 + 1, 1)
            else:
                period = date(period.year + rrule.interval, 1, 1)
        except (OverflowError, ValueError):
            return


def expand_event(
    event: Event,
    window_start: datetime | date,
    window_end: datetime | date,
    overrides: dict[tuple[str, str], Event] | None = None,
    tz_resolver: TimezoneResolver | None = None,
) -> list[EventOccurrence]:
    """Expand an Event into occurrences within the given [window_start, window_end] window.

    Handles RRULE recurrence expansion, EXDATE exclusions, RDATE additions,
    and RECURRENCE-ID overrides.
    """
    win_start_dt = _to_comparable_datetime(window_start)
    win_end_dt = _to_comparable_datetime(window_end)

    # Prepare EXDATE lookup set
    exdate_set = {_to_comparable_datetime(ex) for ex in event.exdate}

    occurrences: list[EventOccurrence] = []

    def make_occurrence(
        start_val: datetime | date,
        src_event: Event,
        is_override: bool = False,
        rec_id: datetime | date | None = None,
    ) -> EventOccurrence:
        if isinstance(start_val, datetime):
            end_val: datetime | date = start_val + src_event.effective_duration
        else:
            days = max(1, src_event.effective_duration.days)
            end_val = start_val + timedelta(days=days)

        return EventOccurrence(
            uid=src_event.uid,
            start=start_val,
            end=end_val,
            summary=src_event.summary,
            description=src_event.description,
            location=src_event.location,
            status=src_event.status,
            is_all_day=src_event.is_all_day,
            recurrence_id=rec_id,
            is_overridden=is_override,
            categories=list(src_event.categories),
            event=src_event,
        )

    # 1. Non-recurring event
    if not event.rrule and not event.rdate:
        occ = make_occurrence(event.dtstart, event)
        occ_start_dt = _to_comparable_datetime(occ.start)
        occ_end_dt = _to_comparable_datetime(occ.end)
        if occ_start_dt <= win_end_dt and occ_end_dt >= win_start_dt:
            occurrences.append(occ)
        return occurrences

    # 2. Recurring event: generate dates from RRULE
    generated_dates: list[datetime | date] = []
    if event.rrule:
        rule = parse_rrule(event.rrule, tz_resolver)
        generated_dates = list(generate_recurrence_dates(event.dtstart, rule, window_end=window_end))
    else:
        generated_dates = [event.dtstart]

    # Add RDATE items
    for rd in event.rdate:
        if rd not in generated_dates:
            generated_dates.append(rd)

    # Sort all instance dates
    generated_dates.sort(key=lambda x: _to_comparable_datetime(x))

    for inst_start in generated_dates:
        inst_cmp = _to_comparable_datetime(inst_start)

        # Check EXDATE
        if inst_cmp in exdate_set:
            continue

        # Check for RECURRENCE-ID override
        override_key = (event.uid, inst_start.isoformat())
        overridden_event = overrides.get(override_key) if overrides else None

        if overridden_event is not None:
            # If status is CANCELLED, drop occurrence
            if overridden_event.status.upper() == "CANCELLED":
                continue
            occ = make_occurrence(
                overridden_event.dtstart,
                overridden_event,
                is_override=True,
                rec_id=inst_start,
            )
        else:
            occ = make_occurrence(inst_start, event, is_override=False, rec_id=inst_start)

        occ_start_dt = _to_comparable_datetime(occ.start)
        occ_end_dt = _to_comparable_datetime(occ.end)

        if occ_start_dt <= win_end_dt and occ_end_dt >= win_start_dt:
            occurrences.append(occ)

    # An override can move an instance from beyond the expansion window into it.
    for (uid, _rec_key), override in (overrides or {}).items():
        rec_id = override.recurrence_id
        if (
            uid != event.uid
            or rec_id is None
            or rec_id in generated_dates
            or _to_comparable_datetime(rec_id) in exdate_set
            or override.status.upper() == "CANCELLED"
        ):
            continue
        occ = make_occurrence(override.dtstart, override, is_override=True, rec_id=rec_id)
        if _to_comparable_datetime(occ.start) <= win_end_dt and _to_comparable_datetime(occ.end) >= win_start_dt:
            occurrences.append(occ)

    return sorted(occurrences, key=lambda occ: _to_comparable_datetime(occ.start))
