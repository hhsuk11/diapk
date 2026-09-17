from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "가즈아 드어넥슴"
    app_env: str = "local"
    auth_mode: Literal["dev", "google"] = "dev"
    dev_admin_email: str = "dev-admin@example.local"
    database_url: str = "sqlite+pysqlite:///./pvpgg.local.db"
    session_secret: str = "change-me"
    session_https_only: bool = False
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str | None = None
    google_super_admin_emails: str = ""
    google_oauth_verify_ssl: bool = True
    public_cache_ttl_seconds: int = 300

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)

    @property
    def google_super_admin_email_set(self) -> frozenset[str]:
        return frozenset(
            email.strip().lower()
            for email in self.google_super_admin_emails.split(",")
            if email.strip()
        )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
