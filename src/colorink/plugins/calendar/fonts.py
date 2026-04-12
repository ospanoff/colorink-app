"""Font loading, the MonthFonts dataclass, and text-measurement helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import ImageDraw, ImageFont

from colorink.plugins.calendar.palette import _EVENT_LINE_STEP_FACTOR

# Bundled Noto Sans (SIL OFL) - same family for regular vs bold; see fonts/OFL.txt
_FONTS_DIR = Path(__file__).resolve().parent / "fonts"
_NOTO_REGULAR = _FONTS_DIR / "NotoSans-Regular.ttf"
_NOTO_BOLD = _FONTS_DIR / "NotoSans-Bold.ttf"


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


def _truncate_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_w: int,
) -> str:
    if max_w <= 0:
        return ""
    if draw.textlength(text, font=font) <= max_w:
        return text
    ell = "..."
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        candidate = text[:mid] + ell
        if draw.textlength(candidate, font=font) <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + ell if lo > 0 else ell


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
        return _truncate_to_width(draw, time_str, font_time, max_w), ""
    budget = max_w - w_time - w_gap
    if budget <= 0:
        return time_str, ""
    return time_str, _truncate_to_width(draw, title_str, font_title, int(budget))
