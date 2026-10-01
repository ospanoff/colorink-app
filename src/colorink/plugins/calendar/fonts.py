"""Font loading, the MonthFonts dataclass, and text layout with bitmap emoji."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import regex
from PIL import Image, ImageDraw, ImageFont

from colorink.plugins.calendar.palette import _EVENT_LINE_STEP_FACTOR

# Emoji bitmap height vs Inter “M” line box (bumped slightly for e-paper readability).
_EMOJI_HEIGHT_VS_TEXT = 1.20

# Inter for Latin and Cyrillic; bundled Noto bitmap emoji (CBDT).
# COLRv1 often does not rasterize in Pillow.
_FONTS_DIR = Path(__file__).resolve().parent / "fonts"
_TEXT_REGULAR = _FONTS_DIR / "Inter-Regular.ttf"
_TEXT_BOLD = _FONTS_DIR / "Inter-Bold.ttf"
_NOTO_COLOR_BITMAP = _FONTS_DIR / "NotoColorEmoji.ttf"

_PIC = regex.compile(r"\p{Extended_Pictographic}", regex.VERSION1)


def _is_emoji(grapheme: str) -> bool:
    return _PIC.search(grapheme) is not None


@cache
def _bitmap_emoji_native_pem() -> int | None:
    if not _NOTO_COLOR_BITMAP.is_file():
        return None
    path = str(_NOTO_COLOR_BITMAP)
    for px in range(8, 256):
        try:
            font = ImageFont.truetype(path, px)
        except OSError:
            continue
        try:
            if font.getmask("🙂").size[1] > 0:
                return px
        except (OSError, TypeError, ValueError, AttributeError):
            continue
    return None


@cache
def _emoji_font() -> ImageFont.FreeTypeFont | None:
    pem = _bitmap_emoji_native_pem()
    if pem is None:
        return None
    try:
        return ImageFont.truetype(str(_NOTO_COLOR_BITMAP), pem)
    except OSError:
        return None


def _text_line_height(
    draw: ImageDraw.ImageDraw,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    anchor: str,
) -> int:
    bb = draw.textbbox((0, 0), "M", font=font, anchor=anchor)
    return max(1, int(bb[3] - bb[1]))


def _raster_emoji(grapheme: str, *, target_h: int) -> tuple[int, Image.Image]:
    face = _emoji_font()
    if face is None or target_h < 1:
        return 0, Image.new("RGBA", (0, 0), (0, 0, 0, 0))
    scratch = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    dr = ImageDraw.Draw(scratch)
    dr.text((0, 0), grapheme, font=face, anchor="lt", embedded_color=True)
    bb = scratch.getbbox()
    if not bb:
        return 0, Image.new("RGBA", (0, 0), (0, 0, 0, 0))
    crop = scratch.crop(bb)
    w0, h0 = crop.size
    if h0 <= 0:
        return 0, Image.new("RGBA", (0, 0), (0, 0, 0, 0))
    th = max(1, target_h)
    tw = max(1, int(round(w0 * th / h0)))
    resized = crop.resize((tw, th), Image.Resampling.LANCZOS)
    return tw, resized


def _graphemes(text: str) -> list[str]:
    return regex.findall(r"\X", text, regex.VERSION1)


def _each_glyph(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    anchor: str,
):
    """Walk user-perceived characters: text uses ``font``, emoji uses bundled bitmap (if any)."""
    emoji_face = _emoji_font()
    line_h = _text_line_height(draw, font, anchor)
    emoji_h = max(1, int(round(line_h * _EMOJI_HEIGHT_VS_TEXT)))
    for g in _graphemes(text):
        if emoji_face is not None and _is_emoji(g):
            tw, rgba = _raster_emoji(g, target_h=emoji_h)
            yield ("emoji", tw, rgba)
        else:
            yield ("text", g)


def line_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    anchor: str = "ls",
) -> float:
    """Pixel width: Inter for text, scaled bitmap for emoji."""
    w = 0.0
    for part in _each_glyph(draw, text, font=font, anchor=anchor):
        if part[0] == "emoji":
            w += float(part[1])
        else:
            w += float(draw.textlength(part[1], font=font))
    return w


def truncate_line(
    draw: ImageDraw.ImageDraw,
    text: str,
    *,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_w: int,
    anchor: str = "ls",
) -> str:
    """Truncate on grapheme boundaries to ``max_w``; ellipsis in ``font``."""
    ell, ell_w = "...", float(draw.textlength("...", font=font))
    if max_w <= 0:
        return ""
    if line_width(draw, text, font=font, anchor=anchor) <= max_w:
        return text
    if ell_w > max_w:
        return ""
    clusters = _graphemes(text)
    lo, hi = 0, len(clusters)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        candidate = "".join(clusters[:mid]) + ell
        if line_width(draw, candidate, font=font, anchor=anchor) <= max_w:
            lo = mid
        else:
            hi = mid - 1
    if lo == 0:
        return ell if line_width(draw, ell, font=font, anchor=anchor) <= max_w else ""
    return "".join(clusters[:lo]) + ell


def draw_line(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    *,
    image: Image.Image,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: tuple[int, int, int],
    anchor: str = "ls",
) -> None:
    """Draw a line: ``font`` for text, bitmap emoji pasted when bundled Noto is available.

    ``image`` must be the ``Image.Image`` used to build ``draw``.
    """
    x0, y0 = xy
    x = float(x0)
    for part in _each_glyph(draw, text, font=font, anchor=anchor):
        if part[0] == "emoji":
            tw, rgba = part[1], part[2]
            if tw > 0 and rgba.height > 0:
                bb = draw.textbbox((x, y0), "M", font=font, anchor=anchor)
                mid_y = (bb[1] + bb[3]) / 2.0
                paste_y = int(mid_y - rgba.height / 2.0)
                image.paste(rgba, (int(x), paste_y), rgba)
            x += float(tw)
        else:
            g = part[1]
            draw.text((x, y0), g, font=font, fill=fill, anchor=anchor)
            x += float(draw.textlength(g, font=font))


def _calendar_font_regular(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if not _TEXT_REGULAR.is_file():
        raise FileNotFoundError(f"Bundled font missing: {_TEXT_REGULAR}")
    return ImageFont.truetype(str(_TEXT_REGULAR), size)


def _calendar_font_bold(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if not _TEXT_BOLD.is_file():
        raise FileNotFoundError(f"Bundled font missing: {_TEXT_BOLD}")
    return ImageFont.truetype(str(_TEXT_BOLD), size)


def _line_box(font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
    """Ascent + descent: the vertical space one line of ``font`` occupies."""
    if isinstance(font, ImageFont.FreeTypeFont):
        ascent, descent = font.getmetrics()
        return ascent + descent
    return max(8, int(getattr(font, "size", 12) * 1.2))


def _ascent(font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
    if isinstance(font, ImageFont.FreeTypeFont):
        return font.getmetrics()[0]
    return max(8, int(getattr(font, "size", 12) * 0.75))


@dataclass(frozen=True)
class MonthFonts:
    """Scaled fonts and vertical rhythm for a given canvas size."""

    pad: int
    dow_px: int
    daynum_px: int
    event_px: int
    event_line_step: int
    meta: ImageFont.FreeTypeFont | ImageFont.ImageFont
    dow: ImageFont.FreeTypeFont | ImageFont.ImageFont
    day_number: ImageFont.FreeTypeFont | ImageFont.ImageFont
    event_regular: ImageFont.FreeTypeFont | ImageFont.ImageFont
    event_bold: ImageFont.FreeTypeFont | ImageFont.ImageFont

    @classmethod
    def for_canvas(cls, width: int, height: int) -> MonthFonts:
        """Sizes for a two-week hour grid: modest day numbers, compact all-day bars.

        Timed events use a separate face sized to the half-hour slot at draw time.
        """
        short = min(width, height)
        pad = max(10, short // 80)
        col = max(1.0, (width - 2 * pad) / 7.0)
        daynum_px = max(15, min(21, short // 70))
        meta_px = max(11, min(13, daynum_px - 4))
        dow_px = max(14, min(18, short // 78))
        event_px = max(16, min(18, int(col / 14)))
        return cls(
            pad=pad,
            dow_px=dow_px,
            daynum_px=daynum_px,
            event_px=event_px,
            event_line_step=max(event_px + 2, int(event_px * _EVENT_LINE_STEP_FACTOR)),
            meta=_calendar_font_regular(meta_px),
            dow=_calendar_font_bold(dow_px),
            day_number=_calendar_font_bold(daynum_px),
            event_regular=_calendar_font_regular(event_px),
            event_bold=_calendar_font_bold(event_px),
        )
