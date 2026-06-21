from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from typing import Optional


class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    db_path: str = "flipperboards.db"

    # Default display dimensions
    default_rows: int = 6
    default_cols: int = 22

    # API keys (set via environment or .env file)
    weather_api_key: Optional[str] = None
    news_api_key: Optional[str] = None

    # Comma-separated list of plugin names to load (e.g. FB_PLUGINS=billing,analytics)
    plugins: list[str] = []

    @field_validator("plugins", mode="before")
    @classmethod
    def _parse_plugins(cls, v):
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v or []

    model_config = SettingsConfigDict(env_file=".env", env_prefix="FB_")


settings = Settings()
