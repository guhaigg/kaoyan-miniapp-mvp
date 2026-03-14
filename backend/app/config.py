from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = "kaoyan-miniapp-backend"
    app_env: str = "dev"
    api_prefix: str = "/api/v1"

    secret_key: str = "replace-with-strong-secret"
    visitor_token_ttl_seconds: int = 7 * 24 * 60 * 60

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/kaoyan_mvp"
    redis_url: str = "redis://localhost:6379/0"

    wechat_appid: str = ""
    wechat_secret: str = ""
    use_mock_wechat: bool = True

    admin_token: str = "replace-admin-token"
    rate_limit_per_minute: int = 120


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
