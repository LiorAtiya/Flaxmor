"""Application configuration, loaded from environment variables (and .env in local dev)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration. Field names map 1:1 to env vars (case-insensitive)."""

    # ".env" covers Docker/CWD runs; "../.env" lets `uvicorn` run from middleware/
    # while the single .env lives at the project root. Real env vars always win.
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    served_models: list[str] = ["gpt-4o-mini", "gpt-4o"]
    connect_timeout_seconds: float = 10.0
    read_timeout_seconds: float = 120.0
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance (cached after first call)."""
    return Settings()
