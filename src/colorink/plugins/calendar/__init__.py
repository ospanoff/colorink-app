"""Calendar plugin package: ICS URL -> month grid PNG.

Set optional ``today`` in :class:`~colorink.plugins.calendar.config.CalendarPluginConfig` to
pin the visible month and grid anchor; omit for the current local day in the configured
timezone.
"""

from __future__ import annotations

from colorink.plugins.calendar.config import CalendarPluginConfig
from colorink.plugins.calendar.plugin import CalendarPlugin

__all__ = [
    "CalendarPlugin",
    "CalendarPluginConfig",
]
