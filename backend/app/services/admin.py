import json
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError
from app.core.time import utc_now
from app.db.models import Ad, AuditLog, Report, User
from app.schemas.admin import (
    AdminAdResponse,
    AdminAuditLogItemResponse,
    AdminAuditLogResponse,
    AdminBanUserRequest,
    AdminDashboardResponse,
    AdminUserResponse,
)
from app.schemas.ads import PaginationResponse
from app.services.ads import ACTIVE, NotFoundError, ad_detail_response
from app.services.audit import write_audit


async def get_dashboard(db: AsyncSession) -> AdminDashboardResponse:
    users_total = await _count(db, select(func.count()).select_from(User))
    users_banned = await _count(
        db,
        select(func.count()).select_from(User).where(User.is_banned.is_(True)),
    )
    ads_active = await _count(
        db,
        select(func.count()).select_from(Ad).where(Ad.status == ACTIVE),
    )
    ads_hidden = await _count(
        db,
        select(func.count()).select_from(Ad).where(Ad.status == "HIDDEN"),
    )
    reports_new = await _count(
        db,
        select(func.count()).select_from(Report).where(Report.status == "NEW"),
    )
    return AdminDashboardResponse(
        users_total=users_total,
        users_banned=users_banned,
        ads_active=ads_active,
        ads_hidden=ads_hidden,
        reports_new=reports_new,
    )


async def ban_user(
    db: AsyncSession,
    *,
    user_id: int,
    payload: AdminBanUserRequest,
    actor: User,
) -> AdminUserResponse:
    if actor.id == user_id:
        raise ForbiddenError("cannot ban yourself")
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("user not found")

    now = utc_now()
    user.is_banned = True
    user.banned_reason = payload.reason
    user.updated_at = now
    await write_audit(
        db,
        actor_user_id=actor.id,
        action="ban_user",
        entity_type="user",
        entity_id=user.id,
        payload={"reason": payload.reason},
    )
    await db.flush()
    return admin_user_response(user)


async def unban_user(
    db: AsyncSession,
    *,
    user_id: int,
    actor: User,
) -> AdminUserResponse:
    user = await db.get(User, user_id)
    if user is None:
        raise NotFoundError("user not found")

    user.is_banned = False
    user.banned_reason = None
    user.updated_at = utc_now()
    await write_audit(
        db,
        actor_user_id=actor.id,
        action="unban_user",
        entity_type="user",
        entity_id=user.id,
        payload={},
    )
    await db.flush()
    return admin_user_response(user)


async def hide_ad(
    db: AsyncSession,
    *,
    ad_id: int,
    actor: User,
) -> AdminAdResponse:
    ad, author = await _get_ad_and_author(db, ad_id=ad_id)
    if ad.status == "HIDDEN":
        await write_audit(
            db,
            actor_user_id=actor.id,
            action="hide_ad",
            entity_type="ad",
            entity_id=ad.id,
            payload={"old_status": "HIDDEN", "new_status": "HIDDEN"},
        )
        await db.flush()
        return ad_detail_response(ad, author)
    if ad.status != ACTIVE:
        raise ForbiddenError("only active ads can be hidden")

    now = utc_now()
    ad.status = "HIDDEN"
    ad.hidden_at = now
    ad.updated_at = now
    await write_audit(
        db,
        actor_user_id=actor.id,
        action="hide_ad",
        entity_type="ad",
        entity_id=ad.id,
        payload={"old_status": ACTIVE, "new_status": "HIDDEN"},
    )
    await db.flush()
    return ad_detail_response(ad, author)


async def restore_ad(
    db: AsyncSession,
    *,
    ad_id: int,
    actor: User,
) -> AdminAdResponse:
    ad, author = await _get_ad_and_author(db, ad_id=ad_id)
    if ad.status != "HIDDEN":
        raise ForbiddenError("only hidden ads can be restored")

    ad.status = ACTIVE
    ad.hidden_at = None
    ad.updated_at = utc_now()
    await write_audit(
        db,
        actor_user_id=actor.id,
        action="restore_ad",
        entity_type="ad",
        entity_id=ad.id,
        payload={"old_status": "HIDDEN", "new_status": ACTIVE},
    )
    await db.flush()
    return ad_detail_response(ad, author)


async def list_audit_log(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> AdminAuditLogResponse:
    total = (await db.execute(select(func.count()).select_from(AuditLog))).scalar_one()
    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return AdminAuditLogResponse(
        items=[audit_log_response(entry) for entry in result.scalars().all()],
        pagination=PaginationResponse(limit=limit, offset=offset, total=total),
    )


def admin_user_response(user: User) -> AdminUserResponse:
    return AdminUserResponse(
        id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
        is_admin=user.is_admin,
        is_banned=user.is_banned,
        banned_reason=user.banned_reason,
    )


def audit_log_response(entry: AuditLog) -> AdminAuditLogItemResponse:
    return AdminAuditLogItemResponse(
        id=entry.id,
        actor_user_id=entry.actor_user_id,
        action=entry.action,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        payload=_payload_dict(entry.payload_json),
        ip_hash=entry.ip_hash,
        created_at=entry.created_at,
    )


async def _get_ad_and_author(db: AsyncSession, *, ad_id: int) -> tuple[Ad, User]:
    result = await db.execute(
        select(Ad, User).join(User, User.id == Ad.user_id).where(Ad.id == ad_id)
    )
    row = result.one_or_none()
    if row is None:
        raise NotFoundError("ad not found")
    return row


async def _count(db: AsyncSession, statement) -> int:
    return int((await db.execute(statement)).scalar_one())


def _payload_dict(payload_json: str | None) -> dict[str, object] | None:
    if payload_json is None:
        return None
    payload = json.loads(payload_json)
    if not isinstance(payload, dict):
        return None
    return cast(dict[str, object], payload)
