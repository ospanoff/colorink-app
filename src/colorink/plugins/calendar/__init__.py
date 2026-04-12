"""Calendar plugin package: ICS URL -> month grid PNG.

Configure ``test_year`` and ``test_month`` together to pin the visible month; omit both
for the current month in UTC (see :class:`~colorink.plugins.calendar.config.CalendarPluginConfig`).
"""

from __future__ import annotations

from colorink.plugins.calendar.config import CalendarPluginConfig
from colorink.plugins.calendar.plugin import CalendarPlugin

__all__ = [
    "CalendarPlugin",
    "CalendarPluginConfig",
]
