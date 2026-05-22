import json
from datetime import timedelta
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.time import utc_now
from app.db.models import RequiredChannel, User, UserChannelMembership
from app.schemas.auth import AccessResponse, RequiredChannelResponse
from app.telegram.client import ChatMemberResult

MEMBERSHIP_CACHE_TTL_SECONDS = 600
MEMBER_STATUSES = {"creator", "administrator", "member"}


class TelegramMembershipClient(Protocol):
    async def get_chat_member(self, *, chat_id: str, user_id: int) -> ChatMemberResult:
        raise NotImplementedError


async def ensure_required_channels(
    db: AsyncSession,
    *,
    user: User,
    settings: Settings,
    telegram_client: TelegramMembershipClient,
) -> AccessResponse:
    if user.is_banned:
        return AccessResponse(allowed=False)

    channels = await _get_required_channels(db, settings=settings)
    if not channels:
        return AccessResponse(allowed=True)

    required: list[RequiredChannelResponse] = []
    missing: list[RequiredChannelResponse] = []

    for channel in channels:
        membership = await _get_or_refresh_membership(
            db,
            user=user,
            channel=channel,
            telegram_client=telegram_client,
        )
        item = RequiredChannelResponse(
            chat_id=channel.chat_id,
            title=channel.title,
            is_member=membership.is_member,
        )
        required.append(item)
        if not membership.is_member:
            missing.append(item)

    return AccessResponse(
        allowed=not missing,
        required_channels=required,
        missing_channels=missing,
    )


async def _get_required_channels(
    db: AsyncSession,
    *,
    settings: Settings,
) -> list[RequiredChannel]:
    await _sync_required_channels(db, settings.required_channels)
    result = await db.execute(
        select(RequiredChannel)
        .where(RequiredChannel.is_active.is_(True))
        .order_by(RequiredChannel.id)
    )
    return list(result.scalars().all())


async def _sync_required_channels(db: AsyncSession, chat_ids: list[str]) -> None:
    configured_chat_ids = list(dict.fromkeys(chat_ids))
    configured = set(configured_chat_ids)
    result = await db.execute(select(RequiredChannel))
    existing = {channel.chat_id: channel for channel in result.scalars().all()}
    now = utc_now()

    for chat_id, channel in existing.items():
        should_be_active = chat_id in configured
        if channel.is_active != should_be_active:
            channel.is_active = should_be_active
            channel.updated_at = now

    for chat_id in configured_chat_ids:
        if chat_id in existing:
            continue
        db.add(
            RequiredChannel(
                chat_id=chat_id,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )

    await db.flush()


async def _get_or_refresh_membership(
    db: AsyncSession,
    *,
    user: User,
    channel: RequiredChannel,
    telegram_client: TelegramMembershipClient,
) -> UserChannelMembership:
    now = utc_now()
    result = await db.execute(
        select(UserChannelMembership).where(
            UserChannelMembership.user_id == user.id,
            UserChannelMembership.channel_id == channel.id,
        )
    )
    membership = result.scalar_one_or_none()
    if membership is not None and membership.expires_at > now:
        return membership

    telegram_result = await telegram_client.get_chat_member(
        chat_id=channel.chat_id,
        user_id=user.telegram_id,
    )
    is_member = telegram_result.status in MEMBER_STATUSES
    expires_at = now + timedelta(seconds=MEMBERSHIP_CACHE_TTL_SECONDS)
    raw_response_json = json.dumps(telegram_result.raw, separators=(",", ":"), sort_keys=True)

    if membership is None:
        membership = UserChannelMembership(
            user_id=user.id,
            channel_id=channel.id,
            telegram_status=telegram_result.status,
            is_member=is_member,
            checked_at=now,
            expires_at=expires_at,
            raw_response_json=raw_response_json,
        )
        db.add(membership)
    else:
        membership.telegram_status = telegram_result.status
        membership.is_member = is_member
        membership.checked_at = now
        membership.expires_at = expires_at
        membership.raw_response_json = raw_response_json

    await db.flush()
    return membership
