from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = "kaoyan-miniapp-backend"
    app_env: str = "dev"
    api_prefix: str = "/api/v1"

    secret_key: str = "replace-with-strong-secret"
    visitor_token_ttl_seconds: int = 7 * 24 * 60 * 60

    database_url: str = "mysql+pymysql://root:root@localhost:3306/kaoyan_mvp?charset=utf8mb4"
    redis_url: str = "redis://localhost:6379/0"

    wechat_appid: str = ""
    wechat_secret: str = ""
    use_mock_wechat: bool = False
    auto_create_tables: bool = True

    admin_token: str = "replace-admin-token"
    rate_limit_per_minute: int = 120
    worker_poll_interval_seconds: int = 5
    worker_max_sources_per_job: int = 20
    worker_max_items_per_source: int = 10


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
