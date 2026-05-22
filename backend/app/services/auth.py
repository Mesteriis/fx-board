import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated
from urllib.parse import parse_qsl

from fastapi import Cookie, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import verify_double_submit_csrf
from app.core.time import utc_now
from app.db.models import User
from app.db.session import get_session
from app.schemas.auth import UserResponse
from app.services.sessions import get_valid_session


class InitDataError(ValueError):
    pass


@dataclass(frozen=True)
class TelegramUserPayload:
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    language_code: str | None
    photo_url: str | None


def verify_telegram_init_data(
    *,
    init_data: str,
    bot_token: str,
    now: datetime,
    max_age_seconds: int,
) -> TelegramUserPayload:
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError as exc:
        raise InitDataError("invalid init data") from exc

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise InitDataError("missing hash")

    auth_date_raw = pairs.get("auth_date")
    if not auth_date_raw:
        raise InitDataError("missing auth_date")

    try:
        auth_timestamp = int(auth_date_raw)
    except ValueError as exc:
        raise InitDataError("invalid auth_date") from exc

    age_seconds = int(now.timestamp()) - auth_timestamp
    if age_seconds < 0 or age_seconds > max_age_seconds:
        raise InitDataError("expired auth_date")

    data_check_string = "\n".join(f"{key}={pairs[key]}" for key in sorted(pairs))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise InitDataError("invalid hash")

    try:
        user_data = json.loads(pairs["user"])
    except (KeyError, json.JSONDecodeError) as exc:
        raise InitDataError("invalid user") from exc

    telegram_id = user_data.get("id")
    if not isinstance(telegram_id, int):
        raise InitDataError("invalid user id")

    return TelegramUserPayload(
        telegram_id=telegram_id,
        username=_optional_str(user_data.get("username")),
        first_name=_optional_str(user_data.get("first_name")),
        last_name=_optional_str(user_data.get("last_name")),
        language_code=_optional_str(user_data.get("language_code")),
        photo_url=_optional_str(user_data.get("photo_url")),
    )


async def upsert_telegram_user(
    db: AsyncSession,
    *,
    telegram_user: TelegramUserPayload,
    admin_ids: set[int],
) -> User:
    now = utc_now()
    result = await db.execute(select(User).where(User.telegram_id == telegram_user.telegram_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            telegram_id=telegram_user.telegram_id,
            username=telegram_user.username,
            first_name=telegram_user.first_name,
            last_name=telegram_user.last_name,
            language_code=telegram_user.language_code,
            photo_url=telegram_user.photo_url,
            is_admin=telegram_user.telegram_id in admin_ids,
            is_banned=False,
            first_seen_at=now,
            last_seen_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(user)
    else:
        user.username = telegram_user.username
        user.first_name = telegram_user.first_name
        user.last_name = telegram_user.last_name
        user.language_code = telegram_user.language_code
        user.photo_url = telegram_user.photo_url
        user.is_admin = telegram_user.telegram_id in admin_ids
        user.last_seen_at = now
        user.updated_at = now

    await db.flush()
    return user


def to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        telegram_id=user.telegram_id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        is_admin=user.is_admin,
        is_banned=user.is_banned,
    )


async def require_current_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    session_id = request.cookies.get(settings.session_cookie_name)
    db_session = await get_valid_session(db, session_id=session_id)
    if db_session is None:
        raise UnauthorizedError("authentication required")

    user = await db.get(User, db_session.user_id)
    if user is None:
        raise UnauthorizedError("authentication required")
    if user.is_banned:
        raise ForbiddenError("user is banned")
    return user


def require_csrf(
    csrf_cookie: str | None = Cookie(default=None, alias="csrf_token"),
    csrf_header: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> None:
    verify_double_submit_csrf(csrf_cookie=csrf_cookie, csrf_header=csrf_header)


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None
