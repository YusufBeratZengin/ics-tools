"""Recurrence rule (RRULE) parser and expansion engine according to RFC 5545."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import TYPE_CHECKING, Generator

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
                if val == 0:
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
    return sorted(result, key=lambda x: _to_comparable_datetime(x))


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


def generate_recurrence_dates(
    dtstart: datetime | date,
    rrule: RecurrenceRule,
    window_end: datetime | date | None = None,
) -> Generator[datetime | date, None, None]:
    """Generate recurrence dates based on an RRULE until COUNT, UNTIL, or window_end."""
    is_dt = isinstance(dtstart, datetime)
    base_time = dtstart.time() if is_dt else time.min
    base_tz = dtstart.tzinfo if is_dt else None

    until_dt = _to_comparable_datetime(rrule.until) if rrule.until else None
    window_end_dt = _to_comparable_datetime(window_end) if window_end else None

    count = 0
    max_count = rrule.count

    def should_stop(current: datetime | date) -> bool:
        c_dt = _to_comparable_datetime(current)
        if until_dt is not None and c_dt > until_dt:
            return True
        if max_count is not None and count >= max_count:
            return True
        if max_count is None and window_end_dt is not None and c_dt > window_end_dt:
            return True
        return False

    freq = rrule.freq
    interval = rrule.interval

    # --- FREQ: DAILY ---
    if freq == "DAILY":
        current_date = dtstart.date() if is_dt else dtstart
        while True:
            inst: datetime | date = (
                datetime.combine(current_date, base_time, tzinfo=base_tz) if is_dt else current_date
            )
            if rrule.bymonth and inst.month not in rrule.bymonth:
                current_date += timedelta(days=interval)
                continue

            if should_stop(inst):
                break

            yield inst
            count += 1
            if max_count is not None and count >= max_count:
                break

            current_date += timedelta(days=interval)

    # --- FREQ: WEEKLY ---
    elif freq == "WEEKLY":
        # Days to check in each week
        target_weekdays = [spec.weekday_int for spec in rrule.byday] if rrule.byday else [dtstart.weekday()]
        wkst_int = WEEKDAY_TO_INT.get(rrule.wkst, 0)

        # Find the start of the week for dtstart based on WKST
        dt_day = dtstart.date() if is_dt else dtstart
        day_offset = (dt_day.weekday() - wkst_int) % 7
        current_week_start = dt_day - timedelta(days=day_offset)

        while True:
            week_candidates: list[datetime | date] = []
            for offset in range(7):
                candidate_day = current_week_start + timedelta(days=offset)
                if candidate_day.weekday() in target_weekdays:
                    inst = datetime.combine(candidate_day, base_time, tzinfo=base_tz) if is_dt else candidate_day
                    if _to_comparable_datetime(inst) < _to_comparable_datetime(dtstart):
                        continue
                    if rrule.bymonth and inst.month not in rrule.bymonth:
                        continue
                    week_candidates.append(inst)

            week_candidates = _apply_setpos(week_candidates, rrule.bysetpos)

            terminated = False
            for cand in week_candidates:
                if should_stop(cand):
                    terminated = True
                    break
                yield cand
                count += 1
                if max_count is not None and count >= max_count:
                    terminated = True
                    break

            if terminated:
                break

            current_week_start += timedelta(weeks=interval)
            # Early break if far beyond window
            if max_count is None and window_end_dt is not None:
                if _to_comparable_datetime(current_week_start) > window_end_dt:
                    break

    # --- FREQ: MONTHLY ---
    elif freq == "MONTHLY":
        cur_year = dtstart.year
        cur_month = dtstart.month

        while True:
            # Candidates for this month
            if rrule.byday or rrule.bymonthday:
                day_nums = _get_matching_days_for_month(cur_year, cur_month, rrule.byday, rrule.bymonthday)
            else:
                _, days_in_cur = calendar.monthrange(cur_year, cur_month)
                day_nums = [dtstart.day] if dtstart.day <= days_in_cur else []

            month_candidates: list[datetime | date] = []
            for d in day_nums:
                inst = _create_instance_date(dtstart, cur_year, cur_month, d)
                if inst is not None and _to_comparable_datetime(inst) >= _to_comparable_datetime(dtstart):
                    if not rrule.bymonth or inst.month in rrule.bymonth:
                        month_candidates.append(inst)

            month_candidates = _apply_setpos(month_candidates, rrule.bysetpos)

            terminated = False
            for cand in month_candidates:
                if should_stop(cand):
                    terminated = True
                    break
                yield cand
                count += 1
                if max_count is not None and count >= max_count:
                    terminated = True
                    break

            if terminated:
                break

            # Advance month by interval
            total_months = cur_year * 12 + (cur_month - 1) + interval
            cur_year = total_months // 12
            cur_month = (total_months % 12) + 1

            if max_count is None and window_end_dt is not None:
                first_of_next = datetime(cur_year, cur_month, 1, tzinfo=timezone.utc)
                if first_of_next > window_end_dt:
                    break

    # --- FREQ: YEARLY ---
    elif freq == "YEARLY":
        cur_year = dtstart.year
        months_to_visit = rrule.bymonth if rrule.bymonth else [dtstart.month]

        while True:
            year_candidates: list[datetime | date] = []
            for m in months_to_visit:
                if rrule.byday or rrule.bymonthday:
                    day_nums = _get_matching_days_for_month(cur_year, m, rrule.byday, rrule.bymonthday)
                else:
                    _, days_in_m = calendar.monthrange(cur_year, m)
                    day_nums = [dtstart.day] if dtstart.day <= days_in_m else []

                for d in day_nums:
                    inst = _create_instance_date(dtstart, cur_year, m, d)
                    if inst is not None and _to_comparable_datetime(inst) >= _to_comparable_datetime(dtstart):
                        year_candidates.append(inst)

            year_candidates = _apply_setpos(year_candidates, rrule.bysetpos)

            terminated = False
            for cand in year_candidates:
                if should_stop(cand):
                    terminated = True
                    break
                yield cand
                count += 1
                if max_count is not None and count >= max_count:
                    terminated = True
                    break

            if terminated:
                break

            cur_year += interval
            if max_count is None and window_end_dt is not None:
                if datetime(cur_year, 1, 1, tzinfo=timezone.utc) > window_end_dt:
                    break


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
    duration = event.effective_duration

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

    return occurrences
