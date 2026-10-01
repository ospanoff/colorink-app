"""Payload parsing, lane packing, and cell geometry helpers."""

from __future__ import annotations

from datetime import date
from typing import Any

from colorink.plugins.calendar.fonts import MonthFonts, _line_box
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
        loc = item.get("location")
        if loc:
            row["location"] = str(loc)
        out.append(row)
    return out


def _event_time_and_title(item: Any) -> tuple[str | None, str]:
    """Time line (start or start–end) and title; None time for all-day / legacy."""
    if isinstance(item, str):
        return None, str(item)
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


def _event_location(item: Any) -> str | None:
    """Place line from an event dict, or None."""
    if not isinstance(item, dict):
        return None
    raw = item.get("location")
    if not raw:
        return None
    text = str(raw).strip()
    return text or None


# --- Lane packing ----------------------------------------------------------------------------


def _pack_lanes[T](
    spans: list[tuple[int, int, T]],
    *,
    inclusive: bool,
) -> tuple[list[tuple[int, int, T, int]], int]:
    """Greedy lanes for overlapping ``(start, end, payload)`` spans.

    Longer spans win ties at the same start. ``inclusive`` treats ``end`` as part of the span
    (week columns); otherwise spans are half-open (minutes), so back-to-back events share a lane.
    """

    def overlaps(a0: int, a1: int, b0: int, b1: int) -> bool:
        if inclusive:
            return a0 <= b1 and b0 <= a1
        return a0 < b1 and b0 < a1

    ordered = sorted(spans, key=lambda s: (s[0], -(s[1] - s[0])))
    lanes: list[list[tuple[int, int]]] = []
    out: list[tuple[int, int, T, int]] = []
    for start, end, payload in ordered:
        lane = next(
            (
                i
                for i, occupied in enumerate(lanes)
                if not any(overlaps(start, end, a, b) for a, b in occupied)
            ),
            None,
        )
        if lane is None:
            lanes.append([])
            lane = len(lanes) - 1
        lanes[lane].append((start, end))
        out.append((start, end, payload, lane))
    return out, len(lanes)


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


def _week_bar_segments(
    week: tuple[date, ...],
    spans: list[dict[str, Any]],
) -> list[tuple[int, int, dict[str, Any], int]]:
    """Multiday spans clipped to ``week`` as ``(first_col, last_col, span, lane)``."""
    segments: list[tuple[int, int, dict[str, Any]]] = []
    for span in spans:
        clipped = _clip_span_to_week(span["start"], span["end"], week)
        if clipped:
            segments.append((clipped[0], clipped[1], span))
    annotated, _lane_count = _pack_lanes(segments, inclusive=True)
    return annotated


def _bars_per_column(annotated: list[tuple[int, int, dict[str, Any], int]]) -> list[int]:
    """Max (lane + 1) for each grid column, so later bars stack below every multiday strip."""
    bars_per_col = [0] * _GRID_COLUMNS
    for i0, i1, _span, lane in annotated:
        for ci in range(i0, i1 + 1):
            bars_per_col[ci] = max(bars_per_col[ci], lane + 1)
    return bars_per_col


# --- Cell geometry ---------------------------------------------------------------------------


def _cell_content_top_y(cell_top: float, fonts: MonthFonts) -> int:
    """First y coordinate below the day number (all-day bars and the hour grid start here)."""
    return int(cell_top + _DAY_NUMBER_TOP_PAD + _line_box(fonts.day_number) + _GAP_BELOW_DAY_NUMBER)
