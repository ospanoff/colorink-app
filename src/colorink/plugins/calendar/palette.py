"""RGB palette constants, layout tuning values, and the multiday bar colour selector.

All colour constants use neutral grey (R = G = B) mapped to one of the sixteen
quantisation steps produced by a 4-bit greyscale e-paper display:

    0  17  34  51  68  85  102  119  136  153  170  187  204  221  238  255
    L0  L1  L2  L3  L4  L5   L6   L7   L8   L9  L10  L11  L12  L13  L14  L15

Keeping source colours on these exact steps means every element lands on a
distinct, predictable level after dithering — no two adjacent elements blend into
the same apparent shade.
"""

from __future__ import annotations

# --- Palette (16-step greyscale) -----------------------------------------------------------

_HEADER_TEXT = (17, 17, 17)  # L1  – month-section headings
_WEEKDAY_LABEL = (68, 68, 68)  # L4  – Mon–Sun header labels
_DAY_IN_MONTH = (17, 17, 17)  # L1  – day-of-month digit in current month
_DAY_OTHER_MONTH = (187, 187, 187)  # L11 – clearly faded overflow days
# Slightly darker than the original ~220 so grid lines survive Floyd-Steinberg.
# If lines are still invisible on your device, set dither_mode = NONE.
_GRID_LINE = (170, 170, 170)  # L10 – cell borders
_WEEKDAY_CELL_BG = (255, 255, 255)  # L15 – plain white
_WEEKEND_CELL_BG = (238, 238, 238)  # L14 – subtle Sat/Sun tint

_EVENT_TIME = (68, 68, 68)  # L4  – timed-event clock text
_EVENT_TITLE = (17, 17, 17)  # L1  – event title
_OVERFLOW_MORE = (51, 51, 51)  # L3  – "+N events" chip text
_ERROR_TEXT = (34, 34, 34)  # L2  – ICS error message (no colour on greyscale)

# Past-day events: visibly muted but distinct from each other and from background.
_EVENT_TIME_PAST = (153, 153, 153)  # L9
_EVENT_TITLE_PAST = (119, 119, 119)  # L7
_OVERFLOW_PAST = (119, 119, 119)  # L7

# Overflow chip ("+N events" pill)
_OVERFLOW_CHIP_BG = (221, 221, 221)  # L13 – active
_OVERFLOW_CHIP_BG_PAST = (238, 238, 238)  # L14 – past
_OVERFLOW_CHIP_OUTLINE = (153, 153, 153)  # L9  – active border
_OVERFLOW_CHIP_OUTLINE_PAST = (204, 204, 204)  # L12 – past border
_OVERFLOW_CHIP_RADIUS = 4

# Multiday bar fills/outlines – three distinct grey levels so stacked lanes are
# distinguishable even without colour.  Past bars all use a single light grey.
_MULTIDAY_BAR_FILLS = (
    (204, 204, 204),  # L12 – lane 0
    (221, 221, 221),  # L13 – lane 1
    (187, 187, 187),  # L11 – lane 2
)
_MULTIDAY_BAR_FILLS_PAST = (
    (238, 238, 238),  # L14 – all past lanes
    (238, 238, 238),
    (238, 238, 238),
)
_MULTIDAY_BAR_OUTLINES = (
    (119, 119, 119),  # L7  – lane 0 border
    (136, 136, 136),  # L8  – lane 1 border
    (102, 102, 102),  # L6  – lane 2 border
)
_MULTIDAY_BAR_OUTLINES_PAST = (
    (204, 204, 204),  # L12 – all past lane borders
    (204, 204, 204),
    (204, 204, 204),
)
_MULTIDAY_BG_TOP_INSET = 2
# Multiday stripe corner radius is derived from ``bar_h`` in ``render`` (pill caps).

# Today: clearly distinct from white (L15) and near-white weekend (L14).
_TODAY_CELL_BG = (204, 204, 204)  # L12 – 3 steps below white
_TODAY_OUTLINE = (51, 51, 51)  # L3  – strong border
_TODAY_DAY_NUMBER = (0, 0, 0)  # L0  – black for maximum contrast

# --- Layout constants -----------------------------------------------------------------------

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
# Padding inside each day cell (day number, event text); must match header alignment math.
_CELL_INNER_PAD = 4
# Day-of-month digit: must match ``_draw_day_cell_chrome`` y offset.
_DAY_NUMBER_TOP_PAD = 3
# Space between bottom of day number and first multiday bar / event line.
_GAP_BELOW_DAY_NUMBER = 4
# List row height = event_px * this factor; multiday stripes use the same step.
# Slightly > 1.0 gives air between lines and room inside bars.
_EVENT_LINE_STEP_FACTOR = 1.26
# Monday-first week: column indices for Sat/Sun background tint.
_WEEKEND_COLUMNS = frozenset((5, 6))
_GRID_COLUMNS = 7
# Vertical space between one month's section and the next.
_MONTH_INTER_BLOCK_GAP = 10


def _multiday_bar_palette(
    lane: int, is_past: bool
) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    """Bar fill and outline for a multiday lane (cycles three grey levels)."""
    i = lane % len(_MULTIDAY_BAR_FILLS)
    if is_past:
        return _MULTIDAY_BAR_FILLS_PAST[i], _MULTIDAY_BAR_OUTLINES_PAST[i]
    return _MULTIDAY_BAR_FILLS[i], _MULTIDAY_BAR_OUTLINES[i]
