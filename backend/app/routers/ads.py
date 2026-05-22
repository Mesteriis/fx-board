import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError
from app.core.limits import check_rate_limit
from app.db.models import User
from app.db.session import get_session
from app.routers.auth import get_telegram_client
from app.schemas.ads import (
    AdCreateRequest,
    AdDetailResponse,
    AdsBySideResponse,
    AdUpdateRequest,
    ContactAttemptResponse,
    MyAdsResponse,
    PaginationResponse,
)
from app.services import ads as ads_service
from app.services import contacts as contacts_service
from app.services import rates as rates_service
from app.services.access import TelegramMembershipClient, ensure_required_channels
from app.services.auth import require_csrf, require_current_user
from app.services.sessions import get_valid_session
from app.telegram.client import TelegramApiError, TelegramBotApiClient

router = APIRouter(prefix="/api/ads", tags=["ads"])
logger = logging.getLogger(__name__)


async def require_channel_access(
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
    if not access.allowed:
        raise ForbiddenError("required channel membership missing")
    return user


async def require_mutating_user(
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


async def optional_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User | None:
    session_id = request.cookies.get(settings.session_cookie_name)
    db_session = await get_valid_session(db, session_id=session_id)
    if db_session is None:
        return None
    user = await db.get(User, db_session.user_id)
    if user is None or user.is_banned:
        return None
    return user


@router.post("", response_model=AdDetailResponse, status_code=201)
async def create_ad(
    payload: AdCreateRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_mutating_user)],
) -> AdDetailResponse:
    await check_rate_limit(
        db,
        key=f"user:{user.id}",
        action="ads.create",
        limit=5,
        window_seconds=3600,
    )
    await db.commit()
    rate = await rates_service.get_pair_rate(
        db,
        settings=settings,
        base_currency=payload.base_currency,
        quote_currency=payload.quote_currency,
    )
    await db.commit()
    ad = await ads_service.create_ad(
        db,
        user=user,
        payload=payload,
        settings=settings,
        rate=rate,
    )
    await db.commit()
    return ads_service.ad_detail_response(ad, user)


@router.get("", response_model=AdsBySideResponse)
async def list_ads(
    db: Annotated[AsyncSession, Depends(get_session)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AdsBySideResponse:
    sell_ads, buy_ads, total = await ads_service.list_active_ads_by_side(
        db,
        limit=limit,
        offset=offset,
    )
    return AdsBySideResponse(
        sell=[ads_service.ad_list_item_response(ad) for ad in sell_ads],
        buy=[ads_service.ad_list_item_response(ad) for ad in buy_ads],
        pagination=PaginationResponse(limit=limit, offset=offset, total=total),
    )


@router.get("/my", response_model=MyAdsResponse)
async def list_my_ads(
    db: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(require_current_user)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MyAdsResponse:
    rows, total = await ads_service.list_my_ads(db, user=user, limit=limit, offset=offset)
    return ads_service.my_ads_response(rows, limit=limit, offset=offset, total=total)


@router.get("/{ad_id}", response_model=AdDetailResponse)
async def get_ad(
    ad_id: int,
    db: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User | None, Depends(optional_current_user)],
) -> AdDetailResponse:
    ad, author = await ads_service.get_visible_ad_detail(
        db,
        ad_id=ad_id,
        current_user=current_user,
    )
    return ads_service.ad_detail_response(ad, author)


@router.patch("/{ad_id}", response_model=AdDetailResponse)
async def update_ad(
    ad_id: int,
    payload: AdUpdateRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(require_mutating_user)],
) -> AdDetailResponse:
    await check_rate_limit(
        db,
        key=f"user:{user.id}",
        action="ads.update",
        limit=30,
        window_seconds=3600,
    )
    await db.commit()
    ad = await ads_service.update_ad(db, ad_id=ad_id, user=user, payload=payload)
    await db.commit()
    return ads_service.ad_detail_response(ad, user)


@router.post("/{ad_id}/revoke", response_model=AdDetailResponse)
async def revoke_ad(
    ad_id: int,
    db: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(require_mutating_user)],
) -> AdDetailResponse:
    ad = await ads_service.revoke_ad(db, ad_id=ad_id, user=user)
    await db.commit()
    return ads_service.ad_detail_response(ad, user)


@router.post("/{ad_id}/contact", response_model=ContactAttemptResponse, status_code=201)
async def contact_ad(
    ad_id: int,
    db: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_mutating_user)],
    telegram_client: Annotated[TelegramBotApiClient, Depends(get_telegram_client)],
) -> ContactAttemptResponse:
    await check_rate_limit(
        db,
        key=f"user:{user.id}",
        action="ads.contact",
        limit=20,
        window_seconds=3600,
    )
    await db.commit()
    contact_attempt = await contacts_service.create_contact_attempt(
        db,
        ad_id=ad_id,
        initiator=user,
        settings=settings,
        telegram_client=telegram_client,
    )
    await db.commit()
    return ContactAttemptResponse(
        contact_attempt_id=contact_attempt.id,
        message="Сообщение отправлено продавцу",
    )
