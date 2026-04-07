from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from epaper_dithering import ColorScheme


@dataclass(frozen=True, slots=True)
class DeviceContext:
    """Resolved device for plugin rendering and dithering."""

    id: str
    width: int
    height: int
    color_scheme: ColorScheme


@runtime_checkable
class ImagePlugin(Protocol):
    """Plugin contract: fetch data, render PNG bytes, expose defaults and slug."""

    slug: str
    title: str

    def default_config(self) -> dict[str, Any]:
        """Must satisfy ``PluginDefaultConfig`` (required keys + any plugin-specific keys)."""
        ...

    def fetch_data(self, plugin_config: dict[str, Any], device: DeviceContext) -> Any: ...

    def render_raw(
        self,
        data: Any,
        device: DeviceContext,
        plugin_config: dict[str, Any],
    ) -> bytes: ...
