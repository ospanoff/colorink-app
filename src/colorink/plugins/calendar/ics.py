"""Parse ICS bytes into per-day events (title + optional local time label)."""

from __future__ import annotations

import calendar
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import NotRequired, TypedDict
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from icalendar import Calendar
from recurring_ical_events import of

# Matches :class:`calendar.Calendar` usage in ``render_month_image`` (Monday-first weeks).
_FIRST_WEEKDAY = calendar.MONDAY


def rolling_weeks_and_visible(
    year: int, month: int, today: date
) -> tuple[list[tuple[date, ...]], frozenset[date]]:
    """Mon-first weeks: first row is the week that contains ``today``, for the given view month.

    ``year``/``month`` fix the visible month (row count from
    :meth:`calendar.Calendar.monthdatescalendar`). ``today`` picks the first week row: the
    week that contains this calendar date (its Monday starts row 0).
    """
    cal = calendar.Calendar(firstweekday=_FIRST_WEEKDAY)
    n_weeks = len(cal.monthdatescalendar(year, month))
    monday0 = today - timedelta(days=today.weekday())
    weeks: list[tuple[date, ...]] = []
    for i in range(n_weeks):
        w0 = monday0 + timedelta(days=7 * i)
        weeks.append(tuple(w0 + timedelta(days=d) for d in range(7)))
    visible = frozenset(d for w in weeks for d in w)
    return weeks, visible


class IcsEventRow(TypedDict):
    title: str
    time: str | None  # "HH:MM" start in configured timezone, or None for all-day
    end_time: NotRequired[str | None]  # "HH:MM" end when same local day as start


class MultidaySpanDict(TypedDict):
    """Span drawn as a rounded bar; ``end`` is inclusive. All-day uses ``time`` None."""

    title: str
    time: str | None
    end_time: NotRequired[str | None]
    start: str  # ISO date
    end: str  # ISO date, inclusive


def host_for_label(url: str) -> str:
    try:
        host = urlsplit(url).hostname
        return host or url
    except ValueError:
        return url


def _timed_event_end_time_label(comp, tz: ZoneInfo, raw_start: datetime) -> str | None:
    """Local wall-clock end time (HH:MM) from DTEND or DTSTART + DURATION, or None."""
    dtend_prop = comp.get("dtend")
    if dtend_prop is not None:
        raw_end = dtend_prop.dt
        if isinstance(raw_end, datetime):
            edt = raw_end
            if edt.tzinfo is None:
                edt = edt.replace(tzinfo=tz)
            else:
                edt = edt.astimezone(tz)
            return edt.strftime("%H:%M")
        return None

    duration_prop = comp.get("duration")
    if duration_prop is None:
        return None
    sdt = raw_start
    if sdt.tzinfo is None:
        sdt = sdt.replace(tzinfo=tz)
    else:
        sdt = sdt.astimezone(tz)
    dur = duration_prop.dt
    if not isinstance(dur, timedelta):
        return None
    end = sdt + dur
    return end.astimezone(tz).strftime("%H:%M")


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


def _process_all_day_event(
    comp,
    title: str,
    start_d: date,
    end_d: date,
    visible_dates: frozenset[date],
    seen_multiday: set[tuple[str, str, str]],
    multiday: list[MultidaySpanDict],
) -> None:
    """Clip an all-day event to the visible grid and append to ``multiday`` (deduplicating)."""
    clip_start = max(start_d, min(visible_dates))
    clip_end = min(end_d, max(visible_dates))
    if clip_start > clip_end:
        return
    uid_str = str(comp.get("uid") or "")
    key = (
        (uid_str, clip_start.isoformat(), clip_end.isoformat())
        if uid_str
        else (title, clip_start.isoformat(), clip_end.isoformat())
    )
    if key in seen_multiday:
        return
    seen_multiday.add(key)
    multiday.append(
        MultidaySpanDict(
            title=title,
            time=None,
            start=clip_start.isoformat(),
            end=clip_end.isoformat(),
        )
    )


def _process_timed_multiday_span(
    comp,
    title: str,
    start_d: date,
    end_d: date,
    time_label: str | None,
    end_lbl: str | None,
    visible_dates: frozenset[date],
    seen_multiday: set[tuple[str, str, str]],
    multiday: list[MultidaySpanDict],
) -> None:
    """Clip a multi-day timed instance to the grid and append to ``multiday`` (deduped)."""
    if not time_label:
        return
    clip_start = max(start_d, min(visible_dates))
    clip_end = min(end_d, max(visible_dates))
    if clip_start > clip_end:
        return
    uid_str = str(comp.get("uid") or "")
    key = (
        (uid_str, clip_start.isoformat(), clip_end.isoformat())
        if uid_str
        else (title, clip_start.isoformat(), clip_end.isoformat())
    )
    if key in seen_multiday:
        return
    seen_multiday.add(key)
    row: MultidaySpanDict = MultidaySpanDict(
        title=title,
        time=time_label,
        start=clip_start.isoformat(),
        end=clip_end.isoformat(),
    )
    if end_lbl is not None:
        row["end_time"] = end_lbl
    multiday.append(row)


def _process_timed_event(
    comp,
    raw_start: date | datetime,
    title: str,
    start_d: date,
    end_d: date,
    visible_dates: frozenset[date],
    tz: ZoneInfo,
    by_day: dict[date, list[IcsEventRow]],
    seen_multiday: set[tuple[str, str, str]],
    multiday: list[MultidaySpanDict],
) -> None:
    """Single-day timed → ``by_day``; multi-day timed → spanning ``multiday`` bar (not listed)."""
    _, time_label = _local_date_and_time_label(raw_start, tz)
    end_lbl: str | None = None
    if isinstance(raw_start, datetime) and time_label is not None:
        end_lbl = _timed_event_end_time_label(comp, tz, raw_start)
        if not end_lbl or end_lbl == time_label:
            end_lbl = None

    def _row() -> IcsEventRow:
        base: IcsEventRow = {"title": title, "time": time_label}
        if end_lbl is not None:
            base["end_time"] = end_lbl
        return base

    if start_d == end_d:
        if start_d in visible_dates:
            by_day[start_d].append(_row())
        return
    _process_timed_multiday_span(
        comp,
        title,
        start_d,
        end_d,
        time_label,
        end_lbl,
        visible_dates,
        seen_multiday,
        multiday,
    )


def events_by_day_from_ics(
    ics_bytes: bytes,
    tz: ZoneInfo,
    today: date,
) -> tuple[dict[date, list[IcsEventRow]], list[MultidaySpanDict]]:
    """Map local dates to events for the **visible rolling grid** (Mon-Sun weeks).

    Row count and visible dates come from :func:`rolling_weeks_and_visible` using the
    calendar month of ``today`` and that same ``today`` as the anchor (first week = week
    of ``today``).

    **All-day** instances (``DTSTART`` is a ``DATE``) go to ``multiday`` as ``time=None``.

    **Timed** instances on a single local day go to ``events_by_day``. **Timed** instances
    that span multiple local days are clipped into ``multiday`` (with ``time`` set) so they
    render as spanning bars, not repeated list rows.
    """
    year, month = today.year, today.month
    cal = Calendar.from_ical(ics_bytes)
    query = of(cal, skip_bad_series=True)
    _, visible_dates = rolling_weeks_and_visible(year, month, today)
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

        if _dtstart_is_all_day(comp):
            _process_all_day_event(
                comp, title, start_d, end_d, visible_dates, seen_multiday, multiday
            )
        else:
            _process_timed_event(
                comp,
                raw_start,
                title,
                start_d,
                end_d,
                visible_dates,
                tz,
                by_day,
                seen_multiday,
                multiday,
            )

    out: dict[date, list[IcsEventRow]] = {}
    for d, rows in by_day.items():
        out[d] = sorted(rows, key=_sort_key)
    multiday.sort(key=lambda m: (m["start"], m["end"], m["title"].lower()))
    return out, multiday
