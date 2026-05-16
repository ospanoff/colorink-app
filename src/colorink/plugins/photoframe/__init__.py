"""Photoframe plugin: images from on-disk ``photoframe/img``.

Put ``.jpg``, ``.png``, ``.webp``, ``.bmp``, or ``.gif`` files directly in that folder
(flat layout).

On **each generation** for a device (when new artwork is produced, not skipped for being
within ``refresh_interval_seconds``), this plugin selects the **next** file in alphabetical
order and wraps after the last. The index is persisted per device in the app database.

``refresh_interval_seconds`` still drives how often the device is allowed to request a new image.
Optional config key ``fit`` is ``contain`` (letterboxed) or ``cover`` (cropped fill).
"""

from __future__ import annotations

from colorink.plugins.photoframe.config import PhotoFramePluginConfig
from colorink.plugins.photoframe.plugin import PhotoFramePlugin

__all__ = [
    "PhotoFramePlugin",
    "PhotoFramePluginConfig",
]
