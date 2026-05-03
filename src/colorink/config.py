from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DitherBackend = Literal["auto", "epaper"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COLORINK_", env_file=".env", extra="ignore")

    database_path: Path = Path("data/colorink.db")
    """SQLite database (metadata only for generated images)."""

    artifacts_path: Path = Path("data/generated")
    """Directory for plugin render output (PNG + BMP per device/plugin)."""

    dither_backend: DitherBackend = Field(
        default="auto",
        description=(
            "auto: Pillow palette quantize (C dither) for FLOYD_STEINBERG / NONE / ORDERED; "
            "other dither modes use epaper-dithering. epaper: always epaper-dithering."
        ),
    )
