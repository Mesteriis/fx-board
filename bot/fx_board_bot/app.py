import asyncio

from aiogram import Bot, Dispatcher

from .config import get_bot_settings


async def run_bot() -> None:
    settings = get_bot_settings()
    bot = Bot(token=settings.telegram_bot_token.get_secret_value())
    dispatcher = Dispatcher()
    await dispatcher.start_polling(bot)


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
