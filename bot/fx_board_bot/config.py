from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: SecretStr
    app_base_url: str = "http://localhost:3000"
    backend_base_url: str = "http://localhost:8000"
    admin_telegram_ids: str = ""

    @property
    def admin_ids(self) -> set[int]:
        return {int(raw.strip()) for raw in self.admin_telegram_ids.split(",") if raw.strip()}


@lru_cache
def get_bot_settings() -> BotSettings:
    return BotSettings()
