import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError
from app.core.limits import check_rate_limit
from app.db.models import User
from app.db.session import get_session
from app.routers.auth import get_telegram_client
from app.schemas.reports import ReportCreateRequest, ReportResponse
from app.services import reports as reports_service
from app.services.access import TelegramMembershipClient, ensure_required_channels
from app.services.auth import require_csrf, require_current_user
from app.telegram.client import TelegramApiError

router = APIRouter(prefix="/api/reports", tags=["reports"])
logger = logging.getLogger(__name__)


async def require_report_user(
    _csrf: Annotated[None, Depends(require_csrf)],
    db: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_current_user)],
    telegram_client: Annotated[TelegramMembershipClient, Depends(get_telegram_client)],
) -> User:
    try:
        access = await ensure_required_channels(
            db,
            user=user,
            settings=settings,
            telegram_client=telegram_client,
        )
    except TelegramApiError as exc:
        logger.warning("Telegram membership check failed", exc_info=True)
        raise ForbiddenError("could not verify required channel access") from exc
    await db.commit()
    if not access.allowed:
        raise ForbiddenError("required channel membership missing")
    return user


@router.post("", response_model=ReportResponse)
async def create_report(
    payload: ReportCreateRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_report_user)],
) -> ReportResponse:
    await check_rate_limit(
        db,
        key=f"user:{user.id}",
        action="reports.create",
        limit=10,
        window_seconds=86400,
    )
    await db.commit()
    report = await reports_service.create_report(
        db,
        reporter_user_id=user.id,
        payload=payload,
        auto_hide_threshold=settings.reports_to_auto_hide,
    )
    await db.commit()
    return reports_service.report_response(report)
