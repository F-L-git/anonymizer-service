from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Anonymizer Service"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://anonymizer:anonymizer@localhost:5432/anonymizer"
    redis_url: str = "redis://localhost:6379/0"

    # Cache TTL in seconds
    cache_ttl: int = 3600

    # Auth (optional simple JWT)
    secret_key: str = "change-me-in-production-super-secret-key-32chars"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Rate limiting (requests per minute per IP)
    rate_limit_per_minute: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()
