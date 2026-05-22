from fx_board_bot.config import BotSettings


def test_admin_ids_are_parsed() -> None:
    settings = BotSettings(
        telegram_bot_token="123456:token",
        admin_telegram_ids="123, 456",
    )

    assert settings.admin_ids == {123, 456}
