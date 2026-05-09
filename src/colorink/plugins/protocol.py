from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from epaper_dithering import ColorScheme
from PIL import Image

from colorink.plugins.config import PluginBaseConfig


@dataclass(frozen=True, slots=True)
class DeviceContext:
    """Resolved device for plugin rendering and dithering."""

    id: str
    width: int
    height: int
    color_scheme: ColorScheme


@runtime_checkable
class ImagePlugin(Protocol):
    """Plugin contract: fetch data, render a Pillow RGB image, expose defaults and slug.

    :meth:`render_raw` must return a freshly constructed image sized for ``device``.
    The generation service closes it after encoding PNG and dithering to BMP.
    """

    slug: str
    title: str

    def config_model(self) -> type[PluginBaseConfig]:
        """Pydantic model class for merged runtime config (base fields + plugin-specific fields)."""
        ...

    def default_config(self) -> dict[str, Any]:
        """Must validate against :meth:`config_model`."""
        ...

    def fetch_data(
        self,
        plugin_config: dict[str, Any],
        device: DeviceContext,
        conn: sqlite3.Connection,
    ) -> Any: ...

    def render_raw(
        self,
        data: Any,
        device: DeviceContext,
        plugin_config: dict[str, Any],
    ) -> Image.Image: ...
