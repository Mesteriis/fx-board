from secrets import compare_digest
from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook")
async def telegram_webhook(
    _update: dict[str, object],
    settings: Annotated[Settings, Depends(get_settings)],
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
) -> dict[str, bool]:
    expected = settings.telegram_webhook_secret.get_secret_value()
    if x_telegram_bot_api_secret_token is None or not compare_digest(
        x_telegram_bot_api_secret_token,
        expected,
    ):
        raise ForbiddenError("invalid telegram webhook secret")
    return {"ok": True}
