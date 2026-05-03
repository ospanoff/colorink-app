from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COLORINK_", env_file=".env", extra="ignore")

    database_path: Path = Path("data/colorink.db")
    """SQLite database (metadata only for generated images)."""

    artifacts_path: Path = Path("data/generated")
    """Directory for plugin render output (PNG + BMP per device/plugin)."""
