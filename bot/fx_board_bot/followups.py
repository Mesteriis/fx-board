import asyncio
import logging
from collections.abc import Mapping, Sequence
from typing import Protocol

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .callbacks import encode_deal_callback

logger = logging.getLogger(__name__)


class MessageSender(Protocol):
    async def send_message(
        self,
        *,
        chat_id: int,
        text: str,
        reply_markup: InlineKeyboardMarkup,
    ) -> object: ...


class FollowupClaimClient(Protocol):
    async def claim_due_followups(self, *, limit: int = 25) -> list[dict[str, object]]: ...


FollowupItem = Mapping[str, object]


def build_deal_keyboard(*, contact_attempt_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да",
                    callback_data=encode_deal_callback(
                        contact_attempt_id=contact_attempt_id,
                        answer="yes",
                    ),
                ),
                InlineKeyboardButton(
                    text="Нет",
                    callback_data=encode_deal_callback(
                        contact_attempt_id=contact_attempt_id,
                        answer="no",
                    ),
                ),
            ]
        ]
    )


def build_initiator_prompt(item: FollowupItem) -> str:
    return (
        f"Удалось ли договориться по объявлению #{_required_int(item, 'ad_id')}?\n\n"
        f"{_required_str(item, 'summary')}\n\n"
        "Нажмите Да, если сделка состоялась."
    )


def build_author_prompt(item: FollowupItem) -> str:
    return (
        f"Пользователь сообщил, что сделка по объявлению #{_required_int(item, 'ad_id')} "
        "состоялась.\n\n"
        f"{_required_str(item, 'summary')}\n\n"
        "Подтвердите, что сделка действительно состоялась."
    )


async def send_due_prompts(
    bot: MessageSender,
    items: Sequence[FollowupItem],
) -> None:
    for item in items:
        contact_attempt_id = _required_int(item, "contact_attempt_id")
        await bot.send_message(
            chat_id=_required_int(item, "initiator_telegram_id"),
            text=build_initiator_prompt(item),
            reply_markup=build_deal_keyboard(contact_attempt_id=contact_attempt_id),
        )


async def send_author_confirmation_prompt(
    bot: MessageSender,
    item: FollowupItem,
) -> None:
    contact_attempt_id = _required_int(item, "contact_attempt_id")
    await bot.send_message(
        chat_id=_required_int(item, "author_telegram_id"),
        text=build_author_prompt(item),
        reply_markup=build_deal_keyboard(contact_attempt_id=contact_attempt_id),
    )


async def poll_contact_followups(
    bot: MessageSender,
    backend_client: FollowupClaimClient,
    *,
    interval_seconds: float = 60.0,
) -> None:
    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")

    while True:
        try:
            items = await backend_client.claim_due_followups()
            await send_due_prompts(bot, items)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Contact follow-up polling failed")
        await asyncio.sleep(interval_seconds)


def _required_int(item: FollowupItem, key: str) -> int:
    value = item.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"follow-up item missing integer {key}")
    return value


def _required_str(item: FollowupItem, key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"follow-up item missing string {key}")
    return value
