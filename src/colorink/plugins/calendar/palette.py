"""RGB palette constants and layout tuning values for the two-week grid.

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

_WEEKDAY_LABEL = (119, 119, 119)  # L7  – quiet Mon–Sun header labels
_WEEKDAY_LABEL_TODAY = (17, 17, 17)  # L1  – today's weekday label
_HEADER_RULE = (221, 221, 221)  # L13 – hairline under the weekday labels
_DAY_IN_MONTH = (17, 17, 17)  # L1  – day-of-month digit
_DAY_NUMBER_PAST = (153, 153, 153)  # L9  – day number on a past day
_MONTH_TAG = (102, 102, 102)  # L6  – "Oct" beside the 1st
_MONTH_TAG_PAST = (170, 170, 170)  # L10
# Exact palette steps survive dithering, so near-white rules stay crisp.
_GRID_LINE = (238, 238, 238)  # L14 – column separators
_HOUR_LINE = (238, 238, 238)  # L14 – barely-there hour rules
_HOUR_LABEL = (153, 153, 153)  # L9  – hour gutter labels
_ERROR_TEXT = (34, 34, 34)  # L2  – ICS error message (no colour on greyscale)

# Timed event cards: grey fill with a dark left edge, no outline.
_TIMED_BLOCK_FILL = (221, 221, 221)  # L13
_TIMED_BLOCK_ACCENT = (51, 51, 51)  # L3
_TIMED_BLOCK_FILL_PAST = (238, 238, 238)  # L14
_TIMED_BLOCK_ACCENT_PAST = (170, 170, 170)  # L10
_TIMED_BLOCK_RADIUS = 5
_TIMED_BLOCK_ACCENT_WIDTH = 3

# Event text (cards and all-day bars).
_EVENT_TIME = (68, 68, 68)  # L4  – clock line
_EVENT_TITLE = (17, 17, 17)  # L1  – event title
_EVENT_LOCATION = (85, 85, 85)  # L5  – place line under the title
# Past-day events: visibly muted but distinct from each other and from background.
_EVENT_TIME_PAST = (153, 153, 153)  # L9
_EVENT_TITLE_PAST = (119, 119, 119)  # L7
_EVENT_LOCATION_PAST = (153, 153, 153)  # L9

# All-day bars: borderless soft pills.
_BAR_FILL = (204, 204, 204)  # L12
_BAR_FILL_PAST = (238, 238, 238)  # L14
_BAR_TOP_INSET = 2
_BAR_GAP = 3

# Today: black capsule on the day number, and a now-line with a dot on today's column.
_TODAY_PILL = (0, 0, 0)  # L0  – day-number capsule
_TODAY_PILL_TEXT = (255, 255, 255)  # L15
_NOW_RULE = (17, 17, 17)  # L1  – current half-hour line and its left dot
_NOW_DOT_RADIUS = 6

# --- Layout constants -----------------------------------------------------------------------

_WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_GRID_COLUMNS = 7
# Padding inside each day cell (day number, weekday label).
_CELL_INNER_PAD = 4
# Leaves room for the today capsule, which grows upward from the glyph.
_DAY_NUMBER_TOP_PAD = 3
# Space between bottom of day number and first all-day bar / hour grid.
_GAP_BELOW_DAY_NUMBER = 6
# Whitespace between the two week rows (replaces a separator rule).
_WEEK_GAP = 18
# All-day bar height = event_px * this factor.
_EVENT_LINE_STEP_FACTOR = 1.34
