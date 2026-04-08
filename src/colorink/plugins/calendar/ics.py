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


def _sort_key(row: IcsEventRow) -> tuple[int | str, ...]:
    """All-day first (by title), then timed events by clock time then title."""
    if row["time"] is None:
        return (0, row["title"].lower())
    return (1, row["time"], row["title"].lower())


def events_by_day_from_ics(
    ics_bytes: bytes,
    year: int,
    month: int,
    tz: ZoneInfo,
) -> dict[date, list[IcsEventRow]]:
    """Map local dates to events for the **visible month grid** (Mon–Sun weeks).

    Includes leading/trailing days from adjacent months that appear in the grid, not only
    ``year``/``month``.
    """
    cal = Calendar.from_ical(ics_bytes)
    query = of(cal, skip_bad_series=True)
    visible_dates = visible_dates_for_month_grid(year, month)
    range_start = min(visible_dates)
    range_end_excl = max(visible_dates) + timedelta(days=1)
    components = query.between(range_start, range_end_excl)
    by_day: dict[date, list[IcsEventRow]] = defaultdict(list)
    for comp in components:
        if str(comp.get("STATUS", "")).upper() == "CANCELLED":
            continue
        summ = comp.get("summary")
        title = str(summ) if summ else "(No title)"
        dt_prop = comp.get("dtstart")
        if dt_prop is None:
            continue
        v = dt_prop.dt
        d, time_label = _local_date_and_time_label(v, tz)
        if d not in visible_dates:
            continue
        row: IcsEventRow = {"title": title, "time": time_label}
        by_day[d].append(row)
    out: dict[date, list[IcsEventRow]] = {}
    for d, rows in by_day.items():
        out[d] = sorted(rows, key=_sort_key)
    return out
