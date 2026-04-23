"""RGB palette constants, layout tuning values, and the multiday bar colour selector."""

from __future__ import annotations

# --- Palette (RGB) ---------------------------------------------------------------------------

_HEADER_TEXT = (45, 45, 45)
_WEEKDAY_LABEL = (90, 90, 90)
_DAY_IN_MONTH = (25, 25, 25)
_DAY_OTHER_MONTH = (200, 200, 200)
# Soft grid (was ~220). If Floyd-Steinberg hides lines on device, prefer dither_mode NONE.
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

# --- Layout constants ------------------------------------------------------------------------

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
# Vertical space between one month's section and the next (after last week of prior month).
_MONTH_INTER_BLOCK_GAP = 10


def _multiday_bar_palette(
    lane: int, is_past: bool
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Bar fill and outline for a multiday lane (cycles three cool pastels)."""
    i = lane % len(_MULTIDAY_BAR_FILLS)
    if is_past:
        return _MULTIDAY_BAR_FILLS_PAST[i], _MULTIDAY_BAR_OUTLINES_PAST[i]
    return _MULTIDAY_BAR_FILLS[i], _MULTIDAY_BAR_OUTLINES[i]
