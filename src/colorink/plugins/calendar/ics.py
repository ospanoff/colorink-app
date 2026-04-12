"""Parse ICS bytes into per-day events (title + optional local time label)."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import TypedDict
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from icalendar import Calendar
from recurring_ical_events import of

# Matches :class:`calendar.Calendar` usage in ``render_month_png`` (Monday-first weeks).
_FIRST_WEEKDAY = calendar.MONDAY


def visible_dates_for_month_grid(year: int, month: int) -> frozenset[date]:
    """All dates shown in the month view grid (includes spillover from adjacent months)."""
    weeks = calendar.Calendar(firstweekday=_FIRST_WEEKDAY).monthdatescalendar(year, month)
    return frozenset(d for week in weeks for d in week)


class IcsEventRow(TypedDict):
    title: str
    time: str | None  # "HH:MM" in configured timezone, or None for all-day


class MultidaySpanDict(TypedDict):
    """One multi-day instance; ``end`` is inclusive (last calendar day)."""

    title: str
    time: str | None
    start: str  # ISO date
    end: str  # ISO date, inclusive


def host_for_label(url: str) -> str:
    try:
        host = urlsplit(url).hostname
        return host or url
    except ValueError:
        return url


def _local_date_and_time_label(
    v: date | datetime,
    tz: ZoneInfo,
) -> tuple[date, str | None]:
    if isinstance(v, datetime):
        if v.tzinfo is None:
            local = v.replace(tzinfo=tz)
        else:
            local = v.astimezone(tz)
        return local.date(), local.strftime("%H:%M")
    return v, None


def _inclusive_date_range_from_component(comp, tz: ZoneInfo) -> tuple[date, date] | None:
    """Return first and last local calendar day for this component instance."""
    dt_prop = comp.get("dtstart")
    if dt_prop is None:
        return None
    raw_start = dt_prop.dt
    dtend_prop = comp.get("dtend")
    duration_prop = comp.get("duration")

    if isinstance(raw_start, datetime):
        sdt = raw_start
        if sdt.tzinfo is None:
            sdt = sdt.replace(tzinfo=tz)
        start_d = sdt.astimezone(tz).date()
        if dtend_prop is not None:
            raw_end = dtend_prop.dt
            if isinstance(raw_end, datetime):
                edt = raw_end
                if edt.tzinfo is None:
                    edt = edt.replace(tzinfo=tz)
                end_d = edt.astimezone(tz).date()
            else:
                end_d = raw_end
        elif duration_prop is not None:
            dur = duration_prop.dt
            end_d = (sdt + dur).astimezone(tz).date()
        else:
            end_d = start_d
        if end_d < start_d:
            end_d = start_d
        return start_d, end_d

    # All-day (DATE)
    start_d = raw_start
    if dtend_prop is not None:
        ex = dtend_prop.dt
        if isinstance(ex, datetime):
            ex = ex.date()
        end_inclusive = ex - timedelta(days=1)
    else:
        end_inclusive = start_d
    if end_inclusive < start_d:
        end_inclusive = start_d
    return start_d, end_inclusive


def _sort_key(row: IcsEventRow) -> tuple[int | str, ...]:
    """All-day first (by title), then timed events by clock time then title."""
    if row["time"] is None:
        return (0, row["title"].lower())
    return (1, row["time"], row["title"].lower())


def _dtstart_is_all_day(comp) -> bool:
    """True when ``DTSTART`` is a calendar date (``VALUE=DATE``), not a date-time."""
    dt_prop = comp.get("dtstart")
    if dt_prop is None:
        return False
    return not isinstance(dt_prop.dt, datetime)


def events_by_day_from_ics(
    ics_bytes: bytes,
    year: int,
    month: int,
    tz: ZoneInfo,
) -> tuple[dict[date, list[IcsEventRow]], list[MultidaySpanDict]]:
    """Map local dates to events for the **visible month grid** (Mon–Sun weeks).

    Single-calendar-day instances go into ``events_by_day``. **All-day** multi-day
    instances (``DTSTART`` is a ``DATE``) are listed in ``multiday_spans`` (one entry per
    instance) and drawn as week-spanning bars — they are not duplicated into
    ``events_by_day``.

    Timed events that span more than one **local** calendar day are listed in
    ``events_by_day`` once per affected day (same time label from ``DTSTART``); they never
    appear in ``multiday_spans``.
    """
    cal = Calendar.from_ical(ics_bytes)
    query = of(cal, skip_bad_series=True)
    visible_dates = visible_dates_for_month_grid(year, month)
    range_start = min(visible_dates)
    range_end_excl = max(visible_dates) + timedelta(days=1)
    components = query.between(range_start, range_end_excl)
    by_day: dict[date, list[IcsEventRow]] = defaultdict(list)
    multiday: list[MultidaySpanDict] = []
    seen_multiday: set[tuple[str, str, str]] = set()

    for comp in components:
        if str(comp.get("STATUS", "")).upper() == "CANCELLED":
            continue
        summ = comp.get("summary")
        title = str(summ) if summ else "(No title)"
        bounds = _inclusive_date_range_from_component(comp, tz)
        if bounds is None:
            continue
        start_d, end_d = bounds
        if start_d > end_d:
            continue

        dt_prop = comp.get("dtstart")
        if dt_prop is None:
            continue
        raw_start = dt_prop.dt

        if start_d == end_d:
            _, time_label = _local_date_and_time_label(raw_start, tz)
            if start_d not in visible_dates:
                continue
            row: IcsEventRow = {"title": title, "time": time_label}
            by_day[start_d].append(row)
            continue

        # Multiple local calendar days.
        if not _dtstart_is_all_day(comp):
            _, time_label = _local_date_and_time_label(raw_start, tz)
            d = start_d
            while d <= end_d:
                if d in visible_dates:
                    by_day[d].append({"title": title, "time": time_label})
                d += timedelta(days=1)
            continue

        # All-day multi-day: clip to grid; one span record (renderer clips per week).
        clip_start = max(start_d, min(visible_dates))
        clip_end = min(end_d, max(visible_dates))
        if clip_start > clip_end:
            continue

        time_label = None

        uid_str = str(comp.get("uid") or "")
        key = (
            (uid_str, clip_start.isoformat(), clip_end.isoformat())
            if uid_str
            else (title, clip_start.isoformat(), clip_end.isoformat())
        )
        if key in seen_multiday:
            continue
        seen_multiday.add(key)
        multiday.append(
            MultidaySpanDict(
                title=title,
                time=time_label,
                start=clip_start.isoformat(),
                end=clip_end.isoformat(),
            )
        )

    out: dict[date, list[IcsEventRow]] = {}
    for d, rows in by_day.items():
        out[d] = sorted(rows, key=_sort_key)
    multiday.sort(key=lambda m: (m["start"], m["end"], m["title"].lower()))
    return out, multiday
