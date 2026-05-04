"""Pillow rendering for the month grid."""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from colorink.plugins.calendar.fonts import (
    MonthFonts,
    _calendar_font_regular,
    _truncate_time_and_title_one_line,
    _truncate_to_width,
)
from colorink.plugins.calendar.ics import rolling_weeks_and_visible
from colorink.plugins.calendar.layout import (
    _assign_multiday_lanes,
    _cell_content_top_y,
    _clip_span_to_week,
    _event_row_slots_for_item,
    _event_row_slots_in_cell,
    _event_time_and_title,
    _events_by_day_from_payload,
    _group_weeks_by_week_start_month,
    _multiday_lane_height_px,
    _multiday_spans_from_payload,
    _reserved_px_for_column_bar_count,
    bars_per_column_from_annotated,
)
from colorink.plugins.calendar.palette import (
    _CELL_INNER_PAD,
    _DAY_IN_MONTH,
    _DAY_NUMBER_TOP_PAD,
    _DAY_OTHER_MONTH,
    _ERROR_TEXT,
    _EVENT_TIME,
    _EVENT_TIME_PAST,
    _EVENT_TITLE,
    _EVENT_TITLE_PAST,
    _GRID_COLUMNS,
    _GRID_LINE,
    _HEADER_TEXT,
    _MONTH_INTER_BLOCK_GAP,
    _MULTIDAY_BG_TOP_INSET,
    _OVERFLOW_CHIP_BG,
    _OVERFLOW_CHIP_BG_PAST,
    _OVERFLOW_CHIP_OUTLINE,
    _OVERFLOW_CHIP_OUTLINE_PAST,
    _OVERFLOW_CHIP_RADIUS,
    _OVERFLOW_MORE,
    _OVERFLOW_PAST,
    _TODAY_CELL_BG,
    _TODAY_DAY_NUMBER,
    _TODAY_OUTLINE,
    _WEEKDAY_CELL_BG,
    _WEEKEND_CELL_BG,
    _WEEKEND_COLUMNS,
    _multiday_bar_palette,
)


def _event_row_baseline(y_slot_top: float, fonts: MonthFonts) -> int:
    """``anchor=ls`` baseline: slot top + ``event_regular`` ascent (list + multiday rows)."""
    line_top = int(y_slot_top)
    font = fonts.event_regular
    if isinstance(font, ImageFont.FreeTypeFont):
        ascent, _ = font.getmetrics()
    else:
        ascent = max(8, int(getattr(font, "size", 12) * 0.75))
    return line_top + ascent


def _multiday_strip_y_bounds(y0: float, bar_h: int) -> tuple[float, float]:
    """Top/bottom y for the rounded fill; full height ``bar_h`` (see ``_MULTIDAY_BG_TOP_INSET``)."""
    y_top = y0 + _MULTIDAY_BG_TOP_INSET
    return y_top, y_top + bar_h


def _multiday_bar_corner_radius(bar_h: int) -> int:
    """Corner radius for spanning multiday bars: pill-like caps within stripe height."""
    return max(5, bar_h // 2)


def _draw_multiday_rounded_fill(
    draw: ImageDraw.ImageDraw,
    *,
    x0: float,
    x1: float,
    y0: float,
    bar_h: int,
    fill: tuple[int, int, int],
    outline: tuple[int, int, int],
) -> None:
    y_top, y_bot = _multiday_strip_y_bounds(y0, bar_h)
    draw.rounded_rectangle(
        [x0, y_top, x1, y_bot],
        radius=_multiday_bar_corner_radius(bar_h),
        fill=fill,
        outline=outline,
        width=1,
    )


def _draw_timed_event_line(
    draw: ImageDraw.ImageDraw,
    *,
    left_x: int,
    line_top: float,
    max_width: int,
    time_text: str,
    title_text: str,
    fonts: MonthFonts,
    muted: bool = False,
) -> None:
    fill_time = _EVENT_TIME_PAST if muted else _EVENT_TIME
    fill_title = _EVENT_TITLE_PAST if muted else _EVENT_TITLE
    time_line = _truncate_to_width(draw, time_text, fonts.event_regular, max_width)
    tab = int(draw.textlength("   ", font=fonts.event_regular))
    title_budget = max(1, max_width - tab)
    title_draw = _truncate_to_width(draw, title_text, fonts.event_bold, title_budget)
    bl1 = _event_row_baseline(line_top, fonts)
    draw.text(
        (float(left_x), bl1),
        time_line,
        fill=fill_time,
        font=fonts.event_regular,
        anchor="ls",
    )
    bl2 = _event_row_baseline(line_top + fonts.event_line_step, fonts)
    draw.text(
        (float(left_x + tab), bl2),
        title_draw,
        fill=fill_title,
        font=fonts.event_bold,
        anchor="ls",
    )


def _draw_title_only_event_line(
    draw: ImageDraw.ImageDraw,
    *,
    left_x: int,
    baseline_y: int,
    max_width: int,
    title: str,
    fonts: MonthFonts,
    muted: bool = False,
) -> None:
    fill_title = _EVENT_TITLE_PAST if muted else _EVENT_TITLE
    line = _truncate_to_width(draw, title, fonts.event_bold, max_width)
    draw.text((left_x, baseline_y), line, fill=fill_title, font=fonts.event_bold, anchor="ls")


def _overflow_chip_label(hidden_count: int) -> str:
    """Chip text for events that did not fit: ``+1 event`` / ``+N events``."""
    if hidden_count == 1:
        return "+1 event"
    return f"+{hidden_count} events"


def _draw_overflow_chip(
    draw: ImageDraw.ImageDraw,
    *,
    left_x: float,
    line_top: float,
    max_width: int,
    hidden_count: int,
    fonts: MonthFonts,
    muted: bool = False,
) -> None:
    """Pill-shaped overflow label when the list is truncated; left-aligned with event text."""
    font = fonts.event_bold
    pad_h = max(3, fonts.event_px // 5)
    pad_v = max(1, fonts.event_px // 8)
    inner_text_max = max(1, max_width - 2 * pad_h)
    label = _truncate_to_width(draw, _overflow_chip_label(hidden_count), font, inner_text_max)
    tw = float(draw.textlength(label, font=font))
    line_h = float(fonts.event_line_step)
    if isinstance(font, ImageFont.FreeTypeFont):
        ascent, descent = font.getmetrics()
        text_h = ascent + descent
    else:
        text_h = max(8, int(getattr(font, "size", 12) * 1.2))
    ch = int(min(float(text_h + 2 * pad_v), max(8.0, line_h - 1.0)))
    cw = int(min(tw + 2.0 * pad_h, float(max(1, max_width))))
    y0 = line_top + max(0.0, (line_h - float(ch)) / 2.0)
    x0 = left_x
    x1 = left_x + float(cw)
    y1 = y0 + float(ch)
    cy = (y0 + y1) / 2.0
    fill_bg = _OVERFLOW_CHIP_BG_PAST if muted else _OVERFLOW_CHIP_BG
    outline = _OVERFLOW_CHIP_OUTLINE_PAST if muted else _OVERFLOW_CHIP_OUTLINE
    text_fill = _OVERFLOW_PAST if muted else _OVERFLOW_MORE
    draw.rounded_rectangle(
        [x0, y0, x1, y1],
        radius=_OVERFLOW_CHIP_RADIUS,
        fill=fill_bg,
        outline=outline,
        width=1,
    )
    draw.text(
        (x0 + float(pad_h), cy),
        _truncate_to_width(draw, label, font, max(1, cw - 2)),
        fill=text_fill,
        font=font,
        anchor="lm",
    )


def _draw_multiday_bar_label(
    draw: ImageDraw.ImageDraw,
    *,
    inner_left: int,
    max_inner: int,
    span: dict[str, Any],
    fonts: MonthFonts,
    line_top: float,
    muted: bool,
) -> None:
    """Draw multiday text using the same colors and layout as list-event rows."""
    time_part, title_part = _event_time_and_title(span)
    if time_part:
        t_draw, title_draw = _truncate_time_and_title_one_line(
            draw,
            time_part,
            title_part,
            fonts.event_regular,
            fonts.event_bold,
            max_inner,
        )
        bl = _event_row_baseline(line_top, fonts)
        fill_time = _EVENT_TIME_PAST if muted else _EVENT_TIME
        fill_title = _EVENT_TITLE_PAST if muted else _EVENT_TITLE
        gap = " "
        x = float(inner_left)
        draw.text((x, bl), t_draw, fill=fill_time, font=fonts.event_regular, anchor="ls")
        if title_draw:
            x += draw.textlength(t_draw, font=fonts.event_regular)
            x += draw.textlength(gap, font=fonts.event_regular)
            draw.text((x, bl), title_draw, fill=fill_title, font=fonts.event_bold, anchor="ls")
    else:
        _draw_title_only_event_line(
            draw,
            left_x=inner_left,
            baseline_y=_event_row_baseline(line_top, fonts),
            max_width=max_inner,
            title=title_part,
            fonts=fonts,
            muted=muted,
        )


def _events_fit_and_overflow(items: list[Any], max_steps: int) -> tuple[int, bool]:
    """How many items fit in ``max_steps`` line units; use overflow chip when some are hidden."""
    if sum(_event_row_slots_for_item(it) for it in items) <= max_steps:
        return len(items), False
    cap_with_chip = max(0, max_steps - 1)
    used = 0
    for i, item in enumerate(items):
        need = _event_row_slots_for_item(item)
        if used + need > cap_with_chip:
            return i, True
        used += need
    return len(items), False


def _draw_events_in_cell(
    draw: ImageDraw.ImageDraw,
    *,
    cell_left: float,
    cell_top: float,
    column_width: float,
    row_height: float,
    items: list[Any],
    fonts: MonthFonts,
    muted: bool = False,
    reserved_top: float = 0,
) -> None:
    """Draw stacked event lines inside one day cell."""
    text_left = int(cell_left + _CELL_INNER_PAD)
    line_top = _cell_content_top_y(cell_top, fonts) + int(reserved_top)
    max_w = int(column_width - 2 * _CELL_INNER_PAD)
    slots = _event_row_slots_in_cell(row_height, fonts, reserved_top)
    event_limit, overflow = _events_fit_and_overflow(items, slots)

    for i, item in enumerate(items):
        if i >= event_limit:
            if overflow:
                _draw_overflow_chip(
                    draw,
                    left_x=float(text_left),
                    line_top=float(line_top),
                    max_width=max_w,
                    hidden_count=len(items) - event_limit,
                    fonts=fonts,
                    muted=muted,
                )
            break

        time_part, title_part = _event_time_and_title(item)
        if time_part:
            _draw_timed_event_line(
                draw,
                left_x=text_left,
                line_top=float(line_top),
                max_width=max_w,
                time_text=time_part,
                title_text=title_part,
                fonts=fonts,
                muted=muted,
            )
            line_top += 2 * fonts.event_line_step
        else:
            _draw_title_only_event_line(
                draw,
                left_x=text_left,
                baseline_y=_event_row_baseline(float(line_top), fonts),
                max_width=max_w,
                title=title_part,
                fonts=fonts,
                muted=muted,
            )
            line_top += fonts.event_line_step


def _draw_multiday_bars_for_week(
    draw: ImageDraw.ImageDraw,
    *,
    week: tuple[date, ...],
    cell_top: float,
    pad: int,
    col_w: float,
    fonts: MonthFonts,
    spans: list[dict[str, Any]],
    today: date,
    bar_h: int,
    bar_gap: int,
) -> list[float]:
    """Draw week-spanning bars; returns per-column px to reserve above list events (length 7).

    Reserve height is ``max_lane + 1`` stacked rows for that column (lane indices can have
    gaps when a bar ends mid-week), so timed/list lines always start below every multiday strip.
    """
    segments: list[tuple[int, int, dict[str, Any]]] = []
    for m in spans:
        clipped = _clip_span_to_week(m["start"], m["end"], week)
        if clipped:
            i0, i1 = clipped
            segments.append((i0, i1, m))
    if not segments:
        return [0.0] * _GRID_COLUMNS
    annotated, _n_lanes = _assign_multiday_lanes(segments)
    base_y = float(_cell_content_top_y(cell_top, fonts))
    for i0, i1, m, lane in annotated:
        y0 = float(base_y + lane * (bar_h + bar_gap))
        x0 = pad + i0 * col_w + 2.0
        x1 = pad + (i1 + 1) * col_w - 2.0
        span_end: date = m["end"]
        is_past_span = span_end < today
        fill, outline = _multiday_bar_palette(lane, is_past_span)
        _draw_multiday_rounded_fill(
            draw, x0=x0, x1=x1, y0=y0, bar_h=bar_h, fill=fill, outline=outline
        )
        max_inner = int(x1 - x0 - 2 * _CELL_INNER_PAD)
        if max_inner <= 0:
            continue
        inner_left = int(x0 + _CELL_INNER_PAD)
        _draw_multiday_bar_label(
            draw,
            inner_left=inner_left,
            max_inner=max_inner,
            span=m,
            fonts=fonts,
            line_top=y0,
            muted=is_past_span,
        )

    bars_per_col = bars_per_column_from_annotated(annotated)
    return [
        _reserved_px_for_column_bar_count(bars_per_col[i], bar_h, bar_gap)
        for i in range(_GRID_COLUMNS)
    ]


def _draw_day_cell_chrome(
    draw: ImageDraw.ImageDraw,
    *,
    cell_left: float,
    cell_top: float,
    cell_right: float,
    row_h: float,
    day_index: int,
    d: date,
    focused_month: int,
    fonts: MonthFonts,
    today: date,
) -> None:
    """Background, grid outline, and day-of-month number (no events)."""
    is_weekend = day_index in _WEEKEND_COLUMNS
    is_today = d == today
    if is_today:
        cell_fill = _TODAY_CELL_BG
    else:
        cell_fill = _WEEKEND_CELL_BG if is_weekend else _WEEKDAY_CELL_BG
    draw.rectangle(
        [cell_left, cell_top, cell_right, cell_top + row_h],
        fill=cell_fill,
        outline=_GRID_LINE,
        width=1,
    )

    if is_today:
        inset = 1.0
        draw.rectangle(
            [
                cell_left + inset,
                cell_top + inset,
                cell_right - inset,
                cell_top + row_h - inset,
            ],
            outline=_TODAY_OUTLINE,
            width=2,
        )

    if is_today:
        day_color = _TODAY_DAY_NUMBER
    else:
        day_color = _DAY_IN_MONTH if d.month == focused_month else _DAY_OTHER_MONTH

    draw.text(
        (cell_left + _CELL_INNER_PAD, cell_top + _DAY_NUMBER_TOP_PAD),
        str(d.day),
        fill=day_color,
        font=fonts.day_number,
    )


def _draw_day_cell_events(
    draw: ImageDraw.ImageDraw,
    *,
    cell_left: float,
    cell_top: float,
    col_w: float,
    row_h: float,
    d: date,
    events_by_day: dict[date, list[Any]],
    fonts: MonthFonts,
    today: date,
    reserved_top: float,
) -> None:
    """Single-day event lines inside one cell (below multiday bars when ``reserved_top`` > 0)."""
    is_past = d < today
    day_items = events_by_day.get(d, [])
    if not day_items:
        return

    _draw_events_in_cell(
        draw,
        cell_left=cell_left,
        cell_top=cell_top,
        column_width=col_w,
        row_height=row_h,
        items=day_items,
        fonts=fonts,
        muted=is_past,
        reserved_top=reserved_top,
    )


def _month_section_title_font(fonts: MonthFonts) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Slightly smaller than ``fonts.header`` for month block titles."""
    return _calendar_font_regular(max(14, int(fonts.header_px * 0.78)))


def _month_block_lead_height(fonts: MonthFonts) -> float:
    """Height for month title + air below (uses long name for a stable row budget)."""
    font = _month_section_title_font(fonts)
    d = ImageDraw.Draw(Image.new("RGB", (2, 2)))
    sample = "September"
    d.text((0, 0), sample, font=font, fill=0, anchor="lt")
    b = d.textbbox((0, 0), sample, font=font, anchor="lt")
    th = float(b[3] - b[1])
    return th + 2.0 + 4.0


def _draw_month_block_header(
    draw: ImageDraw.ImageDraw,
    *,
    pad: int,
    y0: float,
    month_name: str,
    lead_h: float,
    fonts: MonthFonts,
) -> float:
    """Draw month title only; return ``y0 + lead_h`` (start of this block's first week)."""
    tfont = _month_section_title_font(fonts)
    draw.text((pad, y0 + 2.0), month_name, font=tfont, fill=_HEADER_TEXT, anchor="lt")
    return y0 + lead_h


def _draw_ics_error_banner(
    draw: ImageDraw.ImageDraw,
    *,
    width: int,
    grid_top: float,
    message: str,
    fonts: MonthFonts,
) -> None:
    msg_font = _calendar_font_regular(max(12, fonts.title_px // 2))
    text = message or "Could not load calendar."
    wrapped = _truncate_to_width(draw, text, msg_font, width - 2 * fonts.pad)
    draw.text((fonts.pad, grid_top + 8), wrapped, fill=_ERROR_TEXT, font=msg_font)


def render_month_image(
    *,
    width: int,
    height: int,
    data: dict[str, Any],
) -> Image.Image:
    """Raster month view suitable for Pillow + dithering (no PNG round-trip)."""
    year = int(data["year"])
    month = int(data["month"])
    ok = bool(data.get("ok"))
    err = str(data.get("error", ""))
    events_by_day = _events_by_day_from_payload(data.get("events_by_day"))
    multiday_spans = _multiday_spans_from_payload(data.get("multiday_spans"))
    raw_today = data.get("today")
    if raw_today:
        try:
            today = date.fromisoformat(str(raw_today))
        except ValueError:
            today = date.today()
    else:
        today = date.today()

    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    fonts = MonthFonts.for_canvas(width, height)
    col_w = (width - 2.0 * fonts.pad) / 7.0

    weeks, _ = rolling_weeks_and_visible(year, month, today)
    n_weeks = len(weeks)
    month_blocks = _group_weeks_by_week_start_month(weeks)
    n_blocks = len(month_blocks)
    inter = _MONTH_INTER_BLOCK_GAP
    lead = _month_block_lead_height(fonts)
    block_overhead = lead * n_blocks + inter * max(0, n_blocks - 1)
    grid_h = float(height) - 2.0 * fonts.pad
    row_h = (grid_h - block_overhead) / float(n_weeks) if n_weeks else grid_h

    if not ok:
        _draw_ics_error_banner(draw, width=width, grid_top=fonts.pad, message=err, fonts=fonts)
        return img

    bar_h = _multiday_lane_height_px(fonts)
    bar_gap = 0

    def _draw_one_week(week: tuple[date, ...], y0: float) -> None:
        p, wk = fonts.pad, tuple(week)
        for day_index, d in enumerate(week):
            cl = p + day_index * col_w
            cr = p + (day_index + 1) * col_w
            _draw_day_cell_chrome(
                draw,
                cell_left=cl,
                cell_top=y0,
                cell_right=cr,
                row_h=row_h,
                day_index=day_index,
                d=d,
                focused_month=month,
                fonts=fonts,
                today=today,
            )
        reserved = _draw_multiday_bars_for_week(
            draw,
            week=wk,
            cell_top=y0,
            pad=p,
            col_w=col_w,
            fonts=fonts,
            spans=multiday_spans,
            today=today,
            bar_h=bar_h,
            bar_gap=bar_gap,
        )
        for day_index, d in enumerate(week):
            cl = p + day_index * col_w
            _draw_day_cell_events(
                draw,
                cell_left=cl,
                cell_top=y0,
                col_w=col_w,
                row_h=row_h,
                d=d,
                events_by_day=events_by_day,
                fonts=fonts,
                today=today,
                reserved_top=reserved[day_index],
            )

    y = float(fonts.pad)
    for bi, (ym, wlist) in enumerate(month_blocks):
        if bi > 0:
            y += inter
        y = _draw_month_block_header(
            draw,
            pad=fonts.pad,
            y0=y,
            month_name=calendar.month_name[ym[1]],
            lead_h=lead,
            fonts=fonts,
        )
        for week in wlist:
            _draw_one_week(week, y)
            y += row_h

    return img
