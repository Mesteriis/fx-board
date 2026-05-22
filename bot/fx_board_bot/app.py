import asyncio
import logging
from contextlib import suppress

import httpx
from aiogram import Bot, Dispatcher, F
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command
from aiogram.types import CallbackQuery, MenuButtonWebApp, Message, WebAppInfo

from .backend_client import BackendClient
from .callbacks import decode_deal_callback
from .commands import admin_commands, public_commands, webapp_keyboard
from .config import get_bot_settings
from .followups import poll_contact_followups, send_author_confirmation_prompt

logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "Добро пожаловать в FX Board.\n\n"
    "Здесь можно размещать объявления о покупке и продаже USD, EUR, RUB, USDT и USDC.\n\n"
    "Нажмите кнопку ниже, чтобы открыть приложение."
)

PUBLIC_START_PARAMS = {
    "new": "new",
    "sell": "sell",
    "buy": "buy",
    "my_ads": "my_ads",
    "rates": "rates",
    "channels": "channels",
    "rules": "rules",
    "support": "support",
    "report": "report",
}


async def open_app_handler(message: Message) -> None:
    settings = get_bot_settings()
    command = _message_command(message)
    await message.answer(
        _public_command_text(command),
        reply_markup=webapp_keyboard(
            base_url=settings.app_base_url,
            start_param=PUBLIC_START_PARAMS.get(command),
        ),
    )


async def admin_command_handler(message: Message) -> None:
    settings = get_bot_settings()
    if message.from_user is None or message.from_user.id not in settings.admin_ids:
        await message.answer("Недоступно.")
        return

    await message.answer(
        "Админская команда принята. Откройте приложение для дальнейших действий.",
        reply_markup=webapp_keyboard(base_url=settings.app_base_url, start_param="admin"),
    )


async def deal_callback_handler(
    callback: CallbackQuery,
    *,
    backend_client: BackendClient,
) -> None:
    try:
        payload = decode_deal_callback(callback.data or "")
    except ValueError:
        await callback.answer("Некорректный ответ.", show_alert=True)
        return

    try:
        result = await backend_client.answer_followup(
            contact_attempt_id=payload.contact_attempt_id,
            actor_telegram_id=callback.from_user.id,
            answer=payload.answer,
        )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {400, 403, 404}:
            await callback.answer("Этот запрос уже не актуален.", show_alert=True)
            return
        logger.warning("Backend rejected contact follow-up answer", exc_info=True)
        await callback.answer("Не удалось сохранить ответ.", show_alert=True)
        return
    except httpx.HTTPError:
        logger.warning("Backend contact follow-up answer failed", exc_info=True)
        await callback.answer("Не удалось сохранить ответ.", show_alert=True)
        return

    if result.get("action") == "ask_author":
        await send_author_confirmation_prompt(
            callback.bot,
            result,
            prompt_client=backend_client,
        )
    await callback.answer(_answer_acknowledgement(result))


async def configure_bot(bot: Bot) -> None:
    settings = get_bot_settings()
    await bot.set_my_commands(public_commands())
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="FX Board",
                web_app=WebAppInfo(url=f"{settings.app_base_url.rstrip('/')}/app"),
            )
        )
    except TelegramAPIError:
        logger.info("Telegram menu button setup is unavailable", exc_info=True)


def register_handlers(dispatcher: Dispatcher, *, backend_client: BackendClient) -> None:
    for command in public_commands():
        dispatcher.message.register(open_app_handler, Command(command.command))
    for command in admin_commands():
        dispatcher.message.register(admin_command_handler, Command(command.command))

    async def _deal_callback_handler(callback: CallbackQuery) -> None:
        await deal_callback_handler(callback, backend_client=backend_client)

    dispatcher.callback_query.register(_deal_callback_handler, F.data.startswith("deal:"))


async def run_bot() -> None:
    settings = get_bot_settings()
    bot = Bot(token=settings.telegram_bot_token.get_secret_value())
    dispatcher = Dispatcher()
    backend_client = BackendClient(
        base_url=settings.backend_base_url,
        internal_secret=settings.telegram_internal_bot_secret.get_secret_value(),
    )
    register_handlers(dispatcher, backend_client=backend_client)
    await configure_bot(bot)

    followup_task = asyncio.create_task(
        poll_contact_followups(bot, backend_client),
        name="contact-followups",
    )
    try:
        await dispatcher.start_polling(bot)
    finally:
        followup_task.cancel()
        with suppress(asyncio.CancelledError):
            await followup_task


def _message_command(message: Message) -> str:
    raw_command = (message.text or "").split(maxsplit=1)[0].lstrip("/")
    return raw_command.split("@", 1)[0]


def _public_command_text(command: str) -> str:
    if command in {"help", "start", "app"}:
        return WELCOME_TEXT
    if command == "rules":
        return "Правила и требования к доступу доступны в приложении."
    if command == "support":
        return "Откройте приложение, чтобы обратиться в поддержку."
    if command == "report":
        return "Откройте объявление в приложении, чтобы отправить жалобу."
    return "Откройте FX Board, чтобы продолжить."


def _answer_acknowledgement(result: dict[str, object]) -> str:
    action = result.get("action")
    if action == "ask_author":
        return "Ответ принят. Ждем подтверждения автора."
    if action == "completed":
        return "Сделка подтверждена."
    return "Ответ принят."


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
