from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_base_url: str = "http://localhost:3000"
    database_url: str = "postgresql+asyncpg://fx_board:fx_board@localhost:15432/fx_board"

    session_secret: SecretStr = Field(min_length=32)
    session_cookie_name: str = "session"
    session_ttl_seconds: int = 604800

    telegram_bot_token: SecretStr
    telegram_bot_username: str
    telegram_webhook_secret: SecretStr
    telegram_internal_bot_secret: SecretStr = Field(min_length=32)
    telegram_required_channels_enabled: bool = False
    telegram_required_channels: str = ""
    admin_telegram_ids: str = ""

    rates_provider: str = "cbr"
    cbr_rates_xml_url: str = "https://www.cbr.ru/scripts/XML_daily.asp"
    binance_ar_usdt_ticker_url: str = (
        "https://api.binance.com/api/v3/ticker/price?symbol=ARUSDT"
    )
    google_rates_csv_url: str = ""
    rates_refresh_timezone: str = "Europe/Madrid"

    max_init_data_age_seconds: int = 86400
    max_active_ads_per_user: int = 10
    ad_default_ttl_hours: int = 24
    reports_to_auto_hide: int = 3
    deal_followup_delay_hours: int = 2

    dev_auth_enabled: bool = False
    dev_auth_token: SecretStr | None = None
    dev_auth_allow_production: bool = False

    @property
    def dev_auth_available(self) -> bool:
        return self.dev_auth_enabled and (
            self.app_env != "production" or self.dev_auth_allow_production
        )

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
