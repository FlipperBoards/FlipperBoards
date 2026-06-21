from pydantic_settings import BaseSettings
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

    class Config:
        env_file = ".env"
        env_prefix = "FB_"


settings = Settings()
