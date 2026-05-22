from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import new_csrf_token, new_session_id
from app.core.time import utc_now
from app.db.models import Session as DbSession


async def create_session(
    db: AsyncSession,
    *,
    user_id: int,
    ttl_seconds: int,
    user_agent: str | None,
    ip_hash: str | None,
) -> tuple[str, str]:
    now = utc_now()
    session_id = new_session_id()
    csrf_token = new_csrf_token()
    db.add(
        DbSession(
            id=session_id,
            user_id=user_id,
            expires_at=now + timedelta(seconds=ttl_seconds),
            created_at=now,
            last_used_at=now,
            user_agent=user_agent,
            ip_hash=ip_hash,
        )
    )
    await db.flush()
    return session_id, csrf_token


async def get_valid_session(db: AsyncSession, *, session_id: str | None) -> DbSession | None:
    if not session_id:
        return None

    now = utc_now()
    result = await db.execute(
        select(DbSession).where(DbSession.id == session_id, DbSession.expires_at > now)
    )
    session = result.scalar_one_or_none()
    if session is None:
        return None

    session.last_used_at = now
    await db.flush()
    return session


async def delete_session(db: AsyncSession, *, session_id: str | None) -> None:
    if not session_id:
        return
    await db.execute(delete(DbSession).where(DbSession.id == session_id))
