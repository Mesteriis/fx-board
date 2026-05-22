import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import hash_ip, sign_csrf_token, verified_csrf_cookie_token
from app.core.time import utc_now
from app.db.models import Session as DbSession
from app.db.models import User
from app.db.session import get_session
from app.schemas.auth import AccessResponse, AuthResponse, TelegramWebAppAuthRequest
from app.services.access import TelegramMembershipClient, ensure_required_channels
from app.services.auth import (
    InitDataError,
    require_csrf,
    require_current_session,
    require_current_user,
    to_user_response,
    upsert_telegram_user,
    verify_telegram_init_data,
)
from app.services.sessions import create_session, delete_session
from app.telegram.client import TelegramApiError, TelegramBotApiClient

router = APIRouter(prefix="/api/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def get_telegram_client(
    settings: Annotated[Settings, Depends(get_settings)],
) -> TelegramBotApiClient:
    return TelegramBotApiClient(token=settings.telegram_bot_token.get_secret_value())


@router.post("/telegram-webapp", response_model=AuthResponse)
async def telegram_webapp_auth(
    payload: TelegramWebAppAuthRequest,
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    telegram_client: Annotated[TelegramMembershipClient, Depends(get_telegram_client)],
) -> AuthResponse:
    try:
        telegram_user = verify_telegram_init_data(
            init_data=payload.init_data,
            bot_token=settings.telegram_bot_token.get_secret_value(),
            now=utc_now(),
            max_age_seconds=settings.max_init_data_age_seconds,
        )
    except InitDataError as exc:
        raise UnauthorizedError("invalid telegram init data") from exc

    user = await upsert_telegram_user(db, telegram_user=telegram_user, admin_ids=settings.admin_ids)
    if user.is_banned:
        raise ForbiddenError("user is banned")

    access = await _ensure_access(db, user=user, settings=settings, telegram_client=telegram_client)
    if not access.allowed:
        raise ForbiddenError("required channel membership missing")

    session_id, raw_csrf_token = await create_session(
        db,
        user_id=user.id,
        ttl_seconds=settings.session_ttl_seconds,
        user_agent=request.headers.get("user-agent"),
        ip_hash=hash_ip(
            request.client.host if request.client else None,
            settings.session_secret.get_secret_value(),
        ),
    )
    await db.commit()

    signed_csrf_token = sign_csrf_token(
        session_id=session_id,
        raw_token=raw_csrf_token,
        secret=settings.session_secret.get_secret_value(),
    )
    _set_auth_cookies(
        response,
        settings=settings,
        session_id=session_id,
        csrf_token=signed_csrf_token,
    )
    return AuthResponse(user=to_user_response(user), access=access, csrf_token=raw_csrf_token)


@router.get("/me", response_model=AuthResponse)
async def me(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    user: Annotated[User, Depends(require_current_user)],
    telegram_client: Annotated[TelegramMembershipClient, Depends(get_telegram_client)],
) -> AuthResponse:
    access = await _ensure_access(db, user=user, settings=settings, telegram_client=telegram_client)
    await db.commit()
    session_id = request.cookies.get(settings.session_cookie_name)
    csrf_token = (
        verified_csrf_cookie_token(
            session_id=session_id,
            signed_token=request.cookies.get("csrf_token"),
            secret=settings.session_secret.get_secret_value(),
        )
        if session_id
        else ""
    )
    return AuthResponse(user=to_user_response(user), access=access, csrf_token=csrf_token)


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[DbSession, Depends(require_current_session)],
    _csrf: Annotated[None, Depends(require_csrf)],
) -> dict[str, bool]:
    await delete_session(db, session_id=session.id)
    await db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")
    response.delete_cookie("csrf_token", path="/")
    return {"ok": True}


def _set_auth_cookies(
    response: Response,
    *,
    settings: Settings,
    session_id: str,
    csrf_token: str,
) -> None:
    secure = settings.app_env == "production"
    response.set_cookie(
        settings.session_cookie_name,
        session_id,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_seconds,
    )
    response.set_cookie(
        "csrf_token",
        csrf_token,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_seconds,
    )


async def _ensure_access(
    db: AsyncSession,
    *,
    user: User,
    settings: Settings,
    telegram_client: TelegramMembershipClient,
) -> AccessResponse:
    try:
        return await ensure_required_channels(
            db,
            user=user,
            settings=settings,
            telegram_client=telegram_client,
        )
    except TelegramApiError as exc:
        logger.warning("Telegram membership check failed", exc_info=True)
        raise ForbiddenError("could not verify required channel access") from exc
