from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

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
    rate_limit_per_minute: int = 120
    cors_allow_origins: str = "*"

    def cors_allow_origins_list(self) -> List[str]:
        if self.cors_allow_origins.strip() == "*":
            return ["*"]

        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
