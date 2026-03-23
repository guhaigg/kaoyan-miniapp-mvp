from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    app_name: str = "gewu-jianlu-backend"
    app_env: str = "dev"
    api_prefix: str = "/api/v1"

    secret_key: str = "replace-with-strong-secret"
    visitor_token_ttl_seconds: int = 7 * 24 * 60 * 60
    user_session_ttl_seconds: int = 7 * 24 * 60 * 60

    database_url: str = "mysql+pymysql://root:password@127.0.0.1:3306/gewu_jianlu?charset=utf8mb4"
    redis_url: str = "redis://localhost:6379/0"

    wechat_appid: str = ""
    wechat_secret: str = ""
    use_mock_wechat: bool = True

    admin_token: str = "replace-admin-token"
    admin_username: str = "admin"
    admin_password: str = ""
    admin_session_ttl_seconds: int = 8 * 60 * 60
    admin_login_fail_limit: int = 5
    admin_login_lock_seconds: int = 15 * 60
    user_refresh_ttl_seconds: int = 30 * 24 * 60 * 60
    wechat_bind_code_ttl_seconds: int = 10 * 60
    web_base_url: str = "https://gewujl.cloud"
    rate_limit_per_minute: int = 120
    enable_notification_worker: bool = True
    notification_batch_size: int = 100
    notification_poll_interval_seconds: float = 1.0
    notification_cache_refresh_seconds: int = 60
    notification_batch_window_seconds: int = 180
    notification_inapp_delay_seconds: int = 0
    notification_retry_delay_seconds: int = 10
    notification_max_attempts: int = 5
    notification_processing_timeout_seconds: int = 120
    notification_sse_poll_seconds: float = 1.0
    search_cache_ttl_seconds: int = 5 * 60
    search_cache_max_entries: int = 500
    search_cache_max_page: int = 2
    enable_bark_notifications: bool = False
    bark_server_url: str = "https://api.day.app"
    bark_push_group: str = "gewujl"
    bark_push_sound: str = ""
    enable_crawl_worker: bool = True
    crawl_batch_size: int = 20
    crawl_poll_interval_seconds: float = 1.0
    crawl_fetch_timeout_seconds: float = 10.0
    crawl_retry_attempts: int = 3
    crawl_retry_backoff_seconds: float = 0.1
    crawl_processing_timeout_seconds: int = 5 * 60
    cors_allow_origins: str = ",".join(
        [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "https://gewujl.cloud",
            "https://www.gewujl.cloud",
        ]
    )

    def cors_allow_origins_list(self) -> List[str]:
        if self.cors_allow_origins.strip() == "*":
            return ["*"]

        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
