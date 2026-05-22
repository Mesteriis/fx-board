from datetime import timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import AppError, ForbiddenError
from app.core.time import utc_now
from app.db.models import Ad, User
from app.db.transactions import begin_write_transaction
from app.schemas.ads import (
    AdCreateRequest,
    AdDetailResponse,
    AdListItemResponse,
    AdUpdateRequest,
    AuthorResponse,
    MyAdsResponse,
    PaginationResponse,
    payment_method_has_cash,
)

ACTIVE = "ACTIVE"
REVOKED = "REVOKED"
VALID_ACTIVE_STATUSES = {ACTIVE}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


async def create_ad(
    db: AsyncSession,
    *,
    user: User,
    payload: AdCreateRequest,
    settings: Settings,
    rate: Decimal,
) -> Ad:
    await begin_write_transaction(db)
    await ensure_active_ad_limit(db, user_id=user.id, settings=settings)
    now = utc_now()
    expires_at = now + timedelta(hours=settings.ad_default_ttl_hours)
    location = payload.location if payment_method_has_cash(payload.payment_method) else None

    ad = Ad(
        user_id=user.id,
        side="SELL",
        base_currency=payload.base_currency,
        quote_currency=payload.quote_currency,
        amount=payload.amount,
        min_amount=None,
        max_amount=None,
        rate=rate,
        payment_method=payload.payment_method,
        location=location,
        comment=None,
        status=ACTIVE,
        report_count=0,
        expires_at=expires_at,
        created_at=now,
        updated_at=now,
    )
    db.add(ad)
    await db.flush()
    return ad


async def ensure_active_ad_limit(
    db: AsyncSession,
    *,
    user_id: int,
    settings: Settings,
) -> None:
    now = utc_now()
    result = await db.execute(
        select(func.count())
        .select_from(Ad)
        .where(Ad.user_id == user_id, Ad.status == ACTIVE, Ad.expires_at > now)
    )
    active_count = result.scalar_one()
    if active_count >= settings.max_active_ads_per_user:
        raise AppError("active ad limit reached")


async def list_active_ads_by_side(
    db: AsyncSession,
    *,
    limit: int,
    offset: int,
) -> tuple[list[Ad], list[Ad], int]:
    now = utc_now()
    base_query = Ad.status == ACTIVE, Ad.expires_at > now
    total = (
        await db.execute(select(func.count()).select_from(Ad).where(*base_query))
    ).scalar_one()
    sell_result = await db.execute(
        select(Ad)
        .where(*base_query, Ad.side == "SELL")
        .order_by(Ad.created_at.desc(), Ad.id.desc())
        .limit(limit)
        .offset(offset)
    )
    buy_result = await db.execute(
        select(Ad)
        .where(*base_query, Ad.side == "BUY")
        .order_by(Ad.created_at.desc(), Ad.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(sell_result.scalars().all()), list(buy_result.scalars().all()), total


async def list_my_ads(
    db: AsyncSession,
    *,
    user: User,
    limit: int,
    offset: int,
) -> tuple[list[tuple[Ad, User]], int]:
    total = (
        await db.execute(
            select(func.count()).select_from(Ad).where(Ad.user_id == user.id)
        )
    ).scalar_one()
    result = await db.execute(
        select(Ad, User)
        .join(User, User.id == Ad.user_id)
        .where(Ad.user_id == user.id)
        .order_by(Ad.created_at.desc(), Ad.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.all()), total


async def get_visible_ad_detail(
    db: AsyncSession,
    *,
    ad_id: int,
    current_user: User | None,
) -> tuple[Ad, User]:
    result = await db.execute(
        select(Ad, User).join(User, User.id == Ad.user_id).where(Ad.id == ad_id)
    )
    row = result.one_or_none()
    if row is None:
        raise NotFoundError("ad not found")

    ad, author = row
    if ad.status == ACTIVE and ad.expires_at > utc_now():
        return ad, author
    if current_user is not None and ad.user_id == current_user.id:
        return ad, author
    raise NotFoundError("ad not found")


async def get_owned_ad(db: AsyncSession, *, ad_id: int, user: User) -> Ad:
    ad = await db.get(Ad, ad_id)
    if ad is None:
        raise NotFoundError("ad not found")
    if ad.user_id != user.id:
        raise ForbiddenError("ad belongs to another user")
    return ad


async def update_ad(
    db: AsyncSession,
    *,
    ad_id: int,
    user: User,
    payload: AdUpdateRequest,
) -> Ad:
    ad = await get_owned_ad(db, ad_id=ad_id, user=user)
    data = payload.model_dump(exclude_unset=True)
    expires_at = data.get("expires_at", ad.expires_at)
    if expires_at is not None and expires_at <= utc_now():
        raise AppError("expires_at must be in the future")
    payment_method = data.get("payment_method", ad.payment_method)
    location = data.get("location", ad.location)
    if payment_method_has_cash(payment_method) and not location:
        raise AppError("location is required for cash payment method")
    if payment_method is not None and not payment_method_has_cash(payment_method):
        data["location"] = None

    for field_name, value in data.items():
        setattr(ad, field_name, value)
    ad.updated_at = utc_now()
    await db.flush()
    return ad


async def revoke_ad(db: AsyncSession, *, ad_id: int, user: User) -> Ad:
    ad = await get_owned_ad(db, ad_id=ad_id, user=user)
    if ad.status == REVOKED:
        return ad
    if ad.status != ACTIVE:
        raise ForbiddenError("only active ads can be revoked")
    now = utc_now()
    ad.status = REVOKED
    ad.revoked_at = now
    ad.updated_at = now
    await db.flush()
    return ad


def ad_list_item_response(ad: Ad) -> AdListItemResponse:
    return AdListItemResponse(
        id=ad.id,
        side=ad.side,  # type: ignore[arg-type]
        base_currency=ad.base_currency,  # type: ignore[arg-type]
        quote_currency=ad.quote_currency,  # type: ignore[arg-type]
        amount=ad.amount,
        min_amount=ad.min_amount,
        max_amount=ad.max_amount,
        rate=ad.rate,
        payment_method=ad.payment_method,
        location=ad.location,
        comment=ad.comment,
        status=ad.status,  # type: ignore[arg-type]
        expires_at=ad.expires_at,
        created_at=ad.created_at,
        updated_at=ad.updated_at,
    )


def ad_detail_response(ad: Ad, author: User) -> AdDetailResponse:
    return AdDetailResponse(
        **ad_list_item_response(ad).model_dump(),
        author=AuthorResponse(id=author.id, username=author.username),
        revoked_at=ad.revoked_at,
        hidden_at=ad.hidden_at,
        completed_at=ad.completed_at,
    )


def my_ads_response(
    rows: list[tuple[Ad, User]],
    *,
    limit: int,
    offset: int,
    total: int,
) -> MyAdsResponse:
    return MyAdsResponse(
        items=[ad_detail_response(ad, author) for ad, author in rows],
        pagination=PaginationResponse(limit=limit, offset=offset, total=total),
    )


def _validate_update_limits(
    *,
    amount: Decimal,
    min_amount: Decimal | None,
    max_amount: Decimal | None,
) -> None:
    if min_amount is not None and min_amount > amount:
        raise AppError("min_amount cannot exceed amount")
    if max_amount is not None and max_amount > amount:
        raise AppError("max_amount cannot exceed amount")
    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        raise AppError("min_amount cannot exceed max_amount")
