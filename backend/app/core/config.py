from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_base_url: str = "http://localhost:3000"
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    session_secret: SecretStr = Field(min_length=32)
    session_cookie_name: str = "session"
    session_ttl_seconds: int = 604800

    telegram_bot_token: SecretStr
    telegram_bot_username: str
    telegram_webhook_secret: SecretStr
    telegram_required_channels: str = ""
    admin_telegram_ids: str = ""

    google_rates_csv_url: str = ""
    rates_refresh_timezone: str = "Europe/Madrid"

    max_init_data_age_seconds: int = 86400
    max_active_ads_per_user: int = 10
    ad_default_ttl_hours: int = 24
    reports_to_auto_hide: int = 3
    deal_followup_delay_hours: int = 2

    @property
    def required_channels(self) -> list[str]:
        return [
            value.strip()
            for value in self.telegram_required_channels.split(",")
            if value.strip()
        ]

    @property
    def admin_ids(self) -> set[int]:
        ids: set[int] = set()
        for raw in self.admin_telegram_ids.split(","):
            value = raw.strip()
            if value:
                ids.add(int(value))
        return ids


@lru_cache
def get_settings() -> Settings:
    return Settings()
