"""Pydantic config for the photoframe plugin."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field

from colorink.plugins.config import PluginBaseConfig


class PhotoFramePluginConfig(PluginBaseConfig):
    """Typed config for :class:`~colorink.plugins.photoframe.plugin.PhotoFramePlugin`."""

    model_config = ConfigDict(extra="forbid")

    fit: Literal["contain", "cover"] = Field(
        default="contain",
        description="How photos are scaled to the display: letterbox vs crop-to-fill.",
    )
