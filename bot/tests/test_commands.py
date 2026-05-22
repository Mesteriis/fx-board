from fx_board_bot.commands import admin_commands, public_commands, webapp_keyboard


def test_public_commands_include_app_entrypoints_without_leading_slashes() -> None:
    names = {command.command for command in public_commands()}

    assert {
        "start",
        "app",
        "new",
        "sell",
        "buy",
        "my_ads",
        "rates",
        "channels",
        "rules",
        "help",
        "support",
        "report",
    } <= names
    assert all(not name.startswith("/") for name in names)


def test_admin_commands_are_separate_without_leading_slashes() -> None:
    names = {command.command for command in admin_commands()}

    assert {"admin", "reports", "ban", "unban", "stats"} <= names
    assert all(not name.startswith("/") for name in names)


def test_webapp_keyboard_builds_app_url_with_start_param() -> None:
    markup = webapp_keyboard(base_url="https://example.test/", start_param="sell")

    button = markup.inline_keyboard[0][0]
    assert button.text == "Открыть доску"
    assert button.web_app is not None
    assert button.web_app.url == "https://example.test/app?startapp=sell"
