"""Required keys for every plugin's ``default_config()`` and merged runtime config."""

from __future__ import annotations

from typing import Annotated, Any

from epaper_dithering import DitherMode
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_serializer


def parse_dither_mode_value(v: Any) -> DitherMode:
    """Coerce plugin config JSON (member name, int value, or ``DitherMode``) for validation."""
    if isinstance(v, DitherMode):
        return v
    if isinstance(v, str):
        return DitherMode[v.upper()]
    if isinstance(v, int):
        for m in DitherMode:
            if m.value == v:
                return m
    raise ValueError(f"Invalid dither_mode: {v!r}")


class PluginDefaultConfig(BaseModel):
    """Every plugin must include these keys in ``default_config()``; more keys are allowed."""

    refresh_interval_seconds: int = Field(..., gt=0)
    dither_mode: Annotated[
        DitherMode,
        BeforeValidator(parse_dither_mode_value),
    ] = Field(...)
    model_config = ConfigDict(extra="allow")

    @field_serializer("dither_mode", when_used="json")
    def _dither_mode_json(self, v: DitherMode) -> str:
        """JSON responses use ``DitherMode`` member names (e.g. ``FLOYD_STEINBERG``)."""
        return v.name


def validate_plugin_defaults(data: dict[str, Any]) -> None:
    """Raise ``ValidationError`` if a plugin's ``default_config()`` is missing required keys."""
    PluginDefaultConfig.model_validate(data)
