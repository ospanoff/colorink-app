from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COLORINK_", env_file=".env", extra="ignore")

    database_path: Path = Path("data/colorink.db")
