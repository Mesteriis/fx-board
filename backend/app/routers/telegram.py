from secrets import compare_digest
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError
from app.db.session import get_session
from app.services.contacts import (
    apply_contact_answer,
    claim_due_contact_attempts,
    mark_contact_followup_prompt_sent,
)

telegram_router = APIRouter(prefix="/api/telegram", tags=["telegram"])
internal_router = APIRouter(prefix="/api/internal", tags=["internal"])


class ContactFollowupAnswerRequest(BaseModel):
    actor_telegram_id: int
    answer: Literal["yes", "no"]


class ContactFollowupPromptSentRequest(BaseModel):
    prompt_type: Literal["initiator", "author"]


@telegram_router.post("/webhook")
async def telegram_webhook(
    _update: dict[str, object],
    settings: Annotated[Settings, Depends(get_settings)],
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
) -> dict[str, bool]:
    expected = settings.telegram_webhook_secret.get_secret_value()
    if x_telegram_bot_api_secret_token is None or not compare_digest(
        x_telegram_bot_api_secret_token,
        expected,
    ):
        raise ForbiddenError("invalid telegram webhook secret")
    return {"ok": True}


@internal_router.post("/contact-followups/claim")
async def claim_contact_followups(
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_session)],
    x_internal_bot_secret: Annotated[str | None, Header()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> dict[str, object]:
    _require_internal_bot_secret(
        provided=x_internal_bot_secret,
        settings=settings,
    )
    items = await claim_due_contact_attempts(db, limit=limit)
    await db.commit()
    return {"items": items}


@internal_router.post("/contact-followups/{contact_attempt_id}/prompt-sent")
async def contact_followup_prompt_sent(
    contact_attempt_id: int,
    payload: ContactFollowupPromptSentRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_session)],
    x_internal_bot_secret: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _require_internal_bot_secret(
        provided=x_internal_bot_secret,
        settings=settings,
    )
    result = await mark_contact_followup_prompt_sent(
        db,
        contact_attempt_id=contact_attempt_id,
        prompt_type=payload.prompt_type,
    )
    await db.commit()
    return result


@internal_router.post("/contact-followups/{contact_attempt_id}/answer")
async def answer_contact_followup(
    contact_attempt_id: int,
    payload: ContactFollowupAnswerRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_session)],
    x_internal_bot_secret: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    _require_internal_bot_secret(
        provided=x_internal_bot_secret,
        settings=settings,
    )
    result = await apply_contact_answer(
        db,
        contact_attempt_id=contact_attempt_id,
        actor_telegram_id=payload.actor_telegram_id,
        answer=payload.answer,
    )
    await db.commit()
    return result


def _require_internal_bot_secret(
    *,
    provided: str | None,
    settings: Settings,
) -> None:
    expected = settings.telegram_internal_bot_secret.get_secret_value()
    if provided is None or not compare_digest(provided, expected):
        raise ForbiddenError("invalid internal bot secret")


router = APIRouter()
router.include_router(telegram_router)
router.include_router(internal_router)
