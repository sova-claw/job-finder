from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Career Intelligence System"
    app_env: str = "development"
    app_debug: bool = False
    api_prefix: str = "/api"

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/cis",
        description="Async PostgreSQL URL",
    )
    sync_database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/cis",
        description="Sync PostgreSQL URL for Alembic and sync tasks",
    )

    anthropic_api_key: str = ""
    anthropic_base_url: str = "https://api.anthropic.com/v1/messages"
    anthropic_extractor_model: str = "claude-3-5-haiku-latest"
    anthropic_cover_letter_model: str = "claude-sonnet-4-20250514"
    apify_token: str = ""
    cf_tunnel_token: str = ""

    frontend_url: str = "http://localhost:3000"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    dou_scrape_interval_hours: int = 6
    djinni_scrape_interval_hours: int = 6
    request_timeout_seconds: float = 25.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
