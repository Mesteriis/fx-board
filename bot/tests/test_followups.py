from fx_board_bot.followups import (
    build_deal_keyboard,
    build_initiator_prompt,
    send_author_confirmation_prompt,
    send_due_prompts,
)
from fx_board_bot.messages import COMPLIANCE_NOTICE


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str, object]] = []
        self.sent_messages: list[object] = []

    async def send_message(self, *, chat_id: int, text: str, reply_markup: object) -> object:
        self.messages.append((chat_id, text, reply_markup))
        message = FakeMessage()
        self.sent_messages.append(message)
        return message


class FakeMessage:
    def __init__(self) -> None:
        self.deleted = False

    async def delete(self) -> None:
        self.deleted = True


class FakePromptClient:
    def __init__(self, *, action: str = "prompt_recorded") -> None:
        self.action = action
        self.calls: list[tuple[int, str]] = []

    async def mark_followup_prompt_sent(
        self,
        *,
        contact_attempt_id: int,
        prompt_type: str,
    ) -> dict[str, object]:
        self.calls.append((contact_attempt_id, prompt_type))
        return {"action": self.action}


def test_build_deal_keyboard_uses_deal_callback_payloads() -> None:
    markup = build_deal_keyboard(contact_attempt_id=12)

    buttons = markup.inline_keyboard[0]
    assert [button.text for button in buttons] == ["Да", "Нет"]
    assert [button.callback_data for button in buttons] == ["deal:12:yes", "deal:12:no"]


def test_build_initiator_prompt_includes_deal_summary() -> None:
    text = build_initiator_prompt(
        {
            "ad_id": 5,
            "summary": "SELL 100.00000000 USD/RUB",
        }
    )

    assert "#5" in text
    assert "SELL 100.00000000 USD/RUB" in text
    assert COMPLIANCE_NOTICE in text


async def test_send_due_prompts_sends_initiator_message_with_keyboard() -> None:
    bot = FakeBot()

    await send_due_prompts(
        bot,
        [
            {
                "contact_attempt_id": 77,
                "initiator_telegram_id": 1234,
                "ad_id": 5,
                "summary": "SELL 100.00000000 USD/RUB",
            }
        ],
    )

    assert len(bot.messages) == 1
    chat_id, text, reply_markup = bot.messages[0]
    assert chat_id == 1234
    assert "SELL 100.00000000 USD/RUB" in text
    assert reply_markup.inline_keyboard[0][0].callback_data == "deal:77:yes"


async def test_send_due_prompts_records_prompt_after_send() -> None:
    bot = FakeBot()
    prompt_client = FakePromptClient()

    await send_due_prompts(
        bot,
        [
            {
                "contact_attempt_id": 77,
                "initiator_telegram_id": 1234,
                "ad_id": 5,
                "summary": "SELL 100.00000000 USD/RUB",
            }
        ],
        prompt_client=prompt_client,
    )

    assert prompt_client.calls == [(77, "initiator")]
    assert bot.sent_messages[0].deleted is False


async def test_send_due_prompts_deletes_stale_prompt_after_backend_rejects_ack() -> None:
    bot = FakeBot()
    prompt_client = FakePromptClient(action="stale")

    await send_due_prompts(
        bot,
        [
            {
                "contact_attempt_id": 77,
                "initiator_telegram_id": 1234,
                "ad_id": 5,
                "summary": "SELL 100.00000000 USD/RUB",
            }
        ],
        prompt_client=prompt_client,
    )

    assert prompt_client.calls == [(77, "initiator")]
    assert bot.sent_messages[0].deleted is True


async def test_send_author_confirmation_prompt_uses_author_chat() -> None:
    bot = FakeBot()

    await send_author_confirmation_prompt(
        bot,
        {
            "contact_attempt_id": 78,
            "author_telegram_id": 5678,
            "ad_id": 6,
            "summary": "BUY 250.00000000 EUR/USD",
        },
    )

    assert len(bot.messages) == 1
    chat_id, text, reply_markup = bot.messages[0]
    assert chat_id == 5678
    assert "BUY 250.00000000 EUR/USD" in text
    assert COMPLIANCE_NOTICE in text
    assert reply_markup.inline_keyboard[0][1].callback_data == "deal:78:no"


async def test_send_author_confirmation_prompt_records_author_prompt() -> None:
    bot = FakeBot()
    prompt_client = FakePromptClient()

    await send_author_confirmation_prompt(
        bot,
        {
            "contact_attempt_id": 78,
            "author_telegram_id": 5678,
            "ad_id": 6,
            "summary": "BUY 250.00000000 EUR/USD",
        },
        prompt_client=prompt_client,
    )

    assert prompt_client.calls == [(78, "author")]
