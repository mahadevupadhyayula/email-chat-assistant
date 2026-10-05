from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    app_env: Literal["development", "test", "e2e"] = "development"
    log_level: str = "INFO"
    frontend_url: str = "http://localhost:5173"
    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/email_assistant"
    test_database_url: str = "postgresql+asyncpg://app:app@localhost:5432/email_assistant_test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
