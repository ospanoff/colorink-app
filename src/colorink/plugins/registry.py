"""Central registry: add new plugins here only."""

from __future__ import annotations

from colorink.plugins.builtin.hello import HelloPlugin
from colorink.plugins.config import validate_plugin_defaults
from colorink.plugins.protocol import ImagePlugin

PLUGINS: list[ImagePlugin] = [
    HelloPlugin(),
]

for _plugin in PLUGINS:
    validate_plugin_defaults(_plugin.default_config())


def get_plugin(slug: str) -> ImagePlugin | None:
    for p in PLUGINS:
        if p.slug == slug:
            return p
    return None


def all_plugins() -> list[ImagePlugin]:
    return list(PLUGINS)
