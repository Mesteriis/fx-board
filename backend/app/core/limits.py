from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError
from app.core.time import utc_now
from app.db.models import RateLimitEvent


async def check_rate_limit(
    db: AsyncSession,
    *,
    key: str,
    action: str,
    limit: int,
    window_seconds: int,
) -> None:
    now = utc_now()
    window_start = now - timedelta(seconds=window_seconds)

    await db.execute(delete(RateLimitEvent).where(RateLimitEvent.created_at < window_start))
    count = await db.scalar(
        select(func.count())
        .select_from(RateLimitEvent)
        .where(
            RateLimitEvent.key == key,
            RateLimitEvent.action == action,
            RateLimitEvent.created_at >= window_start,
        )
    )
    if int(count or 0) >= limit:
        raise ForbiddenError("rate limit exceeded")

    db.add(RateLimitEvent(key=key, action=action, created_at=now))
    await db.flush()
