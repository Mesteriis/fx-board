from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import Settings
from app.core.errors import AppError, ForbiddenError
from app.core.time import utc_now
from app.db.models import Ad, ContactAttempt, User
from app.db.transactions import begin_sqlite_immediate
from app.services.ads import ACTIVE, NotFoundError

OPENED = "OPENED"
CANCELED_BY_NEW_CONTACT = "CANCELED_BY_NEW_CONTACT"
ASKED_INITIATOR = "ASKED_INITIATOR"
INITIATOR_NO_DEAL = "INITIATOR_NO_DEAL"
WAITING_AUTHOR_CONFIRMATION = "WAITING_AUTHOR_CONFIRMATION"
COMPLETED_CONFIRMED = "COMPLETED_CONFIRMED"
AUTHOR_REJECTED = "AUTHOR_REJECTED"
COMPLETED = "COMPLETED"

ContactFollowupItem = dict[str, object]
ContactAnswerResult = dict[str, object]


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
            ContactAttempt.status.in_((OPENED, ASKED_INITIATOR)),
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


async def claim_due_contact_attempts(
    db: AsyncSession,
    *,
    limit: int = 25,
) -> list[ContactFollowupItem]:
    if limit < 1:
        raise AppError("limit must be positive")

    await begin_sqlite_immediate(db)
    now = utc_now()
    initiator_user = aliased(User)
    author_user = aliased(User)
    result = await db.execute(
        select(ContactAttempt, initiator_user, author_user, Ad)
        .join(initiator_user, initiator_user.id == ContactAttempt.initiator_user_id)
        .join(author_user, author_user.id == ContactAttempt.author_user_id)
        .join(Ad, Ad.id == ContactAttempt.ad_id)
        .where(
            ContactAttempt.status == OPENED,
            ContactAttempt.followup_due_at <= now,
        )
        .order_by(ContactAttempt.followup_due_at, ContactAttempt.id)
        .limit(limit)
    )

    items: list[ContactFollowupItem] = []
    for attempt, initiator, author, ad in result.all():
        attempt.status = ASKED_INITIATOR
        attempt.updated_at = now
        items.append(_followup_item(attempt=attempt, initiator=initiator, author=author, ad=ad))

    await db.flush()
    return items


async def apply_contact_answer(
    db: AsyncSession,
    *,
    contact_attempt_id: int,
    actor_telegram_id: int,
    answer: str,
) -> ContactAnswerResult:
    normalized_answer = answer.strip().lower()
    if normalized_answer not in {"yes", "no"}:
        raise AppError("invalid contact answer")

    await begin_sqlite_immediate(db)
    row = await _get_contact_attempt_detail(db, contact_attempt_id=contact_attempt_id)
    if row is None:
        raise NotFoundError("contact attempt not found")

    attempt, initiator, author, ad = row
    now = utc_now()

    if attempt.status in {OPENED, ASKED_INITIATOR}:
        if actor_telegram_id != initiator.telegram_id:
            raise ForbiddenError("actor cannot answer this contact attempt")
        if normalized_answer == "no":
            attempt.status = INITIATOR_NO_DEAL
            attempt.initiator_answered_at = now
            attempt.updated_at = now
            await db.flush()
            return _answer_result(attempt=attempt, action="none")
        if attempt.status != ASKED_INITIATOR:
            raise AppError("contact attempt cannot be answered in its current state")

        attempt.status = WAITING_AUTHOR_CONFIRMATION
        attempt.initiator_answered_at = now
        attempt.updated_at = now
        await db.flush()
        return {
            **_answer_result(attempt=attempt, action="ask_author"),
            **_followup_item(attempt=attempt, initiator=initiator, author=author, ad=ad),
        }

    if attempt.status == WAITING_AUTHOR_CONFIRMATION:
        if actor_telegram_id != author.telegram_id:
            raise ForbiddenError("actor cannot answer this contact attempt")

        attempt.author_answered_at = now
        attempt.updated_at = now
        if normalized_answer == "yes":
            attempt.status = COMPLETED_CONFIRMED
            ad.status = COMPLETED
            ad.completed_at = now
            ad.updated_at = now
            await db.flush()
            return _answer_result(attempt=attempt, action="completed", ad_id=ad.id)

        attempt.status = AUTHOR_REJECTED
        await db.flush()
        return _answer_result(attempt=attempt, action="none", ad_id=ad.id)

    raise AppError("contact attempt cannot be answered in its current state")


async def _get_contact_attempt_detail(
    db: AsyncSession,
    *,
    contact_attempt_id: int,
) -> tuple[ContactAttempt, User, User, Ad] | None:
    initiator_user = aliased(User)
    author_user = aliased(User)
    result = await db.execute(
        select(ContactAttempt, initiator_user, author_user, Ad)
        .join(initiator_user, initiator_user.id == ContactAttempt.initiator_user_id)
        .join(author_user, author_user.id == ContactAttempt.author_user_id)
        .join(Ad, Ad.id == ContactAttempt.ad_id)
        .where(ContactAttempt.id == contact_attempt_id)
    )
    return result.one_or_none()


def _followup_item(
    *,
    attempt: ContactAttempt,
    initiator: User,
    author: User,
    ad: Ad,
) -> ContactFollowupItem:
    amount = str(ad.amount)
    pair = f"{ad.base_currency}/{ad.quote_currency}"
    summary = f"{ad.side} {amount} {pair}"
    return {
        "contact_attempt_id": attempt.id,
        "initiator_telegram_id": initiator.telegram_id,
        "author_telegram_id": author.telegram_id,
        "ad_id": ad.id,
        "side": ad.side,
        "pair": pair,
        "amount": amount,
        "summary": summary,
    }


def _answer_result(
    *,
    attempt: ContactAttempt,
    action: str,
    ad_id: int | None = None,
) -> ContactAnswerResult:
    result: ContactAnswerResult = {
        "contact_attempt_id": attempt.id,
        "status": attempt.status,
        "action": action,
    }
    if ad_id is not None:
        result["ad_id"] = ad_id
    return result
