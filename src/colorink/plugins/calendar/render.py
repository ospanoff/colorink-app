"""Pillow rendering for the two-week grid."""

from __future__ import annotations

import calendar
from datetime import date, datetime
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from colorink.plugins.calendar.fonts import (
    MonthFonts,
    _ascent,
    _calendar_font_bold,
    _calendar_font_regular,
    _line_box,
    draw_line,
    line_width,
    truncate_line,
)
from colorink.plugins.calendar.ics import rolling_weeks_and_visible
from colorink.plugins.calendar.layout import (
    _bars_per_column,
    _cell_content_top_y,
    _event_location,
    _event_time_and_title,
    _events_by_day_from_payload,
    _multiday_spans_from_payload,
    _pack_lanes,
    _week_bar_segments,
)
from colorink.plugins.calendar.palette import (
    _BAR_FILL,
    _BAR_FILL_PAST,
    _BAR_GAP,
    _BAR_TOP_INSET,
    _CELL_INNER_PAD,
    _DAY_IN_MONTH,
    _DAY_NUMBER_PAST,
    _DAY_NUMBER_TOP_PAD,
    _ERROR_TEXT,
    _EVENT_LOCATION,
    _EVENT_LOCATION_PAST,
    _EVENT_TIME,
    _EVENT_TIME_PAST,
    _EVENT_TITLE,
    _EVENT_TITLE_PAST,
    _GRID_COLUMNS,
    _GRID_LINE,
    _HEADER_RULE,
    _HOUR_LABEL,
    _HOUR_LINE,
    _MONTH_TAG,
    _MONTH_TAG_PAST,
    _NOW_DOT_RADIUS,
    _NOW_RULE,
    _TIMED_BLOCK_ACCENT,
    _TIMED_BLOCK_ACCENT_PAST,
    _TIMED_BLOCK_ACCENT_WIDTH,
    _TIMED_BLOCK_FILL,
    _TIMED_BLOCK_FILL_PAST,
    _TIMED_BLOCK_RADIUS,
    _TODAY_PILL,
    _TODAY_PILL_TEXT,
    _WEEK_GAP,
    _WEEKDAY_LABEL,
    _WEEKDAY_LABEL_TODAY,
    _WEEKDAYS,
)

# Share of a title's line box that must fit inside a card; the rest is descender room.
_TITLE_FIT = 0.75


def _bar_radius(bar_h: int) -> int:
    """Pill caps: half the stripe height, and never sharper than 5px."""
    return max(5, bar_h // 2)


def _bar_label_inset(bar_h: int) -> int:
    """Left inset past the pill cap so the name is not against the edge."""
    return _bar_radius(bar_h) + 6


def _bar_fill(is_past: bool) -> tuple[int, int, int]:
    return _BAR_FILL_PAST if is_past else _BAR_FILL


def _bar_bounds(y0: float, bar_h: int) -> tuple[float, float]:
    y_top = y0 + _BAR_TOP_INSET
    return y_top, y_top + bar_h


def _draw_bar(
    draw: ImageDraw.ImageDraw,
    *,
    x0: float,
    x1: float,
    y0: float,
    bar_h: int,
    fill: tuple[int, int, int],
) -> None:
    y_top, y_bot = _bar_bounds(y0, bar_h)
    draw.rounded_rectangle(
        [x0, y_top, x1, y_bot],
        radius=_bar_radius(bar_h),
        fill=fill,
        outline=fill,
        width=1,
    )


def _bar_baseline(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    y0: float,
    bar_h: int,
) -> int:
    """Baseline that puts the glyph box in the vertical middle of the pill.

    Cap-height sits above the em-box center, so the result is dropped 2px.
    """
    y_top, y_bot = _bar_bounds(y0, bar_h)
    box = draw.textbbox((0, 0), "Ag", font=font, anchor="ls")
    center_from_baseline = (box[1] + box[3]) / 2.0
    return int(round((y_top + y_bot) / 2.0 - center_from_baseline)) + 2


def _truncate_bar_time_title(
    draw: ImageDraw.ImageDraw,
    time_str: str,
    title_str: str,
    font_time: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    font_title: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_w: int,
) -> tuple[str, str]:
    """Timed all-day label: time + space + truncated bold title within ``max_w``."""
    gap = " "
    w_time = line_width(draw, time_str, font=font_time)
    w_gap = line_width(draw, gap, font=font_time)
    if w_time >= max_w:
        return truncate_line(draw, time_str, font=font_time, max_w=max_w), ""
    budget = max_w - int(w_time + w_gap)
    if budget <= 0:
        return time_str, ""
    return time_str, truncate_line(draw, title_str, font=font_title, max_w=budget)


def _draw_bar_label(
    draw: ImageDraw.ImageDraw,
    *,
    img: Image.Image,
    inner_left: int,
    max_inner: int,
    span: dict[str, Any],
    fonts: MonthFonts,
    line_top: float,
    bar_h: int,
    muted: bool,
) -> None:
    """All-day text centered in the pill, inset from the rounded ends."""
    time_part, title_part = _event_time_and_title(span)
    location = _event_location(span)
    if location:
        title_part = f"{title_part} · {location}" if title_part else location
    baseline = _bar_baseline(draw, fonts.event_bold, line_top, bar_h)
    title_fill = _EVENT_TITLE_PAST if muted else _EVENT_TITLE
    if not time_part:
        draw_line(
            draw,
            (inner_left, baseline),
            truncate_line(draw, title_part, font=fonts.event_bold, max_w=max_inner),
            image=img,
            font=fonts.event_bold,
            fill=title_fill,
            anchor="ls",
        )
        return
    time_draw, title_draw = _truncate_bar_time_title(
        draw,
        time_part,
        title_part,
        fonts.event_regular,
        fonts.event_bold,
        max_inner,
    )
    x = float(inner_left)
    draw_line(
        draw,
        (x, baseline),
        time_draw,
        image=img,
        font=fonts.event_regular,
        fill=_EVENT_TIME_PAST if muted else _EVENT_TIME,
        anchor="ls",
    )
    if title_draw:
        x += line_width(draw, time_draw, font=fonts.event_regular)
        x += line_width(draw, " ", font=fonts.event_regular)
        draw_line(
            draw,
            (x, baseline),
            title_draw,
            image=img,
            font=fonts.event_bold,
            fill=title_fill,
            anchor="ls",
        )


def _draw_bars_for_week(
    draw: ImageDraw.ImageDraw,
    *,
    img: Image.Image,
    week: tuple[date, ...],
    cell_top: float,
    pad: int,
    col_w: float,
    fonts: MonthFonts,
    spans: list[dict[str, Any]],
    today: date,
    bar_h: int,
) -> list[float]:
    """Draw week-spanning bars. Returns per-column px reserved above the hour grid."""
    annotated = _week_bar_segments(week, spans)
    if not annotated:
        return [0.0] * _GRID_COLUMNS
    base_y = float(_cell_content_top_y(cell_top, fonts))
    for i0, i1, span, lane in annotated:
        y0 = float(base_y + lane * (bar_h + _BAR_GAP))
        x0 = pad + i0 * col_w + 2.0
        x1 = pad + (i1 + 1) * col_w - 2.0
        is_past = span["end"] < today
        _draw_bar(draw, x0=x0, x1=x1, y0=y0, bar_h=bar_h, fill=_bar_fill(is_past))
        inset = _bar_label_inset(bar_h)
        max_inner = int(x1 - x0 - 2 * inset)
        if max_inner <= 0:
            continue
        _draw_bar_label(
            draw,
            img=img,
            inner_left=int(x0 + inset),
            max_inner=max_inner,
            span=span,
            fonts=fonts,
            line_top=y0,
            bar_h=bar_h,
            muted=is_past,
        )
    return [
        float(k * bar_h + (k - 1) * _BAR_GAP) if k else 0.0 for k in _bars_per_column(annotated)
    ]


def _draw_day_chrome(
    draw: ImageDraw.ImageDraw,
    *,
    cell_left: float,
    cell_top: float,
    cell_right: float,
    row_h: float,
    day_index: int,
    d: date,
    fonts: MonthFonts,
    today: date,
) -> None:
    """Hairline column separator and the day number."""
    if day_index > 0:
        draw.rectangle([cell_left, cell_top, cell_left, cell_top + row_h], fill=_GRID_LINE)
    _draw_day_heading(
        draw,
        cell_left=cell_left,
        cell_right=cell_right,
        cell_top=cell_top,
        d=d,
        fonts=fonts,
        today=today,
    )


def _hhmm_minutes(value: str) -> int | None:
    """``HH:MM`` as minutes from midnight. ``24:00`` is allowed as an end."""
    parts = value.split(":")
    if len(parts) != 2:
        return None
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if hour == 24 and minute == 0:
        return 24 * 60
    if not (0 <= hour <= 23 and 0 <= minute < 60):
        return None
    return hour * 60 + minute


def _event_span_minutes(item: Any) -> tuple[int, int] | None:
    """Start and end minutes for a timed event, or None when it has no clock time."""
    if not isinstance(item, dict):
        return None
    raw = item.get("time")
    if not raw:
        return None
    start = _hhmm_minutes(str(raw))
    if start is None:
        return None
    end_raw = item.get("end_time")
    end = _hhmm_minutes(str(end_raw)) if end_raw else None
    if end is None or end <= start:
        end = min(24 * 60, start + 60)
    return start, end


def _snap_half_hour(start: int, end: int) -> tuple[int, int]:
    """Floor the start and ceil the end onto a 30-minute grid. At least 30 minutes."""
    snapped_start = (start // 30) * 30
    snapped_end = ((end + 29) // 30) * 30
    if snapped_end <= snapped_start:
        snapped_end = snapped_start + 30
    return snapped_start, min(snapped_end, 24 * 60)


def _hour_window(
    events_by_day: dict[date, list[Any]],
    visible: set[date],
) -> tuple[int, int] | None:
    """Inclusive start hour and exclusive end hour for one week.

    Every day in the week uses this scale. It begins at the whole hour at or
    before the earliest timed start that week, and runs through the hour that
    contains the latest snapped end.
    """
    spans: list[tuple[int, int]] = []
    for day, items in events_by_day.items():
        if day not in visible:
            continue
        for item in items:
            raw = _event_span_minutes(item)
            if raw is not None:
                spans.append(_snap_half_hour(*raw))
    if not spans:
        return None
    start_min = min(start for start, _end in spans)
    end_min = max(end for _start, end in spans)
    return _hours_covering(start_min, end_min)


def _hours_covering(start_min: int, end_min: int) -> tuple[int, int]:
    """Inclusive start hour and exclusive end hour covering ``[start_min, end_min)``."""
    start_hour = start_min // 60
    end_hour = (end_min + 59) // 60
    if end_hour <= start_hour:
        end_hour = start_hour + 1
    return start_hour, end_hour


def _draw_timed_block(
    draw: ImageDraw.ImageDraw,
    *,
    img: Image.Image,
    box: tuple[float, float, float, float],
    item: Any,
    font_regular: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    font_bold: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    muted: bool,
) -> None:
    """Grey event card with a dark left edge. Text is the clock, title, and place."""
    x0, y0, x1, y1 = box
    if x1 - x0 < 6 or y1 - y0 < 6:
        return
    accent_w = _TIMED_BLOCK_ACCENT_WIDTH
    radius = max(2, min(_TIMED_BLOCK_RADIUS, int((y1 - y0) / 2), int((x1 - x0) / 2)))
    draw.rounded_rectangle(
        [x0, y0, x1, y1],
        radius=radius,
        fill=_TIMED_BLOCK_ACCENT_PAST if muted else _TIMED_BLOCK_ACCENT,
    )
    draw.rounded_rectangle(
        [x0 + accent_w, y0, x1, y1],
        radius=radius,
        fill=_TIMED_BLOCK_FILL_PAST if muted else _TIMED_BLOCK_FILL,
        corners=(False, True, True, False),
    )
    pad = 1 if (y1 - y0) < 28 else 2
    text_x = x0 + accent_w + pad
    max_w = max(1, int(x1 - text_x) - pad)
    inner_h = (y1 - y0) - 2 * pad
    title_h = _line_box(font_bold)
    if inner_h < title_h * _TITLE_FIT:
        return
    time_part, title_part = _event_time_and_title(item)
    location = _event_location(item)
    lines: list[tuple[str, ImageFont.FreeTypeFont | ImageFont.ImageFont, tuple[int, int, int]]] = []
    title_fill = _EVENT_TITLE_PAST if muted else _EVENT_TITLE
    time_fill = _EVENT_TIME_PAST if muted else _EVENT_TIME
    loc_fill = _EVENT_LOCATION_PAST if muted else _EVENT_LOCATION
    meta_h = _line_box(font_regular)
    used = 0
    if time_part and meta_h + title_h * _TITLE_FIT <= inner_h:
        lines.append((time_part, font_regular, time_fill))
        used = meta_h
    lines.append((title_part, font_bold, title_fill))
    used += title_h
    if location and used + meta_h * _TITLE_FIT <= inner_h:
        lines.append((location, font_regular, loc_fill))
    text_y = y0 + pad
    for text, font, fill in lines:
        draw_line(
            draw,
            (text_x, int(text_y) + _ascent(font)),
            truncate_line(draw, text, font=font, max_w=max_w),
            image=img,
            font=font,
            fill=fill,
            anchor="ls",
        )
        text_y += _line_box(font)


def _allday_band_rows(
    week: tuple[date, ...],
    spans: list[dict[str, Any]],
    events_by_day: dict[date, list[Any]],
) -> int:
    """Tallest stack of multiday bars plus single-day timeless items in ``week``."""
    counts = _bars_per_column(_week_bar_segments(week, spans))
    rows = 0
    for index, day in enumerate(week):
        timeless = sum(
            1 for item in events_by_day.get(day, []) if _event_span_minutes(item) is None
        )
        rows = max(rows, counts[index] + timeless)
    return rows


def _event_font_px(half_h: float) -> int:
    """Largest bold title whose glyphs fit a half-hour card (descenders may use the padding)."""
    inner = half_h - 4.0
    for px in range(20, 12, -1):
        if _line_box(_calendar_font_bold(px)) * _TITLE_FIT <= inner:
            return px
    return 12


def _clock_minutes(raw_now: Any) -> int:
    """Minutes from midnight for the device clock. Falls back to the host clock."""
    if raw_now:
        try:
            parsed = datetime.fromisoformat(str(raw_now))
        except ValueError:
            parsed = None
        if parsed is not None:
            return parsed.hour * 60 + parsed.minute
    local = datetime.now().astimezone()
    return local.hour * 60 + local.minute


def _half_hour_slot(minutes: int) -> tuple[int, int]:
    """``[start, end)`` minutes for the 30-minute block that contains ``minutes``."""
    start = (minutes // 30) * 30
    return start, min(24 * 60, start + 30)


def _window_including_slot(
    window: tuple[int, int] | None,
    slot: tuple[int, int],
) -> tuple[int, int]:
    """Grow an hour window so the current half-hour is on the grid."""
    start_min, end_min = slot
    grown = _hours_covering(start_min, end_min)
    if window is None:
        return grown
    return min(window[0], grown[0]), max(window[1], grown[1])


def _now_line(
    *,
    week: tuple[date, ...],
    today: date,
    window: tuple[int, int] | None,
    hour_origin: float,
    hour_h: float,
    y0: float,
    origin: float,
    col_w: float,
    now_slot: tuple[int, int],
) -> tuple[float, float, float] | None:
    """``(left, right, y)`` of the current half-hour on today's column, or None."""
    if window is None or hour_h <= 0 or today not in week:
        return None
    start, end = now_slot
    grid_start = window[0] * 60
    grid_end = window[1] * 60
    if end <= grid_start or start >= grid_end:
        return None
    day_index = week.index(today)
    left = origin + day_index * col_w
    right = origin + (day_index + 1) * col_w
    hour_top = y0 + hour_origin
    y_start = hour_top + (max(start, grid_start) - grid_start) / 60.0 * hour_h
    y_end = hour_top + (min(end, grid_end) - grid_start) / 60.0 * hour_h
    if y_end - y_start < 1:
        return None
    return left, right, y_start


def _text_height(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> float:
    box = draw.textbbox((0, 0), text, font=font, anchor="lt")
    return float(box[3] - box[1])


def _draw_day_heading(
    draw: ImageDraw.ImageDraw,
    *,
    cell_left: float,
    cell_right: float,
    cell_top: float,
    d: date,
    fonts: MonthFonts,
    today: date,
) -> None:
    """Day number, today capsule, and a month tag on the 1st."""
    x = cell_left + _CELL_INNER_PAD
    y = cell_top + _DAY_NUMBER_TOP_PAD
    num = str(d.day)
    font = fonts.day_number
    is_today = d == today
    is_past = d < today
    if is_today:
        bb = draw.textbbox((x, y), num, font=font)
        inset_x = max(3, fonts.daynum_px // 6)
        inset_y = max(1, fonts.daynum_px // 10)
        pill = [bb[0] - inset_x, bb[1] - inset_y, bb[2] + inset_x, bb[3] + inset_y]
        radius = max(4, int((pill[3] - pill[1]) / 2))
        draw.rounded_rectangle(pill, radius=radius, fill=_TODAY_PILL)
        draw.text((x, y), num, font=font, fill=_TODAY_PILL_TEXT)
        tag_x = float(pill[2]) + 6.0
    else:
        draw.text(
            (x, y),
            num,
            font=font,
            fill=_DAY_NUMBER_PAST if is_past else _DAY_IN_MONTH,
        )
        bb = draw.textbbox((x, y), num, font=font)
        tag_x = float(bb[2]) + 6.0

    if d.day != 1:
        return
    tag = calendar.month_abbr[d.month]
    tag_w = float(draw.textlength(tag, font=fonts.meta))
    if tag_x + tag_w > cell_right - _CELL_INNER_PAD:
        return
    tag_bb = draw.textbbox((0, 0), tag, font=fonts.meta)
    tag_y = float(bb[3]) - float(tag_bb[3])
    draw.text(
        (tag_x, tag_y),
        tag,
        font=fonts.meta,
        fill=_MONTH_TAG if is_today or not is_past else _MONTH_TAG_PAST,
    )


def _draw_ics_error_banner(
    draw: ImageDraw.ImageDraw,
    *,
    img: Image.Image,
    width: int,
    height: int,
    grid_top: float,
    message: str,
    fonts: MonthFonts,
) -> None:
    header_px = max(18, min(min(width, height) // 22, 32))
    msg_font = _calendar_font_regular(max(12, header_px // 2))
    text = message or "Could not load calendar."
    wrapped = truncate_line(
        draw,
        text,
        font=msg_font,
        max_w=width - 2 * fonts.pad,
        anchor="lt",
    )
    draw_line(
        draw,
        (fonts.pad, grid_top + 8),
        wrapped,
        image=img,
        font=msg_font,
        fill=_ERROR_TEXT,
        anchor="lt",
    )


def render_month_image(
    *,
    width: int,
    height: int,
    data: dict[str, Any],
) -> Image.Image:
    """Raster two-week view suitable for Pillow + dithering (no PNG round-trip)."""
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
    now_slot = _half_hour_slot(_clock_minutes(data.get("now")))

    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    fonts = MonthFonts.for_canvas(width, height)
    pad = fonts.pad

    weeks, _ = rolling_weeks_and_visible(today)
    n_weeks = len(weeks)
    dow_h = _text_height(draw, "WED", fonts.dow)
    band_h = dow_h + 2.0 * max(4.0, fonts.dow_px / 3.0)
    rule_h = 1.0
    gaps = _WEEK_GAP * max(0, n_weeks - 1)
    grid_h = float(height) - 2.0 * pad - band_h - rule_h - gaps
    row_h = grid_h / float(n_weeks) if n_weeks else grid_h

    if not ok:
        _draw_ics_error_banner(
            draw,
            img=img,
            width=width,
            height=height,
            grid_top=float(pad),
            message=err,
            fonts=fonts,
        )
        return img

    bar_h = fonts.event_line_step
    header_h = float(_cell_content_top_y(0.0, fonts))

    def _scale_for_week(week: tuple[date, ...]) -> tuple[tuple[int, int] | None, float, float, int]:
        """Hour window, top of the grid, row height, and hour count for this week."""
        window = _hour_window(events_by_day, set(week))
        if today in week:
            window = _window_including_slot(window, now_slot)
        band_rows = _allday_band_rows(week, multiday_spans, events_by_day)
        hour_origin = header_h + band_rows * (bar_h + _BAR_GAP)
        n_hours = (window[1] - window[0]) if window else 0
        hour_h = (row_h - hour_origin) / n_hours if n_hours else 0.0
        return window, hour_origin, hour_h, n_hours

    week_scales = [_scale_for_week(tuple(week)) for week in weeks]
    shortest = min((scale[2] for scale in week_scales if scale[2] > 0), default=0.0)
    # One event size for both weeks, taken from the tighter hour row so titles match.
    half_h = shortest / 2.0
    block_px = _event_font_px(half_h) if shortest else 14
    block_regular = _calendar_font_regular(max(10, block_px - 2))
    block_bold = _calendar_font_bold(block_px)
    hour_font = _calendar_font_regular(max(12, min(15, int(shortest * 0.36) if shortest else 13)))
    gutter = int(draw.textlength("00", font=hour_font)) + 8 if shortest else 0
    origin = float(pad + gutter)
    col_w = (width - pad - origin) / 7.0

    y = float(pad)
    today_index = today.weekday() if weeks and weeks[0][0] <= today <= weeks[-1][6] else -1
    for day_index, name in enumerate(_WEEKDAYS):
        draw.text(
            (origin + day_index * col_w + _CELL_INNER_PAD, y + band_h / 2.0 + 3),
            name.upper(),
            font=fonts.dow,
            fill=_WEEKDAY_LABEL_TODAY if day_index == today_index else _WEEKDAY_LABEL,
            anchor="lm",
        )
    y += band_h
    draw.rectangle([origin, y, width - pad, y], fill=_HEADER_RULE)
    y += rule_h

    def _draw_one_week(
        week: tuple[date, ...],
        y0: float,
        scale: tuple[tuple[int, int] | None, float, float, int],
    ) -> None:
        window, hour_origin, hour_h, n_hours = scale
        wk = tuple(week)
        for day_index, day in enumerate(week):
            left = origin + day_index * col_w
            right = origin + (day_index + 1) * col_w
            _draw_day_chrome(
                draw,
                cell_left=left,
                cell_top=y0,
                cell_right=right,
                row_h=row_h,
                day_index=day_index,
                d=day,
                fonts=fonts,
                today=today,
            )
        if window and hour_h > 0:
            hour_top = y0 + hour_origin
            for step in range(n_hours):
                line_y = hour_top + step * hour_h
                draw.rectangle([origin, line_y, width - pad, line_y], fill=_HOUR_LINE)
                draw.text(
                    (origin - 6, line_y),
                    f"{window[0] + step:02d}",
                    font=hour_font,
                    fill=_HOUR_LABEL,
                    anchor="rm",
                )
        now = _now_line(
            week=wk,
            today=today,
            window=window,
            hour_origin=hour_origin,
            hour_h=hour_h,
            y0=y0,
            origin=origin,
            col_w=col_w,
            now_slot=now_slot,
        )
        reserved = _draw_bars_for_week(
            draw,
            img=img,
            week=wk,
            cell_top=y0,
            pad=int(origin),
            col_w=col_w,
            fonts=fonts,
            spans=multiday_spans,
            today=today,
            bar_h=bar_h,
        )
        for day_index, day in enumerate(week):
            left = origin + day_index * col_w
            right = origin + (day_index + 1) * col_w
            muted = day < today
            timeless_items = [
                item for item in events_by_day.get(day, []) if _event_span_minutes(item) is None
            ]
            bar_top = float(_cell_content_top_y(y0, fonts) + reserved[day_index])
            if reserved[day_index]:
                bar_top += _BAR_GAP
            for offset, item in enumerate(timeless_items):
                y_bar = bar_top + offset * (bar_h + _BAR_GAP)
                _draw_bar(
                    draw,
                    x0=left + 2,
                    x1=right - 2,
                    y0=y_bar,
                    bar_h=bar_h,
                    fill=_bar_fill(muted),
                )
                inset = _bar_label_inset(bar_h)
                _draw_bar_label(
                    draw,
                    img=img,
                    inner_left=int(left + 2 + inset),
                    max_inner=max(1, int(right - left - 4 - 2 * inset)),
                    span=item if isinstance(item, dict) else {"title": str(item)},
                    fonts=fonts,
                    line_top=y_bar,
                    bar_h=bar_h,
                    muted=muted,
                )
            if not window or hour_h <= 0:
                continue
            raw_spans = [
                (*_snap_half_hour(*raw), item)
                for item in events_by_day.get(day, [])
                if (raw := _event_span_minutes(item)) is not None
            ]
            placed, lane_count = _pack_lanes(raw_spans, inclusive=False)
            if lane_count == 0:
                continue
            hour_top = y0 + hour_origin
            grid_start = window[0] * 60
            lane_w = (col_w - 4.0) / lane_count
            cell_bottom = y0 + row_h - 1
            for start, end, item, lane in placed:
                y_start = hour_top + (start - grid_start) / 60.0 * hour_h
                y_end = hour_top + (end - grid_start) / 60.0 * hour_h
                _draw_timed_block(
                    draw,
                    img=img,
                    box=(
                        left + 2 + lane * lane_w + 1,
                        y_start + 1,
                        left + 2 + (lane + 1) * lane_w - 1,
                        min(y_end - 1, cell_bottom),
                    ),
                    item=item,
                    font_regular=block_regular,
                    font_bold=block_bold,
                    muted=muted,
                )
        if now is not None:
            slot_left, slot_right, slot_top = now
            radius = float(_NOW_DOT_RADIUS)
            cy = slot_top + 0.5
            draw.rectangle([slot_left, slot_top, slot_right, slot_top + 1], fill=_NOW_RULE)
            draw.ellipse(
                [slot_left - radius, cy - radius, slot_left + radius, cy + radius],
                fill=_NOW_RULE,
            )

    for week, scale in zip(weeks, week_scales, strict=True):
        _draw_one_week(week, y, scale)
        y += row_h + _WEEK_GAP

    return img
