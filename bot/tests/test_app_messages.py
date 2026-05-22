from aiogram.exceptions import TelegramNetworkError
from aiogram.methods import SetMyCommands

from fx_board_bot.app import WELCOME_TEXT, _public_command_text, configure_bot
from fx_board_bot.config import BotSettings
from fx_board_bot.messages import COMPLIANCE_NOTICE


def test_welcome_text_includes_compliance_notice() -> None:
    assert COMPLIANCE_NOTICE in WELCOME_TEXT


def test_rules_text_includes_compliance_notice() -> None:
    assert COMPLIANCE_NOTICE in _public_command_text("rules")


async def test_configure_bot_continues_when_command_setup_times_out(monkeypatch) -> None:
    class FakeBot:
        menu_button_set = False

        async def set_my_commands(self, commands):
            raise TelegramNetworkError(
                method=SetMyCommands(commands=commands),
                message="timeout",
            )

        async def set_chat_menu_button(self, *, menu_button):
            self.menu_button_set = True

    monkeypatch.setattr(
        "fx_board_bot.app.get_bot_settings",
        lambda: BotSettings(
            telegram_bot_token="123456:token",
            telegram_webhook_secret="webhook_secret",
            telegram_internal_bot_secret="internal_secret_long_enough_for_tests",
            app_base_url="https://example.test",
        ),
    )

    fake_bot = FakeBot()

    await configure_bot(fake_bot)

    assert fake_bot.menu_button_set is True
