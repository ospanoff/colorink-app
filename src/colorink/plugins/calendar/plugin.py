"""Calendar :class:`~colorink.plugins.protocol.ImagePlugin` implementation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from epaper_dithering import DitherMode

from colorink.plugins.calendar.config import CalendarPluginConfig
from colorink.plugins.calendar.ics import events_by_day_from_ics, host_for_label
from colorink.plugins.calendar.render import render_month_png
from colorink.plugins.protocol import DeviceContext, ImagePlugin

_PLACEHOLDER_URL = "https://example.com/calendar.ics"


def _make_result(
    *,
    ok: bool,
    error: str,
    year: int,
    month: int,
    events_by_day: dict[str, Any],
    multiday_spans: list[Any],
    url_label: str,
    timezone: str,
    today: str,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "error": error,
        "year": year,
        "month": month,
        "events_by_day": events_by_day,
        "multiday_spans": multiday_spans,
        "url_label": url_label,
        "timezone": timezone,
        "today": today,
    }


class CalendarPlugin(ImagePlugin):
    """Fetches an ICS feed from a URL and draws a month grid with events."""

    slug = "calendar"
    title = "Calendar"

    def config_model(self) -> type[CalendarPluginConfig]:
        return CalendarPluginConfig

    def default_config(self) -> dict[str, Any]:
        return {
            "ics_url": _PLACEHOLDER_URL,
            "timezone": "UTC",
            "refresh_interval_seconds": 3600,
            "dither_mode": DitherMode.FLOYD_STEINBERG,
        }

    def fetch_data(self, plugin_config: dict[str, Any], device: DeviceContext) -> dict[str, Any]:
        _ = device
        tz = ZoneInfo(str(plugin_config.get("timezone") or "UTC"))
        today_iso = datetime.now(tz).date().isoformat()
        url = str(plugin_config.get("ics_url", "")).strip()
        ty = plugin_config.get("test_year")
        tm = plugin_config.get("test_month")
        if ty is not None and tm is not None:
            year, month = int(ty), int(tm)
        else:
            now = datetime.now(UTC)
            year, month = now.year, now.month

        if not url or url == _PLACEHOLDER_URL:
            return _make_result(
                ok=False,
                error="Set ics_url in plugin config to a calendar feed URL.",
                year=year,
                month=month,
                events_by_day={},
                multiday_spans=[],
                url_label="",
                timezone=str(tz),
                today=today_iso,
            )

        try:
            with httpx.Client(timeout=25.0) as client:
                response = client.get(url, follow_redirects=True)
                response.raise_for_status()
                ics_bytes = response.content
            by_day, multiday_spans = events_by_day_from_ics(ics_bytes, year, month, tz)
            return _make_result(
                ok=True,
                error="",
                year=year,
                month=month,
                events_by_day={k.isoformat(): v for k, v in by_day.items()},
                multiday_spans=multiday_spans,
                url_label=host_for_label(url),
                timezone=str(tz),
                today=today_iso,
            )
        except (httpx.HTTPError, OSError, ValueError) as e:
            return _make_result(
                ok=False,
                error=str(e),
                year=year,
                month=month,
                events_by_day={},
                multiday_spans=[],
                url_label=host_for_label(url),
                timezone=str(tz),
                today=today_iso,
            )

    def render_raw(
        self,
        data: dict[str, Any],
        device: DeviceContext,
        plugin_config: dict[str, Any],
    ) -> bytes:
        _ = plugin_config
        return render_month_png(width=device.width, height=device.height, data=data)
