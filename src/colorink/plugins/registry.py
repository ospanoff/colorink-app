"""Central registry: add new plugins here only."""

from __future__ import annotations

from typing import cast

from colorink.plugins.builtin.hello import HelloPlugin
from colorink.plugins.calendar import CalendarPlugin
from colorink.plugins.protocol import ImagePlugin
from colorink.services.plugin_config import merge_and_validate_plugin_config

PLUGINS: list[ImagePlugin] = cast(list[ImagePlugin], [HelloPlugin(), CalendarPlugin()])

for _plugin in PLUGINS:
    merge_and_validate_plugin_config(_plugin, {})


def get_plugin(slug: str) -> ImagePlugin | None:
    for p in PLUGINS:
        if p.slug == slug:
            return p
    return None


def all_plugins() -> list[ImagePlugin]:
    return list(PLUGINS)
