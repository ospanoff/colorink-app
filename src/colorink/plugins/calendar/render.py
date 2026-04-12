"""Pillow rendering for the month grid."""

from __future__ import annotations

import calendar
import io
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

# Bundled Noto Sans (SIL OFL) — same family for regular vs bold; see fonts/OFL.txt
_FONTS_DIR = Path(__file__).resolve().parent / "fonts"
_NOTO_REGULAR = _FONTS_DIR / "NotoSans-Regular.ttf"
_NOTO_BOLD = _FONTS_DIR / "NotoSans-Bold.ttf"

# --- Palette (RGB) ---------------------------------------------------------------------------

_HEADER_TEXT = (45, 45, 45)
_WEEKDAY_LABEL = (90, 90, 90)
_DAY_IN_MONTH = (25, 25, 25)
_DAY_OTHER_MONTH = (200, 200, 200)
# Soft grid (was ~220). If Floyd–Steinberg hides lines on device, prefer dither_mode NONE.
_GRID_LINE = (186, 186, 190)
_WEEKDAY_CELL_BG = (255, 255, 255)
# Sat/Sun columns (Mon-first week); matches header strip tint.
_WEEKEND_CELL_BG = (244, 244, 246)
_EVENT_TIME = (105, 105, 105)
_EVENT_TITLE = (28, 28, 28)
_OVERFLOW_MORE = (45, 55, 95)
_ERROR_TEXT = (160, 0, 0)
# Days before today: muted event text only (cell chrome unchanged).
_EVENT_TIME_PAST = (150, 150, 152)
_EVENT_TITLE_PAST = (128, 128, 130)
_OVERFLOW_PAST = (105, 105, 125)
_OVERFLOW_CHIP_BG = (228, 234, 244)
_OVERFLOW_CHIP_BG_PAST = (236, 236, 240)
_OVERFLOW_CHIP_OUTLINE = (168, 182, 202)
_OVERFLOW_CHIP_OUTLINE_PAST = (205, 208, 214)
_OVERFLOW_CHIP_RADIUS = 4
# Stacked multiday bars: three cool pastels (blue-gray, soft green, mauve) by lane.
_MULTIDAY_BAR_FILLS = (
    (218, 228, 242),
    (224, 236, 228),
    (236, 228, 240),
)
_MULTIDAY_BAR_FILLS_PAST = (
    (230, 232, 236),
    (232, 236, 233),
    (236, 232, 236),
)
_MULTIDAY_BAR_OUTLINES = (
    (168, 182, 202),
    (158, 184, 168),
    (190, 172, 196),
)
_MULTIDAY_BAR_OUTLINES_PAST = (
    (200, 203, 208),
    (198, 208, 200),
    (208, 200, 210),
)
# Nudge multiday fill down vs. glyphs; height stays ``bar_h`` (same as ``event_line_step``).
_MULTIDAY_BG_TOP_INSET = 2
_MULTIDAY_BAR_CORNER_RADIUS = 3
# Current day: cell tint + frame (events use normal palette; past days stay un-tinted).
_TODAY_CELL_BG = (232, 242, 255)
_TODAY_OUTLINE = (50, 90, 145)
_TODAY_DAY_NUMBER = (18, 52, 110)

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
# Padding inside each day cell (day number, event text); must match header alignment math.
_CELL_INNER_PAD = 4
# Day-of-month digit: must match ``_draw_day_cell_chrome`` y offset.
_DAY_NUMBER_TOP_PAD = 3
# Space between bottom of day number and first multiday bar / event line.
_GAP_BELOW_DAY_NUMBER = 4
# List row height = event_px * this factor; multiday stripes use the same step (see
# ``_multiday_lane_height_px``). Slightly > 1.0 gives air between lines and room inside bars.
_EVENT_LINE_STEP_FACTOR = 1.26
# Monday-first week: column indices for Sat/Sun background tint.
_WEEKEND_COLUMNS = frozenset((5, 6))
_GRID_COLUMNS = 7


def _calendar_font_regular(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if not _NOTO_REGULAR.is_file():
        raise FileNotFoundError(f"Bundled font missing: {_NOTO_REGULAR}")
    return ImageFont.truetype(str(_NOTO_REGULAR), size)


def _calendar_font_bold(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if not _NOTO_BOLD.is_file():
        raise FileNotFoundError(f"Bundled font missing: {_NOTO_BOLD}")
    return ImageFont.truetype(str(_NOTO_BOLD), size)


@dataclass(frozen=True)
class MonthFonts:
    """Scaled fonts and vertical rhythm for a given canvas size."""

    pad: int
    title_px: int
    header_px: int
    dow_px: int
    daynum_px: int
    event_px: int
    event_line_step: int
    header: ImageFont.FreeTypeFont | ImageFont.ImageFont
    dow: ImageFont.FreeTypeFont | ImageFont.ImageFont
    day_number: ImageFont.FreeTypeFont | ImageFont.ImageFont
    event_regular: ImageFont.FreeTypeFont | ImageFont.ImageFont
    event_bold: ImageFont.FreeTypeFont | ImageFont.ImageFont

    @classmethod
    def for_canvas(cls, width: int, height: int) -> MonthFonts:
        short = min(width, height)
        title_px = max(16, min(short // 11, 52))
        header_px = max(22, min(short // 12, 36))
        dow_px = max(11, int(title_px * 0.42))
        daynum_px = max(10, int(title_px * 0.38))
        event_px = max(12, int(title_px * 0.38))
        pad = max(6, short // 64)
        return cls(
            pad=pad,
            title_px=title_px,
            header_px=header_px,
            dow_px=dow_px,
            daynum_px=daynum_px,
            event_px=event_px,
            event_line_step=int(event_px * _EVENT_LINE_STEP_FACTOR),
            header=_calendar_font_bold(header_px),
            dow=_calendar_font_regular(dow_px),
            day_number=_calendar_font_regular(daynum_px),
            event_regular=_calendar_font_regular(event_px),
            event_bold=_calendar_font_bold(event_px),
        )


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
        out.append({"title": title, "time": time_s, "start": s, "end": e})
    return out


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


def _multiday_bar_palette(
    lane: int, is_past: bool
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Bar fill and outline for a multiday lane (cycles three cool pastels)."""
    i = lane % len(_MULTIDAY_BAR_FILLS)
    if is_past:
        return _MULTIDAY_BAR_FILLS_PAST[i], _MULTIDAY_BAR_OUTLINES_PAST[i]
    return _MULTIDAY_BAR_FILLS[i], _MULTIDAY_BAR_OUTLINES[i]


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


def _event_time_and_title(item: Any) -> tuple[str | None, str]:
    """Time string (or None for all-day / legacy) and title for separate fonts."""
    if isinstance(item, str):
        return None, item
    if isinstance(item, dict):
        title = str(item.get("title", ""))
        t = item.get("time")
        if t:
            return str(t), title
        return None, title
    return None, str(item)


def _truncate_time_and_title(
    draw: ImageDraw.ImageDraw,
    time_str: str,
    title_str: str,
    font_time: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    font_title: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_w: int,
) -> tuple[str, str]:
    """Leave time unbold; truncate title to fit after ``time + space``."""
    gap = " "
    w_time = draw.textlength(time_str, font=font_time)
    w_gap = draw.textlength(gap, font=font_time)
    if w_time >= max_w:
        return truncate_to_width(draw, time_str, font_time, max_w), ""
    budget = max_w - w_time - w_gap
    if budget <= 0:
        return time_str, ""
    return time_str, truncate_to_width(draw, title_str, font_title, int(budget))


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
        radius=_MULTIDAY_BAR_CORNER_RADIUS,
        fill=fill,
        outline=outline,
        width=1,
    )


def _draw_multiday_bar_label(
    draw: ImageDraw.ImageDraw,
    *,
    inner_left: int,
    max_inner: int,
    span: dict[str, Any],
    fonts: MonthFonts,
    baseline_y: int,
    muted: bool,
) -> None:
    """Draw multiday text using the same colors and layout as list-event rows."""
    time_part, title_part = _event_time_and_title(span)
    if time_part:
        _draw_timed_event_line(
            draw,
            left_x=inner_left,
            baseline_y=baseline_y,
            max_width=max_inner,
            time_text=time_part,
            title_text=title_part,
            fonts=fonts,
            muted=muted,
        )
    else:
        _draw_title_only_event_line(
            draw,
            left_x=inner_left,
            baseline_y=baseline_y,
            max_width=max_inner,
            title=title_part,
            fonts=fonts,
            muted=muted,
        )


def truncate_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_w: int,
) -> str:
    if max_w <= 0:
        return ""
    if draw.textlength(text, font=font) <= max_w:
        return text
    ell = "…"
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        candidate = text[:mid] + ell
        if draw.textlength(candidate, font=font) <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + ell if lo > 0 else ell


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _draw_month_title_and_weekday_row(
    draw: ImageDraw.ImageDraw,
    *,
    width: int,
    year: int,
    month: int,
    fonts: MonthFonts,
) -> tuple[float, float]:
    """Draw ``Month YYYY`` and Mon–Sun labels.

    Returns ``(grid_top_y, column_width)`` for the week grid below.
    """
    pad = fonts.pad
    y = float(pad)

    month_name = calendar.month_name[month]
    draw.text((pad, y), f"{month_name} {year}", fill=_HEADER_TEXT, font=fonts.header)
    y += int(fonts.header_px * 1.12)

    col_w = (width - 2 * pad) / 7.0
    dow_top = y
    dow_row_h = int(fonts.dow_px * 1.25)
    grid_top = dow_top + dow_row_h

    for col in sorted(_WEEKEND_COLUMNS):
        draw.rectangle(
            [pad + col * col_w, dow_top, pad + (col + 1) * col_w, grid_top],
            fill=_WEEKEND_CELL_BG,
        )
    for i, label in enumerate(_WEEKDAYS):
        draw.text((pad + i * col_w, dow_top), label, fill=_WEEKDAY_LABEL, font=fonts.dow)

    return float(grid_top), col_w


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
    wrapped = truncate_to_width(draw, text, msg_font, width - 2 * fonts.pad)
    draw.text((fonts.pad, grid_top + 8), wrapped, fill=_ERROR_TEXT, font=msg_font)


def _day_number_row_height_px(fonts: MonthFonts) -> int:
    """Height from cell top through the bottom of the day-of-month glyph."""
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


def _draw_ls_advance(
    draw: ImageDraw.ImageDraw,
    x: float,
    baseline_y: int,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int],
) -> float:
    """Draw ``anchor='ls'`` text and return the x position after the glyph run."""
    draw.text((x, baseline_y), text, fill=fill, font=font, anchor="ls")
    return x + draw.textlength(text, font=font)


def _draw_timed_event_line(
    draw: ImageDraw.ImageDraw,
    *,
    left_x: int,
    baseline_y: int,
    max_width: int,
    time_text: str,
    title_text: str,
    fonts: MonthFonts,
    muted: bool = False,
) -> None:
    fill_time = _EVENT_TIME_PAST if muted else _EVENT_TIME
    fill_title = _EVENT_TITLE_PAST if muted else _EVENT_TITLE
    t_draw, title_draw = _truncate_time_and_title(
        draw, time_text, title_text, fonts.event_regular, fonts.event_bold, max_width
    )
    x = float(left_x)
    x = _draw_ls_advance(draw, x, baseline_y, t_draw, fonts.event_regular, fill_time)
    if title_draw:
        x = _draw_ls_advance(draw, x, baseline_y, " ", fonts.event_regular, fill_time)
        draw.text(
            (x, baseline_y),
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
    line = truncate_to_width(draw, title, fonts.event_bold, max_width)
    draw.text((left_x, baseline_y), line, fill=fill_title, font=fonts.event_bold, anchor="ls")


def _overflow_chip_label(hidden_count: int) -> str:
    """Chip text for events that did not fit: ``+1 event`` / ``+N events``."""
    if hidden_count == 1:
        return "+1 event"
    return f"+{hidden_count} events"


def _draw_overflow_chip(
    draw: ImageDraw.ImageDraw,
    *,
    center_x: float,
    line_top: float,
    max_width: int,
    hidden_count: int,
    fonts: MonthFonts,
    muted: bool = False,
) -> None:
    """Pill-shaped overflow label when the list is truncated; centered in the cell."""
    font = fonts.event_bold
    pad_h = max(3, fonts.event_px // 5)
    pad_v = max(1, fonts.event_px // 8)
    inner_text_max = max(1, max_width - 2 * pad_h)
    label = truncate_to_width(draw, _overflow_chip_label(hidden_count), font, inner_text_max)
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
    half = float(cw) / 2.0
    x0 = center_x - half
    x1 = center_x + half
    y1 = y0 + float(ch)
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
        ((x0 + x1) / 2.0, (y0 + y1) / 2.0),
        truncate_to_width(draw, label, font, max(1, cw - 2)),
        fill=text_fill,
        font=font,
        anchor="mm",
    )


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
    # Overflow chip uses one row; leave that slot empty when trimming the list.
    overflow = len(items) > slots
    event_limit = len(items) if not overflow else max(0, slots - 1)

    for i, item in enumerate(items):
        if i >= event_limit:
            if overflow:
                _draw_overflow_chip(
                    draw,
                    center_x=float(text_left) + float(max_w) / 2.0,
                    line_top=float(line_top),
                    max_width=max_w,
                    hidden_count=len(items) - event_limit,
                    fonts=fonts,
                    muted=muted,
                )
            break

        baseline_y = _event_row_baseline(float(line_top), fonts)
        time_part, title_part = _event_time_and_title(item)
        if time_part:
            _draw_timed_event_line(
                draw,
                left_x=text_left,
                baseline_y=baseline_y,
                max_width=max_w,
                time_text=time_part,
                title_text=title_part,
                fonts=fonts,
                muted=muted,
            )
        else:
            _draw_title_only_event_line(
                draw,
                left_x=text_left,
                baseline_y=baseline_y,
                max_width=max_w,
                title=title_part,
                fonts=fonts,
                muted=muted,
            )

        line_top += fonts.event_line_step


def _reserved_px_for_column_bar_count(k: int, bar_h: int, bar_gap: int) -> float:
    """Vertical space for ``k`` stacked multiday bars (``k == 0`` → none)."""
    if k <= 0:
        return 0.0
    return float(k * bar_h + (k - 1) * bar_gap)


def _draw_multiday_bars_for_week(
    draw: ImageDraw.ImageDraw,
    *,
    week: tuple[date, ...],
    cell_top: float,
    pad: float,
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
        bl = _event_row_baseline(y0, fonts)
        _draw_multiday_bar_label(
            draw,
            inner_left=inner_left,
            max_inner=max_inner,
            span=m,
            fonts=fonts,
            baseline_y=bl,
            muted=is_past_span,
        )

    # Rows needed = max(lane)+1 among spans covering the column (not span count: lanes can skip).
    bars_per_col = [0] * _GRID_COLUMNS
    for i0, i1, _m, lane in annotated:
        for ci in range(i0, i1 + 1):
            bars_per_col[ci] = max(bars_per_col[ci], lane + 1)
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


def render_month_png(
    *,
    width: int,
    height: int,
    data: dict[str, Any],
) -> bytes:
    """Render ``data`` from :meth:`CalendarPlugin.fetch_data` to PNG bytes."""
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

    grid_top, col_w = _draw_month_title_and_weekday_row(
        draw, width=width, year=year, month=month, fonts=fonts
    )
    grid_h = height - grid_top - fonts.pad

    cal_grid = calendar.Calendar(firstweekday=calendar.MONDAY)
    weeks = cal_grid.monthdatescalendar(year, month)
    n_weeks = len(weeks)
    row_h = grid_h / float(n_weeks) if n_weeks else grid_h

    if not ok:
        _draw_ics_error_banner(draw, width=width, grid_top=grid_top, message=err, fonts=fonts)
        return _png_bytes(img)

    bar_h = _multiday_lane_height_px(fonts)
    bar_gap = 0

    for week_index, week in enumerate(weeks):
        cell_top = grid_top + week_index * row_h
        week_t = tuple(week)
        for day_index, d in enumerate(week):
            cell_left = fonts.pad + day_index * col_w
            cell_right = fonts.pad + (day_index + 1) * col_w
            _draw_day_cell_chrome(
                draw,
                cell_left=cell_left,
                cell_top=cell_top,
                cell_right=cell_right,
                row_h=row_h,
                day_index=day_index,
                d=d,
                focused_month=month,
                fonts=fonts,
                today=today,
            )

        reserved_per_column = _draw_multiday_bars_for_week(
            draw,
            week=week_t,
            cell_top=cell_top,
            pad=float(fonts.pad),
            col_w=col_w,
            fonts=fonts,
            spans=multiday_spans,
            today=today,
            bar_h=bar_h,
            bar_gap=bar_gap,
        )

        for day_index, d in enumerate(week):
            cell_left = fonts.pad + day_index * col_w
            _draw_day_cell_events(
                draw,
                cell_left=cell_left,
                cell_top=cell_top,
                col_w=col_w,
                row_h=row_h,
                d=d,
                events_by_day=events_by_day,
                fonts=fonts,
                today=today,
                reserved_top=reserved_per_column[day_index],
            )

    return _png_bytes(img)
