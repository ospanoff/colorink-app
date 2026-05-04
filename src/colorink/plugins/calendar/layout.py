"""Payload parsing, lane-packing algorithms, and cell geometry helpers."""

from __future__ import annotations

from datetime import date
from typing import Any

from colorink.plugins.calendar.fonts import MonthFonts
from colorink.plugins.calendar.palette import (
    _DAY_NUMBER_TOP_PAD,
    _GAP_BELOW_DAY_NUMBER,
    _GRID_COLUMNS,
)

# --- Payload parsing -------------------------------------------------------------------------


def _events_by_day_from_payload(raw_map: Any) -> dict[date, list[Any]]:
    out: dict[date, list[Any]] = {}
    if not raw_map:
        return out
    for k, v in raw_map.items():
        try:
            out[date.fromisoformat(str(k))] = list(v)
        except ValueError:
            continue
    return out


def _multiday_spans_from_payload(raw: Any) -> list[dict[str, Any]]:
    """Parse ``multiday_spans`` from plugin JSON into dicts with ``date`` objects."""
    out: list[dict[str, Any]] = []
    if not raw:
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            s = date.fromisoformat(str(item["start"]))
            e = date.fromisoformat(str(item["end"]))
        except (KeyError, ValueError, TypeError):
            continue
        title = str(item.get("title") or "")
        t = item.get("time")
        time_s = str(t) if t else None
        row: dict[str, Any] = {"title": title, "time": time_s, "start": s, "end": e}
        et = item.get("end_time")
        if et:
            row["end_time"] = str(et)
        out.append(row)
    return out


def _group_weeks_by_week_start_month(
    weeks: list[tuple[date, ...]],
) -> list[tuple[tuple[int, int], list[tuple[date, ...]]]]:
    """Split Mon-first week rows into blocks that share the same (year, month) on day 0.

    Day 0 is Monday. Used so month title bands align when the grid spans two months.
    """
    if not weeks:
        return []
    out: list[tuple[tuple[int, int], list[tuple[date, ...]]]] = []
    cur = (weeks[0][0].year, weeks[0][0].month)
    run: list[tuple[date, ...]] = [weeks[0]]
    for w in weeks[1:]:
        k = (w[0].year, w[0].month)
        if k == cur:
            run.append(w)
        else:
            out.append((cur, run))
            cur = k
            run = [w]
    out.append((cur, run))
    return out


def _event_time_and_title(item: Any) -> tuple[str | None, str]:
    """Time line (start or start–end) and title; None time for all-day / legacy."""
    if isinstance(item, str):
        return None, item
    if isinstance(item, dict):
        title = str(item.get("title", ""))
        t = item.get("time")
        if not t:
            return None, title
        start_s = str(t)
        end = item.get("end_time")
        if end:
            end_s = str(end)
            if end_s and end_s != start_s:
                return f"{start_s}–{end_s}", title
        return start_s, title
    return None, str(item)


def _event_row_slots_for_item(item: Any) -> int:
    """Vertical budget in ``event_line_step`` units (timed rows use two lines)."""
    time_part, _ = _event_time_and_title(item)
    return 2 if time_part else 1


# --- Multiday lane-packing algorithms --------------------------------------------------------


def _intervals_overlap_col(a0: int, a1: int, b0: int, b1: int) -> bool:
    """Inclusive column indices within a week row."""
    return a0 <= b1 and b0 <= a1


def _clip_span_to_week(
    span_start: date,
    span_end: date,
    week: tuple[date, ...],
) -> tuple[int, int] | None:
    w0, w6 = week[0], week[6]
    if span_end < w0 or span_start > w6:
        return None
    i0 = next(i for i, d in enumerate(week) if d >= span_start)
    i1 = next(i for i in range(6, -1, -1) if week[i] <= span_end)
    return i0, i1


def _assign_multiday_lanes(
    segments: list[tuple[int, int, dict[str, Any]]],
) -> tuple[list[tuple[int, int, dict[str, Any], int]], int]:
    """Greedy lane packing for overlapping week segments. Returns (annotated, lane_count)."""
    ordered = sorted(segments, key=lambda s: (s[0], -(s[1] - s[0])))
    lanes: list[list[tuple[int, int]]] = []
    out: list[tuple[int, int, dict[str, Any], int]] = []
    for i0, i1, m in ordered:
        placed: int | None = None
        for li, occ in enumerate(lanes):
            if not any(_intervals_overlap_col(i0, i1, a, b) for a, b in occ):
                occ.append((i0, i1))
                placed = li
                break
        if placed is None:
            lanes.append([(i0, i1)])
            placed = len(lanes) - 1
        out.append((i0, i1, m, placed))
    return out, len(lanes)


# --- Cell geometry helpers -------------------------------------------------------------------


def _day_number_row_height_px(fonts: MonthFonts) -> int:
    """Height from cell top through the bottom of the day-of-month glyph."""
    from PIL import ImageFont  # local import to avoid hard PIL dep at module level

    if isinstance(fonts.day_number, ImageFont.FreeTypeFont):
        ascent, descent = fonts.day_number.getmetrics()
        return _DAY_NUMBER_TOP_PAD + ascent + descent
    return _DAY_NUMBER_TOP_PAD + int(fonts.daynum_px * 1.28)


def _cell_content_top_y(cell_top: float, fonts: MonthFonts) -> int:
    """First y coordinate below the day number (multiday bars and event lines start here)."""
    return int(
        cell_top + _day_number_row_height_px(fonts) + _GAP_BELOW_DAY_NUMBER,
    )


def _multiday_lane_height_px(fonts: MonthFonts) -> int:
    """One multiday stripe uses exactly the same vertical quantum as a list event row."""
    return fonts.event_line_step


def _event_row_slots_in_cell(
    row_height: float,
    fonts: MonthFonts,
    reserved_top: float = 0,
) -> int:
    """Row slots below the day number (and multiday reserve); each is ``event_line_step`` tall."""
    header = _day_number_row_height_px(fonts) + _GAP_BELOW_DAY_NUMBER
    step = float(fonts.event_line_step)
    return max(1, int((row_height - header - reserved_top) // max(11.0, step)))


def _reserved_px_for_column_bar_count(k: int, bar_h: int, bar_gap: int) -> float:
    """Vertical space for ``k`` stacked multiday bars (``k == 0`` -> none)."""
    if k <= 0:
        return 0.0
    return float(k * bar_h + (k - 1) * bar_gap)


def bars_per_column_from_annotated(
    annotated: list[tuple[int, int, dict[str, Any], int]],
) -> list[int]:
    """Max (lane + 1) for each grid column, derived from lane-annotated segments."""
    bars_per_col = [0] * _GRID_COLUMNS
    for i0, i1, _m, lane in annotated:
        for ci in range(i0, i1 + 1):
            bars_per_col[ci] = max(bars_per_col[ci], lane + 1)
    return bars_per_col
