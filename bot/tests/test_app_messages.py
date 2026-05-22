from fx_board_bot.app import WELCOME_TEXT, _public_command_text
from fx_board_bot.messages import COMPLIANCE_NOTICE


def test_welcome_text_includes_compliance_notice() -> None:
    assert COMPLIANCE_NOTICE in WELCOME_TEXT


def test_rules_text_includes_compliance_notice() -> None:
    assert COMPLIANCE_NOTICE in _public_command_text("rules")
