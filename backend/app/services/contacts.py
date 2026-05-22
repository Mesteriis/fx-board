from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ForbiddenError
from app.core.time import utc_now
from app.db.models import Ad, ContactAttempt, User
from app.db.transactions import begin_sqlite_immediate
from app.services.ads import ACTIVE, NotFoundError

OPENED = "OPENED"
CANCELED_BY_NEW_CONTACT = "CANCELED_BY_NEW_CONTACT"


async def create_contact_attempt(
    db: AsyncSession,
    *,
    ad_id: int,
    initiator: User,
    settings: Settings,
) -> tuple[ContactAttempt, str]:
    await begin_sqlite_immediate(db)
    result = await db.execute(
        select(Ad, User).join(User, User.id == Ad.user_id).where(Ad.id == ad_id)
    )
    row = result.one_or_none()
    if row is None:
        raise NotFoundError("ad not found")

    ad, author = row
    if ad.status != ACTIVE or ad.expires_at <= utc_now():
        raise NotFoundError("ad not found")
    if ad.user_id == initiator.id:
        raise ForbiddenError("cannot contact your own ad")
    if not author.username:
        raise ForbiddenError("contact unavailable")

    now = utc_now()
    open_attempts = await db.execute(
        select(ContactAttempt).where(
            ContactAttempt.initiator_user_id == initiator.id,
            ContactAttempt.status == OPENED,
        )
    )
    for attempt in open_attempts.scalars():
        attempt.status = CANCELED_BY_NEW_CONTACT
        attempt.updated_at = now

    contact_attempt = ContactAttempt(
        initiator_user_id=initiator.id,
        author_user_id=author.id,
        ad_id=ad.id,
        status=OPENED,
        followup_due_at=now + timedelta(hours=settings.deal_followup_delay_hours),
        created_at=now,
        updated_at=now,
    )
    db.add(contact_attempt)
    await db.flush()
    return contact_attempt, f"https://t.me/{author.username}"
