from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI Agent Platform"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:55432/ai_agent"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = "change_me"
    deepseek_api_key: str | None = None
    access_token_expire_minutes: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-v4-flash"
    llm_timeout_seconds: float = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
