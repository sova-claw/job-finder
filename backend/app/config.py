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
    apify_linkedin_actor_id: str = "valig/linkedin-jobs-scraper"
    apify_linkedin_titles_csv: str = (
        "Python AI Engineer,ML Engineer,AI Platform Engineer,LLM Engineer"
    )
    apify_linkedin_location: str = "Europe"
    apify_linkedin_date_posted: str = "r604800"
    apify_linkedin_limit_per_title: int = 20
    apify_linkedin_company_names_csv: str = ""
    apify_linkedin_contract_types_csv: str = ""
    apify_linkedin_experience_levels_csv: str = ""
    apify_linkedin_remote_codes_csv: str = ""
    apify_linkedin_skip_job_ids_csv: str = ""
    apify_actor_timeout_seconds: int = 240
    cf_tunnel_token: str = ""
    hn_thread_id: str = "42306918"

    frontend_url: str = "http://localhost:3000"
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    cors_origin_regex: str = (
        r"https?://("
        r"localhost|127\.0\.0\.1|"
        r"192\.168\.\d{1,3}\.\d{1,3}|"
        r"10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
        r"172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}"
        r")(:\d+)?$"
    )

    dou_scrape_interval_hours: int = 6
    djinni_scrape_interval_hours: int = 6
    request_timeout_seconds: float = 25.0
    scraper_user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
