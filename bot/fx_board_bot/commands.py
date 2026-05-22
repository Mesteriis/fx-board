from urllib.parse import quote

from aiogram.types import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


def public_commands() -> list[BotCommand]:
    return [
        BotCommand(command="start", description="Открыть FX Board"),
        BotCommand(command="app", description="Открыть приложение"),
        BotCommand(command="new", description="Создать объявление"),
        BotCommand(command="sell", description="Создать продажу"),
        BotCommand(command="buy", description="Создать покупку"),
        BotCommand(command="my_ads", description="Мои объявления"),
        BotCommand(command="rates", description="Курсы валют"),
        BotCommand(command="channels", description="Обязательные каналы"),
        BotCommand(command="rules", description="Правила"),
        BotCommand(command="help", description="Помощь"),
        BotCommand(command="support", description="Поддержка"),
        BotCommand(command="report", description="Жалобы"),
    ]


def admin_commands() -> list[BotCommand]:
    return [
        BotCommand(command="admin", description="Админ-панель"),
        BotCommand(command="reports", description="Новые репорты"),
        BotCommand(command="ban", description="Заблокировать пользователя"),
        BotCommand(command="unban", description="Разблокировать пользователя"),
        BotCommand(command="stats", description="Статистика"),
    ]


def webapp_keyboard(*, base_url: str, start_param: str | None = None) -> InlineKeyboardMarkup:
    url = f"{base_url.rstrip('/')}/app"
    if start_param:
        url = f"{url}?startapp={quote(start_param, safe='')}"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Открыть доску", web_app=WebAppInfo(url=url))]
        ]
    )
