from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.schemas.rates import RatesResponse
from app.services.rates import get_rates
from app.telegram.notifications import NotificationSink, get_notification_sink

router = APIRouter(prefix="/api/rates", tags=["rates"])


@router.get("", response_model=RatesResponse)
async def rates(
    db: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    notification_sink: Annotated[NotificationSink, Depends(get_notification_sink)],
) -> RatesResponse:
    return await get_rates(db, settings=settings, notification_sink=notification_sink)
