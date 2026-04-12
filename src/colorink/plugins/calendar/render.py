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
_OVERFLOW_MORE = (60, 60, 120)
_ERROR_TEXT = (160, 0, 0)
# Days before today: muted event text only (cell chrome unchanged).
_EVENT_TIME_PAST = (150, 150, 152)
_EVENT_TITLE_PAST = (128, 128, 130)
_OVERFLOW_PAST = (105, 105, 125)
# Current day: cell tint + frame (events use normal palette; past days stay un-tinted).
_TODAY_CELL_BG = (232, 242, 255)
_TODAY_OUTLINE = (50, 90, 145)
_TODAY_DAY_NUMBER = (18, 52, 110)

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
# Padding inside each day cell (day number, event text); must match header alignment math.
_CELL_INNER_PAD = 4
# Monday-first week: column indices for Sat/Sun background tint.
_WEEKEND_COLUMNS = frozenset((5, 6))


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
            event_line_step=int(event_px * 1.18),
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


def _baseline_y_from_line_top(
    line_top: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> int:
    """Convert a line's top ``y`` to a shared baseline for ``anchor='ls'`` text."""
    if isinstance(font, ImageFont.FreeTypeFont):
        ascent, _ = font.getmetrics()
    else:
        ascent = max(8, int(getattr(font, "size", 12) * 0.75))
    return line_top + ascent


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


def _max_visible_event_rows(row_height: float, daynum_px: int, event_px: int) -> int:
    return max(1, int((row_height - daynum_px * 1.4) // max(11.0, event_px * 1.2)))


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


def _draw_overflow_footer(
    draw: ImageDraw.ImageDraw,
    *,
    left_x: int,
    baseline_y: int,
    max_width: int,
    hidden_count: int,
    fonts: MonthFonts,
    muted: bool = False,
) -> None:
    fill_ov = _OVERFLOW_PAST if muted else _OVERFLOW_MORE
    more = f"+{hidden_count} more"
    draw.text(
        (left_x, baseline_y),
        truncate_to_width(draw, more, fonts.event_bold, max_width),
        fill=fill_ov,
        font=fonts.event_bold,
        anchor="ls",
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
) -> None:
    """Draw stacked event lines inside one day cell."""
    text_left = int(cell_left + _CELL_INNER_PAD)
    line_top = int(cell_top + int(fonts.daynum_px * 1.15))
    max_w = int(column_width - 2 * _CELL_INNER_PAD)
    max_rows = _max_visible_event_rows(row_height, fonts.daynum_px, fonts.event_px)

    shown = 0
    for item in items:
        baseline_y = _baseline_y_from_line_top(line_top, fonts.event_regular)

        if shown >= max_rows:
            _draw_overflow_footer(
                draw,
                left_x=text_left,
                baseline_y=baseline_y,
                max_width=max_w,
                hidden_count=len(items) - max_rows,
                fonts=fonts,
                muted=muted,
            )
            break

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
        shown += 1


def _draw_day_cell(
    draw: ImageDraw.ImageDraw,
    *,
    cell_left: float,
    cell_top: float,
    cell_right: float,
    row_h: float,
    day_index: int,
    d: date,
    focused_month: int,
    col_w: float,
    events_by_day: dict[date, list[Any]],
    fonts: MonthFonts,
    today: date,
) -> None:
    """Background, grid outline, day number, and optional event stack for one grid cell."""
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
    is_past = d < today

    draw.text(
        (cell_left + _CELL_INNER_PAD, cell_top + 3),
        str(d.day),
        fill=day_color,
        font=fonts.day_number,
    )

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

    for week_index, week in enumerate(weeks):
        cell_top = grid_top + week_index * row_h
        for day_index, d in enumerate(week):
            cell_left = fonts.pad + day_index * col_w
            cell_right = fonts.pad + (day_index + 1) * col_w
            _draw_day_cell(
                draw,
                cell_left=cell_left,
                cell_top=cell_top,
                cell_right=cell_right,
                row_h=row_h,
                day_index=day_index,
                d=d,
                focused_month=month,
                col_w=col_w,
                events_by_day=events_by_day,
                fonts=fonts,
                today=today,
            )

    return _png_bytes(img)
