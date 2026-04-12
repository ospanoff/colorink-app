"""Pydantic config for the calendar plugin."""

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ConfigDict, Field, field_validator, model_validator

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
    test_year: int | None = Field(
        default=None,
        ge=1,
        le=9999,
        description="Year (with test_month). Omit both for current UTC month.",
    )
    test_month: int | None = Field(
        default=None,
        ge=1,
        le=12,
        description="Month 1-12 (with test_year). Omit both for current UTC month.",
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

    @model_validator(mode="after")
    def _test_year_month_both_or_neither(self) -> CalendarPluginConfig:
        y, m = self.test_year, self.test_month
        if (y is None) != (m is None):
            raise ValueError("test_year and test_month must both be set or both omitted")
        return self
