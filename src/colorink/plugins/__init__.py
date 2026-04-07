"""Plugin registry and protocols."""

from colorink.plugins.config import PluginDefaultConfig
from colorink.plugins.protocol import DeviceContext, ImagePlugin
from colorink.plugins.registry import all_plugins, get_plugin

__all__ = [
    "DeviceContext",
    "ImagePlugin",
    "PluginDefaultConfig",
    "all_plugins",
    "get_plugin",
]
