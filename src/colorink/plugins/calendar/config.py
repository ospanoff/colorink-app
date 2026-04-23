"""Pydantic config for the calendar plugin."""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ConfigDict, Field, field_validator

from colorink.plugins.config import PluginBaseConfig


class CalendarPluginConfig(PluginBaseConfig):
    """Typed config for :class:`~colorink.plugins.calendar.plugin.CalendarPlugin`."""

    model_config = ConfigDict(extra="forbid")

    ics_url: str = Field(
        default="https://example.com/calendar.ics",
        min_length=1,
        description="HTTPS URL returning an iCalendar (.ics) document.",
    )
    timezone: str = Field(
        default="UTC",
        min_length=1,
        description="IANA timezone for event times and which calendar day an event falls on.",
    )
    today: date | None = Field(
        default=None,
        description="Optional calendar day to pin the view (year/month and rolling grid). "
        "Omit to use the current local day in the configured timezone.",
    )

    @field_validator("timezone")
    @classmethod
    def _timezone_must_exist(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("timezone must be non-empty")
        try:
            ZoneInfo(s)
        except ZoneInfoNotFoundError as e:
            raise ValueError(f"Unknown IANA timezone: {s!r}") from e
        return s
